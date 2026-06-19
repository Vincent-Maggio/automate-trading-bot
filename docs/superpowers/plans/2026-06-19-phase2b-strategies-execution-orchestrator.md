# Phase 2b: Strategies + Execution + Orchestrator + Audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Phase 2a safety core to real strategies and the Alpaca paper broker — add RSI and momentum strategies, a broker-agnostic execution layer (simulated + Alpaca paper), a SQLite audit log, and a cycle orchestrator that runs one full data→strategies→decision→risk→safety→execution→audit pass.

**Architecture:** The orchestrator (`TradingCycle.run_once`) is the integration point. It reuses Phase 1 (`MarketData`, strategies) and Phase 2a (`aggregate`, `RiskManager`, `evaluate_exits`, `SafetyState`, `Portfolio`) unchanged, depends on an `ExecutionClient` interface (simulated for tests, Alpaca for paper), and writes every signal/decision/risk-check/order/fill/event to an `AuditLog`. One pipeline, swappable execution end.

**Tech Stack:** Python 3.10+, `alpaca-py` (paper trading), stdlib `sqlite3`, `pytest`. Builds on Phases 1 and 2a.

## Global Constraints

- Python 3.10+ (sandbox 3.10.12; no 3.11+ syntax).
- Paper-first: the Alpaca executor MUST use the paper endpoint. Live trading is out of scope for this plan and gated for a later phase behind `LIVE_TRADING=true`.
- No secrets in code; Alpaca keys load from `.env` via Phase 1's `load_secrets`.
- No financial parameter hardcoded — sizing, thresholds, and risk values come from `config.yaml`.
- Risk module and safety gate run on every order; the orchestrator must call them before any execution and must skip a symbol whose decision the risk module vetoes.
- Tests must not hit the network — the Alpaca executor takes an injected client (`_client=`), and orchestrator tests use the simulated executor.
- Run pytest with Linux-local temp: `PYTHONPATH=src python -m pytest -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`.
- **Mount caveat (observed in this environment):** when MODIFYING an existing file, verify the change reached disk (`wc -l <file>`); if a Write/Edit to an existing file doesn't appear, append the addition from the shell instead. New-file writes persist normally. This affects only `models.py` and `config.yaml` edits here.
- Sizing by dollar notional (fractional shares). Commits run where git is available (the user's Windows machine); stage the listed files per task.

---

## File Structure

```
src/trading_bot/
├── domain/
│   └── models.py            # MODIFY: add Fill
├── strategies/
│   ├── rsi.py               # NEW: RsiMeanReversion
│   └── momentum.py          # NEW: MomentumBreakout
├── execution/
│   ├── __init__.py          # NEW
│   ├── base.py              # NEW: ExecutionClient ABC
│   ├── simulated.py         # NEW: SimulatedExecutor (immediate fill at ref price)
│   └── alpaca_exec.py       # NEW: AlpacaPaperExecutor
├── audit/
│   ├── __init__.py          # NEW
│   └── audit_log.py         # NEW: AuditLog (SQLite persistence)
└── engine/
    ├── __init__.py          # NEW
    └── cycle.py             # NEW: TradingCycle.run_once()
scripts/
└── run_paper_cycle.py       # NEW: CLI — one paper cycle from config + .env
tests/
├── test_rsi.py
├── test_momentum.py
├── test_execution_simulated.py
├── test_alpaca_exec.py
├── test_audit_log.py
└── test_cycle.py
```

---

### Task 1: Add `Fill` domain model

**Files:**
- Modify: `src/trading_bot/domain/models.py` (append `Fill`)
- Test: `tests/test_fill_model.py` (Create)

**Interfaces:**
- Consumes: `OrderSide` (Phase 2a).
- Produces: `@dataclass(frozen=True) Fill`: `order_id: str`, `symbol: str`, `side: OrderSide`, `qty: float`, `price: float`, `timestamp: datetime`. Property `notional -> float` = `qty * price`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fill_model.py
from datetime import datetime
from trading_bot.domain.models import Fill, OrderSide


def test_fill_notional():
    f = Fill(order_id="o1", symbol="AAPL", side=OrderSide.BUY,
             qty=2.0, price=50.0, timestamp=datetime(2023, 1, 1))
    assert f.notional == 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_fill_model.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ImportError: cannot import name 'Fill'`

- [ ] **Step 3: Append implementation to `models.py`**

```python
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
```

After saving, verify it reached disk: `grep -n "class Fill" src/trading_bot/domain/models.py` should print a line. If not, append the block from the shell (see Mount caveat).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_fill_model.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/domain/models.py tests/test_fill_model.py
git commit -m "feat: Fill domain model"
```

---

### Task 2: RSI mean-reversion strategy

**Files:**
- Create: `src/trading_bot/strategies/rsi.py`, `tests/test_rsi.py`

**Interfaces:**
- Consumes: `Action`, `Signal`, `Bar` (Phase 1), `Strategy` (Phase 1 base).
- Produces: `class RsiMeanReversion(Strategy)`:
  - `__init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0)`.
  - `generate_signal(self, symbol, history) -> Signal`: needs `len(history) >= period + 1`, else `HOLD` conf 0.0. Compute RSI over the last `period` deltas using Wilder's simple average (mean gain / mean loss). RSI `< oversold` → `BUY`; RSI `> overbought` → `SELL`; else `HOLD`. Confidence = distance past the threshold normalized by the threshold band to `[0,1]` (e.g. BUY conf = `min(1.0, (oversold - rsi) / oversold)`).
  - If average loss is 0 (no down moves), RSI = 100 (→ SELL side). If average gain is 0, RSI = 0 (→ BUY side).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rsi.py
from datetime import datetime, timedelta
from trading_bot.domain.models import Bar, Action
from trading_bot.strategies.rsi import RsiMeanReversion


def _series(closes):
    base = datetime(2023, 1, 1)
    return [Bar("AAPL", base + timedelta(days=i), c, c, c, c, 100)
            for i, c in enumerate(closes)]


def test_hold_when_insufficient_history():
    strat = RsiMeanReversion(period=14)
    sig = strat.generate_signal("AAPL", _series([100, 101, 102]))
    assert sig.action == Action.HOLD
    assert sig.confidence == 0.0


def test_all_down_moves_is_oversold_buy():
    strat = RsiMeanReversion(period=5, oversold=30.0, overbought=70.0)
    sig = strat.generate_signal("AAPL", _series([100, 99, 98, 97, 96, 95]))
    assert sig.action == Action.BUY  # RSI ~ 0


def test_all_up_moves_is_overbought_sell():
    strat = RsiMeanReversion(period=5, oversold=30.0, overbought=70.0)
    sig = strat.generate_signal("AAPL", _series([95, 96, 97, 98, 99, 100]))
    assert sig.action == Action.SELL  # RSI ~ 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_rsi.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.strategies.rsi'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/strategies/rsi.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_rsi.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/strategies/rsi.py tests/test_rsi.py
git commit -m "feat: RSI mean-reversion strategy"
```

---

### Task 3: Momentum / breakout strategy

**Files:**
- Create: `src/trading_bot/strategies/momentum.py`, `tests/test_momentum.py`

**Interfaces:**
- Consumes: `Action`, `Signal`, `Bar`, `Strategy`.
- Produces: `class MomentumBreakout(Strategy)`:
  - `__init__(self, lookback: int = 20)`.
  - `generate_signal(self, symbol, history) -> Signal`: needs `len(history) >= lookback + 1`, else `HOLD` conf 0.0. Let `prior = history[-(lookback+1):-1]` (the `lookback` bars before the latest). `hi = max(close of prior)`, `lo = min(close of prior)`, `last = history[-1].close`. If `last > hi` → `BUY` (breakout up); if `last < lo` → `SELL` (breakdown); else `HOLD`. Confidence = `min(1.0, abs(last - ref) / ref)` where `ref` is `hi` for BUY, `lo` for SELL.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_momentum.py
from datetime import datetime, timedelta
from trading_bot.domain.models import Bar, Action
from trading_bot.strategies.momentum import MomentumBreakout


def _series(closes):
    base = datetime(2023, 1, 1)
    return [Bar("AAPL", base + timedelta(days=i), c, c, c, c, 100)
            for i, c in enumerate(closes)]


def test_hold_when_insufficient_history():
    strat = MomentumBreakout(lookback=20)
    sig = strat.generate_signal("AAPL", _series([100, 101]))
    assert sig.action == Action.HOLD
    assert sig.confidence == 0.0


def test_breakout_up_is_buy():
    strat = MomentumBreakout(lookback=3)
    # prior 3 closes max = 102; last = 105 -> breakout
    sig = strat.generate_signal("AAPL", _series([100, 101, 102, 105]))
    assert sig.action == Action.BUY


def test_breakdown_is_sell():
    strat = MomentumBreakout(lookback=3)
    # prior 3 closes min = 100; last = 97 -> breakdown
    sig = strat.generate_signal("AAPL", _series([102, 101, 100, 97]))
    assert sig.action == Action.SELL


def test_inside_range_is_hold():
    strat = MomentumBreakout(lookback=3)
    sig = strat.generate_signal("AAPL", _series([100, 105, 95, 101]))
    assert sig.action == Action.HOLD
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_momentum.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.strategies.momentum'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/strategies/momentum.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_momentum.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/strategies/momentum.py tests/test_momentum.py
git commit -m "feat: momentum breakout strategy"
```

---

### Task 4: Execution interface + simulated executor

**Files:**
- Create: `src/trading_bot/execution/__init__.py`, `src/trading_bot/execution/base.py`, `src/trading_bot/execution/simulated.py`, `tests/test_execution_simulated.py`

**Interfaces:**
- Consumes: `Order`, `OrderSide`, `OrderStatus`, `Fill` (Tasks 1 + Phase 2a).
- Produces:
  - `class ExecutionClient(ABC)`: `@abstractmethod submit_order(self, order: Order, ref_price: float) -> Fill`.
  - `class SimulatedExecutor(ExecutionClient)`: fills immediately at `ref_price`. `qty = order.notional / ref_price`. Returns a `Fill` and sets `order.status = OrderStatus.FILLED`. Idempotency: keeps a dict keyed by `order.idempotency_key`; a repeat key returns the cached `Fill` without creating a new one (skip when key is empty string — treat empty as non-idempotent). `timestamp` via an injectable `now` callable (default `datetime.utcnow`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_execution_simulated.py
from datetime import datetime
from trading_bot.execution.simulated import SimulatedExecutor
from trading_bot.domain.models import Order, OrderSide, OrderStatus


def _now():
    return datetime(2023, 1, 1)


def test_fills_notional_into_qty():
    ex = SimulatedExecutor(now=_now)
    order = Order(id="1", symbol="AAPL", side=OrderSide.BUY, notional=100.0)
    fill = ex.submit_order(order, ref_price=50.0)
    assert fill.qty == 2.0
    assert fill.price == 50.0
    assert order.status == OrderStatus.FILLED


def test_idempotent_repeat_returns_same_fill():
    ex = SimulatedExecutor(now=_now)
    o1 = Order(id="1", symbol="AAPL", side=OrderSide.BUY, notional=100.0,
               idempotency_key="k1")
    o2 = Order(id="2", symbol="AAPL", side=OrderSide.BUY, notional=100.0,
               idempotency_key="k1")
    f1 = ex.submit_order(o1, ref_price=50.0)
    f2 = ex.submit_order(o2, ref_price=50.0)
    assert f1 is f2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_execution_simulated.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.execution.simulated'`

- [ ] **Step 3: Write the base interface**

```python
# src/trading_bot/execution/base.py
from abc import ABC, abstractmethod
from trading_bot.domain.models import Order, Fill


class ExecutionClient(ABC):
    @abstractmethod
    def submit_order(self, order: Order, ref_price: float) -> Fill:
        ...
```

- [ ] **Step 4: Write the simulated executor**

```python
# src/trading_bot/execution/simulated.py
from datetime import datetime
from trading_bot.domain.models import Fill, OrderStatus
from trading_bot.execution.base import ExecutionClient


class SimulatedExecutor(ExecutionClient):
    def __init__(self, now=None):
        self._now = now or datetime.utcnow
        self._fills_by_key: dict = {}

    def submit_order(self, order, ref_price: float) -> Fill:
        key = order.idempotency_key
        if key and key in self._fills_by_key:
            return self._fills_by_key[key]
        qty = order.notional / ref_price
        fill = Fill(order_id=order.id, symbol=order.symbol, side=order.side,
                    qty=qty, price=ref_price, timestamp=self._now())
        order.status = OrderStatus.FILLED
        if key:
            self._fills_by_key[key] = fill
        return fill
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_execution_simulated.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/execution/__init__.py src/trading_bot/execution/base.py src/trading_bot/execution/simulated.py tests/test_execution_simulated.py
git commit -m "feat: execution interface and simulated executor"
```

---

### Task 5: Alpaca paper executor

**Files:**
- Create: `src/trading_bot/execution/alpaca_exec.py`, `tests/test_alpaca_exec.py`

**Interfaces:**
- Consumes: `Order`, `OrderSide`, `OrderStatus`, `Fill`, `ExecutionClient`.
- Produces: `class AlpacaPaperExecutor(ExecutionClient)`:
  - `__init__(self, api_key: str, secret_key: str, _client=None)` — `_client` is the injection seam; production builds `alpaca.trading.client.TradingClient(api_key, secret_key, paper=True)`.
  - `submit_order(self, order, ref_price) -> Fill` — builds a `MarketOrderRequest` with `notional=order.notional`, `side` mapped from `OrderSide`, `time_in_force=DAY`; submits via `self._client.submit_order(...)`; reads `filled_avg_price` and `filled_qty` from the returned object to build the `Fill`. If `filled_qty` is 0/None (not yet filled), fall back to `ref_price` and `notional/ref_price` and leave status `PENDING`; otherwise set `OrderStatus.FILLED`. The real SDK import happens inside `__init__`/`submit_order` so tests with `_client` never import `alpaca`.

- [ ] **Step 1: Write the failing test (injected fake client — no network)**

```python
# tests/test_alpaca_exec.py
from types import SimpleNamespace
from trading_bot.execution.alpaca_exec import AlpacaPaperExecutor
from trading_bot.domain.models import Order, OrderSide, OrderStatus


class _FakeTradingClient:
    def __init__(self):
        self.last_request = None

    def submit_order(self, order_data):
        self.last_request = order_data
        return SimpleNamespace(id="srv-1", filled_avg_price="50.0", filled_qty="2")


def test_submit_returns_fill_from_response():
    fake = _FakeTradingClient()
    ex = AlpacaPaperExecutor("k", "s", _client=fake)
    order = Order(id="1", symbol="AAPL", side=OrderSide.BUY, notional=100.0)
    fill = ex.submit_order(order, ref_price=49.0)
    assert fill.qty == 2.0
    assert fill.price == 50.0
    assert order.status == OrderStatus.FILLED
    assert fake.last_request is not None  # a request was built and sent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_alpaca_exec.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.execution.alpaca_exec'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/execution/alpaca_exec.py
from datetime import datetime
from trading_bot.domain.models import Fill, OrderSide, OrderStatus
from trading_bot.execution.base import ExecutionClient


class AlpacaPaperExecutor(ExecutionClient):
    def __init__(self, api_key: str, secret_key: str, _client=None):
        if _client is not None:
            self._client = _client
        else:
            from alpaca.trading.client import TradingClient
            self._client = TradingClient(api_key, secret_key, paper=True)

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
                    price=price, timestamp=datetime.utcnow())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_alpaca_exec.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/execution/alpaca_exec.py tests/test_alpaca_exec.py
git commit -m "feat: Alpaca paper execution client"
```

---

### Task 6: Audit log (SQLite persistence)

**Files:**
- Create: `src/trading_bot/audit/__init__.py`, `src/trading_bot/audit/audit_log.py`, `tests/test_audit_log.py`

**Interfaces:**
- Consumes: `Signal`, `Decision`, `RiskResult`, `Order`, `Fill` (Phases 1, 2a, Task 1).
- Produces: `class AuditLog`:
  - `__init__(self, db_path: str)` — creates tables `signals, decisions, risk_checks, orders, fills, events` if absent. Every table has `run_id TEXT` and `ts TEXT`.
  - `log_signal(self, run_id, signal) -> None`
  - `log_decision(self, run_id, decision) -> None`
  - `log_risk(self, run_id, symbol, risk_result) -> None`
  - `log_order(self, run_id, order) -> None`
  - `log_fill(self, run_id, fill) -> None`
  - `log_event(self, run_id, kind: str, detail: str) -> None`
  - `count(self, table: str) -> int` — row count (test/inspection helper; `table` validated against the known set).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_audit_log.py
from datetime import datetime
from trading_bot.audit.audit_log import AuditLog
from trading_bot.domain.models import (
    Action, Signal, Decision, RiskResult, Order, OrderSide, Fill,
)


def test_logs_each_record_type(tmp_path):
    log = AuditLog(str(tmp_path / "audit.sqlite"))
    rid = "run-1"
    log.log_signal(rid, Signal("AAPL", Action.BUY, 0.8, "r"))
    log.log_decision(rid, Decision("AAPL", Action.BUY, 0.8, True, "r", []))
    log.log_risk(rid, "AAPL", RiskResult(True, 100.0, "ok", []))
    log.log_order(rid, Order("o1", "AAPL", OrderSide.BUY, 100.0))
    log.log_fill(rid, Fill("o1", "AAPL", OrderSide.BUY, 2.0, 50.0, datetime(2023, 1, 1)))
    log.log_event(rid, "circuit_breaker", "tripped")
    for table in ("signals", "decisions", "risk_checks", "orders", "fills", "events"):
        assert log.count(table) == 1


def test_count_rejects_unknown_table(tmp_path):
    log = AuditLog(str(tmp_path / "audit.sqlite"))
    try:
        log.count("drop_me")
        assert False, "expected ValueError"
    except ValueError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_audit_log.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.audit.audit_log'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/audit/audit_log.py
import sqlite3
from datetime import datetime

_TABLES = {
    "signals": "run_id TEXT, ts TEXT, symbol TEXT, action TEXT, confidence REAL, rationale TEXT",
    "decisions": "run_id TEXT, ts TEXT, symbol TEXT, action TEXT, net_score REAL, consensus_met INTEGER, rationale TEXT",
    "risk_checks": "run_id TEXT, ts TEXT, symbol TEXT, approved INTEGER, approved_notional REAL, reason TEXT",
    "orders": "run_id TEXT, ts TEXT, order_id TEXT, symbol TEXT, side TEXT, notional REAL, status TEXT, idempotency_key TEXT",
    "fills": "run_id TEXT, ts TEXT, order_id TEXT, symbol TEXT, side TEXT, qty REAL, price REAL",
    "events": "run_id TEXT, ts TEXT, kind TEXT, detail TEXT",
}


class AuditLog:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        for name, cols in _TABLES.items():
            self.conn.execute(f"CREATE TABLE IF NOT EXISTS {name} ({cols})")
        self.conn.commit()

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    def log_signal(self, run_id, signal) -> None:
        self.conn.execute(
            "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, self._now(), signal.symbol, signal.action.value,
             signal.confidence, signal.rationale))
        self.conn.commit()

    def log_decision(self, run_id, d) -> None:
        self.conn.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, self._now(), d.symbol, d.action.value, d.net_score,
             int(d.consensus_met), d.rationale))
        self.conn.commit()

    def log_risk(self, run_id, symbol, r) -> None:
        self.conn.execute(
            "INSERT INTO risk_checks VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, self._now(), symbol, int(r.approved),
             r.approved_notional, r.reason))
        self.conn.commit()

    def log_order(self, run_id, o) -> None:
        self.conn.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, self._now(), o.id, o.symbol, o.side.value, o.notional,
             o.status.value, o.idempotency_key))
        self.conn.commit()

    def log_fill(self, run_id, f) -> None:
        self.conn.execute(
            "INSERT INTO fills VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, self._now(), f.order_id, f.symbol, f.side.value,
             f.qty, f.price))
        self.conn.commit()

    def log_event(self, run_id, kind: str, detail: str) -> None:
        self.conn.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?)",
            (run_id, self._now(), kind, detail))
        self.conn.commit()

    def count(self, table: str) -> int:
        if table not in _TABLES:
            raise ValueError(f"unknown table {table}")
        cur = self.conn.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_audit_log.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/audit/__init__.py src/trading_bot/audit/audit_log.py tests/test_audit_log.py
