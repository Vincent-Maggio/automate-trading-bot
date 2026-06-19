from types import SimpleNamespace
from trading_bot.execution.alpaca_exec import AlpacaPaperExecutor
from trading_bot.domain.models import Order, OrderSide, OrderStatus


class _FakeTradingClient:
    def __init__(self):
        self.last_request = None

    def submit_order(self, order_data):
        self.last_request = order_data
        return SimpleNamespace(id="srv-1", filled_avg_price="50.0", filled_qty="2")


def test_submit_returns_fill_from_response():
    fake = _FakeTradingClient()
    ex = AlpacaPaperExecutor("k", "s", _client=fake)
    order = Order(id="1", symbol="AAPL", side=OrderSide.BUY, notional=100.0)
    fill = ex.submit_order(order, ref_price=49.0)
    assert fill.qty == 2.0
    assert fill.price == 50.0
    assert order.status == OrderStatus.FILLED
    assert fake.last_request is not None
