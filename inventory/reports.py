from .db import query, transaction
from .validation import Problem, integer, order_date


def reports(args):
    start = order_date(args["start"], "Start date") if args.get("start") else None
    end = order_date(args["end"], "End date") if args.get("end") else None
    threshold = integer(args.get("threshold", 10), "Stock threshold", minimum=0)
    if start and end and start > end:
        raise Problem("Start date must be on or before end date.")
    join = "o.status='Confirmed'"
    values = []
    if start:
        join += " AND o.order_date >= %s"
        values.append(start)
    if end:
        join += " AND o.order_date <= %s"
        values.append(end)
    with transaction():
        return {
            "customers": query(
                """SELECT c.name, COUNT(o.id) AS order_count, COALESCE(SUM(o.grand_total),0) AS total
                   FROM customers c LEFT JOIN orders o ON o.customer_id=c.id AND """ + join +
                " GROUP BY c.id,c.name ORDER BY total DESC,c.name,c.id", values
            ),
            "products": query(
                """SELECT p.code,p.name,SUM(i.quantity) AS quantity,SUM(i.amount) AS gross
                   FROM order_items i JOIN orders o ON o.id=i.order_id
                   JOIN products p ON p.id=i.product_id WHERE o.status='Confirmed'
                   GROUP BY p.id,p.code,p.name ORDER BY quantity DESC,p.code"""
            ),
            "low_stock": query(
                "SELECT code,name,stock,active FROM products WHERE stock < %s ORDER BY stock,code",
                (threshold,),
            ),
            "movements": query(
                """SELECT p.code,p.name,m.movement_type,m.quantity_change,o.number AS order_number,
                          m.reason,m.created_at
                   FROM stock_movements m JOIN products p ON p.id=m.product_id
                   LEFT JOIN orders o ON o.id=m.order_id
                   ORDER BY m.created_at DESC,m.id DESC"""
            ),
        }
