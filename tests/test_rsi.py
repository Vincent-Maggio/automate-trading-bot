from datetime import datetime, timedelta
from trading_bot.domain.models import Bar, Action
from trading_bot.strategies.rsi import RsiMeanReversion


def _series(closes):
    base = datetime(2023, 1, 1)
    return [Bar("AAPL", base + timedelta(days=i), c, c, c, c, 100)
            for i, c in enumerate(closes)]


def test_hold_when_insufficient_history():
    strat = RsiMeanReversion(period=14)
    sig = strat.generate_signal("AAPL", _series([100, 101, 102]))
    assert sig.action == Action.HOLD
    assert sig.confidence == 0.0


def test_all_down_moves_is_oversold_buy():
    strat = RsiMeanReversion(period=5, oversold=30.0, overbought=70.0)
    sig = strat.generate_signal("AAPL", _series([100, 99, 98, 97, 96, 95]))
    assert sig.action == Action.BUY


def test_all_up_moves_is_overbought_sell():
    strat = RsiMeanReversion(period=5, oversold=30.0, overbought=70.0)
    sig = strat.generate_signal("AAPL", _series([95, 96, 97, 98, 99, 100]))
    assert sig.action == Action.SELL
