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


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"


@dataclass(frozen=True)
class StrategyVote:
    name: str
    signal: Signal
    weight: float


@dataclass
class Decision:
    symbol: str
    action: Action
    net_score: float
    consensus_met: bool
    rationale: str
    votes: list = field(default_factory=list)


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: float
    avg_cost: float

    def market_value(self, price: float) -> float:
        return self.qty * price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.avg_cost) * self.qty


@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    notional: float
    status: OrderStatus = OrderStatus.PENDING
    idempotency_key: str = ""


@dataclass
class RiskResult:
    approved: bool
    approved_notional: float
    reason: str
    checks: list = field(default_factory=list)


@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    side: OrderSide
    qty: float
    price: float
    timestamp: datetime

    @property
    def notional(self) -> float:
        return self.qty * self.price
