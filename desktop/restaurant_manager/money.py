from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

CENT = Decimal("0.01")
HUNDRED = Decimal(100)


def yuan_decimal(value: Any) -> Decimal:
    """Parse an external yuan value without going through binary float math."""
    try:
        return Decimal(str(value if value is not None else 0)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValueError(f"无效金额：{value}") from error


def yuan_to_cents(value: Any) -> int:
    """Convert yuan input to the canonical integer-cent storage unit."""
    return int(yuan_decimal(value) * HUNDRED)


def cents_to_yuan(cents: Any) -> str:
    """Return a fixed two-decimal yuan string for API/legacy compatibility."""
    try:
        value = Decimal(int(cents)) / HUNDRED
    except (ValueError, TypeError) as error:
        raise ValueError(f"无效分值：{cents}") from error
    return format(value.quantize(CENT), ".2f")


def cents_to_legacy_number(cents: Any) -> float:
    """Legacy state currently exposes monetary values as JSON numbers in yuan."""
    return float(cents_to_yuan(cents))
