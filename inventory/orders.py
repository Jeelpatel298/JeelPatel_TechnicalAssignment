from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from .db import execute, query, transaction
from .pricing import item_amount, order_totals
from .validation import MAX_STOCK, Problem, decimal, integer, object_data, order_date


def accessible_order(order_id, user, *, lock=False):
    sql = "SELECT * FROM orders WHERE id=%s"
    params = (order_id,)
    if user["role"] != "admin":
        sql += " AND created_by=%s"
        params += (user["id"],)
    if lock:
        sql += " FOR UPDATE"
    order = query(sql, params, one=True)
    if order is None:
        raise Problem("Order not found.", 404)
    return order


def add_order_details(order):
    customer = query("SELECT name, active FROM customers WHERE id=%s",
                     (order["customer_id"],), one=True)
    order["customer_name"] = customer["name"]
    order["customer_active"] = customer["active"]
    order["items"] = query(
        """SELECT i.product_id, i.quantity, i.rate, i.amount,
                  p.code, p.name, p.stock, p.active
           FROM order_items i JOIN products p ON p.id=i.product_id
           WHERE i.order_id=%s ORDER BY i.id""", (order["id"],)
    )
    return order


def order_detail(order_id, user):
    with transaction():
        return add_order_details(accessible_order(order_id, user))


def list_orders(user):
    sql = """SELECT o.id, o.number, o.order_date, o.status, o.grand_total,
                    c.name AS customer_name, u.name AS owner
             FROM orders o JOIN customers c ON c.id=o.customer_id
             JOIN users u ON u.id=o.created_by"""
    args = ()
    if user["role"] != "admin":
        sql += " WHERE o.created_by=%s"
        args = (user["id"],)
    return query(sql + " ORDER BY o.id DESC", args)


def validated_draft(data):
    data = object_data(data)
    customer_id = integer(data.get("customer_id"), "Customer", maximum=4_294_967_295)
    date_value = data.get("order_date", datetime.now(timezone.utc).date().isoformat())
    placed = order_date(date_value)
    discount = decimal(data.get("discount_pct", 0), "Discount", Decimal(20))
    rows = data.get("items")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise Problem("An order needs between 1 and 100 items.")
    items = {}
    for index, row in enumerate(rows, 1):
        row = object_data(row)
        product_id = integer(row.get("product_id"), f"Row {index} product", maximum=4_294_967_295)
        if product_id in items:
            raise Problem("A product can appear only once per order.")
        items[product_id] = integer(row.get("quantity"), f"Row {index} quantity")
    return customer_id, placed, discount, items


def locked_products(product_ids):
    products = {}
    for product_id in sorted(product_ids):
        product = query("SELECT * FROM products WHERE id=%s FOR UPDATE", (product_id,), one=True)
        if product is None:
            raise Problem(f"Product {product_id} was not found.", 404)
        products[product_id] = product
    return products


def save_draft(data, user, order_id=None):
    customer_id, placed, discount, quantities = validated_draft(data)
    with transaction():
        saved_rates = {}
        if order_id is not None:
            existing = accessible_order(order_id, user, lock=True)
            if existing["status"] != "Draft":
                raise Problem("Only Draft orders can be edited.", 409)
            saved_rates = {
                item["product_id"]: item["rate"] for item in query(
                    "SELECT product_id, rate FROM order_items WHERE order_id=%s", (order_id,)
                )
            }
        customer = query("SELECT active FROM customers WHERE id=%s FOR SHARE", (customer_id,), one=True)
        if customer is None or not customer["active"]:
            raise Problem("Choose an active customer.")
        products = locked_products(quantities)
        items = []
        for product_id, quantity in quantities.items():
            product = products[product_id]
            if not product["active"]:
                raise Problem(f"Product {product['code']} is inactive.")
            rate = saved_rates.get(product_id, product["price"])
            items.append({"product_id": product_id, "quantity": quantity, "rate": rate,
                          "amount": item_amount(quantity, rate)})
        subtotal, discount_amount, grand_total = order_totals(items, discount)
        values = (customer_id, placed, discount, subtotal, discount_amount, grand_total)
        if order_id is None:
            order_id = execute(
                """INSERT INTO orders (customer_id, order_date, discount_pct, subtotal,
                       discount_amount, grand_total, number, created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (*values, uuid4().hex, user["id"]),
            )
            # Finalize the number in the same transaction as the insert.
            number = f"SO-{datetime.now(timezone.utc).year}-{order_id:06d}"
            execute("UPDATE orders SET number=%s WHERE id=%s", (number, order_id))
        else:
            execute(
                """UPDATE orders SET customer_id=%s, order_date=%s, discount_pct=%s,
                       subtotal=%s, discount_amount=%s, grand_total=%s WHERE id=%s""",
                (*values, order_id),
            )
            execute("DELETE FROM order_items WHERE order_id=%s", (order_id,))
        for item in items:
            execute(
                """INSERT INTO order_items (order_id, product_id, quantity, rate, amount)
                   VALUES (%s,%s,%s,%s,%s)""",
                (order_id, item["product_id"], item["quantity"], item["rate"], item["amount"]),
            )
        return add_order_details(accessible_order(order_id, user))


def movement(product_id, kind, change, reason, user_id, order_id=None):
    execute(
        """INSERT INTO stock_movements (product_id, movement_type, quantity_change, reason,
                                       created_by, order_id) VALUES (%s,%s,%s,%s,%s,%s)""",
        (product_id, kind, change, reason, user_id, order_id),
    )


def change_status(order_id, target, user):
    with transaction():
        order = accessible_order(order_id, user, lock=True)
        current = order["status"]
        if current != target:
            if current == "Cancelled" or (target == "Confirmed" and current != "Draft"):
                raise Problem(f"A {current} order cannot become {target}.", 409)
            if target == "Confirmed" or current == "Confirmed":
                rows = query("SELECT product_id, quantity FROM order_items WHERE order_id=%s",
                             (order_id,))
                products = locked_products(row["product_id"] for row in rows)
                confirming = target == "Confirmed"
                kind, reason = ("Sale", "Order confirmed") if confirming else ("Return", "Order cancelled")
                for row in rows:
                    product = products[row["product_id"]]
                    change = -row["quantity"] if confirming else row["quantity"]
                    balance = product["stock"] + change
                    if balance < 0:
                        raise Problem(f"Insufficient stock for {product['code']}. "
                                      f"Available: {product['stock']}, required: {row['quantity']}.", 409)
                    if balance > MAX_STOCK:
                        raise Problem(f"Restoring {product['code']} would exceed maximum stock.", 409)
                    execute("UPDATE products SET stock=%s WHERE id=%s", (balance, product["id"]))
                    movement(product["id"], kind, change, reason, user["id"], order_id)
            execute("UPDATE orders SET status=%s WHERE id=%s", (target, order_id))
            order["status"] = target
        return add_order_details(order)
