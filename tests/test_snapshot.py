from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.domain.models import OrderSide
from trading_bot.reporting.snapshot import portfolio_snapshot, AccountSnapshot


def test_snapshot_fields():
    pf = Portfolio(1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=2.0, price=100.0)
    snap = portfolio_snapshot(pf, {"AAPL": 110.0})
    assert isinstance(snap, AccountSnapshot)
    assert snap.cash == 800.0
    assert snap.equity == 800.0 + 220.0
    assert snap.positions[0]["symbol"] == "AAPL"
    assert snap.positions[0]["unrealized_pnl"] == 20.0
