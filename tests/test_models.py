from datetime import datetime
import pytest
from trading_bot.domain.models import Action, Bar, Signal, Trade


def test_signal_rejects_out_of_range_confidence():
    with pytest.raises(ValueError):
        Signal(symbol="AAPL", action=Action.BUY, confidence=1.5, rationale="x")


def test_signal_accepts_valid_confidence():
    s = Signal(symbol="AAPL", action=Action.BUY, confidence=0.7, rationale="x")
    assert s.action == Action.BUY


def test_trade_pnl():
    t = Trade(
        symbol="AAPL",
        entry_time=datetime(2023, 1, 1),
        exit_time=datetime(2023, 1, 5),
        entry_price=100.0,
        exit_price=110.0,
        qty=2.0,
    )
    assert t.pnl == 20.0


def test_bar_fields():
    b = Bar("SPY", datetime(2023, 1, 1), 1, 2, 0.5, 1.5, 1000)
    assert b.close == 1.5
