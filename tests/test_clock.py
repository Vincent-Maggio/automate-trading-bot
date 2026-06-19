from datetime import datetime
from types import SimpleNamespace
from trading_bot.runtime.clock import is_market_open, MarketClock


def test_open_during_weekday_session():
    assert is_market_open(datetime(2026, 6, 19, 10, 0)) is True   # Friday 10:00


def test_closed_before_open():
    assert is_market_open(datetime(2026, 6, 19, 9, 0)) is False    # 09:00


def test_closed_after_close():
    assert is_market_open(datetime(2026, 6, 19, 16, 30)) is False


def test_closed_on_weekend():
    assert is_market_open(datetime(2026, 6, 20, 11, 0)) is False    # Saturday


def test_market_clock_uses_client_when_present():
    fake = SimpleNamespace(get_clock=lambda: SimpleNamespace(is_open=True))
    clock = MarketClock(_client=fake)
    assert clock.is_open(datetime(2026, 6, 21, 3, 0)) is True
