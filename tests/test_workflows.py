from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from io import BytesIO
from threading import Barrier

import pytest
from flask import request

import inventory.orders as orders_module
import inventory.reports as reports_module
from inventory import db
from inventory.validation import MAX_STOCK


def create(client, draft):
    result = client("POST", "/api/orders", json=draft)
    assert result.status_code == 201, result.json
    return result.json


def balances(app):
    with app.app_context():
        return [row["stock"] for row in db.query("SELECT stock FROM products ORDER BY id")]


def movements(app):
    with app.app_context():
        return db.query("SELECT movement_type,quantity_change FROM stock_movements ORDER BY id")


def test_order_totals_and_saved_rate(app, client_for, draft):
    sales, admin = client_for("sales"), client_for("admin")
    draft.update(grand_total=1, status="Confirmed", created_by=999)
    draft["items"][0]["rate"] = 1
    order = create(sales, draft)
    assert order["status"] == "Draft"
    assert order["created_by"] != 999
    assert [order[key] for key in ("subtotal", "discount_amount", "grand_total")] == [
        "4500.00", "450.00", "4050.00",
    ]
    assert balances(app) == [20, 5]
    product = app.config["TEST_PRODUCTS"][0]
    response = admin("PUT", f"/api/catalog/products/{product}", json={
        "code": "KEY", "name": "Keyboard", "category": "Demo", "price": 5000, "status": "Active",
    })
    assert response.status_code == 200
    draft["items"][0]["quantity"] = 1
    changed = sales("PUT", f"/api/orders/{order['id']}", json=draft)
    assert changed.status_code == 200
    assert changed.json["items"][0]["rate"] == "1500.00"
    assert changed.json["grand_total"] == "2700.00"


@pytest.mark.parametrize("qty", [0, -1, 1.5, True])
def test_reject_bad_quantity(client_for, draft, qty):
    draft["items"][0]["quantity"] = qty
    assert client_for("sales")("POST", "/api/orders", json=draft).status_code == 400


@pytest.mark.parametrize("discount", ["-0.01", "20.01", "NaN", "1.001"])
def test_reject_bad_discount(client_for, draft, discount):
    draft["discount_pct"] = discount
    assert client_for("sales")("POST", "/api/orders", json=draft).status_code == 400


def test_confirm_cancel_idempotently(app, client_for, draft):
    client = client_for("sales")
    path = f"/api/orders/{create(client, draft)['id']}"
    for _ in range(2):
        result = client("POST", path + "/confirm")
        assert result.status_code == 200 and result.json["status"] == "Confirmed"
        assert balances(app) == [18, 2]
        assert [row["quantity_change"] for row in movements(app)] == [-2, -3]
    assert client("PUT", path, json=draft).status_code == 409
    for _ in range(2):
        result = client("POST", path + "/cancel")
        assert result.status_code == 200 and result.json["status"] == "Cancelled"
        assert balances(app) == [20, 5]
        assert [row["quantity_change"] for row in movements(app)] == [-2, -3, 2, 3]
    assert client("POST", path + "/confirm").status_code == 409


def test_cancel_draft_has_no_stock_effect(app, client_for, draft):
    client = client_for("sales")
    order = create(client, draft)
    assert client("POST", f"/api/orders/{order['id']}/cancel").json["status"] == "Cancelled"
    assert balances(app) == [20, 5] and movements(app) == []


def test_insufficient_stock_rolls_back_entire_order(app, client_for, draft):
    client = client_for("sales")
    draft["items"][1]["quantity"] = 6
    path = f"/api/orders/{create(client, draft)['id']}"
    assert client("POST", path + "/confirm").status_code == 409
    assert client("GET", path).json["status"] == "Draft"
    assert balances(app) == [20, 5] and movements(app) == []


def test_two_sales_users_cannot_oversell(app, client_for, draft):
    clients = [client_for("sales"), client_for("other")]
    paths = [f"/api/orders/{create(client, draft)['id']}/confirm" for client in clients]
    gate = Barrier(2, timeout=10)

    def confirm(index):
        gate.wait()
        return clients[index]("POST", paths[index]).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(confirm, range(2))) == [200, 409]
    assert balances(app) == [18, 2]
    assert len(movements(app)) == 2


