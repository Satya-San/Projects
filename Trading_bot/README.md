# Binance Futures Testnet — Order CLI

Small Python **3.10+** app that places **USDT-M perpetual** orders on **Binance Futures Testnet** using the official base URL:

`https://testnet.binancefuture.com`

The project separates the **REST client** (`bot/client.py`) from the **CLI** (`bot/cli.py`), validates input (`bot/validators.py`), and logs requests, responses, and errors to a **log file** under `./logs/`.

## Features (assignment checklist)

| Requirement | Implementation |
|-------------|----------------|
| Market & limit orders | `MARKET` and `LIMIT` (`timeInForce=GTC` for limits) |
| BUY and SELL | Validated enums |
| CLI: symbol, side, type, quantity, price (limit) | Typer + Rich panels/tables |
| Clear stdout: summary + `orderId`, `status`, `executedQty`, `avgPrice` | Rich table + success/failure messages |
| Layered structure | `client.py` / `orders.py` / `validators.py` / `cli.py` |
| Logging to file | `logging_config.py` → `logs/trading_bot.log` (detailed INFO/DEBUG in file; console WARNING+) |
| Errors | `ValidationError`, `BinanceAPIError`, network handling |

### Bonus (completed)

| Bonus option | Implementation |
|--------------|----------------|
| **Extra order styles** | **Stop-limit** (`STOP` / `STOP_LIMIT`), **OCO-style bracket** (`oco`), **TWAP-style slices** (`twap`), **grid** (`grid`). |
| **Enhanced CLI UX** | **Typer** + **Rich** (help, panels, tables). |
| **Interactive mode** | `python -m bot interactive` — prompts, **choices** for side/type, inline validation, confirm before submit (`bot/interactive.py`). |
| **Lightweight UI** | **Streamlit** app: `python -m bot ui` → `ui/streamlit_app.py` (tabs for single / OCO / TWAP / grid). |

**Notes**

- **OCO:** Binance USDT-M Futures has **no single OCO endpoint**. `oco` sends **two reduce-only legs** in one `batchOrders` call: **LIMIT** (take profit) + **STOP_MARKET** (stop loss). You need an open position to reduce; behaviour is “bracket / exit”, not Spot-style OCO atomics.
- **TWAP:** Native Binance Futures TWAP is **`POST /sapi/v1/algo/futures/newOrderTwap`** on **mainnet** (`api.binance.com`) with large minimums. On **testnet**, `twap` runs **TWAP-style** execution: split total size into **MARKET** slices with sleeps — good for demos, not the exchange algo engine.
- **Grid:** Places evenly spaced **LIMIT** orders between `--low` and `--high` (uses `batchOrders`, max 5 per request, then more batches).
- Binance may reject conditional orders if prices vs. side/mark are invalid; errors are logged and shown.

## Setup

1. **Testnet account & keys**  
   - Register and enable **Binance Futures Testnet**: use the testnet site linked from Binance developer docs.  
   - Create **API Key** + **Secret** for Futures testnet.

2. **Python environment**

   ```bash
   cd trading_bot
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Credentials**

   ```bash
   cp .env.example .env
   # Edit .env: BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET
   ```

   Alternatively export the same variables in your shell.

## How to run

From the `trading_bot` directory (so `bot` is importable):

```bash
# Optional: verify connectivity (no API keys required)
python -m bot ping
```

### Market order example

Use a **small** quantity that satisfies **min notional** and **step size** for your symbol (see assumptions below).

```bash
python -m bot place -s BTCUSDT --side BUY --type MARKET -q 0.001 --log-file market_run.log
```

### Limit order example

Pick a **price** far from market if you only want the assignment logs without an immediate fill, or use a realistic price for a fill.

```bash
python -m bot place -s BTCUSDT --side SELL --type LIMIT -q 0.001 -p 120000 --log-file limit_run.log
```

### Stop-limit (`STOP` / `STOP_LIMIT`) example

Uses Binance Futures **STOP** (stop-limit): when **`stopPrice`** is touched, a **limit** order at **`price`** is placed. Both flags are required.

```bash
python -m bot place -s BTCUSDT --side BUY --type STOP -q 0.001 \
  -p 50000 --stop-price 51000 --log-file stop_run.log
# Equivalent:
python -m bot place -s BTCUSDT --side BUY --type STOP_LIMIT -q 0.001 \
  -p 50000 --stop-price 51000
```

### Interactive mode (bonus)

```bash
python -m bot interactive --log-file interactive_run.log
```

### OCO-style bracket (`oco`)

Exit-side **SELL** (close long) or **BUY** (close short). Same quantity on both legs; **reduceOnly**.

```bash
python -m bot oco -s BTCUSDT --side SELL -q 0.01 \
  --take-profit 70000 --stop-loss 60000 --log-file oco_run.log
```

### TWAP-style (`twap`)

```bash
python -m bot twap -s BTCUSDT --side BUY -q 0.05 --duration 120 --slices 8 --log-file twap_run.log
```

Blocks until all **MARKET** slices are sent (sleeps between slices).

### Grid (`grid`)

```bash
python -m bot grid -s BTCUSDT --side BUY --low 60000 --high 61000 --steps 7 --per-order-qty 0.001 \
  --log-file grid_run.log
```

### Web UI (optional)

Requires `streamlit` (included in `requirements.txt`).

```bash
pip install -r requirements.txt
python -m bot ui --port 8501
```

Opens a local Streamlit app (single order, OCO, TWAP, grid tabs).

After running, you should have:

- `logs/market_run.log` — **one MARKET order** log trail  
- `logs/limit_run.log` — **one LIMIT order** log trail  

Copy or attach those (or the default `logs/trading_bot.log` if you use the default name twice with care) when emailing your submission, as required by the brief.

### Install as a console script (optional)

```bash
pip install -e .
trading-bot ping
trading-bot place -s ETHUSDT --side BUY --type MARKET -q 0.01
```

## Project layout

```text
trading_bot/
  bot/
    __init__.py
    __main__.py
    cli.py            # CLI (Typer + Rich)
    client.py         # Signed REST client
    orders.py         # Orchestration
    validators.py     # Input validation
    interactive.py    # Bonus: interactive prompts
    oco_orders.py     # OCO-style bracket (batch)
    grid_orders.py    # Grid LIMIT ladder
    twap_exec.py      # TWAP-style sliced MARKET
    logging_config.py
    exceptions.py
  ui/
    streamlit_app.py  # Optional Streamlit UI
  README.md
  requirements.txt
  pyproject.toml
  .env.example
```

## Assumptions & notes

- **Logging:** Full API trail (DEBUG/INFO) is written to `./logs/<log-file>`. The terminal stays readable: Rich panels/tables for the human summary, while the logging module prints only **WARNING** and **ERROR** to stderr so successful runs are not noisy.
- **USDT-M perpetuals only** (assignment scope). Symbols like `BTCUSDT` are enforced with a simple `*USDT` pattern.
- **Exchange rules** (min quantity, step size, min notional) are enforced by Binance; if an order is rejected, the API message is logged and printed.
- **System time** should be reasonably accurate; large clock skew can cause Binance error `-1021` (timestamp).
- **Testnet balances and symbols** can differ from mainnet; use small sizes for experiments.
- **Secrets** are read from the environment / `.env` and must not be committed.

## Evaluation / submission

- Ensure **at least one successful MARKET** and **one successful LIMIT** run on testnet, and include the corresponding **log files** with your email, per the application instructions.
- Prefer a **public GitHub repo** or a **zip** containing this folder, `README.md`, and `requirements.txt` / `pyproject.toml`.

## License

MIT — sample submission code for the hiring task.
