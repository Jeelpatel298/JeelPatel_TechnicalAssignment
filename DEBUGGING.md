# Debugging exercise

The original function assigns `total = amount` on every iteration. The first item produces 200, then the second overwrites it with 150. Accumulating each line with `total += item_amount(quantity, rate)` produces 350.00 for the assignment's input.

The corrected [calculate_total](inventory/pricing.py) starts at `Decimal("0.00")`, so an empty list returns 0.00. Missing `qty` or `rate` raises a validation error naming the required keys. Quantity must be a positive whole number within the inventory integer range. The rate must be a finite, non-negative decimal in the supported price range with at most two fractional digits. Zero rates are accepted.

[The pricing tests](tests/test_pricing.py) exercise both items, an empty list, missing fields, negative and fractional quantities, invalid rates, and half-up order discount rounding.

```sh
python -m pytest -q tests/test_pricing.py
```
