# Phase 1: Data Layer + Backtesting Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the market-data ingestion layer and a backtesting harness so trading strategies can be validated against real historical data before any other component exists.

**Architecture:** A common OHLCV `Bar` domain model flows from an Alpaca historical-data client through a cache-through market-data service backed by SQLite. A backtest engine replays cached bars chronologically, feeds them to a `Strategy` via a fixed interface, simulates fills, and produces performance metrics. The `Strategy` interface and backtest engine defined here are the same ones Phase 2's live pipeline will reuse — one pipeline, swappable ends.

**Tech Stack:** Python 3.11+, `alpaca-py` (historical data), `pandas`, `pyyaml`, `python-dotenv`, `pytest`. SQLite via stdlib `sqlite3`.

## Global Constraints

- Python 3.11+ required.
- No secrets in code. Credentials load from `.env` only; `.env` is gitignored, `.env.example` is committed.
- No financial or operational parameter is hardcoded — all come from `config.yaml`.
- Paper-first: Phase 1 touches only historical data; no order placement of any kind.
- Tests must not make live network calls — the Alpaca client is mocked in tests.
- Universe (starter, overridable in config): SPY, QQQ, VTI, IWM, DIA, AAPL, MSFT, GOOGL, AMZN, JPM, JNJ, PG, KO, V.
- Starting capital default: $500.
- Every task ends with a commit using Conventional Commits style.

> **Environment note:** the sandboxed Linux environment was unavailable when this plan was written. The `Run: pytest ...` and `git` steps below must be executed once the environment is restored. Do not mark a step's checkbox until its command has actually run and produced the expected output.

---

## File Structure

```
Automate Trading Bot/
├── requirements.txt                      # pinned deps
├── .env.example                          # documents required secrets (no values)
├── config.yaml                           # all parameters (committed, no secrets)
├── README.md                             # setup + how to run a backtest
├── src/trading_bot/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   └── models.py                     # Action, Bar, Signal, Trade, BacktestResult
│   ├── config/
│   │   ├── __init__.py
│   │   └── loader.py                     # load_config(), load_secrets()
│   ├── data/
│   │   ├── __init__.py
│   │   ├── store.py                      # BarStore: SQLite cache (schema + r/w)
│   │   ├── alpaca_client.py              # AlpacaHistoricalClient: fetch + normalize
│   │   └── market_data.py                # MarketData: cache-through get_bars()
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py                       # Strategy ABC
│   │   └── sma_crossover.py              # reference strategy (validates the harness)
│   └── backtest/
│       ├── __init__.py
│       ├── engine.py                     # BacktestEngine: chronological replay
│       ├── metrics.py                    # compute_metrics()
│       └── report.py                     # render_report()
├── scripts/
│   └── run_backtest.py                   # CLI entrypoint
└── tests/
    ├── __init__.py
    ├── conftest.py                       # shared fixtures (sample bars, tmp db)
    ├── test_config_loader.py
    ├── test_models.py
    ├── test_bar_store.py
    ├── test_alpaca_client.py
    ├── test_market_data.py
    ├── test_sma_crossover.py
    ├── test_backtest_engine.py
    ├── test_metrics.py
    └── test_report.py
```

Each module has one responsibility. Files that change together (a module and its test) are introduced in the same task.

---

### Task 1: Project scaffold + config loader

**Files:**
- Create: `requirements.txt`, `.env.example`, `config.yaml`, `src/trading_bot/__init__.py`, `src/trading_bot/config/__init__.py`, `src/trading_bot/config/loader.py`, `tests/__init__.py`, `tests/test_config_loader.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_config(path: str = "config.yaml") -> dict`, `load_secrets() -> dict`. `load_config` raises `ValueError` if a required top-level key is missing. `load_secrets` reads `.env` into a dict via `python-dotenv` and returns `{"ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_PAPER"}`.

- [ ] **Step 1: Create `requirements.txt`**

```
alpaca-py==0.33.0
pandas==2.2.2
pyyaml==6.0.2
python-dotenv==1.0.1
pytest==8.3.2
```

- [ ] **Step 2: Create `.env.example`**

```
# Copy to .env and fill in. .env is gitignored — never commit real keys.
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_PAPER=true
```

- [ ] **Step 3: Create `config.yaml`**

```yaml
universe:
  - SPY
  - QQQ
  - VTI
  - IWM
  - DIA
  - AAPL
  - MSFT
  - GOOGL
  - AMZN
  - JPM
  - JNJ
  - PG
  - KO
  - V

capital:
  starting_cash: 500.0

data:
  timeframe: "1Day"
  cache_db: "market_data.sqlite"

backtest:
  start: "2023-01-01"
  end: "2024-01-01"

strategies:
  sma_crossover:
    fast: 20
    slow: 50
```

- [ ] **Step 4: Create empty package files**

