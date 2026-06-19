import sys
from datetime import datetime

from trading_bot.config.loader import load_config, load_secrets
from trading_bot.data.store import BarStore
from trading_bot.data.alpaca_client import AlpacaHistoricalClient
from trading_bot.data.market_data import MarketData
from trading_bot.strategies.sma_crossover import SmaCrossover
from trading_bot.backtest.engine import BacktestEngine
from trading_bot.backtest.metrics import compute_metrics
from trading_bot.backtest.report import render_report


def main(symbol: str) -> None:
    cfg = load_config("config.yaml")
    secrets = load_secrets(".env")
    store = BarStore(cfg["data"]["cache_db"])
    client = AlpacaHistoricalClient(secrets["ALPACA_API_KEY"],
                                    secrets["ALPACA_SECRET_KEY"])
    md = MarketData(store, client, cfg["data"]["timeframe"])
    start = datetime.fromisoformat(cfg["backtest"]["start"])
    end = datetime.fromisoformat(cfg["backtest"]["end"])
    bars = md.get_bars(symbol, start, end)

    sma_cfg = cfg["strategies"]["sma_crossover"]
    strat = SmaCrossover(fast=sma_cfg["fast"], slow=sma_cfg["slow"])
    engine = BacktestEngine(starting_cash=cfg["capital"]["starting_cash"])
    result = engine.run(symbol, bars, strat)
    metrics = compute_metrics(result)
    print(render_report(symbol, result, metrics))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/run_backtest.py SYMBOL")
        sys.exit(1)
    main(sys.argv[1])
