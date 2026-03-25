"""
Lightweight Streamlit UI for the Binance Futures **testnet** bot.

Run from the ``trading_bot`` directory::

    python -m bot ui
    # or: streamlit run ui/streamlit_app.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv

from bot.client import BinanceFuturesTestnetClient
from bot.grid_orders import place_grid
from bot.oco_orders import place_oco_bracket
from bot.orders import place_validated_order
from bot.twap_exec import run_twap_sliced
from bot.validators import (
    format_decimal_param,
    validate_order,
    validate_perp_symbol,
)

st.set_page_config(page_title="Futures Testnet Bot", page_icon="📈", layout="wide")


def _load_client() -> BinanceFuturesTestnetClient | None:
    load_dotenv(ROOT / ".env")
    key = os.environ.get("BINANCE_TESTNET_API_KEY", "").strip()
    sec = os.environ.get("BINANCE_TESTNET_API_SECRET", "").strip()
    if not key or not sec:
        st.error("Set **BINANCE_TESTNET_API_KEY** and **BINANCE_TESTNET_API_SECRET** in `.env` (project root).")
        return None
    return BinanceFuturesTestnetClient(key, sec)


st.title("Binance USDT-M Futures — Testnet")
st.caption("Base URL: `https://testnet.binancefuture.com` — same behaviour as the CLI.")

client = _load_client()

tab_simple, tab_oco, tab_twap, tab_grid = st.tabs(
    ["Single order", "OCO-style bracket", "TWAP-style", "Grid"]
)

with tab_simple:
    st.markdown("Place **MARKET**, **LIMIT**, **STOP** / **STOP_LIMIT** like `python -m bot place`.")
    with st.form("single"):
        c1, c2 = st.columns(2)
        with c1:
            symbol = st.text_input("Symbol", value="BTCUSDT")
            side = st.selectbox("Side", ["BUY", "SELL"])
            otype = st.selectbox("Type", ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"])
        with c2:
            qty = st.number_input("Quantity", min_value=0.0, value=0.001, format="%f")
            price = st.number_input("Price (LIMIT / STOP)", min_value=0.0, value=0.0)
            stop_p = st.number_input("Stop price (STOP only)", min_value=0.0, value=0.0)
        go = st.form_submit_button("Submit order")
    if go and client:
        p = price if otype in ("LIMIT", "STOP", "STOP_LIMIT") else None
        sp = stop_p if otype in ("STOP", "STOP_LIMIT") else None
        try:
            v = validate_order(symbol, side, otype, qty, p, sp)
            r = place_validated_order(client, v)
            st.success("Order accepted")
            st.json(r)
        except Exception as e:
            st.exception(e)

with tab_oco:
    st.markdown(
        "**OCO-style bracket** — LIMIT take-profit + STOP_MARKET stop-loss (`reduceOnly`). "
        "Requires a position to reduce. Native OCO is not on Futures; this is two legs in `batchOrders`."
    )
    with st.form("oco"):
        sym = st.text_input("Symbol", value="BTCUSDT", key="oco_sym")
        sd = st.selectbox("Exit side", ["SELL", "BUY"], key="oco_side")
        q = st.number_input("Quantity (per leg)", min_value=0.0, value=0.001, format="%f", key="oco_q")
        tp = st.number_input("Take-profit (LIMIT)", min_value=0.0, value=0.0, key="oco_tp")
        sl = st.number_input("Stop-loss trigger (STOP_MARKET)", min_value=0.0, value=0.0, key="oco_sl")
        go = st.form_submit_button("Place bracket")
    if go and client:
        try:
            s = validate_perp_symbol(sym)
            qs = format_decimal_param(q, field="quantity")
            tps = format_decimal_param(tp, field="take_profit")
            sls = format_decimal_param(sl, field="stop_loss")
            items = place_oco_bracket(
                client,
                symbol=s,
                side=sd,
                quantity=qs,
                take_profit_price=tps,
                stop_loss_price=sls,
            )
            st.success("Batch submitted")
            st.code(json.dumps(items, indent=2, default=str))
        except Exception as e:
            st.exception(e)

with tab_twap:
    st.markdown(
        "**TWAP-style** — sliced **MARKET** orders over time. "
        "Native Binance TWAP algo is mainnet `/sapi/...`; this is a testnet-friendly approximation."
    )
    with st.form("twap"):
        sym = st.text_input("Symbol", value="BTCUSDT", key="tw_sym")
        sd = st.selectbox("Side", ["BUY", "SELL"], key="tw_side")
        q = st.number_input("Total quantity", min_value=0.0, value=0.01, format="%f", key="tw_q")
        dur = st.number_input("Duration (seconds)", min_value=1, value=60)
        slices = st.number_input("Slices", min_value=1, value=5)
        go = st.form_submit_button("Run TWAP-style (blocks until done)")
    if go and client:
        try:
            s = validate_perp_symbol(sym)
            qs = format_decimal_param(q, field="quantity")
            rows = run_twap_sliced(
                client,
                symbol=s,
                side=sd,
                total_quantity=qs,
                duration_sec=int(dur),
                slices=int(slices),
            )
            st.success("Finished")
            st.code(json.dumps(rows, indent=2, default=str))
        except Exception as e:
            st.exception(e)

with tab_grid:
    st.markdown("**Grid** — evenly spaced **LIMIT** orders from **low** to **high**.")
    with st.form("grid"):
        sym = st.text_input("Symbol", value="BTCUSDT", key="g_sym")
        sd = st.selectbox("Side", ["BUY", "SELL"], key="g_side")
        lo = st.number_input("Low price", min_value=0.0, value=60000.0)
        hi = st.number_input("High price", min_value=0.0, value=61000.0)
        steps = st.number_input("Steps", min_value=1, value=5)
        pq = st.number_input("Qty per level", min_value=0.0, value=0.001, format="%f")
        go = st.form_submit_button("Place grid")
    if go and client:
        try:
            s = validate_perp_symbol(sym)
            los = format_decimal_param(lo, field="low")
            his = format_decimal_param(hi, field="high")
            pqs = format_decimal_param(pq, field="per_order_qty")
            if steps < 1 or steps > 100:
                raise ValueError("steps must be 1..100")
            items = place_grid(
                client,
                symbol=s,
                side=sd,
                low=los,
                high=his,
                steps=int(steps),
                quantity_per_order=pqs,
            )
            st.success("Grid submitted")
            st.code(json.dumps(items, indent=2, default=str))
        except Exception as e:
            st.exception(e)

st.divider()
st.caption("Logs still go to `./logs/` when using the CLI; Streamlit runs in-process only.")