Create `src/trading_bot/__init__.py`, `src/trading_bot/config/__init__.py`, and `tests/__init__.py` as empty files.

- [ ] **Step 5: Write the failing test**

```python
# tests/test_config_loader.py
import pytest
from trading_bot.config.loader import load_config


def test_load_config_returns_universe(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "universe: [SPY, AAPL]\n"
        "capital: {starting_cash: 500.0}\n"
        "data: {timeframe: '1Day', cache_db: 'x.sqlite'}\n"
        "backtest: {start: '2023-01-01', end: '2024-01-01'}\n"
        "strategies: {sma_crossover: {fast: 20, slow: 50}}\n"
    )
    cfg = load_config(str(cfg_file))
    assert cfg["universe"] == ["SPY", "AAPL"]
    assert cfg["capital"]["starting_cash"] == 500.0


def test_load_config_missing_required_key_raises(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("universe: [SPY]\n")  # missing capital/data/backtest/strategies
    with pytest.raises(ValueError):
        load_config(str(cfg_file))
```

- [ ] **Step 6: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_config_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.config.loader'`

- [ ] **Step 7: Write minimal implementation**

```python
# src/trading_bot/config/loader.py
import os
import yaml
from dotenv import dotenv_values

REQUIRED_KEYS = ("universe", "capital", "data", "backtest", "strategies")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        raise ValueError(f"config missing required keys: {missing}")
    return cfg


def load_secrets(path: str = ".env") -> dict:
    values = dotenv_values(path) if os.path.exists(path) else {}
    return {
        "ALPACA_API_KEY": values.get("ALPACA_API_KEY", ""),
        "ALPACA_SECRET_KEY": values.get("ALPACA_SECRET_KEY", ""),
        "ALPACA_PAPER": str(values.get("ALPACA_PAPER", "true")).lower() == "true",
    }
```

- [ ] **Step 8: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_config_loader.py -v`
Expected: PASS (2 passed)

- [ ] **Step 9: Commit**

```bash
git add requirements.txt .env.example config.yaml src/trading_bot tests
git commit -m "feat: project scaffold and config loader"
```

---

### Task 2: Domain models

**Files:**
- Create: `src/trading_bot/domain/__init__.py`, `src/trading_bot/domain/models.py`, `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class Action(str, Enum)` with `BUY = "BUY"`, `SELL = "SELL"`, `HOLD = "HOLD"`.
  - `@dataclass(frozen=True) Bar`: `symbol: str`, `timestamp: datetime`, `open: float`, `high: float`, `low: float`, `close: float`, `volume: float`.
  - `@dataclass(frozen=True) Signal`: `symbol: str`, `action: Action`, `confidence: float`, `rationale: str`. Raises `ValueError` in `__post_init__` if `confidence` not in `[0.0, 1.0]`.
  - `@dataclass(frozen=True) Trade`: `symbol: str`, `entry_time: datetime`, `exit_time: datetime`, `entry_price: float`, `exit_price: float`, `qty: float`. Property `pnl -> float` = `(exit_price - entry_price) * qty`.
  - `@dataclass BacktestResult`: `equity_curve: list[tuple[datetime, float]]`, `trades: list[Trade]`, `starting_cash: float`, `ending_equity: float`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from datetime import datetime
import pytest
from trading_bot.domain.models import Action, Bar, Signal, Trade


def test_signal_rejects_out_of_range_confidence():
    with pytest.raises(ValueError):
        Signal(symbol="AAPL", action=Action.BUY, confidence=1.5, rationale="x")


def test_signal_accepts_valid_confidence():
    s = Signal(symbol="AAPL", action=Action.BUY, confidence=0.7, rationale="x")
    assert s.action == Action.BUY


def test_trade_pnl():
    t = Trade(
        symbol="AAPL",
        entry_time=datetime(2023, 1, 1),
        exit_time=datetime(2023, 1, 5),
        entry_price=100.0,
        exit_price=110.0,
        qty=2.0,
    )
    assert t.pnl == 20.0


def test_bar_fields():
    b = Bar("SPY", datetime(2023, 1, 1), 1, 2, 0.5, 1.5, 1000)
    assert b.close == 1.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.domain.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/domain/models.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_models.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Create `src/trading_bot/domain/__init__.py`** (empty file)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/domain tests/test_models.py
git commit -m "feat: domain models (Bar, Signal, Trade, BacktestResult)"
```

---

### Task 3: SQLite bar store (historical cache)

**Files:**
- Create: `src/trading_bot/data/__init__.py`, `src/trading_bot/data/store.py`, `tests/test_bar_store.py`, `tests/conftest.py`

