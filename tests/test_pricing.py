from decimal import Decimal

import pytest

from inventory.pricing import calculate_total, order_totals
from inventory.validation import Problem


def test_accumulates_all_items():
    assert calculate_total([{"qty": 2, "rate": 100}, {"qty": 3, "rate": 50}]) == Decimal("350.00")


def test_empty_items():
    assert calculate_total([]) == Decimal("0.00")


@pytest.mark.parametrize("item", [
    {}, {"qty": 1}, {"rate": 100}, {"qty": 0, "rate": 100}, {"qty": -1, "rate": 100},
    {"qty": 1.2, "rate": 100}, {"qty": True, "rate": 100}, {"qty": 1, "rate": -1},
    {"qty": 1, "rate": "NaN"}, {"qty": 1, "rate": "abc"}, {"qty": 1, "rate": "0.001"},
])
def test_invalid_item(item):
    with pytest.raises(Problem):
        calculate_total([item])


def test_half_cent_discount_rounds_up():
    assert order_totals([{"amount": Decimal("0.05")}], Decimal(10)) == (
        Decimal("0.05"), Decimal("0.01"), Decimal("0.04"),
    )
