from datetime import datetime
from trading_bot.data.store import BarStore


def test_save_and_get_round_trip(tmp_path, sample_bars):
    store = BarStore(str(tmp_path / "t.sqlite"))
    store.save_bars(sample_bars)
    got = store.get_bars("AAPL", datetime(2023, 1, 1), datetime(2023, 1, 10))
    assert len(got) == 10
    assert got[0].timestamp < got[-1].timestamp
    assert got[0].close == sample_bars[0].close


def test_save_is_idempotent(tmp_path, sample_bars):
    store = BarStore(str(tmp_path / "t.sqlite"))
    store.save_bars(sample_bars)
    store.save_bars(sample_bars)
    got = store.get_bars("AAPL", datetime(2023, 1, 1), datetime(2023, 1, 10))
    assert len(got) == 10
