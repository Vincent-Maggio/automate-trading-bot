from types import SimpleNamespace
from trading_bot.reporting.account_reader import AlpacaAccountReader


class _FakeClient:
    def get_account(self):
        return SimpleNamespace(cash="500.0", equity="720.0")

    def get_all_positions(self):
        return [SimpleNamespace(symbol="AAPL", qty="2", avg_entry_price="100.0",
                                current_price="110.0", market_value="220.0",
                                unrealized_pl="20.0")]


def test_snapshot_from_account():
    reader = AlpacaAccountReader("k", "s", _client=_FakeClient())
    snap = reader.snapshot()
    assert snap.cash == 500.0
    assert snap.equity == 720.0
    assert snap.positions[0]["symbol"] == "AAPL"
    assert snap.positions[0]["market_value"] == 220.0
    assert round(snap.exposure, 4) == round(220.0 / 720.0, 4)
