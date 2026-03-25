"""
Interactive prompts (bonus): menus, guided input, and inline validation messages.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from bot.exceptions import ValidationError
from bot.validators import ValidatedOrder, validate_order


def _prompt_non_empty(console: Console, title: str, default: str | None = None) -> str:
    while True:
        raw = Prompt.ask(title, default=default) if default is not None else Prompt.ask(title)
        s = (raw or "").strip()
        if s:
            return s
        console.print("[yellow]Value cannot be empty. Try again.[/yellow]")


def prompt_validated_order(console: Console) -> ValidatedOrder | None:
    """
    Walk through order fields with Rich prompts; re-prompt on validation failure.
    Returns None if the user cancels at confirmation.
    """
    console.print(
        Panel.fit(
            "[bold]Interactive mode[/bold]\n"
            "Answer prompts below. Invalid combinations are caught before sending to the API.",
            border_style="cyan",
        )
    )

    symbol = _prompt_non_empty(console, "Symbol (e.g. BTCUSDT)", default="BTCUSDT")
    side = Prompt.ask("Side", choices=["BUY", "SELL"], default="BUY")
    otype = Prompt.ask(
        "Order type",
        choices=["MARKET", "LIMIT", "STOP", "STOP_LIMIT"],
        default="MARKET",
    )

    qty_raw = _prompt_non_empty(console, "Quantity (base asset)", default="0.001")

    price_in: str | None = None
    stop_in: str | None = None
    if otype in ("LIMIT", "STOP", "STOP_LIMIT"):
        price_in = _prompt_non_empty(console, "Limit price [dim](--price)[/dim]")
    if otype in ("STOP", "STOP_LIMIT"):
        stop_in = _prompt_non_empty(
            console,
            "Stop / trigger price [dim](--stop-price; activates the limit order)[/dim]",
        )

    # Parse numeric fields via shared validator
    while True:
        try:
            q = float(qty_raw)
            price_f = float(price_in) if price_in is not None else None
            stop_f = float(stop_in) if stop_in is not None else None
            validated = validate_order(symbol, side, otype, q, price_f, stop_f)
            break
        except ValidationError as e:
            console.print(f"[bold red]Validation[/bold red] ({e.field or 'input'}): {e}")
            fix = Prompt.ask(
                "Edit field",
                choices=["symbol", "side", "type", "quantity", "price", "stop_price", "retry_same"],
                default="retry_same",
            )
            if fix == "symbol":
                symbol = _prompt_non_empty(console, "Symbol", default=symbol)
            elif fix == "side":
                side = Prompt.ask("Side", choices=["BUY", "SELL"])
            elif fix == "type":
                otype = Prompt.ask(
                    "Order type",
                    choices=["MARKET", "LIMIT", "STOP", "STOP_LIMIT"],
                )
                price_in = stop_in = None
                if otype in ("LIMIT", "STOP", "STOP_LIMIT"):
                    price_in = _prompt_non_empty(console, "Limit price")
                if otype in ("STOP", "STOP_LIMIT"):
                    stop_in = _prompt_non_empty(console, "Stop / trigger price")
            elif fix == "quantity":
                qty_raw = _prompt_non_empty(console, "Quantity", default=qty_raw)
            elif fix == "price":
                if otype in ("LIMIT", "STOP", "STOP_LIMIT"):
                    price_in = _prompt_non_empty(console, "Limit price", default=price_in or "")
                else:
                    console.print("[dim]Price not used for MARKET.[/dim]")
            elif fix == "stop_price":
                if otype in ("STOP", "STOP_LIMIT"):
                    stop_in = _prompt_non_empty(console, "Stop / trigger price", default=stop_in or "")
                else:
                    console.print("[dim]Stop price only for STOP / STOP_LIMIT.[/dim]")
            # retry_same: loop again with same fields

    summary = (
        f"[cyan]symbol[/cyan]={validated.symbol}  [cyan]side[/cyan]={validated.side}  "
        f"[cyan]type[/cyan]={validated.order_type}  [cyan]qty[/cyan]={validated.quantity}"
    )
    if validated.price:
        summary += f"  [cyan]price[/cyan]={validated.price}"
    if validated.stop_price:
        summary += f"  [cyan]stop_price[/cyan]={validated.stop_price}"

    console.print(Panel(summary, title="Confirm order", border_style="green"))
    if not Confirm.ask("Send this order to testnet?", default=False):
        console.print("[dim]Cancelled.[/dim]")
        return None

    return validated
