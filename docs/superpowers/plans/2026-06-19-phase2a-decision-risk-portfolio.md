# Phase 2a: Decision + Risk + Portfolio (pure logic) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the safety-critical core of the live trading pipeline — portfolio accounting, the weighted-vote-plus-consensus decision layer, the risk module with final veto/resize authority, stop-loss/take-profit exits, and the kill switch + circuit breaker — as pure, deterministic, broker-free logic with exhaustive unit tests.

**Architecture:** All components here are pure functions/classes operating on in-memory state and explicit price dicts. No network, no broker, no clock dependence (time is passed in). This is the layer the spec says to test hardest. Phase 2b wires these to real strategies, the Alpaca paper broker, an orchestrator, and audit persistence.

**Tech Stack:** Python 3.10+ (sandbox runs 3.10; no 3.11-only syntax), stdlib only, `pytest`. Builds on Phase 1's `trading_bot.domain.models`.

## Global Constraints

- Python 3.10+ (sandbox is 3.10.12; do not use `match`-only or 3.11+ features).
- No secrets in code; nothing here touches credentials or network.
- No financial parameter hardcoded — risk/decision parameters are passed in from config.
- Capital preservation outranks returns: the risk module has FINAL authority and can only ever reduce or veto exposure, never increase it.
- Run pytest with Linux-local temp to avoid the mounted-FS recursion bug:
  `PYTHONPATH=src python -m pytest -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
- Sizing is by dollar **notional** (fractional shares), consistent with the $500 account.
- Every task ends with a commit (Conventional Commits style). Commits are run on the user's Windows machine (the sandbox mount cannot host git); the implementer stages the listed files and the user commits, OR commits are made wherever git is available. Do not block a task on the commit step if git is unavailable — record it as pending.

---

## File Structure

```
src/trading_bot/
├── domain/
│   └── models.py            # MODIFY: add Decision, StrategyVote, Position, Order,
│                            #         OrderSide, OrderStatus, RiskResult
├── portfolio/
│   ├── __init__.py          # NEW
│   └── portfolio.py         # NEW: Portfolio (cash, positions, fills, P&L, exposure)
├── decision/
│   ├── __init__.py          # NEW
│   └── aggregator.py        # NEW: aggregate() weighted vote + consensus gate
├── risk/
│   ├── __init__.py          # NEW
│   ├── risk_manager.py      # NEW: RiskManager.check() veto/resize
│   ├── exits.py             # NEW: evaluate_exits() stop-loss / take-profit
│   └── safety.py            # NEW: SafetyState (kill switch + circuit breaker)
tests/
├── test_portfolio.py
├── test_decision_aggregator.py
├── test_risk_manager.py
├── test_exits.py
└── test_safety.py
```

---

### Task 1: Extend domain models

**Files:**
- Modify: `src/trading_bot/domain/models.py` (append new types; do not change existing ones)
- Test: `tests/test_models_phase2.py` (Create)

**Interfaces:**
- Consumes: existing `Action`, `Signal` from Phase 1.
- Produces:
  - `class OrderSide(str, Enum)`: `BUY = "BUY"`, `SELL = "SELL"`.
  - `class OrderStatus(str, Enum)`: `PENDING`, `FILLED`, `REJECTED`, `CANCELED`.
  - `@dataclass(frozen=True) StrategyVote`: `name: str`, `signal: Signal`, `weight: float`.
  - `@dataclass Decision`: `symbol: str`, `action: Action`, `net_score: float`, `consensus_met: bool`, `rationale: str`, `votes: list` (of `StrategyVote`), default `votes=[]`.
  - `@dataclass(frozen=True) Position`: `symbol: str`, `qty: float`, `avg_cost: float`. Methods: `market_value(price: float) -> float` = `qty * price`; `unrealized_pnl(price: float) -> float` = `(price - avg_cost) * qty`.
  - `@dataclass Order`: `id: str`, `symbol: str`, `side: OrderSide`, `notional: float`, `status: OrderStatus = OrderStatus.PENDING`, `idempotency_key: str = ""`.
  - `@dataclass RiskResult`: `approved: bool`, `approved_notional: float`, `reason: str`, `checks: list` (of `tuple[str, bool, str]`), default `checks=[]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models_phase2.py
