from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Signal:
    symbol: str
    action: Action
    confidence: float
    rationale: str

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0,1], got {self.confidence}")


@dataclass(frozen=True)
class Trade:
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    qty: float

    @property
    def pnl(self) -> float:
        return (self.exit_price - self.entry_price) * self.qty


@dataclass
class BacktestResult:
    equity_curve: list = field(default_factory=list)
    trades: list = field(default_factory=list)
    starting_cash: float = 0.0
    ending_equity: float = 0.0
