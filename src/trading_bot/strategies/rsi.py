from trading_bot.domain.models import Action, Signal
from trading_bot.strategies.base import Strategy


class RsiMeanReversion(Strategy):
    def __init__(self, period: int = 14, oversold: float = 30.0,
                 overbought: float = 70.0):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def _rsi(self, closes: list) -> float:
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        window = deltas[-self.period:]
        gains = [d for d in window if d > 0]
        losses = [-d for d in window if d < 0]
        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        if avg_gain == 0:
            return 0.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def generate_signal(self, symbol: str, history: list) -> Signal:
        if len(history) < self.period + 1:
            return Signal(symbol, Action.HOLD, 0.0, "insufficient history")
        rsi = self._rsi([b.close for b in history])
        if rsi < self.oversold:
            conf = min(1.0, (self.oversold - rsi) / self.oversold)
            return Signal(symbol, Action.BUY, conf, f"RSI {rsi:.1f} < {self.oversold}")
        if rsi > self.overbought:
            conf = min(1.0, (rsi - self.overbought) / (100.0 - self.overbought))
            return Signal(symbol, Action.SELL, conf, f"RSI {rsi:.1f} > {self.overbought}")
        return Signal(symbol, Action.HOLD, 0.0, f"RSI {rsi:.1f} neutral")
