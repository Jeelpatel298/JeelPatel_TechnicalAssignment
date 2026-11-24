import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MAX_STOCK = 2_147_483_647
MAX_PRICE = Decimal("9999999999.99")
CENT = Decimal("0.01")


class Problem(Exception):
    def __init__(self, message, status=400, *, errors=None):
        super().__init__(message)
        self.status = status
        self.errors = errors


def require_utf8(value):
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise Problem("Text must use valid UTF-8.") from None


def text(value, name, limit):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise Problem(f"{name} must contain 1–{limit} characters.")
    require_utf8(value)
    return value.strip()


def integer(value, name, minimum=1, maximum=MAX_STOCK):
    raw = str(value)
    if len(raw) > 12 or not re.fullmatch(r"-?[0-9]+", raw):
        raise Problem(f"{name} must be a whole number.")
    number = int(raw)
    if not minimum <= number <= maximum:
        raise Problem(f"{name} must be between {minimum} and {maximum}.")
    return number


def decimal(value, name, ceiling):
    raw = str(value).strip()
    if len(raw) > 40:
        raise Problem(f"{name} is too long.")
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", raw):
        raise Problem(f"{name} must be a number.")
    try:
        number = Decimal(raw)
    except InvalidOperation:
        raise Problem(f"{name} must be a number.") from None
    if not number.is_finite() or not 0 <= number <= ceiling:
        raise Problem(f"{name} must be between 0 and {ceiling}.")
    rounded = money(number)
    if number != rounded:
        raise Problem(f"{name} must have at most two decimal places.")
    return rounded


def money(number):
    return number.quantize(CENT, rounding=ROUND_HALF_UP)


def object_data(data):
    if not isinstance(data, dict):
        raise Problem("Send a JSON object.")
    return data


def status(value):
    if value not in ("Active", "Inactive"):
        raise Problem("Status must be Active or Inactive.")
    return value == "Active"


def order_date(value, label="Order date"):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise Problem(f"{label} must use YYYY-MM-DD.")
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise Problem(f"{label} must be a valid calendar date.") from None
    if result.year < 1000:
        raise Problem(f"{label} must be in year 1000 or later.")
    return result
