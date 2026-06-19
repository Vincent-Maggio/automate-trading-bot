import os
import time
from datetime import datetime, timedelta, timezone, date

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
from trading_bot.execution.selector import select_executor
from trading_bot.audit.audit_log import AuditLog
from trading_bot.engine.cycle import TradingCycle
from trading_bot.runtime.clock import MarketClock
from trading_bot.runtime.runtime import Runtime
from trading_bot.runtime.monitoring import maybe_alert
from trading_bot.reporting.account_reader import AlpacaAccountReader
from trading_bot.reporting.snapshot import AccountSnapshot
from trading_bot.reporting.report_builder import build_report
from trading_bot.notify.console_notifier import ConsoleNotifier
from trading_bot.notify.email_notifier import EmailNotifier


def build_runtime():
    cfg = load_config("config.yaml")
    secrets = load_secrets(".env")
    store = BarStore(cfg["data"]["cache_db"])
    hist_client = AlpacaHistoricalClient(secrets["ALPACA_API_KEY"],
                                         secrets["ALPACA_SECRET_KEY"])
    md = MarketData(store, hist_client, cfg["data"]["timeframe"])
    risk = cfg["risk"]
    dec = cfg["decision"]
    rep = cfg["reporting"]
    control_store = ControlStore(cfg["control"]["db"])
    audit = AuditLog(cfg["execution"]["audit_db"])
    notifier = ConsoleNotifier()

    def strategies():
        s = cfg["strategies"]
        return {
            "sma_crossover": SmaCrossover(s["sma_crossover"]["fast"], s["sma_crossover"]["slow"]),
            "rsi": RsiMeanReversion(s["rsi"]["period"], s["rsi"]["oversold"], s["rsi"]["overbought"]),
            "momentum": MomentumBreakout(s["momentum"]["lookback"]),
        }

    def run_cycle():
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=120)
        symbols = cfg["universe"]
        history = {sym: md.get_bars(sym, start, end) for sym in symbols}
        prices = {s: b[-1].close for s, b in history.items() if b}
        rm = RiskManager(risk["max_position_pct"], risk["max_total_exposure_pct"],
                         risk["max_positions"], risk["min_order_notional"])
        safety = SafetyState(risk["max_daily_loss_pct"])
        pf = Portfolio(cfg["capital"]["starting_cash"])
        safety.start_day(pf.total_equity(prices))
        apply_controls(control_store, safety)
        executor = select_executor(cfg["execution"]["mode"], cfg["execution"]["live"],
                                   os.environ.get("LIVE_TRADING", "false"),
                                   secrets["ALPACA_API_KEY"], secrets["ALPACA_SECRET_KEY"])
        cycle = TradingCycle(strategies(), dec["weights"], rm, safety, pf, executor, audit,
                             threshold=dec["threshold"], min_consensus=dec["min_consensus"],
                             stop_loss_pct=risk["stop_loss_pct"],
                             take_profit_pct=risk["take_profit_pct"],
                             per_trade_pct=risk["per_trade_pct"])
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        summary = cycle.run_once([s for s in symbols if s in prices], history, prices, run_id)
        maybe_alert(safety, control_store, notifier)
        print(f"[cycle] {run_id} {summary}")
        return summary

    def send_report(kind):
        activity = {
            "date": date.today().isoformat(),
            "decisions": audit.recent_decisions(rep["recent_limit"]),
            "fills": audit.recent_fills(rep["recent_limit"]),
            "events": audit.recent_events(rep["recent_limit"]),
        }
        if secrets["ALPACA_API_KEY"]:
            snapshot = AlpacaAccountReader(secrets["ALPACA_API_KEY"],
                                           secrets["ALPACA_SECRET_KEY"]).snapshot()
        else:
            snapshot = AccountSnapshot(0.0, 0.0, 0.0, 0.0, [])
        subject, text, html = build_report(kind, snapshot, activity)
        if rep["delivery"] == "email":
            EmailNotifier(host=secrets["SMTP_HOST"], port=secrets["SMTP_PORT"],
                          username=secrets["SMTP_USER"], password=secrets["SMTP_PASS"],
                          sender=secrets["REPORT_FROM_EMAIL"],
                          recipient=secrets["REPORT_TO_EMAIL"]).send(subject, text, html)
        else:
            ConsoleNotifier().send(subject, text, html)
        print(f"[report] sent {kind}: {subject}")

    runtime = Runtime(MarketClock(), control_store, run_cycle, send_report,
                      morning_hour=rep["morning_hour"], nightly_hour=rep["nightly_hour"])
    return runtime, cfg


def main():
    runtime, cfg = build_runtime()
    interval = cfg["runtime"]["poll_interval_seconds"]
    print(f"bot started; polling every {interval}s. Ctrl-C to stop.")
    runtime.run_forever(lambda: datetime.now(timezone.utc), time.sleep, interval)


if __name__ == "__main__":
    main()