from trading_bot.domain.models import (
    Action, Signal, StrategyVote, Decision, Position, Order,
    OrderSide, OrderStatus, RiskResult,
)


def test_position_market_value_and_pnl():
    p = Position(symbol="AAPL", qty=2.0, avg_cost=100.0)
    assert p.market_value(110.0) == 220.0
    assert p.unrealized_pnl(110.0) == 20.0


def test_order_defaults():
    o = Order(id="1", symbol="AAPL", side=OrderSide.BUY, notional=50.0)
    assert o.status == OrderStatus.PENDING
    assert o.idempotency_key == ""


def test_strategy_vote_and_decision():
    s = Signal("AAPL", Action.BUY, 0.8, "x")
    v = StrategyVote(name="sma", signal=s, weight=1.0)
    d = Decision(symbol="AAPL", action=Action.BUY, net_score=0.8,
                 consensus_met=True, rationale="r", votes=[v])
    assert d.votes[0].name == "sma"


def test_risk_result_defaults():
    r = RiskResult(approved=True, approved_notional=50.0, reason="ok")
    assert r.checks == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_models_phase2.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ImportError: cannot import name 'StrategyVote'`

- [ ] **Step 3: Append implementation to `models.py`**

```python
# --- Phase 2 additions (append to src/trading_bot/domain/models.py) ---


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
```

Note: `field` and `Enum` are already imported at the top of `models.py` from Phase 1. Verify the import line reads `from dataclasses import dataclass, field` — it does.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_models_phase2.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/domain/models.py tests/test_models_phase2.py
git commit -m "feat: domain models for decision, risk, portfolio"
```

---

### Task 2: Portfolio state manager

**Files:**
- Create: `src/trading_bot/portfolio/__init__.py`, `src/trading_bot/portfolio/portfolio.py`, `tests/test_portfolio.py`

**Interfaces:**
- Consumes: `Position`, `OrderSide` (Task 1).
- Produces: `class Portfolio`:
  - `__init__(self, starting_cash: float)` — sets `self.cash`, `self.positions: dict[str, Position] = {}`, `self.realized_pnl = 0.0`.
  - `apply_fill(self, symbol: str, side: OrderSide, qty: float, price: float) -> None` — BUY: decreases cash by `qty*price`, increases/creates position with weighted-average cost. SELL: increases cash by `qty*price`, decreases position qty, adds `(price - avg_cost) * qty` to `realized_pnl`; removes the position if qty hits ~0. Selling more than held raises `ValueError`.
  - `market_value(self, prices: dict) -> float` — sum of `position.market_value(prices[symbol])` over held positions.
  - `total_equity(self, prices: dict) -> float` — `cash + market_value(prices)`.
  - `exposure(self, prices: dict) -> float` — `market_value(prices) / total_equity(prices)`; `0.0` if equity ≤ 0.
  - `position_value(self, symbol: str, price: float) -> float` — `0.0` if not held.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_portfolio.py
import pytest
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.domain.models import OrderSide


def test_buy_then_value_and_exposure():
    pf = Portfolio(starting_cash=1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=5.0, price=100.0)
    assert pf.cash == 500.0
    assert pf.market_value({"AAPL": 100.0}) == 500.0
    assert pf.total_equity({"AAPL": 100.0}) == 1000.0
    assert pf.exposure({"AAPL": 100.0}) == 0.5


def test_weighted_average_cost():
    pf = Portfolio(starting_cash=1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=1.0, price=100.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=1.0, price=200.0)
    assert pf.positions["AAPL"].qty == 2.0
    assert pf.positions["AAPL"].avg_cost == 150.0


def test_sell_realizes_pnl_and_closes():
    pf = Portfolio(starting_cash=1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=2.0, price=100.0)
    pf.apply_fill("AAPL", OrderSide.SELL, qty=2.0, price=120.0)
    assert pf.realized_pnl == 40.0
    assert "AAPL" not in pf.positions
    assert pf.cash == 1000.0 - 200.0 + 240.0


