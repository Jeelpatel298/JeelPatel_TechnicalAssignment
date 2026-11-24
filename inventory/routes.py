from functools import wraps
from pathlib import Path

import click
from flask import Blueprint, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import catalog, db, orders
from .reports import reports
from .validation import Problem, object_data

api = Blueprint("api", __name__, url_prefix="/api")
PASSWORD_METHOD = "pbkdf2:sha256:1000000"
DUMMY_HASH = generate_password_hash("unused-login-fallback", method=PASSWORD_METHOD)


def protected(*, admin=False):
    def decorate(view):
        @wraps(view)
        def checked(*args, **kwargs):
            if g.user is None:
                raise Problem("Sign in to continue.", 401)
            if admin and g.user["role"] != "admin":
                raise Problem("This action requires an Admin account.", 403)
            return view(*args, **kwargs)
        return checked
    return decorate


def body():
    return object_data(request.get_json(silent=True))


def catalog_kind(kind):
    if kind not in ("customers", "products"):
        raise Problem("Catalog not found.", 404)
    return kind


@api.get("/session")
def csrf():
    from . import csrf_token
    return jsonify(csrf_token=csrf_token(), user=g.user)


@api.post("/login")
def login():
    data = body()
    email, password = data.get("email"), data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        raise Problem("Enter an email and password.")
    if len(email) > 254 or len(password) > 256:
        raise Problem("Invalid email or password.", 401)
    user = db.query("SELECT * FROM users WHERE email=%s", (email.strip(),), one=True)
    valid = check_password_hash(user["password_hash"] if user else DUMMY_HASH, password)
    if not valid or user is None:
        raise Problem("Invalid email or password.", 401)
    session.clear()
    session["user_id"] = user["id"]
    return jsonify(ok=True)


@api.post("/logout")
@protected()
def logout():
    session.clear()
    return jsonify(ok=True)


@api.get("/products")
@protected()
def products():
    return jsonify(catalog.catalog_list("products", g.user, {**request.args, "status": "Active"}))


@api.get("/catalog/<kind>")
@protected()
def catalog_rows(kind):
    return jsonify(catalog.catalog_list(catalog_kind(kind), g.user, request.args))


@api.get("/catalog/<kind>/<int:item_id>")
@protected()
def catalog_row(kind, item_id):
    return jsonify(catalog.catalog_detail(catalog_kind(kind), item_id, g.user))


@api.post("/catalog/<kind>")
@protected(admin=True)
def catalog_create(kind):
    return jsonify(catalog.save_record(catalog_kind(kind), body(), g.user)), 201


@api.put("/catalog/<kind>/<int:item_id>")
@protected(admin=True)
def catalog_update(kind, item_id):
    return jsonify(catalog.save_record(catalog_kind(kind), body(), g.user, item_id))


@api.delete("/catalog/<kind>/<int:item_id>")
@protected(admin=True)
def catalog_delete(kind, item_id):
    catalog.delete_record(catalog_kind(kind), item_id)
    return "", 204


@api.post("/products/<int:item_id>/adjust")
@protected(admin=True)
def stock_adjust(item_id):
    return jsonify(catalog.adjust_stock(item_id, body(), g.user))


@api.post("/products/import")
@protected(admin=True)
def csv_import():
    count = catalog.import_products(request.files.get("file"), g.user)
    return jsonify(imported=count), 201


@api.get("/orders")
@protected()
def order_list():
    return jsonify(items=orders.list_orders(g.user))


@api.post("/orders")
@protected()
def order_create():
    result = orders.save_draft(body(), g.user)
    return jsonify(result), 201, {"Location": f"/api/orders/{result['id']}"}


@api.get("/orders/<int:order_id>")
@protected()
def order_get(order_id):
    return jsonify(orders.order_detail(order_id, g.user))


@api.put("/orders/<int:order_id>")
@protected()
def order_update(order_id):
    return jsonify(orders.save_draft(body(), g.user, order_id))


@api.post("/orders/<int:order_id>/confirm")
@protected()
def order_confirm(order_id):
    return jsonify(orders.change_status(order_id, "Confirmed", g.user))


@api.post("/orders/<int:order_id>/cancel")
@protected()
def order_cancel(order_id):
    return jsonify(orders.change_status(order_id, "Cancelled", g.user))


@api.get("/reports")
@protected(admin=True)
def report_data():
    return jsonify(reports(request.args))


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        schema = Path(app.root_path).parent / "sql" / "schema.sql"
        for statement in schema.read_text().split(";"):
            if statement.strip():
                db.execute(statement)
        click.echo("Database schema is ready.")

    @app.cli.command("seed")
    def seed():
        """Create three demo users and sample catalog data in an empty database."""
        if db.query("SELECT id FROM users LIMIT 1") or db.query("SELECT id FROM customers LIMIT 1") \
                or db.query("SELECT id FROM products LIMIT 1"):
            raise click.ClickException("Seed requires an empty catalog and user table.")
        passwords = {}
        users = (
            ("Demo Admin", "admin@example.test", "admin"),
            ("Demo Sales", "sales@example.test", "sales"),
            ("Second Sales", "sales2@example.test", "sales"),
        )
        for name, email, _ in users:
            password = click.prompt(f"Password for {email}", hide_input=True, confirmation_prompt=True)
            if not 8 <= len(password) <= 256:
                raise click.ClickException("Use a password between 8 and 256 characters.")
            passwords[email] = generate_password_hash(password, method=PASSWORD_METHOD)
        with db.transaction():
            for name, email, role in users:
                user_id = catalog.insert_record("users", {
                    "name": name, "email": email, "role": role, "password_hash": passwords[email],
                })
                if role == "admin":
                    admin_id = user_id
            for name, email, mobile, city in (
                ("Aster Retail", "hello@aster.example", "+91 90000 00001", "Ahmedabad"),
                ("Bluebird Office", "hello@bluebird.example", "+91 90000 00002", "Surat"),
                ("Cedar Supply", "hello@cedar.example", "+91 90000 00003", "Vadodara"),
            ):
                catalog.insert_record("customers", dict(name=name, email=email, mobile=mobile, city=city))
            for code, name, category, price, stock in (
                ("PRD-001", "Keyboard", "Accessories", "1500.00", 20),
                ("PRD-002", "Mouse", "Accessories", "500.00", 50),
                ("PRD-003", "USB-C Hub", "Connectivity", "1899.00", 4),
                ("PRD-004", "Monitor Riser", "Workspace", "2400.00", 8),
            ):
                catalog.insert_product(dict(code=code, name=name, category=category, price=price),
                                       stock, "Sample opening stock", admin_id)
        click.echo("Demo accounts and sample catalog created.")