**Interfaces:**
- Consumes: `Bar` from Task 2.
- Produces: `class BarStore`:
  - `__init__(self, db_path: str)` — opens/creates SQLite DB and ensures schema.
  - `save_bars(self, bars: list[Bar]) -> None` — idempotent upsert keyed on `(symbol, timestamp)`.
  - `get_bars(self, symbol: str, start: datetime, end: datetime) -> list[Bar]` — inclusive range, ordered by timestamp ascending.

- [ ] **Step 1: Create shared fixtures**

```python
# tests/conftest.py
from datetime import datetime, timedelta
import pytest
from trading_bot.domain.models import Bar


@pytest.fixture
def sample_bars():
    base = datetime(2023, 1, 1)
    out = []
    price = 100.0
    for i in range(10):
        out.append(
            Bar(
                symbol="AAPL",
                timestamp=base + timedelta(days=i),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price + 0.5,
                volume=1_000_000,
            )
        )
        price += 1.0
    return out
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_bar_store.py
from datetime import datetime
from trading_bot.data.store import BarStore


def test_save_and_get_round_trip(tmp_path, sample_bars):
    store = BarStore(str(tmp_path / "t.sqlite"))
    store.save_bars(sample_bars)
    got = store.get_bars("AAPL", datetime(2023, 1, 1), datetime(2023, 1, 10))
    assert len(got) == 10
    assert got[0].timestamp < got[-1].timestamp
    assert got[0].close == sample_bars[0].close


def test_save_is_idempotent(tmp_path, sample_bars):
    store = BarStore(str(tmp_path / "t.sqlite"))
    store.save_bars(sample_bars)
    store.save_bars(sample_bars)  # second save must not duplicate
    got = store.get_bars("AAPL", datetime(2023, 1, 1), datetime(2023, 1, 10))
    assert len(got) == 10
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_bar_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.data.store'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/trading_bot/data/store.py
import sqlite3
from datetime import datetime
from trading_bot.domain.models import Bar


class BarStore:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bars (
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                PRIMARY KEY (symbol, timestamp)
            )
            """
        )
        self.conn.commit()

    def save_bars(self, bars: list) -> None:
        rows = [
            (b.symbol, b.timestamp.isoformat(), b.open, b.high, b.low, b.close, b.volume)
            for b in bars
        ]
        self.conn.executemany(
            "INSERT OR REPLACE INTO bars "
            "(symbol, timestamp, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()

    def get_bars(self, symbol: str, start: datetime, end: datetime) -> list:
        cur = self.conn.execute(
            "SELECT symbol, timestamp, open, high, low, close, volume FROM bars "
            "WHERE symbol = ? AND timestamp >= ? AND timestamp <= ? "
            "ORDER BY timestamp ASC",
            (symbol, start.isoformat(), end.isoformat()),
        )
        return [
            Bar(
                symbol=r[0],
                timestamp=datetime.fromisoformat(r[1]),
                open=r[2], high=r[3], low=r[4], close=r[5], volume=r[6],
            )
            for r in cur.fetchall()
        ]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_bar_store.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Create `src/trading_bot/data/__init__.py`** (empty file)

- [ ] **Step 7: Commit**

```bash
git add src/trading_bot/data/__init__.py src/trading_bot/data/store.py tests/test_bar_store.py tests/conftest.py
git commit -m "feat: SQLite bar store with idempotent upsert"
```

---

### Task 4: Alpaca historical client + normalization

**Files:**
- Create: `src/trading_bot/data/alpaca_client.py`, `tests/test_alpaca_client.py`

**Interfaces:**
- Consumes: `Bar` from Task 2.
- Produces: `class AlpacaHistoricalClient`:
  - `__init__(self, api_key: str, secret_key: str, _data_client=None)` — `_data_client` is an injection seam for tests; in production it builds `alpaca.data.historical.StockHistoricalDataClient`.
  - `fetch_bars(self, symbol: str, start: datetime, end: datetime, timeframe: str) -> list[Bar]` — calls the data client and normalizes the response to `list[Bar]` ordered ascending.
  - Module function `_normalize(symbol, raw_rows) -> list[Bar]` where each `raw_row` has attributes `timestamp, open, high, low, close, volume`.

- [ ] **Step 1: Write the failing test (mocked client — no network)**

```python
# tests/test_alpaca_client.py
from datetime import datetime
from types import SimpleNamespace
from trading_bot.data.alpaca_client import AlpacaHistoricalClient


class _FakeDataClient:
    def get_stock_bars(self, request):
        rows = [
            SimpleNamespace(timestamp=datetime(2023, 1, 2), open=1, high=2,
                            low=0.5, close=1.5, volume=100),
            SimpleNamespace(timestamp=datetime(2023, 1, 1), open=1, high=2,
                            low=0.5, close=1.4, volume=110),
        ]
        return SimpleNamespace(data={"AAPL": rows})


