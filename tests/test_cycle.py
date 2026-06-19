from datetime import datetime, timedelta
from trading_bot.engine.cycle import TradingCycle
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.risk.risk_manager import RiskManager
from trading_bot.risk.safety import SafetyState
from trading_bot.execution.simulated import SimulatedExecutor
from trading_bot.audit.audit_log import AuditLog
from trading_bot.strategies.base import Strategy
from trading_bot.domain.models import Action, Signal, Bar


class _Always(Strategy):
    def __init__(self, action):
        self.action = action

    def generate_signal(self, symbol, history):
        return Signal(symbol, self.action, 0.9, "forced")


def _bars(symbol, closes):
    base = datetime(2023, 1, 1)
    return [Bar(symbol, base + timedelta(days=i), c, c, c, c, 100)
            for i, c in enumerate(closes)]


def _cycle(tmp_path, executor=None):
    strategies = {"a": _Always(Action.BUY), "b": _Always(Action.BUY)}
    weights = {"a": 1.0, "b": 1.0}
    rm = RiskManager(0.20, 0.80, 5, min_order_notional=1.0)
    safety = SafetyState(0.03)
    pf = Portfolio(1000.0)
    audit = AuditLog(str(tmp_path / "audit.sqlite"))
    ex = executor or SimulatedExecutor(now=lambda: datetime(2023, 1, 1))
    return TradingCycle(strategies, weights, rm, safety, pf, ex, audit,
                        threshold=0.5, min_consensus=2,
                        stop_loss_pct=0.05, take_profit_pct=0.10,
                        per_trade_pct=0.10), pf, audit


def test_buy_consensus_places_order_and_updates_portfolio(tmp_path):
    cycle, pf, audit = _cycle(tmp_path)
    hist = {"AAPL": _bars("AAPL", [10, 11, 12])}
    res = cycle.run_once(["AAPL"], hist, {"AAPL": 12.0}, run_id="r1")
    assert res["halted"] is False
    assert res["orders"] == 1
    assert "AAPL" in pf.positions
    assert audit.count("orders") == 1
    assert audit.count("fills") == 1
    assert audit.count("decisions") >= 1


def test_kill_switch_halts_cycle(tmp_path):
    cycle, pf, audit = _cycle(tmp_path)
    cycle.safety.kill()
    res = cycle.run_once(["AAPL"], {"AAPL": _bars("AAPL", [10, 11, 12])},
                         {"AAPL": 12.0}, run_id="r2")
    assert res["halted"] is True
    assert res["orders"] == 0
    assert "AAPL" not in pf.positions
    assert audit.count("events") == 1
