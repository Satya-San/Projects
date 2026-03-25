"""
TWAP-style execution on **Futures testnet** using sliced **MARKET** orders.

The native Binance TWAP **algo** endpoint is ``POST /sapi/v1/algo/futures/newOrderTwap``
on **mainnet** (``https://api.binance.com``) with large minimum notionals — it is not
used here. This module approximates TWAP by splitting quantity across ``slices`` and
sleeping ``duration_sec / slices`` between **MARKET** child orders on testnet.
"""

from __future__ import annotations

import logging
import time
from decimal import ROUND_DOWN, Decimal
from typing import Any

from bot.client import BinanceFuturesTestnetClient

logger = logging.getLogger(__name__)


def _qty_str(d: Decimal) -> str:
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s else "0"


def run_twap_sliced(
    client: BinanceFuturesTestnetClient,
    *,
    symbol: str,
    side: str,
    total_quantity: str,
    duration_sec: int,
    slices: int,
) -> list[dict[str, Any]]:
    if slices < 1:
        raise ValueError("slices must be >= 1")
    if duration_sec < 1:
        raise ValueError("duration_sec must be >= 1")

    total = Decimal(str(total_quantity))
    if total <= 0:
        raise ValueError("total_quantity must be positive")

    sd = side.upper()
    if sd not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")

    base = (total / Decimal(slices)).quantize(Decimal("1e-8"), rounding=ROUND_DOWN)
    if base <= 0:
        raise ValueError("Per-slice quantity rounds to zero; use fewer slices or larger total.")

    gap = duration_sec / slices
    out: list[dict[str, Any]] = []
    acc = Decimal(0)

    for i in range(slices):
        if i < slices - 1:
            q = base
        else:
            q = total - acc
        acc += q
        qty_s = _qty_str(q)
        logger.info("TWAP slice %s/%s qty=%s", i + 1, slices, qty_s)
        r = client.place_order(
            symbol=symbol,
            side=sd,
            order_type="MARKET",
            quantity=qty_s,
        )
        out.append(r)
        if i < slices - 1:
            time.sleep(gap)

    return out
