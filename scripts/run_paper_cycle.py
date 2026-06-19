from datetime import datetime, timedelta

from trading_bot.config.loader import load_config, load_secrets
from trading_bot.data.store import BarStore
from trading_bot.data.alpaca_client import AlpacaHistoricalClient
from trading_bot.data.market_data import MarketData
from trading_bot.strategies.sma_crossover import SmaCrossover
from trading_bot.strategies.rsi import RsiMeanReversion
from trading_bot.strategies.momentum import MomentumBreakout
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.risk.risk_manager import RiskManager
from trading_bot.risk.safety import SafetyState
from trading_bot.control.control_store import ControlStore, apply_controls
from trading_bot.execution.simulated import SimulatedExecutor
from trading_bot.execution.alpaca_exec import AlpacaPaperExecutor
from trading_bot.audit.audit_log import AuditLog
from trading_bot.engine.cycle import TradingCycle


def build_strategies(cfg: dict) -> dict:
    s = cfg["strategies"]
    return {
        "sma_crossover": SmaCrossover(fast=s["sma_crossover"]["fast"],
                                      slow=s["sma_crossover"]["slow"]),
        "rsi": RsiMeanReversion(period=s["rsi"]["period"],
                                oversold=s["rsi"]["oversold"],
                                overbought=s["rsi"]["overbought"]),
        "momentum": MomentumBreakout(lookback=s["momentum"]["lookback"]),
    }


def main() -> None:
    cfg = load_config("config.yaml")
    secrets = load_secrets(".env")
    store = BarStore(cfg["data"]["cache_db"])
    client = AlpacaHistoricalClient(secrets["ALPACA_API_KEY"],
                                    secrets["ALPACA_SECRET_KEY"])
    md = MarketData(store, client, cfg["data"]["timeframe"])

    end = datetime.utcnow()
    start = end - timedelta(days=120)
    symbols = cfg["universe"]
    history = {sym: md.get_bars(sym, start, end) for sym in symbols}
    prices = {sym: bars[-1].close for sym, bars in history.items() if bars}

    risk = cfg["risk"]
    rm = RiskManager(risk["max_position_pct"], risk["max_total_exposure_pct"],
                     risk["max_positions"], risk["min_order_notional"])
    safety = SafetyState(risk["max_daily_loss_pct"])
    pf = Portfolio(cfg["capital"]["starting_cash"])
    safety.start_day(pf.total_equity(prices))

    control_store = ControlStore(cfg.get("control", {}).get("db", "control.sqlite"))
    apply_controls(control_store, safety)

    if cfg["execution"]["mode"] == "alpaca":
        executor = AlpacaPaperExecutor(secrets["ALPACA_API_KEY"],
                                       secrets["ALPACA_SECRET_KEY"])
    else:
        executor = SimulatedExecutor()
    audit = AuditLog(cfg["execution"]["audit_db"])

    dec = cfg["decision"]
    cycle = TradingCycle(
        build_strategies(cfg), dec["weights"], rm, safety, pf, executor, audit,
        threshold=dec["threshold"], min_consensus=dec["min_consensus"],
        stop_loss_pct=risk["stop_loss_pct"], take_profit_pct=risk["take_profit_pct"],
        per_trade_pct=risk["per_trade_pct"],
    )
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    summary = cycle.run_once([s for s in symbols if s in prices], history, prices, run_id)
    print(f"run_id={run_id} summary={summary}")
    print("positions:", {s: (p.qty, p.avg_cost) for s, p in pf.positions.items()})


if __name__ == "__main__":
    main()
