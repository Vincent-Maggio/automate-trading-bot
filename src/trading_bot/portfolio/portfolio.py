from trading_bot.domain.models import Position, OrderSide

_EPS = 1e-9


class Portfolio:
    def __init__(self, starting_cash: float):
        self.cash = starting_cash
        self.positions: dict = {}
        self.realized_pnl = 0.0

    def apply_fill(self, symbol: str, side: OrderSide, qty: float, price: float) -> None:
        if side == OrderSide.BUY:
            self.cash -= qty * price
            existing = self.positions.get(symbol)
            if existing is None:
                self.positions[symbol] = Position(symbol, qty, price)
            else:
                total_qty = existing.qty + qty
                avg = (existing.avg_cost * existing.qty + price * qty) / total_qty
                self.positions[symbol] = Position(symbol, total_qty, avg)
        else:  # SELL
            existing = self.positions.get(symbol)
            held = existing.qty if existing else 0.0
            if qty > held + _EPS:
                raise ValueError(f"cannot sell {qty} of {symbol}; hold {held}")
            self.cash += qty * price
            self.realized_pnl += (price - existing.avg_cost) * qty
            remaining = held - qty
            if remaining <= _EPS:
                del self.positions[symbol]
            else:
                self.positions[symbol] = Position(symbol, remaining, existing.avg_cost)

    def position_value(self, symbol: str, price: float) -> float:
        pos = self.positions.get(symbol)
        return pos.market_value(price) if pos else 0.0

    def market_value(self, prices: dict) -> float:
        return sum(p.market_value(prices[s]) for s, p in self.positions.items())

    def total_equity(self, prices: dict) -> float:
        return self.cash + self.market_value(prices)

    def exposure(self, prices: dict) -> float:
        equity = self.total_equity(prices)
        if equity <= 0:
            return 0.0
        return self.market_value(prices) / equity