git commit -m "feat: SQLite audit log for full trade trail"
```

---

### Task 7: Cycle orchestrator (`run_once`)

**Files:**
- Create: `src/trading_bot/engine/__init__.py`, `src/trading_bot/engine/cycle.py`, `tests/test_cycle.py`

**Interfaces:**
- Consumes: `Action`, `Order`, `OrderSide`, `Signal`, `StrategyVote` (models); `aggregate` (Task 2a-3); `RiskManager` (2a-4); `evaluate_exits` (2a-5); `SafetyState` (2a-6); `Portfolio` (2a-2); `ExecutionClient` (Task 4); `AuditLog` (Task 6).
- Produces: `class TradingCycle`:
  - `__init__(self, strategies: dict, weights: dict, risk_manager, safety, portfolio, executor, audit, *, threshold: float, min_consensus: int, stop_loss_pct: float, take_profit_pct: float, per_trade_pct: float)`. `strategies` maps name→`Strategy`; `weights` maps name→float.
  - `run_once(self, symbols: list, history_by_symbol: dict, prices: dict, run_id: str) -> dict`:
    1. `equity = portfolio.total_equity(prices)`; `safety.update(equity)`. If `not safety.can_trade()`: `audit.log_event(run_id, "halted", reason)` and return `{"halted": True, "orders": 0}`.
    2. **Exits first:** for each `Decision` from `evaluate_exits(portfolio, prices, stop_loss_pct, take_profit_pct)`: run `risk_manager.check` (SELLs pass), build a SELL `Order` for the full position notional (`position_value`), `executor.submit_order`, `portfolio.apply_fill`, and audit decision/risk/order/fill.
    3. **Entries:** for each symbol, build `StrategyVote`s from each strategy's `generate_signal(symbol, history_by_symbol[symbol])` (audit each signal); `decision = aggregate(votes, threshold, min_consensus)`; audit decision. If `decision.action == Action.BUY`: `proposed = per_trade_pct * equity`; `rr = risk_manager.check(decision, proposed, portfolio, prices)`; audit risk. If `rr.approved`: build BUY `Order(notional=rr.approved_notional, idempotency_key=f"{run_id}:{symbol}")`, submit, apply fill, audit order/fill; count it.
    4. Return `{"halted": False, "orders": <count of entry+exit fills>}`.
  - Skip a symbol if it has no history. SELL exits and BUY entries both increment the order count.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cycle.py
from datetime import datetime, timedelta
from trading_bot.engine.cycle import TradingCycle
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.risk.risk_manager import RiskManager
from trading_bot.risk.safety import SafetyState
from trading_bot.execution.simulated import SimulatedExecutor
from trading_bot.audit.audit_log import AuditLog
from trading_bot.strategies.base import Strategy
from trading_bot.domain.models import Action, Signal


class _Always(Strategy):
    def __init__(self, action):
        self.action = action

    def generate_signal(self, symbol, history):
        return Signal(symbol, self.action, 0.9, "forced")


def _bars(symbol, closes):
    from trading_bot.domain.models import Bar
    base = datetime(2023, 1, 1)
    return [Bar(symbol, base + timedelta(days=i), c, c, c, c, 100)
            for i, c in enumerate(closes)]


def _cycle(tmp_path, executor=None):
    strategies = {"a": _Always(Action.BUY), "b": _Always(Action.BUY)}
    weights = {"a": 1.0, "b": 1.0}
    rm = RiskManager(0.20, 0.80, 5, min_order_notional=1.0)
    safety = SafetyState(0.03)
    pf = Portfolio(1000.0)
    audit = AuditLog(str(tmp_path / "audit.sqlite"))
    ex = executor or SimulatedExecutor(now=lambda: datetime(2023, 1, 1))
    return TradingCycle(strategies, weights, rm, safety, pf, ex, audit,
                        threshold=0.5, min_consensus=2,
                        stop_loss_pct=0.05, take_profit_pct=0.10,
                        per_trade_pct=0.10), pf, audit


def test_buy_consensus_places_order_and_updates_portfolio(tmp_path):
    cycle, pf, audit = _cycle(tmp_path)
    hist = {"AAPL": _bars("AAPL", [10, 11, 12])}
    res = cycle.run_once(["AAPL"], hist, {"AAPL": 12.0}, run_id="r1")
    assert res["halted"] is False
    assert res["orders"] == 1
    assert "AAPL" in pf.positions
    assert audit.count("orders") == 1
    assert audit.count("fills") == 1
    assert audit.count("decisions") >= 1


def test_kill_switch_halts_cycle(tmp_path):
    cycle, pf, audit = _cycle(tmp_path)
    cycle.safety.kill()
    res = cycle.run_once(["AAPL"], {"AAPL": _bars("AAPL", [10, 11, 12])},
                         {"AAPL": 12.0}, run_id="r2")
    assert res["halted"] is True
    assert res["orders"] == 0
    assert "AAPL" not in pf.positions
    assert audit.count("events") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_cycle.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.engine.cycle'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/engine/cycle.py
from trading_bot.domain.models import Action, Order, OrderSide, StrategyVote
from trading_bot.decision.aggregator import aggregate
from trading_bot.risk.exits import evaluate_exits


class TradingCycle:
    def __init__(self, strategies: dict, weights: dict, risk_manager, safety,
                 portfolio, executor, audit, *, threshold: float,
                 min_consensus: int, stop_loss_pct: float,
                 take_profit_pct: float, per_trade_pct: float):
        self.strategies = strategies
        self.weights = weights
        self.risk_manager = risk_manager
        self.safety = safety
        self.portfolio = portfolio
        self.executor = executor
        self.audit = audit
        self.threshold = threshold
        self.min_consensus = min_consensus
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.per_trade_pct = per_trade_pct

    def run_once(self, symbols: list, history_by_symbol: dict, prices: dict,
                 run_id: str) -> dict:
        pf = self.portfolio
        equity = pf.total_equity(prices)
        self.safety.update(equity)
        if not self.safety.can_trade():
            self.audit.log_event(run_id, "halted", "safety state blocked trading")
            return {"halted": True, "orders": 0}

        order_count = 0
        seq = 0

        # 1) Exits first (risk-reducing)
        for d in evaluate_exits(pf, prices, self.stop_loss_pct, self.take_profit_pct):
            self.audit.log_decision(run_id, d)
            price = prices[d.symbol]
            notional = pf.position_value(d.symbol, price)
            rr = self.risk_manager.check(d, notional, pf, prices)
            self.audit.log_risk(run_id, d.symbol, rr)
            if not rr.approved or rr.approved_notional <= 0:
                continue
            seq += 1
            order = Order(id=f"{run_id}-x{seq}", symbol=d.symbol,
                          side=OrderSide.SELL, notional=rr.approved_notional,
                          idempotency_key=f"{run_id}:exit:{d.symbol}")
            fill = self.executor.submit_order(order, ref_price=price)
            pf.apply_fill(d.symbol, OrderSide.SELL, fill.qty, fill.price)
            self.audit.log_order(run_id, order)
            self.audit.log_fill(run_id, fill)
            order_count += 1

        # 2) Entries
        for symbol in symbols:
            history = history_by_symbol.get(symbol)
            if not history:
                continue
            votes = []
            for name, strat in self.strategies.items():
                sig = strat.generate_signal(symbol, history)
                self.audit.log_signal(run_id, sig)
                votes.append(StrategyVote(name, sig, self.weights.get(name, 1.0)))
            decision = aggregate(votes, self.threshold, self.min_consensus)
            self.audit.log_decision(run_id, decision)
            if decision.action != Action.BUY:
                continue
            proposed = self.per_trade_pct * equity
            rr = self.risk_manager.check(decision, proposed, pf, prices)
            self.audit.log_risk(run_id, symbol, rr)
            if not rr.approved or rr.approved_notional <= 0:
                continue
            seq += 1
            order = Order(id=f"{run_id}-e{seq}", symbol=symbol,
                          side=OrderSide.BUY, notional=rr.approved_notional,
                          idempotency_key=f"{run_id}:{symbol}")
            fill = self.executor.submit_order(order, ref_price=prices[symbol])
            pf.apply_fill(symbol, OrderSide.BUY, fill.qty, fill.price)
            self.audit.log_order(run_id, order)
            self.audit.log_fill(run_id, fill)
            order_count += 1

        return {"halted": False, "orders": order_count}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_cycle.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (2 passed)

- [ ] **Step 5: Create `src/trading_bot/engine/__init__.py`** (empty file)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/engine/__init__.py src/trading_bot/engine/cycle.py tests/test_cycle.py
git commit -m "feat: trading cycle orchestrator (run_once)"
```