def test_oversell_raises():
    pf = Portfolio(starting_cash=1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=1.0, price=100.0)
    with pytest.raises(ValueError):
        pf.apply_fill("AAPL", OrderSide.SELL, qty=2.0, price=100.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_portfolio.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.portfolio.portfolio'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/portfolio/portfolio.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_portfolio.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (4 passed)

- [ ] **Step 5: Create `src/trading_bot/portfolio/__init__.py`** (empty file)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/portfolio tests/test_portfolio.py
git commit -m "feat: portfolio state manager with cost basis and P&L"
```

---

### Task 3: Decision layer (weighted vote + consensus gate)

**Files:**
- Create: `src/trading_bot/decision/__init__.py`, `src/trading_bot/decision/aggregator.py`, `tests/test_decision_aggregator.py`

**Interfaces:**
- Consumes: `Action`, `Signal`, `StrategyVote`, `Decision` (Task 1).
- Produces: `aggregate(votes: list[StrategyVote], threshold: float, min_consensus: int) -> Decision`:
  - Direction value per vote: `BUY = +1`, `SELL = -1`, `HOLD = 0`.
  - `net_score = sum(weight * confidence * direction)` across votes.
  - Net direction: `BUY` if `net_score > 0`, `SELL` if `net_score < 0`, else `HOLD`.
  - `agree_count` = number of votes whose signal direction matches the net direction (non-HOLD).
  - `consensus_met = agree_count >= min_consensus`.
  - Final `action`: the net direction **only if** `abs(net_score) >= threshold` AND `consensus_met`; otherwise `HOLD`.
  - `symbol` taken from `votes[0].signal.symbol`; empty `votes` raises `ValueError`.
  - `rationale` summarizes net_score, threshold, agree_count, min_consensus.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_decision_aggregator.py
import pytest
from trading_bot.domain.models import Action, Signal, StrategyVote
from trading_bot.decision.aggregator import aggregate


def _vote(name, action, conf, weight=1.0):
    return StrategyVote(name, Signal("AAPL", action, conf, "r"), weight)


def test_unanimous_buy_passes_gate():
    votes = [_vote("a", Action.BUY, 0.9), _vote("b", Action.BUY, 0.8)]
    d = aggregate(votes, threshold=0.5, min_consensus=2)
    assert d.action == Action.BUY
    assert d.consensus_met is True


def test_buy_blocked_by_consensus_gate():
    # net leans BUY but only one strategy agrees; min_consensus=2
    votes = [_vote("a", Action.BUY, 0.9), _vote("b", Action.HOLD, 0.0)]
    d = aggregate(votes, threshold=0.1, min_consensus=2)
    assert d.action == Action.HOLD
    assert d.consensus_met is False


def test_buy_blocked_by_threshold():
    votes = [_vote("a", Action.BUY, 0.2), _vote("b", Action.BUY, 0.1)]
    d = aggregate(votes, threshold=0.5, min_consensus=2)
    assert d.action == Action.HOLD  # net_score 0.3 < 0.5


def test_conflict_nets_to_direction():
    votes = [_vote("a", Action.BUY, 0.9), _vote("b", Action.SELL, 0.2)]
    d = aggregate(votes, threshold=0.5, min_consensus=1)
    assert d.action == Action.BUY
    assert d.net_score == pytest.approx(0.7)


def test_empty_votes_raises():
    with pytest.raises(ValueError):
        aggregate([], threshold=0.5, min_consensus=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_decision_aggregator.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.decision.aggregator'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/decision/aggregator.py
from trading_bot.domain.models import Action, Decision

_DIR = {Action.BUY: 1, Action.SELL: -1, Action.HOLD: 0}


def aggregate(votes: list, threshold: float, min_consensus: int) -> Decision:
    if not votes:
        raise ValueError("aggregate requires at least one vote")
    symbol = votes[0].signal.symbol

    net_score = sum(v.weight * v.signal.confidence * _DIR[v.signal.action]
                    for v in votes)

    if net_score > 0:
        net_dir = Action.BUY
    elif net_score < 0:
        net_dir = Action.SELL
    else:
        net_dir = Action.HOLD

    agree_count = sum(1 for v in votes if v.signal.action == net_dir
                      and net_dir != Action.HOLD)
    consensus_met = agree_count >= min_consensus

    if net_dir != Action.HOLD and abs(net_score) >= threshold and consensus_met:
        action = net_dir
    else:
        action = Action.HOLD

    rationale = (
        f"net_score={net_score:.3f} (threshold={threshold}), "
        f"agree={agree_count}/{min_consensus} -> {action.value}"
    )
    return Decision(symbol=symbol, action=action, net_score=net_score,
                    consensus_met=consensus_met, rationale=rationale,
                    votes=list(votes))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_decision_aggregator.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (5 passed)

- [ ] **Step 5: Create `src/trading_bot/decision/__init__.py`** (empty file)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/decision tests/test_decision_aggregator.py
git commit -m "feat: weighted-vote + consensus-gate decision layer"
```

---

### Task 4: Risk module (veto / resize, final authority)

**Files:**
- Create: `src/trading_bot/risk/__init__.py`, `src/trading_bot/risk/risk_manager.py`, `tests/test_risk_manager.py`

**Interfaces:**
- Consumes: `Action`, `Decision`, `RiskResult` (Task 1), `Portfolio` (Task 2).
- Produces: `class RiskManager`:
  - `__init__(self, max_position_pct: float, max_total_exposure_pct: float, max_positions: int, min_order_notional: float = 1.0)`.
  - `check(self, decision: Decision, proposed_notional: float, portfolio: Portfolio, prices: dict) -> RiskResult`.
  - Rules (apply only to `Action.BUY` entries; `SELL`/`HOLD` are not entries and return approved with the proposed notional unchanged — exits reduce risk and are allowed):
    1. **Per-position cap:** approved notional ≤ `max_position_pct * equity` (counting existing value of that symbol). Resize down if needed.
    2. **Total-exposure cap:** `current_market_value + approved_notional ≤ max_total_exposure_pct * equity`. Resize down if needed.
    3. **Max positions:** if the symbol is not already held and `len(positions) >= max_positions`, veto.
    4. **Min notional:** if the resized notional `< min_order_notional`, veto (not worth trading).
  - `equity = portfolio.total_equity(prices)`. If equity ≤ 0, veto.
  - Each rule appends a `(name, passed, detail)` tuple to `checks`. `approved=False` sets `approved_notional=0.0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_risk_manager.py
from trading_bot.risk.risk_manager import RiskManager
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.domain.models import Action, Decision


def _buy(symbol="AAPL"):
    return Decision(symbol=symbol, action=Action.BUY, net_score=1.0,
                    consensus_met=True, rationale="r", votes=[])


def _rm():
    return RiskManager(max_position_pct=0.20, max_total_exposure_pct=0.80,
                       max_positions=5, min_order_notional=1.0)


def test_within_caps_approved_unchanged():
    pf = Portfolio(1000.0)
    res = _rm().check(_buy(), proposed_notional=100.0, portfolio=pf,
                      prices={"AAPL": 100.0})
    assert res.approved is True
    assert res.approved_notional == 100.0


def test_per_position_cap_resizes_down():
    pf = Portfolio(1000.0)
    # 20% of 1000 = 200 cap; ask for 300 -> resized to 200
    res = _rm().check(_buy(), proposed_notional=300.0, portfolio=pf,
                      prices={"AAPL": 100.0})
    assert res.approved is True
    assert res.approved_notional == 200.0


def test_total_exposure_cap_resizes_down():
    pf = Portfolio(1000.0)
    # already holding 700 of MSFT; exposure cap 80% of 1000 = 800; only 100 headroom
    pf.apply_fill("MSFT", __import__("trading_bot.domain.models",
                  fromlist=["OrderSide"]).OrderSide.BUY, qty=7.0, price=100.0)
    res = _rm().check(_buy("AAPL"), proposed_notional=200.0, portfolio=pf,
                      prices={"AAPL": 100.0, "MSFT": 100.0})
    # per-position cap on AAPL = 20% of equity(1000) = 200; exposure headroom = 100
    assert res.approved is True
    assert res.approved_notional == 100.0


def test_max_positions_vetoes_new_symbol():
    pf = Portfolio(10000.0)
    from trading_bot.domain.models import OrderSide
    for i, sym in enumerate(["A", "B", "C", "D", "E"]):
        pf.apply_fill(sym, OrderSide.BUY, qty=1.0, price=100.0)
    res = _rm().check(_buy("AAPL"), proposed_notional=100.0, portfolio=pf,
                      prices={"A": 100, "B": 100, "C": 100, "D": 100,
                              "E": 100, "AAPL": 100})
    assert res.approved is False


def test_sell_passes_through():
    pf = Portfolio(1000.0)
    d = Decision("AAPL", Action.SELL, -1.0, True, "r", [])
    res = _rm().check(d, proposed_notional=999.0, portfolio=pf,
                      prices={"AAPL": 100.0})
    assert res.approved is True
    assert res.approved_notional == 999.0


def test_zero_equity_vetoes():
    pf = Portfolio(0.0)
    res = _rm().check(_buy(), proposed_notional=100.0, portfolio=pf,
                      prices={"AAPL": 100.0})
    assert res.approved is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_risk_manager.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.risk.risk_manager'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/risk/risk_manager.py
from trading_bot.domain.models import Action, RiskResult


class RiskManager:
    def __init__(self, max_position_pct: float, max_total_exposure_pct: float,
                 max_positions: int, min_order_notional: float = 1.0):
        self.max_position_pct = max_position_pct
        self.max_total_exposure_pct = max_total_exposure_pct
        self.max_positions = max_positions
        self.min_order_notional = min_order_notional

    def check(self, decision, proposed_notional: float, portfolio, prices: dict):
        checks = []

        if decision.action != Action.BUY:
            checks.append(("entry_only", True, f"{decision.action.value} not an entry"))
            return RiskResult(True, proposed_notional, "non-entry approved", checks)

        equity = portfolio.total_equity(prices)
        if equity <= 0:
            checks.append(("equity_positive", False, f"equity={equity}"))
            return RiskResult(False, 0.0, "no equity", checks)

        symbol = decision.symbol
        notional = proposed_notional

        # Rule 1: per-position cap (includes existing holding of this symbol)
        price = prices[symbol]
        existing_val = portfolio.position_value(symbol, price)
        pos_cap = self.max_position_pct * equity
        allowed_add = pos_cap - existing_val
        if allowed_add < notional:
            checks.append(("per_position_cap", allowed_add >= notional,
                           f"cap={pos_cap:.2f} existing={existing_val:.2f} "
                           f"allowed_add={allowed_add:.2f}"))
            notional = max(0.0, allowed_add)
        else:
            checks.append(("per_position_cap", True, f"cap={pos_cap:.2f}"))

        # Rule 2: total exposure cap
        mv = portfolio.market_value(prices)
        exp_cap = self.max_total_exposure_pct * equity
        exp_headroom = exp_cap - mv
        if exp_headroom < notional:
            checks.append(("total_exposure_cap", False,
                           f"cap={exp_cap:.2f} mv={mv:.2f} headroom={exp_headroom:.2f}"))
            notional = max(0.0, exp_headroom)
        else:
            checks.append(("total_exposure_cap", True, f"cap={exp_cap:.2f}"))

        # Rule 3: max positions (new symbol only)
        if symbol not in portfolio.positions and len(portfolio.positions) >= self.max_positions:
            checks.append(("max_positions", False,
                           f"have {len(portfolio.positions)} >= {self.max_positions}"))
            return RiskResult(False, 0.0, "max positions reached", checks)
        checks.append(("max_positions", True, f"{len(portfolio.positions)}"))

        # Rule 4: min notional
        if notional < self.min_order_notional:
            checks.append(("min_notional", False,
                           f"{notional:.2f} < {self.min_order_notional}"))
            return RiskResult(False, 0.0, "below min notional after resize", checks)
        checks.append(("min_notional", True, f"{notional:.2f}"))

        reason = "approved" if notional == proposed_notional else "approved (resized)"
        return RiskResult(True, notional, reason, checks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_risk_manager.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (6 passed)

- [ ] **Step 5: Create `src/trading_bot/risk/__init__.py`** (empty file)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/risk/__init__.py src/trading_bot/risk/risk_manager.py tests/test_risk_manager.py
git commit -m "feat: risk module with veto and resize authority"
```

---

### Task 5: Stop-loss / take-profit exits

**Files:**
- Create: `src/trading_bot/risk/exits.py`, `tests/test_exits.py`

**Interfaces:**
- Consumes: `Action`, `Decision` (Task 1), `Portfolio` (Task 2).
- Produces: `evaluate_exits(portfolio, prices: dict, stop_loss_pct: float, take_profit_pct: float) -> list[Decision]`:
  - For each held position, compute return `r = (price - avg_cost) / avg_cost`.
  - If `r <= -stop_loss_pct`: emit a full `SELL` `Decision` with rationale `"stop-loss"`.
  - Else if `r >= take_profit_pct`: emit a full `SELL` `Decision` with rationale `"take-profit"`.
  - `stop_loss_pct` and `take_profit_pct` are positive fractions (e.g. 0.05 = 5%).
  - Returns a list (possibly empty), ordered by symbol for determinism.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_exits.py
from trading_bot.risk.exits import evaluate_exits
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.domain.models import Action, OrderSide


def _pf():
    pf = Portfolio(1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=1.0, price=100.0)
    return pf


def test_stop_loss_triggers_sell():
    pf = _pf()
    exits = evaluate_exits(pf, {"AAPL": 94.0}, stop_loss_pct=0.05, take_profit_pct=0.10)
    assert len(exits) == 1
    assert exits[0].action == Action.SELL
    assert "stop-loss" in exits[0].rationale


def test_take_profit_triggers_sell():
    pf = _pf()
    exits = evaluate_exits(pf, {"AAPL": 111.0}, stop_loss_pct=0.05, take_profit_pct=0.10)
    assert len(exits) == 1
    assert exits[0].action == Action.SELL
    assert "take-profit" in exits[0].rationale


def test_inside_band_no_exit():
    pf = _pf()
    exits = evaluate_exits(pf, {"AAPL": 102.0}, stop_loss_pct=0.05, take_profit_pct=0.10)
    assert exits == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_exits.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.risk.exits'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/risk/exits.py
from trading_bot.domain.models import Action, Decision


def evaluate_exits(portfolio, prices: dict, stop_loss_pct: float,
                   take_profit_pct: float) -> list:
    out = []
    for symbol in sorted(portfolio.positions):
        pos = portfolio.positions[symbol]
        if pos.avg_cost <= 0:
            continue
        price = prices[symbol]
        r = (price - pos.avg_cost) / pos.avg_cost
        if r <= -stop_loss_pct:
            out.append(Decision(symbol, Action.SELL, -1.0, True,
                                f"stop-loss ({r:.2%})", []))
        elif r >= take_profit_pct:
            out.append(Decision(symbol, Action.SELL, -1.0, True,
                                f"take-profit ({r:.2%})", []))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_exits.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/risk/exits.py tests/test_exits.py
git commit -m "feat: stop-loss and take-profit exit evaluation"
```

---

### Task 6: Kill switch + circuit breaker

**Files:**
- Create: `src/trading_bot/risk/safety.py`, `tests/test_safety.py`

**Interfaces:**
- Consumes: nothing (pure state).
- Produces: `class SafetyState`:
  - `__init__(self, max_daily_loss_pct: float)` — `self.max_daily_loss_pct`, `self.killed = False`, `self.tripped = False`, `self.day_start_equity = None`.
  - `start_day(self, equity: float) -> None` — sets `day_start_equity = equity`, clears `tripped` (does NOT clear `killed`; a manual kill persists until reset).
  - `kill(self) -> None` — sets `killed = True`.
  - `reset_kill(self) -> None` — sets `killed = False`.
  - `update(self, equity: float) -> bool` — if `day_start_equity` is set and `(equity - day_start_equity) / day_start_equity <= -max_daily_loss_pct`, set `tripped = True`. Returns current `tripped`.
  - `can_trade(self) -> bool` — `not self.killed and not self.tripped`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_safety.py
from trading_bot.risk.safety import SafetyState


def test_kill_switch_blocks_trading():
    s = SafetyState(max_daily_loss_pct=0.03)
    assert s.can_trade() is True
    s.kill()
    assert s.can_trade() is False
    s.reset_kill()
    assert s.can_trade() is True


def test_circuit_breaker_within_band_does_not_trip():
    s = SafetyState(max_daily_loss_pct=0.03)
    s.start_day(1000.0)
    assert s.update(980.0) is False   # -2% < 3% threshold
    assert s.can_trade() is True


def test_circuit_breaker_trips_past_threshold():
    s = SafetyState(max_daily_loss_pct=0.03)
    s.start_day(1000.0)
    assert s.update(965.0) is True    # -3.5% breaches 3%
    assert s.can_trade() is False


def test_start_day_clears_trip_but_not_kill():
    s = SafetyState(max_daily_loss_pct=0.03)
    s.start_day(1000.0)
    s.update(900.0)        # trips
    s.kill()
    s.start_day(1000.0)    # new day clears trip
    assert s.tripped is False
    assert s.can_trade() is False  # still killed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_safety.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.risk.safety'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/risk/safety.py
class SafetyState:
    def __init__(self, max_daily_loss_pct: float):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.killed = False
        self.tripped = False
        self.day_start_equity = None

    def start_day(self, equity: float) -> None:
        self.day_start_equity = equity
        self.tripped = False

    def kill(self) -> None:
        self.killed = True

    def reset_kill(self) -> None:
        self.killed = False

    def update(self, equity: float) -> bool:
        if self.day_start_equity:
            change = (equity - self.day_start_equity) / self.day_start_equity
            if change <= -self.max_daily_loss_pct:
                self.tripped = True
        return self.tripped

    def can_trade(self) -> bool:
        return not self.killed and not self.tripped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_safety.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the FULL suite (Phase 1 + 2a) to confirm no regressions**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (all Phase 1 tests + all Phase 2a tests).

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/risk/safety.py tests/test_safety.py
git commit -m "feat: kill switch and daily-loss circuit breaker"
```

---

## Self-Review (completed by plan author)

**Spec coverage (Phase 2a scope):**
- Decision/aggregation layer — weighted vote + consensus gate, configurable threshold + min_consensus, recorded rationale and votes (Task 3). ✓
- Risk management module with final veto/resize authority — per-position cap, total-exposure cap, max positions, min notional; only ever reduces exposure; exits pass through (Task 4). ✓
- Stop-loss + take-profit exit logic (Task 5). ✓
- Portfolio state manager — cash, positions, cost basis, realized P&L, exposure (Task 2). ✓
- Kill switch + circuit breaker, wired as first-class state (Task 6). ✓
- Deferred to Phase 2b: the RSI and momentum strategies, Alpaca paper execution layer, cycle orchestrator that calls data→strategies→aggregate→risk→safety→execution, and SQLite audit persistence of signals/decisions/risk_checks/orders/fills. (Decision/RiskResult/Order models created here so 2b can persist them.)

**Placeholder scan:** No TBD/TODO. Every code step contains complete, runnable code.

**Type consistency:** `Action`/`Signal` reused from Phase 1 unchanged. `Decision`, `StrategyVote`, `Position`, `Order`, `OrderSide`, `OrderStatus`, `RiskResult` defined in Task 1 and used with identical signatures in Tasks 2–6. `Portfolio.total_equity/market_value/position_value/positions` defined in Task 2 and consumed by Tasks 4–5 exactly as named. `aggregate(votes, threshold, min_consensus)` and `RiskManager.check(decision, proposed_notional, portfolio, prices)` signatures are consistent between definition and test usage.
