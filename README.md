# Multi-Strategy Automated Trading System

Paper-first, config-driven automated trading for US equities & ETFs on Alpaca.
**Phase 1** (this state): market-data ingestion + backtesting harness.

## Setup

1. Python 3.11+
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in Alpaca **paper** keys.
4. Review `config.yaml` (universe, capital, backtest window, strategy params).

## Run a backtest

```bash
PYTHONPATH=src python scripts/run_backtest.py SPY
```

## Run tests

```bash
PYTHONPATH=src pytest -v
```

## Safety

- Phase 1 reads historical data only; it places no orders.
- Secrets live in `.env` (gitignored). Never commit real keys.
- All financial parameters live in `config.yaml`; nothing is hardcoded.

## Reporting (Phase 3a)

Generate and deliver the morning or nightly portfolio report:

```bash
PYTHONPATH=src python scripts/send_report.py morning
PYTHONPATH=src python scripts/send_report.py nightly
```

- Delivery channel is set by `reporting.delivery` in `config.yaml` (`console` or `email`).
- For email, set `SMTP_*` and `REPORT_*` in `.env` (Gmail: use an App Password, not your account password).
- Report content: equity, cash, exposure, realized P&L, current positions, what the bot did (fills + decisions), and any alerts (circuit breaker / kill switch).

## Dashboard & API (Phase 3b)

Run the dashboard + API:

```bash
PYTHONPATH=src python scripts/run_api.py
# then open http://127.0.0.1:8000/
```

- Shows equity, cash, exposure, realized P&L, open positions, recent decisions, and alerts, with a **Kill switch / Resume** button.
- The kill switch is persistent (`ControlStore`); the runtime consults it before each cycle, so halting from the dashboard stops new trading.
- Portfolio data reflects the live Alpaca paper account when keys are set; otherwise it shows zeros.

## Operations

See `RUNBOOK.md` for start/stop, kill switch, config changes, and report interpretation.

**Live trading is OFF by default** and requires BOTH `execution.live: true` in `config.yaml` AND `LIVE_TRADING=true` in the environment. Leave it off until you have validated behavior in paper trading.