---

### Task 8: Paper-cycle CLI + config wiring

**Files:**
- Create: `scripts/run_paper_cycle.py`
- Modify: `config.yaml` (append `decision` and `risk` and `execution` sections)

**Interfaces:**
- Consumes: `load_config`, `load_secrets` (Phase 1); `BarStore`, `AlpacaHistoricalClient`, `MarketData` (Phase 1); `SmaCrossover` (Phase 1), `RsiMeanReversion` (Task 2), `MomentumBreakout` (Task 3); `Portfolio`, `RiskManager`, `SafetyState`; `SimulatedExecutor`/`AlpacaPaperExecutor`; `AuditLog`; `TradingCycle`.
- Produces: `scripts/run_paper_cycle.py` — loads config + secrets, builds the data stack and the three strategies with configured weights, fetches recent history for each universe symbol, derives `prices` from the latest bar close, builds `TradingCycle`, calls `run_once`, and prints the returned summary plus the resulting positions. Executor selected by config `execution.mode` (`"sim"` or `"alpaca"`); default `"sim"` so it runs with no keys.

- [ ] **Step 1: Append config sections to `config.yaml`**

```yaml
decision:
  threshold: 0.5
  min_consensus: 2
  weights:
    sma_crossover: 1.0
    rsi: 1.0
    momentum: 1.0

risk:
  max_position_pct: 0.20
  max_total_exposure_pct: 0.80
  max_positions: 5
  min_order_notional: 1.0
  stop_loss_pct: 0.05
  take_profit_pct: 0.10
  per_trade_pct: 0.10
  max_daily_loss_pct: 0.03

execution:
  mode: "sim"   # "sim" or "alpaca"
  audit_db: "audit.sqlite"

strategies:
  sma_crossover:
    fast: 20
    slow: 50
  rsi:
    period: 14
    oversold: 30.0
    overbought: 70.0
  momentum:
    lookback: 20
```

