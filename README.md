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