def test_permissions_and_csrf(app, client_for, draft):
    owner, other = client_for("sales"), client_for("other")
    order = create(owner, draft)
    path = f"/api/orders/{order['id']}"
    for method, suffix in (("GET", ""), ("PUT", ""), ("POST", "/confirm"), ("POST", "/cancel")):
        assert other(method, path + suffix, json=draft).status_code == 403
    assert other("GET", "/api/orders").json["items"] == []
    assert other("GET", "/api/reports").status_code == 403
    assert other("POST", "/api/catalog/products", json={}).status_code == 403
    assert other("POST", "/api/products/import").status_code == 403
    assert app.test_client().get(path).status_code == 401
    assert app.test_client().post("/api/login", json={}).status_code == 403
    assert client_for("admin")("GET", path).status_code == 200


def test_reports_count_order_once_and_keep_zero_customers(client_for, draft):
    admin = client_for("admin")
    order = create(admin, draft)
    assert admin("POST", f"/api/orders/{order['id']}/confirm").status_code == 200
    report = admin("GET", "/api/reports?start=2025-01-01&end=2025-01-31&threshold=3").json
    assert [(row["order_count"], row["total"]) for row in report["customers"]] == [
        (1, "4050.00"), (0, "0.00"),
    ]
    assert [(row["code"], row["gross"]) for row in report["products"]] == [
        ("MSE", "1500.00"), ("KEY", "3000.00"),
    ]
    assert [row["code"] for row in report["low_stock"]] == ["MSE"]
    outside = admin("GET", "/api/reports?start=2025-02-01").json
    assert all(row["order_count"] == 0 for row in outside["customers"])


def test_stock_adjustment_and_referenced_delete(app, client_for, draft):
    admin = client_for("admin")
    product = app.config["TEST_PRODUCTS"][0]
    customer = app.config["TEST_CUSTOMERS"][0]
    create(admin, draft)
    assert admin("DELETE", f"/api/catalog/customers/{customer}").status_code == 409
    assert admin("DELETE", f"/api/catalog/products/{product}").status_code == 409
    path = f"/api/products/{product}/adjust"
    assert admin("POST", path, json={"change": -21, "reason": "Count"}).status_code == 409
    assert admin("POST", path, json={"change": 3}).status_code == 400
    assert admin("POST", path, json={"change": 3, "reason": "Count"}).json["stock"] == 23
    assert movements(app) == [{"movement_type": "Adjustment", "quantity_change": 3}]


def upload(client, lines):
    csv = "product_code,product_name,category,price,stock_quantity,status\n" + lines
    return client("POST", "/api/products/import", data={"file": (BytesIO(csv.encode()), "import.csv")})


def test_csv_invalid_row_imports_nothing(app, client_for):
    admin = client_for("admin")
    response = upload(admin, "NEW,New Product,Demo,12,3,Active\nBAD,Bad Product,Demo,-1,4,Active\n")
    assert response.status_code == 400
    assert response.json["errors"][0]["row"] == 3
    assert admin("GET", "/api/products?q=NEW").json["total"] == 0
    assert movements(app) == []


def test_csv_valid_then_existing_code(app, client_for):
    admin = client_for("admin")
    rows = "NEW,New Product,Demo,12.50,3,Active\nOLD,Archived,Demo,0,0,Inactive\n"
    assert upload(admin, rows).json == {"imported": 2}
    assert movements(app) == [{"movement_type": "Opening", "quantity_change": 3}]
    assert upload(admin, rows).status_code == 400
    assert admin("GET", "/api/products?q=OLD").json["total"] == 0
    assert admin("GET", "/api/catalog/products?q=OLD&status=Inactive").json["total"] == 1


def test_csv_malformed_record_reports_its_starting_line(app, client_for):
    admin = client_for("admin")
    response = upload(admin, 'NEW,New Product,Demo,12,3,Active\nBAD,"Unclosed field\non two lines\n')
    assert response.status_code == 400
    assert response.json["errors"] == [{"row": 3, "reason": "Malformed CSV row."}]
    assert admin("GET", "/api/products?q=NEW").json["total"] == 0
    assert movements(app) == []


def test_csv_rejects_price_with_underscore(app, client_for):
    admin = client_for("admin")
    response = upload(admin, "NEW,New Product,Demo,1_000,3,Active\n")
    assert response.status_code == 400
    assert response.json["errors"] == [{"row": 2, "reason": "Price must be a number."}]
    assert movements(app) == []


