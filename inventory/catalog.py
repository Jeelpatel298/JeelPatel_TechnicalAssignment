import csv
import io
import re

from pymysql.err import IntegrityError

from .db import execute, query, transaction
from .orders import locked_products, movement
from .validation import MAX_PRICE, MAX_STOCK, Problem, decimal, integer, object_data, status, text

CSV_FIELDS = ("product_code", "product_name", "category", "price", "stock_quantity", "status")


def catalog_list(kind, user, filters):
    products = kind == "products"
    columns = ("code", "name") if products else ("name", "email", "mobile")
    where, args = [], []
    active = filters.get("status")
    if user["role"] != "admin":
        where.append("active=1")
    elif active:
        where.append("active=%s")
        args.append(status(active))
    search = filters.get("q", "").strip()
    if search:
        text(search, "Search", 120)
        where.append("(" + " OR ".join(f"LOCATE(%s, {column}) > 0" for column in columns) + ")")
        args.extend([search] * len(columns))
    if products and filters.get("category"):
        where.append("category=%s")
        args.append(text(filters["category"], "Category", 80))
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    page = integer(filters.get("page", 1), "Page", maximum=1_000_000)
    size = integer(filters.get("per_page", 25), "Page size", maximum=100)
    with transaction():
        total = query(f"SELECT COUNT(*) AS total FROM {kind}" + clause, args, one=True)["total"]
        rows = query(f"SELECT * FROM {kind}" + clause + " ORDER BY name,id LIMIT %s OFFSET %s",
                     [*args, size, (page - 1) * size])
    return {"items": rows, "total": total, "page": page, "per_page": size}


def catalog_detail(kind, item_id, user):
    row = query(f"SELECT * FROM {kind} WHERE id=%s", (item_id,), one=True)
    if row is None or (user["role"] != "admin" and not row["active"]):
        raise Problem("Record not found.", 404)
    return row


def product_code(value):
    code = text(value, "Product code", 40)
    return text(code.upper(), "Product code", 40)


def product_fields(data):
    return {
        "code": product_code(data.get("code")),
        "name": text(data.get("name"), "Product name", 120),
        "category": text(data.get("category"), "Category", 80),
        "price": decimal(data.get("price"), "Price", MAX_PRICE),
        "active": status(data.get("status")),
    }


def customer_fields(data):
    email = text(data.get("email"), "Email", 254)
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise Problem("Enter a valid email address.")
    mobile = text(data.get("mobile"), "Mobile", 30)
    if not re.fullmatch(r"\+?[0-9 ()-]+", mobile) or not 5 <= sum(c.isdigit() for c in mobile) <= 20:
        raise Problem("Enter a valid mobile number.")
    return {
        "name": text(data.get("name"), "Customer name", 120),
        "email": email,
        "mobile": mobile,
        "city": text(data.get("city"), "City", 100),
        "active": status(data.get("status")),
    }


def insert_record(kind, fields):
    columns = ", ".join(fields)
    placeholders = ", ".join(["%s"] * len(fields))
    return execute(f"INSERT INTO {kind} ({columns}) VALUES ({placeholders})", tuple(fields.values()))


def insert_product(fields, opening, reason, user_id):
    product_id = insert_record("products", {**fields, "stock": opening})
    if opening:
        movement(product_id, "Opening", opening, reason, user_id)
    return product_id


def save_record(kind, data, user, item_id=None):
    data = object_data(data)
    products = kind == "products"
    fields = product_fields(data) if products else customer_fields(data)
    try:
        with transaction():
            if item_id is not None:
                if query(f"SELECT id FROM {kind} WHERE id=%s FOR UPDATE", (item_id,), one=True) is None:
                    raise Problem("Record not found.", 404)
                assignments = ", ".join(f"{column}=%s" for column in fields)
                execute(f"UPDATE {kind} SET {assignments} WHERE id=%s", (*fields.values(), item_id))
            elif products:
                opening = integer(data.get("stock", 0), "Opening stock", minimum=0)
                item_id = insert_product(fields, opening, "Product opening stock", user["id"])
            else:
                item_id = insert_record(kind, fields)
    except IntegrityError as error:
        if products and error.args[0] == 1062:
            raise Problem("Product code already exists.", 409) from None
        raise
    return catalog_detail(kind, item_id, user)


def delete_record(kind, item_id):
    with transaction():
        row = query(f"SELECT id FROM {kind} WHERE id=%s FOR UPDATE", (item_id,), one=True)
        if row is None:
            raise Problem("Record not found.", 404)
        try:
            execute(f"DELETE FROM {kind} WHERE id=%s", (item_id,))
        except IntegrityError as error:
            if error.args[0] == 1451:
                raise Problem("This record is referenced. Deactivate it instead.", 409) from None
            raise


def adjust_stock(product_id, data, user):
    data = object_data(data)
    change = integer(data.get("change"), "Stock change", minimum=-MAX_STOCK)
    reason = text(data.get("reason"), "Reason", 255)
    if change == 0:
        raise Problem("Stock change cannot be zero.")
    with transaction():
        product = locked_products([product_id])[product_id]
        balance = product["stock"] + change
        if not 0 <= balance <= MAX_STOCK:
            raise Problem("This adjustment would put stock outside the allowed range.", 409)
        execute("UPDATE products SET stock=%s WHERE id=%s", (balance, product_id))
        movement(product_id, "Adjustment", change, reason, user["id"])
    return catalog_detail("products", product_id, user)


def import_products(upload, user):
    if upload is None:
        raise Problem("Choose a CSV file.")
    try:
        raw = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Problem("CSV must use UTF-8 encoding.") from None

    reader = csv.reader(io.StringIO(raw, newline=""), strict=True)
    errors, valid, seen = [], [], set()
    try:
        headers = next(reader, [])
        if len(headers) != len(CSV_FIELDS) or set(headers) != set(CSV_FIELDS):
            raise Problem("CSV columns do not match the required header.",
                          errors=[{"row": 1, "reason": "Expected " + ", ".join(CSV_FIELDS)}])
        with transaction():
            while True:
                line = reader.line_num + 1
                values = next(reader, None)
                if values is None:
                    break
                try:
                    if len(values) != len(headers):
                        raise Problem("Column count does not match the header.")
                    row = dict(zip(headers, values))
                    code = product_code(row["product_code"])
                    if code in seen:
                        raise Problem("Duplicate product code in the file.")
                    seen.add(code)
                    fields = product_fields({**row, "code": code, "name": row["product_name"]})
                    opening = integer(row["stock_quantity"].strip(), "Opening stock", minimum=0)
                    if query("SELECT id FROM products WHERE code=%s", (code,), one=True):
                        raise Problem("Product code already exists.")
                    valid.append((line, fields, opening))
                except Problem as error:
                    errors.append({"row": line, "reason": str(error)})
            if errors or not valid:
                raise Problem("CSV validation failed. No products were imported.",
                              errors=errors or [{"row": 2, "reason": "No product rows found."}])
            for line, fields, opening in sorted(valid, key=lambda entry: entry[1]["code"]):
                try:
                    insert_product(fields, opening, "CSV opening stock", user["id"])
                except IntegrityError as error:
                    if error.args[0] == 1062:
                        raise Problem("CSV import rolled back.", 409, errors=[
                            {"row": line, "reason": "Product code already exists."}
                        ]) from None
                    raise
    except csv.Error:
        raise Problem("Invalid CSV format. No products were imported.",
                      errors=[{"row": reader.line_num + 1, "reason": "Malformed CSV row."}]) from None
    return len(valid)
