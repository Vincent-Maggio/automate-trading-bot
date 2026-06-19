from datetime import datetime
from trading_bot.execution.simulated import SimulatedExecutor
from trading_bot.domain.models import Order, OrderSide, OrderStatus


def _now():
    return datetime(2023, 1, 1)


def test_fills_notional_into_qty():
    ex = SimulatedExecutor(now=_now)
    order = Order(id="1", symbol="AAPL", side=OrderSide.BUY, notional=100.0)
    fill = ex.submit_order(order, ref_price=50.0)
    assert fill.qty == 2.0
    assert fill.price == 50.0
    assert order.status == OrderStatus.FILLED


def test_idempotent_repeat_returns_same_fill():
    ex = SimulatedExecutor(now=_now)
    o1 = Order(id="1", symbol="AAPL", side=OrderSide.BUY, notional=100.0,
               idempotency_key="k1")
    o2 = Order(id="2", symbol="AAPL", side=OrderSide.BUY, notional=100.0,
               idempotency_key="k1")
    f1 = ex.submit_order(o1, ref_price=50.0)
    f2 = ex.submit_order(o2, ref_price=50.0)
    assert f1 is f2
