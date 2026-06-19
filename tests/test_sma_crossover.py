from datetime import datetime, timedelta
from trading_bot.domain.models import Bar, Action
from trading_bot.strategies.sma_crossover import SmaCrossover


def _series(closes):
    base = datetime(2023, 1, 1)
    return [
        Bar("AAPL", base + timedelta(days=i), c, c, c, c, 100)
        for i, c in enumerate(closes)
    ]


def test_hold_when_insufficient_history():
    strat = SmaCrossover(fast=2, slow=3)
    sig = strat.generate_signal("AAPL", _series([10, 11]))
    assert sig.action == Action.HOLD
    assert sig.confidence == 0.0


def test_buy_on_upward_cross():
    strat = SmaCrossover(fast=2, slow=3)
    sig = strat.generate_signal("AAPL", _series([10, 9, 8, 9, 12]))
    assert sig.action == Action.BUY


def test_sell_on_downward_cross():
    strat = SmaCrossover(fast=2, slow=3)
    sig = strat.generate_signal("AAPL", _series([8, 9, 10, 9, 6]))
    assert sig.action == Action.SELL