def test_fetch_bars_normalizes_and_sorts():
    client = AlpacaHistoricalClient("k", "s", _data_client=_FakeDataClient())
    bars = client.fetch_bars("AAPL", datetime(2023, 1, 1), datetime(2023, 1, 2), "1Day")
    assert [b.timestamp for b in bars] == [datetime(2023, 1, 1), datetime(2023, 1, 2)]
    assert bars[0].symbol == "AAPL"
    assert bars[1].close == 1.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_alpaca_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.data.alpaca_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/data/alpaca_client.py
from datetime import datetime
from trading_bot.domain.models import Bar

_TIMEFRAME_MAP = {"1Day": "1Day", "1Hour": "1Hour", "1Min": "1Min"}


def _normalize(symbol: str, raw_rows: list) -> list:
    bars = [
        Bar(
            symbol=symbol,
            timestamp=r.timestamp,
            open=float(r.open),
            high=float(r.high),
            low=float(r.low),
            close=float(r.close),
            volume=float(r.volume),
        )
        for r in raw_rows
    ]
    bars.sort(key=lambda b: b.timestamp)
    return bars


class AlpacaHistoricalClient:
    def __init__(self, api_key: str, secret_key: str, _data_client=None):
        if _data_client is not None:
            self._client = _data_client
        else:
            from alpaca.data.historical import StockHistoricalDataClient
            self._client = StockHistoricalDataClient(api_key, secret_key)

    def fetch_bars(self, symbol: str, start: datetime, end: datetime,
                   timeframe: str) -> list:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        tf = getattr(TimeFrame, "Day") if timeframe == "1Day" else TimeFrame.Day
        request = StockBarsRequest(
            symbol_or_symbols=symbol, timeframe=tf, start=start, end=end
        )
        resp = self._client.get_stock_bars(request)
        raw_rows = resp.data.get(symbol, [])
        return _normalize(symbol, raw_rows)
```

> Note: the `alpaca.*` imports are inside methods so tests using `_data_client` never import the SDK. The `StockBarsRequest`/`TimeFrame` import in `fetch_bars` only runs in production paths; tests inject a fake whose `get_stock_bars` ignores the request object, so the request construction is exercised but not asserted on. If running this test before `alpaca-py` is installed, the in-method import would still trigger — therefore install requirements (Task 1) before running this task's tests.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_alpaca_client.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/data/alpaca_client.py tests/test_alpaca_client.py
git commit -m "feat: Alpaca historical client with bar normalization"
```

---

### Task 5: Market-data service (cache-through)

**Files:**
- Create: `src/trading_bot/data/market_data.py`, `tests/test_market_data.py`

