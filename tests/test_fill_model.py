from datetime import datetime
from trading_bot.domain.models import Fill, OrderSide


def test_fill_notional():
    f = Fill(order_id="o1", symbol="AAPL", side=OrderSide.BUY,
             qty=2.0, price=50.0, timestamp=datetime(2023, 1, 1))
    assert f.notional == 100.0