def test_reports_use_one_snapshot_when_an_order_is_cancelled(client_for, draft, monkeypatch):
    admin = client_for("admin")
    sales = client_for("sales")
    order = create(sales, draft)
    path = f"/api/orders/{order['id']}"
    assert sales("POST", path + "/confirm").status_code == 200
    query = reports_module.query

    def cancel_after_customer_summary(sql, args=()):
        result = query(sql, args)
        if "FROM customers" in sql:
            # Each request needs its own MySQL connection.
            with ThreadPoolExecutor(max_workers=1) as pool:
                cancelled = pool.submit(sales, "POST", path + "/cancel").result(timeout=10)
            assert cancelled.status_code == 200
        return result

    monkeypatch.setattr(reports_module, "query", cancel_after_customer_summary)
    report = admin("GET", "/api/reports?threshold=3").json
    assert report["customers"][0]["order_count"] == 1
    assert [row["code"] for row in report["products"]] == ["MSE", "KEY"]
    assert [row["code"] for row in report["low_stock"]] == ["MSE"]
    assert {row["movement_type"] for row in report["movements"]} == {"Sale"}


def test_confirmation_response_survives_immediate_cancellation(client_for, draft, monkeypatch):
    sales, admin = client_for("sales"), client_for("admin")
    path = f"/api/orders/{create(sales, draft)['id']}"
    transaction = orders_module.transaction
    cancelled = False

    @contextmanager
    def cancel_after_confirmation_commit():
        nonlocal cancelled
        with transaction():
            yield
        if request.path == path + "/confirm" and not cancelled:
            cancelled = True
            with ThreadPoolExecutor(max_workers=1) as pool:
                response = pool.submit(admin, "POST", path + "/cancel").result(timeout=10)
            assert response.status_code == 200

    monkeypatch.setattr(orders_module, "transaction", cancel_after_confirmation_commit)
    response = sales("POST", path + "/confirm")

    assert response.status_code == 200
    assert response.json["status"] == "Confirmed"
    assert [item["stock"] for item in response.json["items"]] == [18, 2]
    assert sales("GET", path).json["status"] == "Cancelled"


def test_stock_adjustment_preserves_capacity_for_cancellation(app, client_for, draft):
    admin = client_for("admin")
    order_path = f"/api/orders/{create(admin, draft)['id']}"
    assert admin("POST", order_path + "/confirm").status_code == 200
    product = app.config["TEST_PRODUCTS"][0]
    adjustment_path = f"/api/products/{product}/adjust"
    # There are 18 in stock and 2 more units might return on cancellation.
    result = admin("POST", adjustment_path, json={"change": MAX_STOCK - 19, "reason": "Count"})
    assert result.status_code == 409
    assert balances(app) == [18, 2]
    assert [row["movement_type"] for row in movements(app)] == ["Sale", "Sale"]

    result = admin("POST", adjustment_path, json={"change": MAX_STOCK - 20, "reason": "Count"})
    assert result.status_code == 200
    assert result.json["stock"] == MAX_STOCK - 2
    assert admin("POST", order_path + "/cancel").status_code == 200
    assert balances(app) == [MAX_STOCK, 5]


def test_unsupported_method_keeps_allow_header(client_for):
    response = client_for("sales")("POST", "/api/products")
    assert response.status_code == 405
    assert "GET" in response.headers["Allow"]
    assert response.is_json and response.json["error"]


@pytest.mark.parametrize("field", ["email", "password"])
def test_invalid_unicode_login_returns_json_validation_error(app, field):
    client = app.test_client()
    token = client.get("/api/session").json["csrf_token"]
    credentials = {"email": "sales@example.test", "password": "local-test-password"}
    credentials[field] = "\ud800"
    result = client.post("/api/login", json=credentials, headers={"X-CSRF-Token": token})
    assert result.status_code == 400
    assert result.json == {"error": "Text must use valid UTF-8."}


def test_invalid_unicode_catalog_name_returns_json_validation_error(client_for):
    result = client_for("admin")("POST", "/api/catalog/customers", json={
        "name": "\ud800", "email": "test@example.test", "mobile": "1234567890",
        "city": "Test City", "status": "Active",
    })
    assert result.status_code == 400
    assert result.json == {"error": "Text must use valid UTF-8."}