**Interfaces:**
- Consumes: `BarStore` (Task 3), `AlpacaHistoricalClient` (Task 4), `Bar` (Task 2).
- Produces: `class MarketData`:
  - `__init__(self, store: BarStore, client, timeframe: str)`.
  - `get_bars(self, symbol: str, start: datetime, end: datetime) -> list[Bar]` — returns cached bars if the store already covers the range; otherwise fetches via the client, saves to the store, and returns. "Covers" = store returns at least one bar AND its first bar ≤ start-window and last bar ≥ end-window is not required for Phase 1; use the simpler rule: if the store returns any bars for the exact range, treat as a hit. (Refinement deferred — YAGNI.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_market_data.py
from datetime import datetime
from trading_bot.data.market_data import MarketData
from trading_bot.domain.models import Bar


class _SpyClient:
    def __init__(self, bars):
        self.bars = bars
        self.calls = 0

    def fetch_bars(self, symbol, start, end, timeframe):
        self.calls += 1
        return self.bars


class _FakeStore:
    def __init__(self):
        self.saved = []
        self._data = []

    def get_bars(self, symbol, start, end):
        return list(self._data)

    def save_bars(self, bars):
        self.saved.extend(bars)
        self._data.extend(bars)


def _bar(day):
    return Bar("AAPL", datetime(2023, 1, day), 1, 2, 0.5, 1.5, 100)


def test_cache_miss_fetches_and_saves():
    store = _FakeStore()
    client = _SpyClient([_bar(1), _bar(2)])
    md = MarketData(store, client, "1Day")
    out = md.get_bars("AAPL", datetime(2023, 1, 1), datetime(2023, 1, 2))
    assert client.calls == 1
    assert len(out) == 2
    assert len(store.saved) == 2


def test_cache_hit_does_not_fetch():
    store = _FakeStore()
    store._data = [_bar(1), _bar(2)]
    client = _SpyClient([])
    md = MarketData(store, client, "1Day")
    out = md.get_bars("AAPL", datetime(2023, 1, 1), datetime(2023, 1, 2))
    assert client.calls == 0
    assert len(out) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_market_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.data.market_data'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/data/market_data.py
from datetime import datetime


class MarketData:
    def __init__(self, store, client, timeframe: str):
        self.store = store
        self.client = client
        self.timeframe = timeframe

    def get_bars(self, symbol: str, start: datetime, end: datetime) -> list:
        cached = self.store.get_bars(symbol, start, end)
        if cached:
            return cached
        fetched = self.client.fetch_bars(symbol, start, end, self.timeframe)
        self.store.save_bars(fetched)
        return fetched
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_market_data.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/data/market_data.py tests/test_market_data.py
git commit -m "feat: cache-through market-data service"
```

---

### Task 6: Strategy interface + SMA crossover reference strategy

**Files:**
- Create: `src/trading_bot/strategies/__init__.py`, `src/trading_bot/strategies/base.py`, `src/trading_bot/strategies/sma_crossover.py`, `tests/test_sma_crossover.py`

**Interfaces:**
- Consumes: `Bar`, `Signal`, `Action` (Task 2).
- Produces:
  - `class Strategy(ABC)` with `@abstractmethod generate_signal(self, symbol: str, history: list[Bar]) -> Signal`. `history` is ascending by time; the latest bar is `history[-1]`.
  - `class SmaCrossover(Strategy)`: `__init__(self, fast: int, slow: int)`. Emits `BUY` when the fast SMA crosses above the slow SMA on the latest bar, `SELL` when it crosses below, else `HOLD`. Confidence = `min(1.0, abs(fast_sma - slow_sma) / slow_sma)`. Returns `HOLD` with confidence 0.0 if `len(history) < slow + 1`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sma_crossover.py
from datetime import datetime, timedelta
from trading_bot.domain.models import Bar, Action
from trading_bot.strategies.sma_crossover import SmaCrossover


def _series(closes):
    base = datetime(2023, 1, 1)
    return [
        Bar("AAPL", base + timedelta(days=i), c, c, c, c, 100)
        for i, c in enumerate(closes)
    ]


def test_hold_when_insufficient_history():
    strat = SmaCrossover(fast=2, slow=3)
    sig = strat.generate_signal("AAPL", _series([10, 11]))
    assert sig.action == Action.HOLD
    assert sig.confidence == 0.0


def test_buy_on_upward_cross():
    strat = SmaCrossover(fast=2, slow=3)
    # rising series: fast SMA crosses above slow SMA
    sig = strat.generate_signal("AAPL", _series([10, 9, 8, 9, 12]))
    assert sig.action == Action.BUY


def test_sell_on_downward_cross():
    strat = SmaCrossover(fast=2, slow=3)
    sig = strat.generate_signal("AAPL", _series([8, 9, 10, 9, 6]))
    assert sig.action == Action.SELL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_sma_crossover.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.strategies.sma_crossover'`

- [ ] **Step 3: Write the base interface**

```python
# src/trading_bot/strategies/base.py
from abc import ABC, abstractmethod
from trading_bot.domain.models import Bar, Signal


class Strategy(ABC):
    @abstractmethod
    def generate_signal(self, symbol: str, history: list) -> Signal:
        ...
```

- [ ] **Step 4: Write the SMA crossover implementation**

```python
# src/trading_bot/strategies/sma_crossover.py
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_sma_crossover.py -v`
Expected: PASS (3 passed). If `test_buy_on_upward_cross` or `test_sell_on_downward_cross` fails, print the fast/slow SMA values for the last two bars and adjust the test series so a cross actually occurs — the implementation is the source of truth for the cross definition.

- [ ] **Step 6: Create `src/trading_bot/strategies/__init__.py`** (empty file)

- [ ] **Step 7: Commit**

```bash
git add src/trading_bot/strategies tests/test_sma_crossover.py
git commit -m "feat: Strategy interface and SMA crossover reference strategy"
```

---

### Task 7: Backtest engine (chronological replay)

**Files:**
- Create: `src/trading_bot/backtest/__init__.py`, `src/trading_bot/backtest/engine.py`, `tests/test_backtest_engine.py`

**Interfaces:**
- Consumes: `Strategy` (Task 6), `Bar`, `Action`, `Trade`, `BacktestResult` (Task 2).
- Produces: `class BacktestEngine`:
  - `__init__(self, starting_cash: float)`.
  - `run(self, symbol: str, bars: list[Bar], strategy: Strategy) -> BacktestResult`.
  - Semantics (single-symbol, long-only, all-in/all-out for Phase 1 simplicity): iterate bars ascending; at each step pass `bars[:i+1]` as history to `strategy.generate_signal`. On `BUY` while flat: buy `cash / close` shares at that bar's close (fractional allowed), record entry. On `SELL` while long: sell all shares at close, record a `Trade`. Mark-to-market equity = `cash + shares * close` recorded to the equity curve each bar. At the end, force-close any open position at the last close.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backtest_engine.py
from datetime import datetime, timedelta
from trading_bot.domain.models import Bar, Action, Signal
from trading_bot.strategies.base import Strategy
from trading_bot.backtest.engine import BacktestEngine


class _Scripted(Strategy):
    """Emits a fixed action per bar index based on a script list."""
    def __init__(self, script):
        self.script = script

    def generate_signal(self, symbol, history):
        action = self.script[len(history) - 1]
        return Signal(symbol, action, 1.0, "scripted")


def _bars(closes):
    base = datetime(2023, 1, 1)
    return [Bar("AAPL", base + timedelta(days=i), c, c, c, c, 100)
            for i, c in enumerate(closes)]


def test_buy_then_sell_realizes_profit():
    bars = _bars([10, 10, 20])
    script = [Action.BUY, Action.HOLD, Action.SELL]
    engine = BacktestEngine(starting_cash=100.0)
    result = engine.run("AAPL", bars, _Scripted(script))
    # bought 10 shares at 10 (=100), sold at 20 (=200)
    assert result.ending_equity == 200.0
    assert len(result.trades) == 1
    assert result.trades[0].pnl == 100.0


def test_open_position_force_closed_at_end():
    bars = _bars([10, 10, 15])
    script = [Action.BUY, Action.HOLD, Action.HOLD]
    engine = BacktestEngine(starting_cash=100.0)
    result = engine.run("AAPL", bars, _Scripted(script))
    assert result.ending_equity == 150.0
    assert len(result.trades) == 1


def test_equity_curve_has_one_point_per_bar():
    bars = _bars([10, 11, 12])
    script = [Action.HOLD, Action.HOLD, Action.HOLD]
    engine = BacktestEngine(starting_cash=100.0)
    result = engine.run("AAPL", bars, _Scripted(script))
    assert len(result.equity_curve) == 3
    assert result.ending_equity == 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_backtest_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.backtest.engine'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/backtest/engine.py
from trading_bot.domain.models import Action, Trade, BacktestResult


class BacktestEngine:
    def __init__(self, starting_cash: float):
        self.starting_cash = starting_cash

    def run(self, symbol: str, bars: list, strategy) -> BacktestResult:
        cash = self.starting_cash
        shares = 0.0
        entry_price = 0.0
        entry_time = None
        trades = []
        equity_curve = []

        for i, bar in enumerate(bars):
            history = bars[: i + 1]
            sig = strategy.generate_signal(symbol, history)
            if sig.action == Action.BUY and shares == 0.0 and cash > 0:
                shares = cash / bar.close
                entry_price = bar.close
                entry_time = bar.timestamp
                cash = 0.0
            elif sig.action == Action.SELL and shares > 0.0:
                cash = shares * bar.close
                trades.append(
                    Trade(symbol, entry_time, bar.timestamp,
                          entry_price, bar.close, shares)
                )
                shares = 0.0
            equity = cash + shares * bar.close
            equity_curve.append((bar.timestamp, equity))

        if shares > 0.0:
            last = bars[-1]
            cash = shares * last.close
            trades.append(
                Trade(symbol, entry_time, last.timestamp,
                      entry_price, last.close, shares)
            )
            shares = 0.0
            equity_curve[-1] = (last.timestamp, cash)

        return BacktestResult(
            equity_curve=equity_curve,
            trades=trades,
            starting_cash=self.starting_cash,
            ending_equity=equity_curve[-1][1] if equity_curve else self.starting_cash,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_backtest_engine.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Create `src/trading_bot/backtest/__init__.py`** (empty file)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/backtest/__init__.py src/trading_bot/backtest/engine.py tests/test_backtest_engine.py
git commit -m "feat: chronological backtest replay engine"
```

---

### Task 8: Performance metrics

**Files:**
- Create: `src/trading_bot/backtest/metrics.py`, `tests/test_metrics.py`

**Interfaces:**
- Consumes: `BacktestResult` (Task 2).
- Produces: `compute_metrics(result: BacktestResult) -> dict` with keys:
  - `total_return` = `(ending_equity / starting_cash) - 1`.
  - `max_drawdown` = largest peak-to-trough fractional decline in the equity curve (a non-positive float, or 0.0 if never declines).
  - `sharpe` = `mean(daily_returns) / std(daily_returns) * sqrt(252)`; `0.0` if fewer than 2 points or zero std.
  - `win_rate` = fraction of trades with `pnl > 0`; `0.0` if no trades.
  - `num_trades` = `len(result.trades)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_metrics.py
import math
from datetime import datetime, timedelta
from trading_bot.domain.models import BacktestResult, Trade
from trading_bot.backtest.metrics import compute_metrics


def _curve(values):
    base = datetime(2023, 1, 1)
    return [(base + timedelta(days=i), v) for i, v in enumerate(values)]


def test_total_return():
    r = BacktestResult(equity_curve=_curve([100, 150]),
                       starting_cash=100.0, ending_equity=150.0)
    m = compute_metrics(r)
    assert m["total_return"] == 0.5


def test_max_drawdown():
    r = BacktestResult(equity_curve=_curve([100, 120, 60, 90]),
                       starting_cash=100.0, ending_equity=90.0)
    m = compute_metrics(r)
    # peak 120 -> trough 60 = -0.5
    assert math.isclose(m["max_drawdown"], -0.5, rel_tol=1e-9)


def test_win_rate():
    t_win = Trade("A", datetime(2023, 1, 1), datetime(2023, 1, 2), 10, 12, 1)
    t_loss = Trade("A", datetime(2023, 1, 3), datetime(2023, 1, 4), 10, 8, 1)
    r = BacktestResult(equity_curve=_curve([100, 100]), trades=[t_win, t_loss],
                       starting_cash=100.0, ending_equity=100.0)
    m = compute_metrics(r)
    assert m["win_rate"] == 0.5
    assert m["num_trades"] == 2


def test_sharpe_zero_when_flat():
    r = BacktestResult(equity_curve=_curve([100, 100, 100]),
                       starting_cash=100.0, ending_equity=100.0)
    m = compute_metrics(r)
    assert m["sharpe"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.backtest.metrics'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/backtest/metrics.py
import math


def compute_metrics(result) -> dict:
    curve = [v for _, v in result.equity_curve]
    starting = result.starting_cash
    ending = result.ending_equity

    total_return = (ending / starting) - 1 if starting else 0.0

    max_dd = 0.0
    peak = curve[0] if curve else 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            dd = (v - peak) / peak
            max_dd = min(max_dd, dd)

    if len(curve) >= 2:
        rets = [(curve[i] / curve[i - 1]) - 1 for i in range(1, len(curve))
                if curve[i - 1] != 0]
        if len(rets) >= 1:
            mean = sum(rets) / len(rets)
            var = sum((r - mean) ** 2 for r in rets) / len(rets)
            std = math.sqrt(var)
            sharpe = (mean / std * math.sqrt(252)) if std > 0 else 0.0
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    trades = result.trades
    wins = sum(1 for t in trades if t.pnl > 0)
    win_rate = (wins / len(trades)) if trades else 0.0

    return {
        "total_return": total_return,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "win_rate": win_rate,
        "num_trades": len(trades),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_metrics.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/backtest/metrics.py tests/test_metrics.py
git commit -m "feat: backtest performance metrics"
```

---

### Task 9: Report renderer + backtest CLI

**Files:**
- Create: `src/trading_bot/backtest/report.py`, `scripts/run_backtest.py`, `tests/test_report.py`

**Interfaces:**
- Consumes: `compute_metrics` (Task 8), `BacktestResult` (Task 2), `load_config`/`load_secrets` (Task 1), `BarStore`, `AlpacaHistoricalClient`, `MarketData`, `SmaCrossover`, `BacktestEngine`.
- Produces:
  - `render_report(symbol: str, result: BacktestResult, metrics: dict) -> str` — a Markdown string containing the symbol, starting cash, ending equity, and each metric formatted to a readable precision.
  - `scripts/run_backtest.py` — CLI: reads `config.yaml` + `.env`, builds the data stack, fetches bars for one symbol over the configured window, runs `SmaCrossover`, prints the report. Usage: `python scripts/run_backtest.py SPY`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
from datetime import datetime
from trading_bot.domain.models import BacktestResult
from trading_bot.backtest.report import render_report


def test_render_report_contains_key_fields():
    r = BacktestResult(equity_curve=[(datetime(2023, 1, 1), 100.0)],
                       starting_cash=100.0, ending_equity=125.0)
    metrics = {"total_return": 0.25, "max_drawdown": -0.1,
               "sharpe": 1.2, "win_rate": 0.6, "num_trades": 5}
    out = render_report("SPY", r, metrics)
    assert "SPY" in out
    assert "125" in out
    assert "Total return" in out
    assert "Max drawdown" in out
    assert "Sharpe" in out
    assert "Win rate" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.backtest.report'`

- [ ] **Step 3: Write the report renderer**

```python
# src/trading_bot/backtest/report.py
def render_report(symbol: str, result, metrics: dict) -> str:
    lines = [
        f"# Backtest report: {symbol}",
        "",
        f"- Starting cash: ${result.starting_cash:,.2f}",
        f"- Ending equity: ${result.ending_equity:,.2f}",
        f"- Total return: {metrics['total_return'] * 100:.2f}%",
        f"- Max drawdown: {metrics['max_drawdown'] * 100:.2f}%",
        f"- Sharpe: {metrics['sharpe']:.2f}",
        f"- Win rate: {metrics['win_rate'] * 100:.2f}%",
        f"- Number of trades: {metrics['num_trades']}",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_report.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Write the CLI entrypoint**

```python
# scripts/run_backtest.py
import sys
from datetime import datetime

from trading_bot.config.loader import load_config, load_secrets
from trading_bot.data.store import BarStore
from trading_bot.data.alpaca_client import AlpacaHistoricalClient
from trading_bot.data.market_data import MarketData
from trading_bot.strategies.sma_crossover import SmaCrossover
from trading_bot.backtest.engine import BacktestEngine
from trading_bot.backtest.metrics import compute_metrics
from trading_bot.backtest.report import render_report


def main(symbol: str) -> None:
    cfg = load_config("config.yaml")
    secrets = load_secrets(".env")
    store = BarStore(cfg["data"]["cache_db"])
    client = AlpacaHistoricalClient(secrets["ALPACA_API_KEY"],
                                    secrets["ALPACA_SECRET_KEY"])
    md = MarketData(store, client, cfg["data"]["timeframe"])
    start = datetime.fromisoformat(cfg["backtest"]["start"])
    end = datetime.fromisoformat(cfg["backtest"]["end"])
    bars = md.get_bars(symbol, start, end)

    sma_cfg = cfg["strategies"]["sma_crossover"]
    strat = SmaCrossover(fast=sma_cfg["fast"], slow=sma_cfg["slow"])
    engine = BacktestEngine(starting_cash=cfg["capital"]["starting_cash"])
    result = engine.run(symbol, bars, strat)
    metrics = compute_metrics(result)
    print(render_report(symbol, result, metrics))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/run_backtest.py SYMBOL")
        sys.exit(1)
    main(sys.argv[1])
```

- [ ] **Step 6: Run the full suite + smoke-test the CLI**

Run: `PYTHONPATH=src pytest -v`
Expected: PASS (all tests across all task files).

Then, with `.env` populated with real Alpaca paper keys:
Run: `PYTHONPATH=src python scripts/run_backtest.py SPY`
Expected: a Markdown backtest report printed for SPY over the configured window. (Requires the sandbox/network + valid keys; if keys are absent, skip this sub-step and note it.)

- [ ] **Step 7: Commit**

```bash
git add src/trading_bot/backtest/report.py scripts/run_backtest.py tests/test_report.py
git commit -m "feat: backtest report renderer and CLI entrypoint"
```

---

### Task 10: README + verification sweep

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: setup + run documentation.

- [ ] **Step 1: Write `README.md`**

```markdown
# Multi-Strategy Automated Trading System

Paper-first, config-driven automated trading for US equities & ETFs on Alpaca.
**Phase 1** (this state): market-data ingestion + backtesting harness.

## Setup

1. Python 3.11+
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in Alpaca **paper** keys.
4. Review `config.yaml` (universe, capital, backtest window, strategy params).

## Run a backtest

```bash
PYTHONPATH=src python scripts/run_backtest.py SPY
```

## Run tests

```bash
PYTHONPATH=src pytest -v
```

## Safety

- Phase 1 reads historical data only; it places no orders.
- Secrets live in `.env` (gitignored). Never commit real keys.
- All financial parameters live in `config.yaml`; nothing is hardcoded.
```

- [ ] **Step 2: Run the full test suite**

Run: `PYTHONPATH=src pytest -v`
Expected: PASS (all tests).

- [ ] **Step 3: Verify no secrets are tracked by git**

Run: `git ls-files | grep -E '(^|/)\.env$' || echo "OK: .env not tracked"`
Expected: `OK: .env not tracked`

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: Phase 1 README and setup instructions"
```

---

## Self-Review (completed by plan author)

**Spec coverage (Phase 1 scope only):**
- Market data layer — ingest historical (Task 4), normalize to common format (Task 4 `_normalize` + `Bar`), cache for backtesting (Tasks 3, 5). ✓
- Backtesting harness — replay through a strategy (Task 7), metrics: return/max drawdown/Sharpe/win rate (Task 8), report (Task 9). ✓
- Strategy interface (pluggable) — defined in Task 6; Phase 2 reuses it. ✓
- No secrets in code / config-driven / paper-first — Tasks 1, 10 + Global Constraints. ✓
- Items intentionally deferred to later phases: live/paper execution, decision/aggregation layer, risk module, portfolio reconciliation, reporting email, dashboard, scheduler, monitoring. These belong to Phases 2–6 and are out of scope here.

**Placeholder scan:** no TBD/TODO; every code step contains complete code. ✓

**Type consistency:** `Bar`, `Signal`, `Action`, `Trade`, `BacktestResult` signatures are defined in Task 2 and used unchanged in Tasks 3–9. `generate_signal(symbol, history) -> Signal` consistent between Task 6 definition and Tasks 7, 9 usage. `compute_metrics(result) -> dict` keys defined in Task 8 match `render_report` usage in Task 9. ✓
