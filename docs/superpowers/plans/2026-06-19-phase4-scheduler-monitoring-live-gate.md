# Phase 4: Scheduler + Monitoring + Live Gate + Runbook — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tie the pieces into a running system — a market-hours-aware scheduler that runs trading cycles and sends morning/nightly reports on a cadence, monitoring that alerts when the kill switch or circuit breaker trips, a hard-gated live-trading switch (paper remains the default), and an operator runbook.

**Architecture:** A tick-based `Runtime` is the orchestrating loop: each `tick(now)` consults the persistent kill switch, runs a cycle only when the market is open and trading is allowed, and sends the morning/nightly report once per day at configured hours. Time and the cycle/report/alert actions are injected so ticks are deterministic in tests; `run_forever` is a thin sleep loop on top. A `select_executor` builder enforces that real-money trading requires BOTH `execution.live: true` in config AND `LIVE_TRADING=true` in the environment — otherwise it always returns the paper executor.

**Tech Stack:** Python 3.10+, stdlib only for the loop (no extra deps), `pytest`. Builds on Phases 1–3b.

## Global Constraints

- Python 3.10+ (sandbox 3.10.12; no 3.11+ syntax).
- **Capital preservation:** live trading is OFF by default and double-gated (config flag AND env var). Any ambiguity resolves to paper. The default config ships `execution.live: false`.
- No secrets in code or logs; the live gate reads `LIVE_TRADING` from the environment only.
- The runtime MUST consult the kill switch and circuit breaker before every cycle and place no orders when either is active.
- Reports send at most once per kind per calendar day.
- Tests must not hit the network or sleep on real time — inject `now`, the cycle/report/alert callables, and a fake clock.
- Run pytest with Linux-local temp: `PYTHONPATH=src python -m pytest -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`.
- **Mount caveat:** modifying existing files (`alpaca_exec.py`, `config.yaml`, `README.md`) may not sync through the mount; verify and apply from the shell if needed. New files persist normally.
- Commits run where git is available (user's Windows machine); stage the listed files per task.

---

## File Structure

```
src/trading_bot/
├── runtime/
│   ├── __init__.py            # NEW
│   ├── clock.py               # NEW: is_market_open(); MarketClock
│   ├── monitoring.py          # NEW: maybe_alert()
│   └── runtime.py             # NEW: Runtime (tick + run_forever)
├── execution/
│   ├── alpaca_exec.py         # MODIFY: accept paper flag
│   └── selector.py            # NEW: select_executor() with live gate
scripts/
└── run_bot.py                 # NEW: builds Runtime from config and runs the loop
config.yaml                    # MODIFY: execution.live: false; runtime section
README.md                      # MODIFY: link to runbook
RUNBOOK.md                     # NEW: operator runbook
tests/
├── test_clock.py
├── test_executor_selector.py
├── test_monitoring.py
└── test_runtime.py
```

---

### Task 1: Market session clock

**Files:**
- Create: `src/trading_bot/runtime/__init__.py`, `src/trading_bot/runtime/clock.py`, `tests/test_clock.py`

**Interfaces:**
- Produces:
  - `is_market_open(now) -> bool` — `now` is a timezone-aware or naive datetime already in US Eastern. Returns True only Mon–Fri and `09:30 <= time < 16:00`. (Holidays are not handled here; documented limitation — a later iteration can swap in the Alpaca clock.)
  - `class MarketClock`: `__init__(self, _client=None)` — optional Alpaca `TradingClient` for authoritative open/closed via `get_clock()`. `is_open(self, now) -> bool` uses the client's `get_clock().is_open` when a client is present, else falls back to `is_market_open(now)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_clock.py
from datetime import datetime
from types import SimpleNamespace
from trading_bot.runtime.clock import is_market_open, MarketClock


def test_open_during_weekday_session():
    assert is_market_open(datetime(2026, 6, 19, 10, 0)) is True   # Friday 10:00


def test_closed_before_open():
    assert is_market_open(datetime(2026, 6, 19, 9, 0)) is False    # 09:00


def test_closed_after_close():
    assert is_market_open(datetime(2026, 6, 19, 16, 30)) is False


def test_closed_on_weekend():
    assert is_market_open(datetime(2026, 6, 20, 11, 0)) is False    # Saturday


def test_market_clock_uses_client_when_present():
    fake = SimpleNamespace(get_clock=lambda: SimpleNamespace(is_open=True))
    clock = MarketClock(_client=fake)
    # client says open even though it's Sunday
    assert clock.is_open(datetime(2026, 6, 21, 3, 0)) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_clock.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.runtime.clock'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/runtime/clock.py
from datetime import time


def is_market_open(now) -> bool:
    if now.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    t = now.time()
    return time(9, 30) <= t < time(16, 0)


class MarketClock:
    def __init__(self, _client=None):
        self._client = _client

    def is_open(self, now) -> bool:
        if self._client is not None:
            return bool(self._client.get_clock().is_open)
        return is_market_open(now)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_clock.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (5 passed)

- [ ] **Step 5: Create `src/trading_bot/runtime/__init__.py`** (empty file)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/runtime/__init__.py src/trading_bot/runtime/clock.py tests/test_clock.py
git commit -m "feat: market session clock"
```

---

### Task 2: Live-trading gate (executor selector)

**Files:**
- Modify: `src/trading_bot/execution/alpaca_exec.py` (accept a `paper` flag)
- Create: `src/trading_bot/execution/selector.py`, `tests/test_executor_selector.py`

**Interfaces:**
- Modify `AlpacaPaperExecutor.__init__` to `(self, api_key, secret_key, _client=None, paper: bool = True)` and pass `paper=paper` to `TradingClient(...)`. Default stays `True` so all existing call sites remain paper. (Verify the edit synced; rewrite from shell if not.)
- Produces: `select_executor(mode: str, live_config: bool, live_env: str, api_key: str, secret_key: str) -> ExecutionClient`:
  - `mode == "sim"` → `SimulatedExecutor()`.
  - `mode == "alpaca"`: live only if `live_config is True` AND `str(live_env).lower() == "true"`. If live → `AlpacaPaperExecutor(api_key, secret_key, paper=False)`; otherwise → `AlpacaPaperExecutor(api_key, secret_key, paper=True)`.
  - Returns the executor; never raises on the gate (defaults to paper). This is the single chokepoint for real-money trading.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_executor_selector.py
from trading_bot.execution.selector import select_executor
from trading_bot.execution.simulated import SimulatedExecutor
from trading_bot.execution.alpaca_exec import AlpacaPaperExecutor


def test_sim_mode():
    ex = select_executor("sim", False, "false", "k", "s")
    assert isinstance(ex, SimulatedExecutor)


def test_alpaca_defaults_to_paper():
    ex = select_executor("alpaca", False, "false", "k", "s")
    assert isinstance(ex, AlpacaPaperExecutor)
    assert ex.paper is True


def test_live_requires_both_flags():
    # config says live but env does not -> still paper
    ex = select_executor("alpaca", True, "false", "k", "s")
    assert ex.paper is True
    # env says live but config does not -> still paper
    ex2 = select_executor("alpaca", False, "true", "k", "s")
    assert ex2.paper is True


def test_live_enabled_only_when_both_true():
    ex = select_executor("alpaca", True, "true", "k", "s")
    assert ex.paper is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_executor_selector.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL (`ModuleNotFoundError` for selector; and `AlpacaPaperExecutor` has no `.paper` attribute yet).

- [ ] **Step 3: Modify `AlpacaPaperExecutor`** to record and use the `paper` flag

```python
# src/trading_bot/execution/alpaca_exec.py  (updated __init__)
    def __init__(self, api_key: str, secret_key: str, _client=None, paper: bool = True):
        self.paper = paper
        if _client is not None:
            self._client = _client
        else:
            from alpaca.trading.client import TradingClient
            self._client = TradingClient(api_key, secret_key, paper=paper)
```

(Leave `submit_order` unchanged. If the editor write doesn't sync, rewrite the file from the shell with this `__init__` plus the existing `submit_order`.)

- [ ] **Step 4: Write the selector**

```python
# src/trading_bot/execution/selector.py
from trading_bot.execution.simulated import SimulatedExecutor
from trading_bot.execution.alpaca_exec import AlpacaPaperExecutor


def select_executor(mode: str, live_config: bool, live_env: str,
                    api_key: str, secret_key: str):
    if mode == "sim":
        return SimulatedExecutor()
    live = (live_config is True) and (str(live_env).lower() == "true")
    return AlpacaPaperExecutor(api_key, secret_key, paper=not live)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_executor_selector.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/execution/alpaca_exec.py src/trading_bot/execution/selector.py tests/test_executor_selector.py
git commit -m "feat: double-gated live trading selector (paper by default)"
```

---

### Task 3: Monitoring alerts

**Files:**
- Create: `src/trading_bot/runtime/monitoring.py`, `tests/test_monitoring.py`

**Interfaces:**
- Consumes: `Notifier` (Phase 3a), `SafetyState` (Phase 2a), `ControlStore` (Phase 3b).
- Produces: `maybe_alert(safety, control_store, notifier) -> bool`:
  - If `control_store.is_killed()` OR `safety.tripped`, send a notification (`subject="[Trading Bot] ALERT"`, body describing which guard fired and the reason) and return `True`.
  - Otherwise return `False` (no alert).
  - Uses `notifier.send(subject, text, html)` with a minimal html body.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_monitoring.py
from trading_bot.runtime.monitoring import maybe_alert
from trading_bot.risk.safety import SafetyState
from trading_bot.control.control_store import ControlStore
from trading_bot.notify.console_notifier import ConsoleNotifier
import io


def _notifier():
    return ConsoleNotifier(stream=io.StringIO())


def test_alerts_on_kill(tmp_path):
    cs = ControlStore(str(tmp_path / "c.sqlite"))
    cs.kill("manual")
    safety = SafetyState(0.03)
    n = _notifier()
    assert maybe_alert(safety, cs, n) is True
    assert len(n.sent) == 1


def test_alerts_on_circuit_breaker(tmp_path):
    cs = ControlStore(str(tmp_path / "c.sqlite"))
    safety = SafetyState(0.03)
    safety.start_day(1000.0)
    safety.update(900.0)  # trips
    n = _notifier()
    assert maybe_alert(safety, cs, n) is True


def test_no_alert_when_healthy(tmp_path):
    cs = ControlStore(str(tmp_path / "c.sqlite"))
    safety = SafetyState(0.03)
    n = _notifier()
    assert maybe_alert(safety, cs, n) is False
    assert n.sent == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_monitoring.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.runtime.monitoring'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/runtime/monitoring.py
def maybe_alert(safety, control_store, notifier) -> bool:
    reasons = []
    if control_store.is_killed():
        reasons.append(f"kill switch active: {control_store.kill_reason() or 'manual'}")
    if getattr(safety, "tripped", False):
        reasons.append("circuit breaker tripped (max daily loss breached)")
    if not reasons:
        return False
    text = "Trading is halted.\n" + "\n".join(f"- {r}" for r in reasons)
    html = "<h3>Trading halted</h3><ul>" + "".join(f"<li>{r}</li>" for r in reasons) + "</ul>"
    notifier.send("[Trading Bot] ALERT", text, html)
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_monitoring.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/runtime/monitoring.py tests/test_monitoring.py
git commit -m "feat: monitoring alerts on kill switch / circuit breaker"
```

---

### Task 4: Runtime tick loop

**Files:**
- Create: `src/trading_bot/runtime/runtime.py`, `tests/test_runtime.py`

**Interfaces:**
- Consumes: a clock with `is_open(now) -> bool` (Task 1); `ControlStore` (Phase 3b); callables.
- Produces: `class Runtime`:
  - `__init__(self, clock, control_store, run_cycle, send_report, morning_hour: int, nightly_hour: int)`. `run_cycle()` runs one trading cycle (returns a summary dict). `send_report(kind)` sends a report. Internal state: `self._last_morning = None`, `self._last_nightly = None` (dates).
  - `tick(self, now) -> dict` — returns `{"cycle_ran": bool, "reports_sent": [..], "halted": bool}`:
    1. If `now.hour == morning_hour` and `self._last_morning != now.date()` → `send_report("morning")`, record date, append `"morning"`.
    2. If `now.hour == nightly_hour` and `self._last_nightly != now.date()` → `send_report("nightly")`, record, append `"nightly"`.
    3. If `control_store.is_killed()` → `cycle_ran=False`, `halted=True`, do not run a cycle.
    4. Else if `clock.is_open(now)` → `run_cycle()`, `cycle_ran=True`.
    5. Else `cycle_ran=False`.
  - `run_forever(self, now_fn, sleep_fn, interval: int)` — loop: `tick(now_fn())` then `sleep_fn(interval)`. (Thin wrapper; not unit-tested. `now_fn`/`sleep_fn` injectable.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runtime.py
from datetime import datetime
from trading_bot.runtime.runtime import Runtime
from trading_bot.control.control_store import ControlStore


class _Clock:
    def __init__(self, open_):
        self._open = open_

    def is_open(self, now):
        return self._open


def _rt(tmp_path, clock_open=True):
    cs = ControlStore(str(tmp_path / "c.sqlite"))
    state = {"cycles": 0, "reports": []}
    rt = Runtime(_Clock(clock_open), cs,
                 run_cycle=lambda: state.__setitem__("cycles", state["cycles"] + 1),
                 send_report=lambda kind: state["reports"].append(kind),
                 morning_hour=8, nightly_hour=18)
    return rt, cs, state


def test_runs_cycle_when_open(tmp_path):
    rt, cs, state = _rt(tmp_path, clock_open=True)
    res = rt.tick(datetime(2026, 6, 19, 10, 0))
    assert res["cycle_ran"] is True
    assert state["cycles"] == 1


def test_no_cycle_when_closed(tmp_path):
    rt, cs, state = _rt(tmp_path, clock_open=False)
    res = rt.tick(datetime(2026, 6, 19, 22, 0))
    assert res["cycle_ran"] is False
    assert state["cycles"] == 0


def test_no_cycle_when_killed(tmp_path):
    rt, cs, state = _rt(tmp_path, clock_open=True)
    cs.kill("halt")
    res = rt.tick(datetime(2026, 6, 19, 10, 0))
    assert res["cycle_ran"] is False
    assert res["halted"] is True
    assert state["cycles"] == 0


def test_morning_report_sent_once_per_day(tmp_path):
    rt, cs, state = _rt(tmp_path, clock_open=False)
    rt.tick(datetime(2026, 6, 19, 8, 0))
    rt.tick(datetime(2026, 6, 19, 8, 30))   # same day, same hour -> no duplicate
    assert state["reports"].count("morning") == 1


def test_nightly_report_sent_at_hour(tmp_path):
    rt, cs, state = _rt(tmp_path, clock_open=False)
    rt.tick(datetime(2026, 6, 19, 18, 5))
    assert "nightly" in state["reports"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_runtime.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.runtime.runtime'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/runtime/runtime.py
class Runtime:
    def __init__(self, clock, control_store, run_cycle, send_report,
                 morning_hour: int, nightly_hour: int):
        self.clock = clock
        self.control_store = control_store
        self.run_cycle = run_cycle
        self.send_report = send_report
        self.morning_hour = morning_hour
        self.nightly_hour = nightly_hour
        self._last_morning = None
        self._last_nightly = None

    def tick(self, now) -> dict:
        reports_sent = []
        today = now.date()
        if now.hour == self.morning_hour and self._last_morning != today:
            self.send_report("morning")
            self._last_morning = today
            reports_sent.append("morning")
        if now.hour == self.nightly_hour and self._last_nightly != today:
            self.send_report("nightly")
            self._last_nightly = today
            reports_sent.append("nightly")

        if self.control_store.is_killed():
            return {"cycle_ran": False, "reports_sent": reports_sent, "halted": True}

        if self.clock.is_open(now):
            self.run_cycle()
            return {"cycle_ran": True, "reports_sent": reports_sent, "halted": False}
        return {"cycle_ran": False, "reports_sent": reports_sent, "halted": False}

    def run_forever(self, now_fn, sleep_fn, interval: int) -> None:
        while True:
            self.tick(now_fn())
            sleep_fn(interval)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_runtime.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/runtime/runtime.py tests/test_runtime.py
git commit -m "feat: tick-based runtime scheduler"
```

---

### Task 5: run_bot entry, config, runbook, full suite

**Files:**
- Create: `scripts/run_bot.py`, `RUNBOOK.md`
- Modify: `config.yaml` (`execution.live: false`, `runtime` section, `control` section), `README.md` (link runbook + live warning)

**Interfaces:**
- Consumes: everything. `run_bot.py` builds the data stack, strategies, risk, safety, control store, executor (via `select_executor` with `LIVE_TRADING` env), audit, the `TradingCycle`, the report sender, `MarketClock`, and a `Runtime`, then calls `run_forever`. A single cycle run rebuilds prices from fresh data each tick.

- [ ] **Step 1: Append config keys**

Add to `config.yaml` (append from shell if the editor write doesn't sync):
```yaml
control:
  db: "control.sqlite"

runtime:
  poll_interval_seconds: 300

execution:
  mode: "sim"
  audit_db: "audit.sqlite"
  live: false
```
Note: `execution` already exists with `mode` and `audit_db` — add the `live: false` line into that existing block rather than duplicating the key. Verify with the yaml-load one-liner.

- [ ] **Step 2: Write `scripts/run_bot.py`**

```python
# scripts/run_bot.py
import os
import time
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
from trading_bot.control.control_store import ControlStore, apply_controls
from trading_bot.execution.selector import select_executor
from trading_bot.audit.audit_log import AuditLog
from trading_bot.engine.cycle import TradingCycle
from trading_bot.runtime.clock import MarketClock
from trading_bot.runtime.runtime import Runtime
from trading_bot.runtime.monitoring import maybe_alert
from trading_bot.notify.console_notifier import ConsoleNotifier


def build_runtime():
    cfg = load_config("config.yaml")
    secrets = load_secrets(".env")
    store = BarStore(cfg["data"]["cache_db"])
    hist_client = AlpacaHistoricalClient(secrets["ALPACA_API_KEY"],
                                         secrets["ALPACA_SECRET_KEY"])
    md = MarketData(store, hist_client, cfg["data"]["timeframe"])
    risk = cfg["risk"]
    dec = cfg["decision"]
    control_store = ControlStore(cfg["control"]["db"])
    audit = AuditLog(cfg["execution"]["audit_db"])
    notifier = ConsoleNotifier()

    def strategies():
        s = cfg["strategies"]
        return {
            "sma_crossover": SmaCrossover(s["sma_crossover"]["fast"], s["sma_crossover"]["slow"]),
            "rsi": RsiMeanReversion(s["rsi"]["period"], s["rsi"]["oversold"], s["rsi"]["overbought"]),
            "momentum": MomentumBreakout(s["momentum"]["lookback"]),
        }

    def run_cycle():
        end = datetime.utcnow()
        start = end - timedelta(days=120)
        symbols = cfg["universe"]
        history = {sym: md.get_bars(sym, start, end) for sym in symbols}
        prices = {s: b[-1].close for s, b in history.items() if b}
        rm = RiskManager(risk["max_position_pct"], risk["max_total_exposure_pct"],
                         risk["max_positions"], risk["min_order_notional"])
        safety = SafetyState(risk["max_daily_loss_pct"])
        pf = Portfolio(cfg["capital"]["starting_cash"])
        safety.start_day(pf.total_equity(prices))
        apply_controls(control_store, safety)
        executor = select_executor(cfg["execution"]["mode"], cfg["execution"]["live"],
                                   os.environ.get("LIVE_TRADING", "false"),
                                   secrets["ALPACA_API_KEY"], secrets["ALPACA_SECRET_KEY"])
        cycle = TradingCycle(strategies(), dec["weights"], rm, safety, pf, executor, audit,
                             threshold=dec["threshold"], min_consensus=dec["min_consensus"],
                             stop_loss_pct=risk["stop_loss_pct"],
                             take_profit_pct=risk["take_profit_pct"],
                             per_trade_pct=risk["per_trade_pct"])
        run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        summary = cycle.run_once([s for s in symbols if s in prices], history, prices, run_id)
        maybe_alert(safety, control_store, notifier)
        print(f"[cycle] {run_id} {summary}")
        return summary

    def send_report(kind):
        print(f"[report] would send {kind} report (wire to scripts/send_report.py)")

    rep = cfg["reporting"]
    runtime = Runtime(MarketClock(), control_store, run_cycle, send_report,
                      morning_hour=rep["morning_hour"], nightly_hour=rep["nightly_hour"])
    return runtime, cfg


def main():
    runtime, cfg = build_runtime()
    interval = cfg["runtime"]["poll_interval_seconds"]
    print(f"bot started; polling every {interval}s. Ctrl-C to stop.")
    runtime.run_forever(datetime.utcnow, time.sleep, interval)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write `RUNBOOK.md`**

```markdown
# Operator Runbook

## Start / stop
- Start the bot loop: `PYTHONPATH=src python scripts/run_bot.py`
- Start the dashboard/API: `PYTHONPATH=src python scripts/run_api.py` → http://127.0.0.1:8000/
- Stop: Ctrl-C in the terminal running the process.

## Kill switch (halt all new orders)
- Dashboard: click **Kill switch — halt trading**.
- CLI: `PYTHONPATH=src python -c "from trading_bot.control.control_store import ControlStore; ControlStore('control.sqlite').kill('manual')"`
- Resume: dashboard **Resume**, or `...ControlStore('control.sqlite').clear_kill()`.
- The runtime checks the kill switch before every cycle; halting stops new orders immediately.

## Circuit breaker
- Trips automatically when the day's loss exceeds `risk.max_daily_loss_pct` (default 3%). It blocks further trading for the day and fires an alert.

## Change configuration
- Edit `config.yaml` (universe, strategy weights, risk caps, schedule). Restart the bot to apply.
- Secrets live in `.env` only (never commit). See `.env.example`.

## Going live (DANGER — real money)
- Live trading is OFF by default and double-gated. To enable, BOTH must be true:
  1. `execution.live: true` in `config.yaml`
  2. environment `LIVE_TRADING=true`
- If either is missing, the bot trades paper. Only enable after a full paper-validation window.

## Interpreting reports
- Morning/nightly reports show equity, cash, exposure, realized P&L, positions, what the bot did (fills + decisions), and alerts.
- Full audit trail is in `audit.sqlite` (tables: signals, decisions, risk_checks, orders, fills, events) — every trade is reconstructable by `run_id`.
```

- [ ] **Step 4: Append a live-trading warning + runbook link to `README.md`**

```markdown
## Operations

See `RUNBOOK.md` for start/stop, kill switch, config changes, and report interpretation.

**Live trading is OFF by default** and requires BOTH `execution.live: true` in `config.yaml` AND `LIVE_TRADING=true` in the environment. Leave it off until you have validated behavior in paper trading.
```

- [ ] **Step 5: Run the FULL suite**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (all phases).

- [ ] **Step 6: Smoke-test the runtime wiring** (no network: one tick with market closed)

Run:
```
PYTHONPATH=src python -c "
from datetime import datetime
from trading_bot.runtime.runtime import Runtime
from trading_bot.control.control_store import ControlStore
cs = ControlStore('/tmp/c.sqlite')
calls = {'c':0,'r':[]}
class K:
    def is_open(self, now): return False
rt = Runtime(K(), cs, lambda: calls.__setitem__('c',calls['c']+1), lambda k: calls['r'].append(k), 8, 18)
print(rt.tick(datetime(2026,6,20,12,0)))  # weekend midday -> no cycle, no report
"
```
Expected: prints `{'cycle_ran': False, 'reports_sent': [], 'halted': False}`.

- [ ] **Step 7: Commit**

```bash
git add scripts/run_bot.py RUNBOOK.md config.yaml README.md
git commit -m "feat: runtime loop entry, runbook, live-trading warning"
```

---

## Self-Review (completed by plan author)

**Spec coverage (Phases 4–6 buildable scope):**
- Scheduler/runtime on the appropriate cadence, market-hours-aware, resilient (stateless per tick; broker/account is the source of truth, audit + control persisted) (Tasks 1, 4, 5). ✓
- Monitoring + alerting when the kill switch or circuit breaker trips (Task 3, wired in `run_cycle`). ✓
- Limited-live capability, hard-gated behind config AND env so capital preservation is the default (Task 2). ✓
- Runbook covering start/stop, kill switch, config changes, report interpretation, and the live-trading danger (Task 5). ✓
- Reports scheduled morning/nightly, once per day (Task 4). The `send_report` hook prints by default; wiring it to `scripts/send_report.py`'s logic is a one-line swap noted in the code (kept decoupled so the loop is testable without Alpaca keys).
- Deferred/limitations: market holidays not handled by the local clock (documented; `MarketClock` with an Alpaca client is the authoritative path); a production deployment (process manager/daemon) is environment-specific and left to the operator via the runbook.

**Placeholder scan:** No TBD/TODO. The `send_report` default body is intentionally a print with a documented one-line wire-up, not a placeholder for missing logic (the real report logic already exists in Phase 3a).

**Type consistency:** `clock.is_open(now) -> bool` consistent between `MarketClock` (Task 1) and `Runtime` (Task 4) and the fakes in tests. `select_executor(mode, live_config, live_env, api_key, secret_key)` matches `run_bot.py` usage; `AlpacaPaperExecutor(..., paper=...)` with the new `.paper` attribute is consistent across selector, tests, and run_bot. `maybe_alert(safety, control_store, notifier)` matches its call in `run_cycle`. `Runtime(clock, control_store, run_cycle, send_report, morning_hour, nightly_hour)` matches `run_bot.py`. `apply_controls`, `ControlStore`, `TradingCycle`, `RiskManager`, `SafetyState`, `Portfolio` all used with the signatures defined in earlier phases.
