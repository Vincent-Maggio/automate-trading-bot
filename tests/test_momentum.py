from datetime import datetime, timedelta
from trading_bot.domain.models import Bar, Action
from trading_bot.strategies.momentum import MomentumBreakout


def _series(closes):
    base = datetime(2023, 1, 1)
    return [Bar("AAPL", base + timedelta(days=i), c, c, c, c, 100)
            for i, c in enumerate(closes)]


def test_hold_when_insufficient_history():
    strat = MomentumBreakout(lookback=20)
    sig = strat.generate_signal("AAPL", _series([100, 101]))
    assert sig.action == Action.HOLD
    assert sig.confidence == 0.0


def test_breakout_up_is_buy():
    strat = MomentumBreakout(lookback=3)
    sig = strat.generate_signal("AAPL", _series([100, 101, 102, 105]))
    assert sig.action == Action.BUY


def test_breakdown_is_sell():
    strat = MomentumBreakout(lookback=3)
    sig = strat.generate_signal("AAPL", _series([102, 101, 100, 97]))
    assert sig.action == Action.SELL


def test_inside_range_is_hold():
    strat = MomentumBreakout(lookback=3)
    sig = strat.generate_signal("AAPL", _series([100, 105, 95, 101]))
    assert sig.action == Action.HOLD
