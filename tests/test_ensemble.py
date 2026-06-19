from datetime import datetime, timedelta
from trading_bot.domain.models import Bar, Action, Signal
from trading_bot.strategies.base import Strategy
from trading_bot.risk.risk_manager import RiskManager
from trading_bot.backtest.ensemble import EnsembleBacktester


class _Always(Strategy):
    def __init__(self, action):
        self.action = action

    def generate_signal(self, symbol, history):
        return Signal(symbol, self.action, 0.9, "forced")


def _bars(closes):
    base = datetime(2023, 1, 1)
    return [Bar("AAPL", base + timedelta(days=i), c, c, c, c, 100)
            for i, c in enumerate(closes)]


def _bt():
    rm = RiskManager(max_position_pct=1.0, max_total_exposure_pct=1.0,
                     max_positions=5, min_order_notional=1.0)
    return EnsembleBacktester(rm, threshold=0.5, min_consensus=2,
                              stop_loss_pct=0.05, take_profit_pct=0.10,
                              per_trade_pct=1.0, starting_cash=100.0)


def test_take_profit_then_reenter_and_close():
    strategies = {"a": _Always(Action.BUY), "b": _Always(Action.BUY)}
    weights = {"a": 1.0, "b": 1.0}
    # buy @10; +10% at 11 -> take-profit sells, re-enters; closes at 12
    result = _bt().run("AAPL", _bars([10, 11, 12]), strategies, weights)
    assert result.ending_equity == 120.0
    assert len(result.trades) == 2
    assert result.trades[0].pnl == 10.0


def test_no_consensus_no_trades():
    # only one strategy buys; min_consensus=2 -> never trades
    strategies = {"a": _Always(Action.BUY), "b": _Always(Action.HOLD)}
    weights = {"a": 1.0, "b": 1.0}
    result = _bt().run("AAPL", _bars([10, 11, 12, 13]), strategies, weights)
    assert result.trades == []
    assert result.ending_equity == 100.0


def test_stop_loss_exits():
    strategies = {"a": _Always(Action.BUY), "b": _Always(Action.BUY)}
    weights = {"a": 1.0, "b": 1.0}
    # buy @100; drop to 94 (-6%) triggers 5% stop-loss
    result = _bt().run("AAPL", _bars([100, 94]), strategies, weights)
    assert len(result.trades) >= 1
    assert result.trades[0].pnl < 0
