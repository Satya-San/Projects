"""
CLI entry point: argparse-style options via Typer + Rich for clear UX (bonus).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from bot.client import BASE_URL, BinanceFuturesTestnetClient
from bot.exceptions import BinanceAPIError, ValidationError
from bot.grid_orders import place_grid
from bot.interactive import prompt_validated_order
from bot.logging_config import setup_logging
from bot.oco_orders import place_oco_bracket
from bot.orders import place_validated_order
from bot.twap_exec import run_twap_sliced
from bot.validators import (
    ValidatedOrder,
    format_decimal_param,
    validate_order,
    validate_perp_symbol,
)

app = typer.Typer(
    name="trading-bot",
    help="Place orders on Binance USDT-M Futures **Testnet** (https://testnet.binancefuture.com).",
    add_completion=False,
    no_args_is_help=True,
)
console = Console(stderr=True)
log = logging.getLogger(__name__)


def _load_credentials() -> tuple[str, str]:
    load_dotenv()
    key = os.environ.get("BINANCE_TESTNET_API_KEY", "").strip()
    secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "").strip()
    if not key or not secret:
        console.print(
            "[bold red]Missing credentials.[/bold red] Set [cyan]BINANCE_TESTNET_API_KEY[/cyan] and "
            "[cyan]BINANCE_TESTNET_API_SECRET[/cyan] in your environment or a [cyan].env[/cyan] file "
            "(see [cyan].env.example[/cyan])."
        )
        raise typer.Exit(code=2)
    return key, secret


def _summarize_response(resp: dict[str, Any]) -> Table:
    table = Table(title="Order response (key fields)", show_header=True, header_style="bold")
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    keys = [
        "orderId",
        "symbol",
        "status",
        "clientOrderId",
        "price",
        "stopPrice",
        "avgPrice",
        "origQty",
        "executedQty",
        "cumQuote",
        "type",
        "side",
        "updateTime",
    ]
    for k in keys:
        if k in resp and resp[k] is not None:
            table.add_row(k, str(resp[k]))
    return table


def _print_batch_results(items: list[Any], *, title: str = "Multi-leg / batch results") -> None:
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("#", style="dim")
    table.add_column("Result")
    for i, item in enumerate(items):
        if isinstance(item, dict):
            if "orderId" in item:
                table.add_row(str(i + 1), f"orderId={item.get('orderId')} status={item.get('status')}")
            elif "code" in item and item.get("code", 0) < 0:
                table.add_row(str(i + 1), f"[red]code={item.get('code')} {item.get('msg')}[/red]")
            else:
                table.add_row(str(i + 1), json.dumps(item, default=str)[:200])
        else:
            table.add_row(str(i + 1), str(item)[:200])
    console.print(table)


def _order_summary_table(validated: ValidatedOrder) -> Table:
    summary = Table(title="Order request summary", show_header=False)
    summary.add_column("Field", style="dim")
    summary.add_column("Value")
    summary.add_row("symbol", validated.symbol)
    summary.add_row("side", validated.side)
    summary.add_row("type", validated.order_type)
    summary.add_row("quantity", validated.quantity)
    summary.add_row("price", validated.price or "—")
    summary.add_row("stop_price", validated.stop_price or "—")
    return summary


def execute_place_order(validated: ValidatedOrder, *, log_file: str) -> None:
    """Shared path for `place` and `interactive`: print summary, call API, print result."""
    console.print(Panel(_order_summary_table(validated), border_style="blue"))

    try:
        api_key, api_secret = _load_credentials()
        client = BinanceFuturesTestnetClient(api_key, api_secret)
        resp = place_validated_order(client, validated)
    except BinanceAPIError as e:
        console.print(f"[bold red]API error[/bold red]: {e}")
        if e.code is not None:
            console.print(f"  [dim]code={e.code}[/dim]")
        log.error("Order failed: %s", e)
        raise typer.Exit(code=3)
    except OSError as e:
        console.print(f"[bold red]I/O error[/bold red]: {e}")
        log.exception("I/O error")
        raise typer.Exit(code=4)

    log.info("Order response JSON: %s", json.dumps(resp, default=str))
    console.print(_summarize_response(resp))
    console.print("[bold green]Success:[/bold green] order accepted by testnet.")
    console.print(
        "[dim]Full response logged at DEBUG level; see logs/ for request/response details.[/dim]"
    )


@app.command("place")
def place_order_cmd(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Perpetual symbol, e.g. BTCUSDT"),
    side: str = typer.Option(..., "--side", help="BUY or SELL"),
    order_type: str = typer.Option(
        ...,
        "--type",
        "-t",
        help="MARKET, LIMIT, STOP, or STOP_LIMIT (stop-limit → API type STOP)",
    ),
    quantity: float = typer.Option(..., "--quantity", "-q", help="Order quantity (base asset)"),
    price: float | None = typer.Option(
        None,
        "--price",
        "-p",
        help="Limit price (required for LIMIT and STOP / STOP_LIMIT)",
    ),
    stop_price: float | None = typer.Option(
        None,
        "--stop-price",
        help="Trigger price for STOP / STOP_LIMIT (Binance: stopPrice)",
    ),
    log_file: str = typer.Option(
        "trading_bot.log",
        "--log-file",
        help="Log file name under ./logs/",
    ),
) -> None:
    """Validate input, place a futures order on testnet, and print a structured summary."""
    setup_logging(log_file=log_file)
    log.info(
        "CLI place: symbol=%s side=%s type=%s qty=%s price=%s stop_price=%s",
        symbol,
        side,
        order_type,
        quantity,
        price,
        stop_price,
    )

    try:
        validated = validate_order(symbol, side, order_type, quantity, price, stop_price)
    except ValidationError as e:
        console.print(f"[bold red]Validation error[/bold red] ({e.field or 'input'}): {e}")
        log.warning("Validation failed: %s", e)
        raise typer.Exit(code=1)

    execute_place_order(validated, log_file=log_file)


@app.command("interactive")
def interactive_cmd(
    log_file: str = typer.Option(
        "trading_bot.log",
        "--log-file",
        help="Log file name under ./logs/",
    ),
) -> None:
    """Bonus: guided prompts, choices, and validation messages before submitting."""
    setup_logging(log_file=log_file)
    log.info("CLI interactive session started")

    validated = prompt_validated_order(console)
    if validated is None:
        raise typer.Exit(code=0)

    execute_place_order(validated, log_file=log_file)


@app.command("oco")
def oco_cmd(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Perpetual symbol, e.g. BTCUSDT"),
    side: str = typer.Option(
        ...,
        "--side",
        help="Exit side: SELL (close long) or BUY (close short); both legs use reduceOnly",
    ),
    quantity: float = typer.Option(..., "--quantity", "-q", help="Size per leg (same for TP + SL)"),
    take_profit: float = typer.Option(..., "--take-profit", help="Take-profit limit price"),
    stop_loss: float = typer.Option(..., "--stop-loss", help="Stop-loss trigger (STOP_MARKET)"),
    working_type: str = typer.Option(
        "CONTRACT_PRICE",
        "--working-type",
        help="Conditional working type for the STOP_MARKET leg",
    ),
    log_file: str = typer.Option("trading_bot.log", "--log-file", help="Log file under ./logs/"),
) -> None:
    """
    OCO-style **bracket**: one LIMIT (take profit) + one STOP_MARKET (stop loss) in ``batchOrders``.

    Binance Futures has no single OCO endpoint; this is two linked **reduce-only** exits.
    Requires an open position sized at least ``quantity`` on testnet.
    """
    setup_logging(log_file=log_file)
    log.info(
        "CLI oco: symbol=%s side=%s qty=%s tp=%s sl=%s",
        symbol,
        side,
        quantity,
        take_profit,
        stop_loss,
    )
    try:
        sym = validate_perp_symbol(symbol)
        sd = side.strip().upper()
        if sd not in ("BUY", "SELL"):
            raise ValidationError("Side must be BUY or SELL.", field="side")
        q_s = format_decimal_param(quantity, field="quantity")
        tp_s = format_decimal_param(take_profit, field="take_profit")
        sl_s = format_decimal_param(stop_loss, field="stop_loss")
    except ValidationError as e:
        console.print(f"[bold red]Validation error[/bold red] ({e.field or 'input'}): {e}")
        raise typer.Exit(code=1)

    console.print(
        Panel.fit(
            "[bold]OCO-style bracket[/bold]\n"
            "LIMIT take-profit + STOP_MARKET stop-loss, both [cyan]reduceOnly[/cyan].",
            border_style="magenta",
        )
    )

    try:
        api_key, api_secret = _load_credentials()
        client = BinanceFuturesTestnetClient(api_key, api_secret)
        items = place_oco_bracket(
            client,
            symbol=sym,
            side=sd,
            quantity=q_s,
            take_profit_price=tp_s,
            stop_loss_price=sl_s,
            working_type=working_type,
        )
    except ValidationError as e:
        console.print(f"[bold red]Validation error[/bold red] ({e.field or 'input'}): {e}")
        raise typer.Exit(code=1)
    except BinanceAPIError as e:
        console.print(f"[bold red]API error[/bold red]: {e}")
        log.error("OCO failed: %s", e)
        raise typer.Exit(code=3)

    log.info("OCO batch response: %s", json.dumps(items, default=str))
    _print_batch_results(items, title="OCO bracket legs")
    console.print("[bold green]Batch submitted.[/bold green] Check each leg status above.")


@app.command("twap")
def twap_cmd(
    symbol: str = typer.Option(..., "--symbol", "-s"),
    side: str = typer.Option(..., "--side", help="BUY or SELL"),
    quantity: float = typer.Option(..., "--quantity", "-q", help="Total base quantity to execute"),
    duration: int = typer.Option(
        300,
        "--duration",
        "-d",
        help="Total seconds to spread slices over (testnet TWAP-style)",
    ),
    slices: int = typer.Option(
        10,
        "--slices",
        help="Number of MARKET child orders",
    ),
    log_file: str = typer.Option("trading_bot.log", "--log-file", help="Log file under ./logs/"),
) -> None:
    """
    TWAP-style **sliced** execution: repeated MARKET orders on testnet over ``duration`` seconds.

    Native Binance TWAP algo (``/sapi/v1/algo/futures/newOrderTwap``) is mainnet-only; this
    approximates TWAP for testnet demos.
    """
    setup_logging(log_file=log_file)
    log.info("CLI twap: symbol=%s side=%s qty=%s duration=%s slices=%s", symbol, side, quantity, duration, slices)
    try:
        sym = validate_perp_symbol(symbol)
        sd = side.strip().upper()
        if sd not in ("BUY", "SELL"):
            raise ValidationError("Side must be BUY or SELL.", field="side")
        q_s = format_decimal_param(quantity, field="quantity")
    except ValidationError as e:
        console.print(f"[bold red]Validation error[/bold red] ({e.field or 'input'}): {e}")
        raise typer.Exit(code=1)

    console.print(
        Panel.fit(
            "[bold]TWAP-style (sliced MARKET)[/bold]\n"
            "This blocks until all slices are sent (sleeps between slices).",
            border_style="yellow",
        )
    )

    try:
        api_key, api_secret = _load_credentials()
        client = BinanceFuturesTestnetClient(api_key, api_secret)
        rows = run_twap_sliced(
            client,
            symbol=sym,
            side=sd,
            total_quantity=q_s,
            duration_sec=duration,
            slices=slices,
        )
    except (BinanceAPIError, ValueError) as e:
        console.print(f"[bold red]Error[/bold red]: {e}")
        log.error("TWAP failed: %s", e)
        raise typer.Exit(code=3)

    log.info("TWAP responses: %s", json.dumps(rows, default=str))
    _print_batch_results(rows, title="TWAP slices (MARKET)")
    console.print("[bold green]TWAP-style run finished.[/bold green]")


@app.command("grid")
def grid_cmd(
    symbol: str = typer.Option(..., "--symbol", "-s"),
    side: str = typer.Option(..., "--side", help="BUY or SELL"),
    low: float = typer.Option(..., "--low", help="Lowest grid price (inclusive)"),
    high: float = typer.Option(..., "--high", help="Highest grid price (inclusive)"),
    steps: int = typer.Option(..., "--steps", help="Number of LIMIT orders (price levels)"),
    per_order_qty: float = typer.Option(
        ...,
        "--per-order-qty",
        help="Base quantity on each level",
    ),
    log_file: str = typer.Option("trading_bot.log", "--log-file", help="Log file under ./logs/"),
) -> None:
    """Place evenly spaced LIMIT orders between ``low`` and ``high`` (batch size ≤ 5 per request)."""
    setup_logging(log_file=log_file)
    log.info(
        "CLI grid: symbol=%s side=%s low=%s high=%s steps=%s per=%s",
        symbol,
        side,
        low,
        high,
        steps,
        per_order_qty,
    )
    try:
        sym = validate_perp_symbol(symbol)
        sd = side.strip().upper()
        if sd not in ("BUY", "SELL"):
            raise ValidationError("Side must be BUY or SELL.", field="side")
        lo = format_decimal_param(low, field="low")
        hi = format_decimal_param(high, field="high")
        pq = format_decimal_param(per_order_qty, field="per_order_qty")
        if steps < 1 or steps > 100:
            raise ValidationError("steps must be between 1 and 100.", field="steps")
    except ValidationError as e:
        console.print(f"[bold red]Validation error[/bold red] ({e.field or 'input'}): {e}")
        raise typer.Exit(code=1)

    try:
        api_key, api_secret = _load_credentials()
        client = BinanceFuturesTestnetClient(api_key, api_secret)
        items = place_grid(
            client,
            symbol=sym,
            side=sd,
            low=lo,
            high=hi,
            steps=steps,
            quantity_per_order=pq,
        )
    except (BinanceAPIError, ValueError) as e:
        console.print(f"[bold red]Error[/bold red]: {e}")
        log.error("Grid failed: %s", e)
        raise typer.Exit(code=3)

    log.info("Grid batch responses count=%s", len(items))
    _print_batch_results(items, title="Grid LIMIT orders (all batches flattened)")
    console.print("[bold green]Grid orders submitted.[/bold green]")


@app.command("ui")
def ui_cmd(
    port: int = typer.Option(8501, "--port", "-p", help="Streamlit server port"),
) -> None:
    """Launch the optional lightweight **Streamlit** web UI (same testnet features)."""
    root = Path(__file__).resolve().parent.parent
    app_path = root / "ui" / "streamlit_app.py"
    if not app_path.is_file():
        console.print(f"[red]Missing UI file:[/red] {app_path}")
        raise typer.Exit(7)
    console.print(
        f"[green]Starting Streamlit[/green] → [cyan]{app_path}[/cyan] on port [bold]{port}[/bold]"
    )
    rc = subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.port",
            str(port),
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(root),
    )
    raise typer.Exit(rc.returncode)


@app.command("ping")
def ping_public() -> None:
    """Check connectivity to Binance Futures testnet (public /fapi/v1/ping, no API keys)."""
    setup_logging()
    url = f"{BASE_URL}/fapi/v1/ping"
    log.info("GET %s", url)
    try:
        r = requests.get(url, timeout=15)
    except requests.RequestException as e:
        console.print(f"[red]Network error:[/red] {e}")
        log.exception("Ping failed")
        raise typer.Exit(5)
    if r.status_code == 200:
        console.print("[green]OK[/green] — testnet reachable ([cyan]%s[/cyan])." % url)
    else:
        console.print(f"[yellow]Unexpected HTTP {r.status_code}[/yellow]: {r.text[:200]}")
        raise typer.Exit(6)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
