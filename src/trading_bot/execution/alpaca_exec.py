from datetime import datetime, timezone
from trading_bot.domain.models import Fill, OrderSide, OrderStatus
from trading_bot.execution.base import ExecutionClient


class AlpacaPaperExecutor(ExecutionClient):
    def __init__(self, api_key: str, secret_key: str, _client=None, paper: bool = True):
        self.paper = paper
        if _client is not None:
            self._client = _client
        else:
            from alpaca.trading.client import TradingClient
            self._client = TradingClient(api_key, secret_key, paper=paper)

    def submit_order(self, order, ref_price: float) -> Fill:
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide as AlpacaSide, TimeInForce
        side = AlpacaSide.BUY if order.side == OrderSide.BUY else AlpacaSide.SELL
        req = MarketOrderRequest(
            symbol=order.symbol, notional=order.notional,
            side=side, time_in_force=TimeInForce.DAY,
        )
        resp = self._client.submit_order(req)
        filled_qty = float(resp.filled_qty) if getattr(resp, "filled_qty", None) else 0.0
        if filled_qty > 0:
            price = float(resp.filled_avg_price)
            order.status = OrderStatus.FILLED
        else:
            price = ref_price
            filled_qty = order.notional / ref_price
            order.status = OrderStatus.PENDING
        return Fill(order_id=str(getattr(resp, "id", order.id)),
                    symbol=order.symbol, side=order.side, qty=filled_qty,
                    price=price, timestamp=datetime.now(timezone.utc))
