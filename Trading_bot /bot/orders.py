"""Order placement orchestration (API layer used by CLI)."""

from __future__ import annotations

import logging
from typing import Any

from bot.client import BinanceFuturesTestnetClient
from bot.validators import ValidatedOrder

logger = logging.getLogger(__name__)


def place_validated_order(
    client: BinanceFuturesTestnetClient,
    order: ValidatedOrder,
) -> dict[str, Any]:
    """Send a validated order to Binance Futures testnet."""
    logger.info(
        "Placing %s %s %s qty=%s price=%s stop_price=%s",
        order.order_type,
        order.side,
        order.symbol,
        order.quantity,
        order.price,
        order.stop_price,
    )
    resp = client.place_order(
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        price=order.price,
        stop_price=order.stop_price,
    )
    logger.info(
        "Order accepted: orderId=%s status=%s executedQty=%s avgPrice=%s",
        resp.get("orderId"),
        resp.get("status"),
        resp.get("executedQty"),
        resp.get("avgPrice"),
    )
    return resp
