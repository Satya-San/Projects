"""Input validation for CLI order parameters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from bot.exceptions import ValidationError

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,20}USDT$")
_ALLOWED_SIDES = frozenset({"BUY", "SELL"})
# User may type STOP_LIMIT; normalized API type is STOP (Binance Futures stop-limit).
_ALLOWED_TYPES = frozenset({"MARKET", "LIMIT", "STOP", "STOP_LIMIT"})
_TYPE_ALIASES = {"STOP_LIMIT": "STOP"}


@dataclass(frozen=True)
class ValidatedOrder:
    """Normalized, validated order input."""

    symbol: str
    side: str
    order_type: str  # API type: MARKET | LIMIT | STOP
    quantity: str
    price: str | None
    stop_price: str | None = None


def _normalize_order_type(order_type: str) -> str:
    u = (order_type or "").strip().upper()
    u = _TYPE_ALIASES.get(u, u)
    return u


def format_decimal_param(value: float | str, *, field: str = "value") -> str:
    """Parse a positive decimal and return a string suitable for API params."""
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"{field} must be a positive number.", field=field)
    if d <= 0:
        raise ValidationError(f"{field} must be greater than zero.", field=field)
    return _normalize_decimal_str(d)


def _normalize_decimal_str(value: Decimal) -> str:
    """Format Decimal without scientific notation for API params."""
    s = format(value, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s else "0"


def _parse_positive_decimal(
    raw: float | str | None,
    *,
    field: str,
    required: bool,
) -> str | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if required:
            raise ValidationError(f"{field} is required.", field=field)
        return None
    try:
        d = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"{field} must be a positive number.", field=field)
    if d <= 0:
        raise ValidationError(f"{field} must be greater than zero.", field=field)
    return _normalize_decimal_str(d)


def validate_perp_symbol(symbol: str) -> str:
    """Validate USDT perpetual symbol only (shared by OCO / grid / TWAP helpers)."""
    sym = (symbol or "").strip().upper()
    if not _SYMBOL_RE.match(sym):
        raise ValidationError(
            "Symbol must look like BTCUSDT (alphanumeric + USDT suffix), e.g. BTCUSDT, ETHUSDT.",
            field="symbol",
        )
    return sym


def validate_order(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float | str,
    price: float | str | None,
    stop_price: float | str | None = None,
) -> ValidatedOrder:
    """
    Validate and normalize order fields.
    Raises ValidationError with a clear message on failure.

    STOP (or STOP_LIMIT): Binance Futures ``type=STOP`` — requires both
    ``price`` (limit) and ``stop_price`` (trigger).
    """
    sym = (symbol or "").strip().upper()
    if not _SYMBOL_RE.match(sym):
        raise ValidationError(
            "Symbol must look like BTCUSDT (alphanumeric + USDT suffix), e.g. BTCUSDT, ETHUSDT.",
            field="symbol",
        )

    sd = (side or "").strip().upper()
    if sd not in _ALLOWED_SIDES:
        raise ValidationError("Side must be BUY or SELL.", field="side")

    raw_type = (order_type or "").strip().upper()
    if raw_type not in _ALLOWED_TYPES:
        raise ValidationError(
            "Order type must be MARKET, LIMIT, STOP, or STOP_LIMIT (alias for STOP).",
            field="order_type",
        )

    ot = _normalize_order_type(raw_type)

    try:
        q = Decimal(str(quantity))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("Quantity must be a positive number.", field="quantity")

    if q <= 0:
        raise ValidationError("Quantity must be greater than zero.", field="quantity")

    qty_str = _normalize_decimal_str(q)

    price_str: str | None = None
    stop_str: str | None = None

    if ot == "MARKET":
        if price is not None:
            raise ValidationError("Price must not be set for MARKET orders.", field="price")
        if stop_price is not None:
            raise ValidationError(
                "Stop price must not be set for MARKET orders.",
                field="stop_price",
            )

    elif ot == "LIMIT":
        price_str = _parse_positive_decimal(price, field="price", required=True)
        if stop_price is not None:
            raise ValidationError(
                "Stop price must not be set for LIMIT orders (use STOP for stop-limit).",
                field="stop_price",
            )

    elif ot == "STOP":
        price_str = _parse_positive_decimal(price, field="price", required=True)
        stop_str = _parse_positive_decimal(stop_price, field="stop_price", required=True)

    return ValidatedOrder(
        symbol=sym,
        side=sd,
        order_type=ot,
        quantity=qty_str,
        price=price_str,
        stop_price=stop_str,
    )
