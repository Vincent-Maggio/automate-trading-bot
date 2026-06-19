from trading_bot.risk.risk_manager import RiskManager
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.domain.models import Action, Decision, OrderSide


def _buy(symbol="AAPL"):
    return Decision(symbol=symbol, action=Action.BUY, net_score=1.0,
                    consensus_met=True, rationale="r", votes=[])


def _rm():
    return RiskManager(max_position_pct=0.20, max_total_exposure_pct=0.80,
                       max_positions=5, min_order_notional=1.0)


def test_within_caps_approved_unchanged():
    pf = Portfolio(1000.0)
    res = _rm().check(_buy(), proposed_notional=100.0, portfolio=pf,
                      prices={"AAPL": 100.0})
    assert res.approved is True
    assert res.approved_notional == 100.0


def test_per_position_cap_resizes_down():
    pf = Portfolio(1000.0)
    res = _rm().check(_buy(), proposed_notional=300.0, portfolio=pf,
                      prices={"AAPL": 100.0})
    assert res.approved is True
    assert res.approved_notional == 200.0


def test_total_exposure_cap_resizes_down():
    pf = Portfolio(1000.0)
    pf.apply_fill("MSFT", OrderSide.BUY, qty=7.0, price=100.0)
    res = _rm().check(_buy("AAPL"), proposed_notional=200.0, portfolio=pf,
                      prices={"AAPL": 100.0, "MSFT": 100.0})
    assert res.approved is True
    assert res.approved_notional == 100.0


def test_max_positions_vetoes_new_symbol():
    pf = Portfolio(10000.0)
    for sym in ["A", "B", "C", "D", "E"]:
        pf.apply_fill(sym, OrderSide.BUY, qty=1.0, price=100.0)
    res = _rm().check(_buy("AAPL"), proposed_notional=100.0, portfolio=pf,
                      prices={"A": 100, "B": 100, "C": 100, "D": 100,
                              "E": 100, "AAPL": 100})
    assert res.approved is False


def test_sell_passes_through():
    pf = Portfolio(1000.0)
    d = Decision("AAPL", Action.SELL, -1.0, True, "r", [])
    res = _rm().check(d, proposed_notional=999.0, portfolio=pf,
                      prices={"AAPL": 100.0})
    assert res.approved is True
    assert res.approved_notional == 999.0


def test_zero_equity_vetoes():
    pf = Portfolio(0.0)
    res = _rm().check(_buy(), proposed_notional=100.0, portfolio=pf,
                      prices={"AAPL": 100.0})
    assert res.approved is False
