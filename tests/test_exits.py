from trading_bot.risk.exits import evaluate_exits
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.domain.models import Action, OrderSide


def _pf():
    pf = Portfolio(1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=1.0, price=100.0)
    return pf


def test_stop_loss_triggers_sell():
    pf = _pf()
    exits = evaluate_exits(pf, {"AAPL": 94.0}, stop_loss_pct=0.05, take_profit_pct=0.10)
    assert len(exits) == 1
    assert exits[0].action == Action.SELL
    assert "stop-loss" in exits[0].rationale


def test_take_profit_triggers_sell():
    pf = _pf()
    exits = evaluate_exits(pf, {"AAPL": 111.0}, stop_loss_pct=0.05, take_profit_pct=0.10)
    assert len(exits) == 1
    assert exits[0].action == Action.SELL
    assert "take-profit" in exits[0].rationale


def test_inside_band_no_exit():
    pf = _pf()
    exits = evaluate_exits(pf, {"AAPL": 102.0}, stop_loss_pct=0.05, take_profit_pct=0.10)
    assert exits == []
