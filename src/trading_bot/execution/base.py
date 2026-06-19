from abc import ABC, abstractmethod
from trading_bot.domain.models import Order, Fill


class ExecutionClient(ABC):
    @abstractmethod
    def submit_order(self, order: Order, ref_price: float) -> Fill:
        ...
