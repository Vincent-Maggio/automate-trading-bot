from datetime import datetime, timedelta
from trading_bot.domain.models import Bar, Action, Signal
from trading_bot.strategies.base import Strategy
from trading_bot.backtest.engine import BacktestEngine


class _Scripted(Strategy):
    """Emits a fixed action per bar index based on a script list."""
    def __init__(self, script):
        self.script = script

    def generate_signal(self, symbol, history):
        action = self.script[len(history) - 1]
        return Signal(symbol, action, 1.0, "scripted")


def _bars(closes):
    base = datetime(2023, 1, 1)
    return [Bar("AAPL", base + timedelta(days=i), c, c, c, c, 100)
            for i, c in enumerate(closes)]


def test_buy_then_sell_realizes_profit():
    bars = _bars([10, 10, 20])
    script = [Action.BUY, Action.HOLD, Action.SELL]
    engine = BacktestEngine(starting_cash=100.0)
    result = engine.run("AAPL", bars, _Scripted(script))
    assert result.ending_equity == 200.0
    assert len(result.trades) == 1
    assert result.trades[0].pnl == 100.0


def test_open_position_force_closed_at_end():
    bars = _bars([10, 10, 15])
    script = [Action.BUY, Action.HOLD, Action.HOLD]
    engine = BacktestEngine(starting_cash=100.0)
    result = engine.run("AAPL", bars, _Scripted(script))
    assert result.ending_equity == 150.0
    assert len(result.trades) == 1


def test_equity_curve_has_one_point_per_bar():
    bars = _bars([10, 11, 12])
    script = [Action.HOLD, Action.HOLD, Action.HOLD]
    engine = BacktestEngine(starting_cash=100.0)
    result = engine.run("AAPL", bars, _Scripted(script))
    assert len(result.equity_curve) == 3
    assert result.ending_equity == 100.0
