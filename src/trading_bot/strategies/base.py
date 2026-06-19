from abc import ABC, abstractmethod
from trading_bot.domain.models import Bar, Signal


class Strategy(ABC):
    @abstractmethod
    def generate_signal(self, symbol: str, history: list) -> Signal:
        ...
