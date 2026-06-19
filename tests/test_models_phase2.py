from trading_bot.domain.models import (
    Action, Signal, StrategyVote, Decision, Position, Order,
    OrderSide, OrderStatus, RiskResult,
)


def test_position_market_value_and_pnl():
    p = Position(symbol="AAPL", qty=2.0, avg_cost=100.0)
    assert p.market_value(110.0) == 220.0
    assert p.unrealized_pnl(110.0) == 20.0


def test_order_defaults():
    o = Order(id="1", symbol="AAPL", side=OrderSide.BUY, notional=50.0)
    assert o.status == OrderStatus.PENDING
    assert o.idempotency_key == ""


def test_strategy_vote_and_decision():
    s = Signal("AAPL", Action.BUY, 0.8, "x")
    v = StrategyVote(name="sma", signal=s, weight=1.0)
    d = Decision(symbol="AAPL", action=Action.BUY, net_score=0.8,
                 consensus_met=True, rationale="r", votes=[v])
    assert d.votes[0].name == "sma"


def test_risk_result_defaults():
    r = RiskResult(approved=True, approved_notional=50.0, reason="ok")
    assert r.checks == []
