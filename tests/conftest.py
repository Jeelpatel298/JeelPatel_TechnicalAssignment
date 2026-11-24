import os
from uuid import uuid4

import pymysql
import pytest
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from inventory import create_app, db

load_dotenv()
PASSWORD = "local-test-password"


@pytest.fixture(scope="session")
def mysql_app():
    if "TEST_DB_USER" not in os.environ:
        pytest.fail("Set TEST_DB_USER for the isolated MySQL integration tests. See README.")
    config = {
        "host": os.getenv("TEST_DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("TEST_DB_PORT", "3306")),
        "user": os.environ["TEST_DB_USER"],
        "password": os.getenv("TEST_DB_PASSWORD", ""),
    }
    name = "inventory_test_" + uuid4().hex
    with pymysql.connect(**config, autocommit=True) as server:
        with server.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}`")
        try:
            app = create_app({
                "TESTING": True,
                "SECRET_KEY": "test-session-key-never-used-outside-tests",
                "DATABASE": {**config, "database": name},
                "SESSION_COOKIE_SECURE": False,
            })
            result = app.test_cli_runner().invoke(args=["init-db"])
            assert result.exit_code == 0, result.exception
            yield app
        finally:
            with server.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")


@pytest.fixture(scope="session")
def password_hash():
    return generate_password_hash(PASSWORD)


@pytest.fixture
def app(mysql_app, password_hash):
    with mysql_app.app_context(), db.transaction():
        for table in ("stock_movements", "order_items", "orders", "products", "customers", "users"):
            db.execute(f"DELETE FROM {table}")
        for email, role in (("sales@example.test", "sales"), ("other@example.test", "sales"),
                            ("admin@example.test", "admin")):
            db.execute("INSERT INTO users (name,email,role,password_hash) VALUES (%s,%s,%s,%s)",
                       (email, email, role, password_hash))
        customers = [db.execute("INSERT INTO customers (name,email,mobile,city) VALUES (%s,%s,%s,%s)",
                                (name, "cust@example.test", "123456789", "Test City"))
                     for name in ("Aster", "Bluebird")]
        products = [db.execute(
            "INSERT INTO products (code,name,category,price,stock) VALUES (%s,%s,'Demo',%s,%s)",
            (code, code, price, stock)
        ) for code, price, stock in (("KEY", 1500, 20), ("MSE", 500, 5))]
        mysql_app.config["TEST_CUSTOMERS"] = customers
        mysql_app.config["TEST_PRODUCTS"] = products
    return mysql_app


@pytest.fixture
def client_for(app):
    def make(role):
        client = app.test_client()
        token = client.get("/api/session").json["csrf_token"]
        result = client.post("/api/login", json={"email": f"{role}@example.test", "password": PASSWORD},
                             headers={"X-CSRF-Token": token})
        assert result.status_code == 200, result.json
        token = client.get("/api/session").json["csrf_token"]

        def request(method, path, **kwargs):
            return client.open(path, method=method, headers={"X-CSRF-Token": token}, **kwargs)
        return request
    return make


@pytest.fixture
def draft(app):
    first, second = app.config["TEST_PRODUCTS"]
    return {
        "customer_id": app.config["TEST_CUSTOMERS"][0],
        "items": [{"product_id": first, "quantity": 2}, {"product_id": second, "quantity": 3}],
        "discount_pct": "10.00",
        "order_date": "2025-01-15",
    }