Note: the existing `config.yaml` already has `universe`, `capital`, `data`, `backtest`, and a `strategies.sma_crossover` block. Merge the `strategies` additions into the existing `strategies` key rather than duplicating it. Verify with `python -c "import yaml; print(yaml.safe_load(open('config.yaml')).keys())"`.

- [ ] **Step 2: Write the CLI**

```python
# scripts/run_paper_cycle.py
from datetime import datetime, timedelta

from trading_bot.config.loader import load_config, load_secrets
from trading_bot.data.store import BarStore
from trading_bot.data.alpaca_client import AlpacaHistoricalClient
from trading_bot.data.market_data import MarketData
from trading_bot.strategies.sma_crossover import SmaCrossover
from trading_bot.strategies.rsi import RsiMeanReversion
from trading_bot.strategies.momentum import MomentumBreakout
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.risk.risk_manager import RiskManager
from trading_bot.risk.safety import SafetyState
from trading_bot.execution.simulated import SimulatedExecutor
from trading_bot.execution.alpaca_exec import AlpacaPaperExecutor
from trading_bot.audit.audit_log import AuditLog
from trading_bot.engine.cycle import TradingCycle


def build_strategies(cfg: dict) -> dict:
    s = cfg["strategies"]
    return {
        "sma_crossover": SmaCrossover(fast=s["sma_crossover"]["fast"],
                                      slow=s["sma_crossover"]["slow"]),
        "rsi": RsiMeanReversion(period=s["rsi"]["period"],
                                oversold=s["rsi"]["oversold"],
                                overbought=s["rsi"]["overbought"]),
        "momentum": MomentumBreakout(lookback=s["momentum"]["lookback"]),
    }


def main() -> None:
    cfg = load_config("config.yaml")
    secrets = load_secrets(".env")
    store = BarStore(cfg["data"]["cache_db"])
    client = AlpacaHistoricalClient(secrets["ALPACA_API_KEY"],
                                    secrets["ALPACA_SECRET_KEY"])
    md = MarketData(store, client, cfg["data"]["timeframe"])

    end = datetime.utcnow()
    start = end - timedelta(days=120)
    symbols = cfg["universe"]
    history = {sym: md.get_bars(sym, start, end) for sym in symbols}
    prices = {sym: bars[-1].close for sym, bars in history.items() if bars}

    risk = cfg["risk"]
    rm = RiskManager(risk["max_position_pct"], risk["max_total_exposure_pct"],
                     risk["max_positions"], risk["min_order_notional"])
    safety = SafetyState(risk["max_daily_loss_pct"])
    pf = Portfolio(cfg["capital"]["starting_cash"])
    safety.start_day(pf.total_equity(prices))

    if cfg["execution"]["mode"] == "alpaca":
        executor = AlpacaPaperExecutor(secrets["ALPACA_API_KEY"],
                                       secrets["ALPACA_SECRET_KEY"])
    else:
        executor = SimulatedExecutor()
    audit = AuditLog(cfg["execution"]["audit_db"])

    dec = cfg["decision"]
    cycle = TradingCycle(
        build_strategies(cfg), dec["weights"], rm, safety, pf, executor, audit,
        threshold=dec["threshold"], min_consensus=dec["min_consensus"],
        stop_loss_pct=risk["stop_loss_pct"], take_profit_pct=risk["take_profit_pct"],
        per_trade_pct=risk["per_trade_pct"],
    )
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    summary = cycle.run_once([s for s in symbols if s in prices], history, prices, run_id)
    print(f"run_id={run_id} summary={summary}")
    print("positions:", {s: (p.qty, p.avg_cost) for s, p in pf.positions.items()})


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-test the CLI in simulated mode (no keys needed)**

Run: `PYTHONPATH=src python scripts/run_paper_cycle.py`
Expected: prints a `run_id=... summary={'halted': False, 'orders': N}` line and a positions dict. (Needs cached/fetchable bars; with no `.env` keys the data fetch may return empty — in that case the summary shows 0 orders, which still exercises the wiring without error.)

- [ ] **Step 4: Run the FULL suite (Phases 1 + 2a + 2b)**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/run_paper_cycle.py config.yaml
git commit -m "feat: paper-cycle CLI and config wiring"
```

