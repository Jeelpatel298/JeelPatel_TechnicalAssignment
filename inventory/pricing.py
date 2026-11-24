from decimal import Decimal

from .validation import MAX_PRICE, Problem, decimal, integer, money


def item_amount(quantity, rate):
    return money(quantity * rate)


def calculate_total(items):
    """Total the debugging exercise's qty/rate records."""
    total = Decimal("0.00")
    for item in items:
        if not isinstance(item, dict) or "qty" not in item or "rate" not in item:
            raise Problem("Each item must contain qty and rate.")
        quantity = integer(item["qty"], "Quantity")
        rate = decimal(item["rate"], "Rate", MAX_PRICE)
        total += item_amount(quantity, rate)
    return total


def order_totals(items, discount_pct):
    subtotal = sum((item["amount"] for item in items), Decimal("0.00"))
    discount_amount = money(subtotal * discount_pct / 100)
    return subtotal, discount_amount, subtotal - discount_amount
