# Operator Runbook

## Start / stop
- Start the bot loop: `PYTHONPATH=src python scripts/run_bot.py`
- Start the dashboard/API: `PYTHONPATH=src python scripts/run_api.py` → http://127.0.0.1:8000/
- Stop: Ctrl-C in the terminal running the process.

## Kill switch (halt all new orders)
- Dashboard: click **Kill switch — halt trading**.
- CLI: `PYTHONPATH=src python -c "from trading_bot.control.control_store import ControlStore; ControlStore('control.sqlite').kill('manual')"`
- Resume: dashboard **Resume**, or `...ControlStore('control.sqlite').clear_kill()`.
- The runtime checks the kill switch before every cycle; halting stops new orders immediately.

## Circuit breaker
- Trips automatically when the day's loss exceeds `risk.max_daily_loss_pct` (default 3%). It blocks further trading for the day and fires an alert.

## Change configuration
- Edit `config.yaml` (universe, strategy weights, risk caps, schedule). Restart the bot to apply.
- Secrets live in `.env` only (never commit). See `.env.example`.

## Going live (DANGER — real money)
- Live trading is OFF by default and double-gated. To enable, BOTH must be true:
  1. `execution.live: true` in `config.yaml`
  2. environment `LIVE_TRADING=true`
- If either is missing, the bot trades paper. Only enable after a full paper-validation window.

## Interpreting reports
- Morning/nightly reports show equity, cash, exposure, realized P&L, positions, what the bot did (fills + decisions), and alerts.
- Full audit trail is in `audit.sqlite` (tables: signals, decisions, risk_checks, orders, fills, events) — every trade is reconstructable by `run_id`.
