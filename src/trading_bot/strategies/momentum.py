from trading_bot.domain.models import Action, Signal
from trading_bot.strategies.base import Strategy


class MomentumBreakout(Strategy):
    def __init__(self, lookback: int = 20):
        self.lookback = lookback

    def generate_signal(self, symbol: str, history: list) -> Signal:
        if len(history) < self.lookback + 1:
            return Signal(symbol, Action.HOLD, 0.0, "insufficient history")
        prior = [b.close for b in history[-(self.lookback + 1):-1]]
        hi = max(prior)
        lo = min(prior)
        last = history[-1].close
        if last > hi:
            conf = min(1.0, (last - hi) / hi) if hi else 0.0
            return Signal(symbol, Action.BUY, conf, f"breakout {last:.2f}>{hi:.2f}")
        if last < lo:
            conf = min(1.0, (lo - last) / lo) if lo else 0.0
            return Signal(symbol, Action.SELL, conf, f"breakdown {last:.2f}<{lo:.2f}")
        return Signal(symbol, Action.HOLD, 0.0, "inside range")
