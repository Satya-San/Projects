"""
OCO-style **bracket** orders on Futures testnet.

Binance USDT-M Futures does **not** expose a single OCO endpoint. This module
places **two reduce-only** legs in one ``batchOrders`` call (take-profit limit +
stop-market), which is the usual way to approximate Spot-style OCO for exits.
"""

from __future__ import annotations

import logging
from typing import Any

from bot.client import BinanceFuturesTestnetClient
from bot.exceptions import ValidationError

logger = logging.getLogger(__name__)


def build_oco_bracket_orders(
    *,
    symbol: str,
    side: str,
    quantity: str,
    take_profit_price: str,
    stop_loss_price: str,
    working_type: str = "CONTRACT_PRICE",
) -> list[dict[str, Any]]:
    """
    Two legs: LIMIT at ``take_profit_price`` and STOP_MARKET at ``stop_loss_price``.

    ``side`` is the **exit** side (SELL to close a long, BUY to close a short).
    """
    sd = side.upper()
    if sd not in ("BUY", "SELL"):
        raise ValidationError("Side must be BUY or SELL.", field="side")

    try:
        tp = float(take_profit_price)
        sl = float(stop_loss_price)
    except (TypeError, ValueError):
        raise ValidationError("Prices must be numeric.", field="price")

    if sd == "SELL" and tp <= sl:
        raise ValidationError(
            "For SELL (e.g. close long), take-profit price should be above stop-loss trigger.",
            field="take_profit_price",
        )
    if sd == "BUY" and tp >= sl:
        raise ValidationError(
            "For BUY (e.g. close short), take-profit price should be below stop-loss trigger.",
            field="take_profit_price",
        )

    leg_tp: dict[str, Any] = {
        "symbol": symbol,
        "side": sd,
        "type": "LIMIT",
        "timeInForce": "GTC",
        "quantity": quantity,
        "price": take_profit_price,
        "reduceOnly": "true",
    }
    leg_sl: dict[str, Any] = {
        "symbol": symbol,
        "side": sd,
        "type": "STOP_MARKET",
        "quantity": quantity,
        "stopPrice": stop_loss_price,
        "reduceOnly": "true",
        "workingType": working_type,
    }
    return [leg_tp, leg_sl]


def place_oco_bracket(
    client: BinanceFuturesTestnetClient,
    *,
    symbol: str,
    side: str,
    quantity: str,
    take_profit_price: str,
    stop_loss_price: str,
    working_type: str = "CONTRACT_PRICE",
) -> list[Any]:
    """Submit OCO-style bracket via ``batchOrders``."""
    orders = build_oco_bracket_orders(
        symbol=symbol,
        side=side,
        quantity=quantity,
        take_profit_price=take_profit_price,
        stop_loss_price=stop_loss_price,
        working_type=working_type,
    )
    logger.info("Placing OCO-style bracket (2 legs) for %s", symbol)
    return client.place_batch_orders(orders)
