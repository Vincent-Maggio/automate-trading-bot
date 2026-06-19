from datetime import datetime
from trading_bot.domain.models import Fill, OrderStatus
from trading_bot.execution.base import ExecutionClient


class SimulatedExecutor(ExecutionClient):
    def __init__(self, now=None):
        self._now = now or datetime.utcnow
        self._fills_by_key: dict = {}

    def submit_order(self, order, ref_price: float) -> Fill:
        key = order.idempotency_key
        if key and key in self._fills_by_key:
            return self._fills_by_key[key]
        qty = order.notional / ref_price
        fill = Fill(order_id=order.id, symbol=order.symbol, side=order.side,
                    qty=qty, price=ref_price, timestamp=self._now())
        order.status = OrderStatus.FILLED
        if key:
            self._fills_by_key[key] = fill
        return fill