---

## Self-Review (completed by plan author)

**Spec coverage (Phase 2b scope):**
- Strategy engine — RSI (Task 2) and momentum/breakout (Task 3) added as pluggable modules implementing the Phase 1 `Strategy` interface; SMA already exists. ✓
- Execution layer — broker-agnostic `ExecutionClient` interface, simulated implementation first (Task 4), Alpaca paper implementation with idempotency-capable orders (Tasks 4–5). ✓
- Portfolio reconciliation against fills — `apply_fill` after each execution in the orchestrator (Task 7). (Live broker-position reconciliation on startup is a Phase 6 hardening item.)
- Reporting/audit — full audit trail of signals/decisions/risk_checks/orders/fills/events to SQLite, queryable (Task 6), written on every cycle (Task 7). ✓
- Orchestrator wiring data→strategies→decision→risk→safety→execution with kill switch + circuit breaker enforced before any order (Task 7). ✓
- CLI + config-driven parameters, sim default so it runs without keys (Task 8). ✓
- Deferred: scheduler loop / timed cadence (Phase 6), morning/nightly email reports + dashboard (Phase 3), live trading (Phase 5). The orchestrator exposes `run_once` so a scheduler is a thin wrapper later.

**Placeholder scan:** No TBD/TODO; every code step is complete and runnable.

**Type consistency:** `Fill` (Task 1) used by execution (4–5), audit (6), orchestrator (7). `ExecutionClient.submit_order(order, ref_price) -> Fill` consistent across base, simulated, alpaca, and orchestrator call sites. `aggregate(votes, threshold, min_consensus)`, `RiskManager.check(decision, proposed_notional, portfolio, prices)`, `evaluate_exits(portfolio, prices, stop_loss_pct, take_profit_pct)`, `SafetyState.update/can_trade/start_day`, `Portfolio.apply_fill/total_equity/position_value` all called with the exact signatures defined in Phase 2a. `AuditLog` method names match orchestrator usage. Strategy constructors match the config keys read in Task 8.
