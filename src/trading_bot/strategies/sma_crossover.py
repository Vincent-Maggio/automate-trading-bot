from trading_bot.domain.models import Action, Signal
from trading_bot.strategies.base import Strategy


def _sma(values: list, n: int) -> float:
    return sum(values[-n:]) / n


class SmaCrossover(Strategy):
    def __init__(self, fast: int, slow: int):
        if fast >= slow:
            raise ValueError("fast period must be < slow period")
        self.fast = fast
        self.slow = slow

    def generate_signal(self, symbol: str, history: list) -> Signal:
        if len(history) < self.slow + 1:
            return Signal(symbol, Action.HOLD, 0.0, "insufficient history")
        closes = [b.close for b in history]
        fast_now = _sma(closes, self.fast)
        slow_now = _sma(closes, self.slow)
        fast_prev = _sma(closes[:-1], self.fast)
        slow_prev = _sma(closes[:-1], self.slow)
        conf = min(1.0, abs(fast_now - slow_now) / slow_now) if slow_now else 0.0
        crossed_up = fast_prev <= slow_prev and fast_now > slow_now
        crossed_down = fast_prev >= slow_prev and fast_now < slow_now
        if crossed_up:
            return Signal(symbol, Action.BUY, conf, "fast SMA crossed above slow")
        if crossed_down:
            return Signal(symbol, Action.SELL, conf, "fast SMA crossed below slow")
        return Signal(symbol, Action.HOLD, conf, "no cross")
