from datetime import datetime
from types import SimpleNamespace
from trading_bot.data.alpaca_client import AlpacaHistoricalClient


class _FakeDataClient:
    def get_stock_bars(self, request):
        rows = [
            SimpleNamespace(timestamp=datetime(2023, 1, 2), open=1, high=2,
                            low=0.5, close=1.5, volume=100),
            SimpleNamespace(timestamp=datetime(2023, 1, 1), open=1, high=2,
                            low=0.5, close=1.4, volume=110),
        ]
        return SimpleNamespace(data={"AAPL": rows})


def test_fetch_bars_normalizes_and_sorts():
    client = AlpacaHistoricalClient("k", "s", _data_client=_FakeDataClient())
    bars = client.fetch_bars("AAPL", datetime(2023, 1, 1), datetime(2023, 1, 2), "1Day")
    assert [b.timestamp for b in bars] == [datetime(2023, 1, 1), datetime(2023, 1, 2)]
    assert bars[0].symbol == "AAPL"
    assert bars[1].close == 1.5
