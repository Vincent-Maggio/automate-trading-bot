import pytest
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.domain.models import OrderSide


def test_buy_then_value_and_exposure():
    pf = Portfolio(starting_cash=1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=5.0, price=100.0)
    assert pf.cash == 500.0
    assert pf.market_value({"AAPL": 100.0}) == 500.0
    assert pf.total_equity({"AAPL": 100.0}) == 1000.0
    assert pf.exposure({"AAPL": 100.0}) == 0.5


def test_weighted_average_cost():
    pf = Portfolio(starting_cash=1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=1.0, price=100.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=1.0, price=200.0)
    assert pf.positions["AAPL"].qty == 2.0
    assert pf.positions["AAPL"].avg_cost == 150.0


def test_sell_realizes_pnl_and_closes():
    pf = Portfolio(starting_cash=1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=2.0, price=100.0)
    pf.apply_fill("AAPL", OrderSide.SELL, qty=2.0, price=120.0)
    assert pf.realized_pnl == 40.0
    assert "AAPL" not in pf.positions
    assert pf.cash == 1000.0 - 200.0 + 240.0


def test_oversell_raises():
    pf = Portfolio(starting_cash=1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=1.0, price=100.0)
    with pytest.raises(ValueError):
        pf.apply_fill("AAPL", OrderSide.SELL, qty=2.0, price=100.0)
