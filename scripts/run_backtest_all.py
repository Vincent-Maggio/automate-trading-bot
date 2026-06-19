import sys
from datetime import datetime

from trading_bot.config.loader import load_config, load_secrets
from trading_bot.data.store import BarStore
from trading_bot.data.alpaca_client import AlpacaHistoricalClient
from trading_bot.data.market_data import MarketData
from trading_bot.strategies.sma_crossover import SmaCrossover
from trading_bot.backtest.engine import BacktestEngine
from trading_bot.backtest.metrics import compute_metrics


def main(start_s: str, end_s: str) -> None:
    cfg = load_config("config.yaml")
    secrets = load_secrets(".env")
    store = BarStore(cfg["data"]["cache_db"])
    client = AlpacaHistoricalClient(secrets["ALPACA_API_KEY"],
                                    secrets["ALPACA_SECRET_KEY"])
    md = MarketData(store, client, cfg["data"]["timeframe"])
    start = datetime.fromisoformat(start_s)
    end = datetime.fromisoformat(end_s)
    sma = cfg["strategies"]["sma_crossover"]
    cash = cfg["capital"]["starting_cash"]

    print(f"SMA-only backtest {start_s} -> {end_s} "
          f"(SMA {sma['fast']}/{sma['slow']}, ${cash:.0f} each)\n")
    print(f"{'symbol':6}  {'return':>8}  {'maxDD':>7}  {'sharpe':>7}  {'win%':>6}  trades")
    print("-" * 56)
    results = []
    for sym in cfg["universe"]:
        bars = md.get_bars(sym, start, end)
        if not bars:
            print(f"{sym:6}  (no data)")
            continue
        strat = SmaCrossover(fast=sma["fast"], slow=sma["slow"])
        result = BacktestEngine(starting_cash=cash).run(sym, bars, strat)
        m = compute_metrics(result)
        results.append((sym, m))
        print(f"{sym:6}  {m['total_return'] * 100:7.2f}%  {m['max_drawdown'] * 100:6.2f}%  "
              f"{m['sharpe']:7.2f}  {m['win_rate'] * 100:5.1f}%  {m['num_trades']}")

    if results:
        avg = sum(m["total_return"] for _, m in results) / len(results)
        wins = sum(1 for _, m in results if m["total_return"] > 0)
        print("-" * 56)
        print(f"Average return: {avg * 100:.2f}%   Profitable symbols: {wins}/{len(results)}")


if __name__ == "__main__":
    cfg = load_config("config.yaml")
    start_s = sys.argv[1] if len(sys.argv) > 1 else cfg["backtest"]["start"]
    end_s = sys.argv[2] if len(sys.argv) > 2 else cfg["backtest"]["end"]
    main(start_s, end_s)
