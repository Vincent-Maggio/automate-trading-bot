from datetime import datetime
from trading_bot.data.market_data import MarketData
from trading_bot.domain.models import Bar


class _SpyClient:
    def __init__(self, bars):
        self.bars = bars
        self.calls = 0

    def fetch_bars(self, symbol, start, end, timeframe):
        self.calls += 1
        return self.bars


class _FakeStore:
    def __init__(self):
        self.saved = []
        self._data = []

    def get_bars(self, symbol, start, end):
        return list(self._data)

    def save_bars(self, bars):
        self.saved.extend(bars)
        self._data.extend(bars)


def _bar(day):
    return Bar("AAPL", datetime(2023, 1, day), 1, 2, 0.5, 1.5, 100)


def test_cache_miss_fetches_and_saves():
    store = _FakeStore()
    client = _SpyClient([_bar(1), _bar(2)])
    md = MarketData(store, client, "1Day")
    out = md.get_bars("AAPL", datetime(2023, 1, 1), datetime(2023, 1, 2))
    assert client.calls == 1
    assert len(out) == 2
    assert len(store.saved) == 2


def test_cache_hit_does_not_fetch():
    store = _FakeStore()
    store._data = [_bar(1), _bar(2)]
    client = _SpyClient([])
    md = MarketData(store, client, "1Day")
    out = md.get_bars("AAPL", datetime(2023, 1, 1), datetime(2023, 1, 2))
    assert client.calls == 0
    assert len(out) == 2
