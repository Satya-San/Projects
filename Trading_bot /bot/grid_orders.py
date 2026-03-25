"""
Grid of **LIMIT** orders between ``low`` and ``high`` (testnet).

Uses ``batchOrders`` (max 5 per call) and additional batches as needed.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from bot.client import BinanceFuturesTestnetClient

logger = logging.getLogger(__name__)


def _linspace(low: Decimal, high: Decimal, steps: int) -> list[Decimal]:
    if steps < 1:
        raise ValueError("steps must be >= 1")
    if steps == 1:
        return [low]
    span = high - low
    n = steps - 1
    return [low + span * Decimal(i) / Decimal(n) for i in range(steps)]


def _fmt_price(p: Decimal) -> str:
    s = format(p, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s else "0"


def build_grid_limit_orders(
    *,
    symbol: str,
    side: str,
    low: str,
    high: str,
    steps: int,
    quantity_per_order: str,
) -> list[dict[str, Any]]:
    """``steps`` evenly spaced LIMIT orders from ``low`` to ``high`` (inclusive)."""
    sd = side.upper()
    if sd not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")

    lo = Decimal(low)
    hi = Decimal(high)
    if lo <= 0 or hi <= 0:
        raise ValueError("low and high must be positive")
    if hi < lo:
        raise ValueError("high must be >= low")
    if steps > 1 and lo >= hi:
        raise ValueError("For multiple steps, high must be greater than low")

    prices = _linspace(lo, hi, steps)
    if sd == "SELL":
        prices = list(reversed(prices))

    out: list[dict[str, Any]] = []
    for p in prices:
        out.append(
            {
                "symbol": symbol,
                "side": sd,
                "type": "LIMIT",
                "timeInForce": "GTC",
                "quantity": quantity_per_order,
                "price": _fmt_price(p),
            }
        )
    return out


def chunk_list(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def place_grid(
    client: BinanceFuturesTestnetClient,
    *,
    symbol: str,
    side: str,
    low: str,
    high: str,
    steps: int,
    quantity_per_order: str,
) -> list[Any]:
    """Place all grid legs; returns concatenated batch responses (each batch is a list)."""
    orders = build_grid_limit_orders(
        symbol=symbol,
        side=side,
        low=low,
        high=high,
        steps=steps,
        quantity_per_order=quantity_per_order,
    )
    all_results: list[Any] = []
    for batch in chunk_list(orders, 5):
        logger.info("Placing grid batch with %s orders", len(batch))
        all_results.extend(client.place_batch_orders(batch))
    return all_results
