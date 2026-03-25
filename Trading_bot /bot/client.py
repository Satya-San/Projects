"""Binance USDT-M Futures Testnet REST client (signed requests)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import urlencode

import requests

from bot.exceptions import BinanceAPIError

logger = logging.getLogger(__name__)

BASE_URL = "https://testnet.binancefuture.com"


class BinanceFuturesTestnetClient:
    """Minimal client for placing futures orders on testnet."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        timeout: float = 30.0,
        recv_window: int = 5000,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout
        self.recv_window = recv_window
        self._session = requests.Session()
        self._session.headers.update({"X-MBX-APIKEY": self.api_key})

    def _sign(self, params: dict[str, Any]) -> str:
        query = urlencode(sorted((k, v) for k, v in params.items() if v is not None))
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request_post(
        self,
        path: str,
        params: dict[str, Any],
    ) -> dict[str, Any] | list[Any]:
        params = {**params}
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.recv_window
        params["signature"] = self._sign(params)

        url = f"{BASE_URL}{path}"
        logger.info("POST %s (signed)", path)
        logger.debug("Request params keys: %s", sorted(params.keys()))

        try:
            r = self._session.post(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            logger.exception("Network failure calling %s: %s", path, e)
            raise BinanceAPIError(f"Network error: {e}", status_code=None) from e

        text = r.text
        logger.debug("HTTP %s body (truncated): %s", r.status_code, text[:4000])

        try:
            data: dict[str, Any] | list[Any] = r.json()
        except ValueError:
            logger.error("Non-JSON response: %s", text[:500])
            raise BinanceAPIError(
                f"Invalid JSON response (HTTP {r.status_code})",
                status_code=r.status_code,
            )

        if isinstance(data, list):
            return data

        if not isinstance(data, dict):
            raise BinanceAPIError(
                f"Unexpected response shape (HTTP {r.status_code})",
                status_code=r.status_code,
            )

        if "code" in data and isinstance(data["code"], int) and data["code"] < 0:
            msg = str(data.get("msg", "Unknown API error"))
            logger.error("API error code=%s msg=%s", data["code"], msg)
            raise BinanceAPIError(msg, code=data["code"], status_code=r.status_code)

        if r.status_code >= 400:
            msg = str(data.get("msg", data))
            raise BinanceAPIError(msg, status_code=r.status_code)

        return data

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: str | None = None,
        stop_price: str | None = None,
        time_in_force: str = "GTC",
        reduce_only: bool | None = None,
        working_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Place a USDT-M futures order on testnet.

        ``STOP`` is Binance Futures stop-limit: trigger at ``stopPrice``,
        limit order at ``price`` (both required).
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if reduce_only is not None:
            params["reduceOnly"] = "true" if reduce_only else "false"
        if working_type:
            params["workingType"] = working_type

        if order_type == "LIMIT":
            if not price:
                raise ValueError("LIMIT orders require price")
            params["price"] = price
            params["timeInForce"] = time_in_force

        elif order_type == "STOP":
            if not price or not stop_price:
                raise ValueError("STOP orders require price (limit) and stop_price (trigger)")
            params["price"] = price
            params["stopPrice"] = stop_price
            params["timeInForce"] = time_in_force

        elif order_type == "STOP_MARKET":
            if not stop_price:
                raise ValueError("STOP_MARKET orders require stop_price")
            params["stopPrice"] = stop_price

        elif order_type == "MARKET":
            pass

        else:
            raise ValueError(f"Unsupported order_type for place_order: {order_type}")

        res = self._request_post("/fapi/v1/order", params)
        if not isinstance(res, dict):
            raise BinanceAPIError("Unexpected non-dict response for single order")
        return res

    def place_batch_orders(self, orders: list[dict[str, Any]]) -> list[Any]:
        """
        POST /fapi/v1/batchOrders — max **5** orders per request.
        ``orders`` are dicts in the same shape as the REST docs (string values).
        """
        if len(orders) < 1 or len(orders) > 5:
            raise ValueError("batchOrders must contain between 1 and 5 orders")

        payload = json.dumps(orders, separators=(",", ":"))
        params: dict[str, Any] = {"batchOrders": payload}
        res = self._request_post("/fapi/v1/batchOrders", params)
        if not isinstance(res, list):
            raise BinanceAPIError("Unexpected batch response shape")
        return res
