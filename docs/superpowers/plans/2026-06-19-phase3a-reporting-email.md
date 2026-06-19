# Phase 3a: Reporting + Email Delivery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate morning and nightly portfolio analysis reports (positions, P&L, exposure, what the bot did and why, alerts) and deliver them by email, with a pluggable notifier so console/Slack can be added later.

**Architecture:** A report builder turns a portfolio snapshot plus recent audit activity into a subject + plaintext + HTML body. A `Notifier` interface delivers it; `EmailNotifier` (SMTP) is primary, `ConsoleNotifier` is the keyless default. An `AlpacaAccountReader` provides the snapshot from the paper account (source of truth), and new `AuditLog` query methods supply the "what the bot did" section. A CLI ties it together for `morning`/`nightly` runs (a scheduler will call it in Phase 6).

**Tech Stack:** Python 3.10+, stdlib `smtplib`/`email`, `alpaca-py` (account read), `pytest`. Builds on Phases 1–2b.

## Global Constraints

- Python 3.10+ (sandbox 3.10.12; no 3.11+ syntax).
- No secrets in code; SMTP + Alpaca creds load from `.env`. Credentials are never logged or included in report bodies.
- No parameter hardcoded — recipient, SMTP host/port, and report settings come from `config.yaml`/`.env`.
- Tests must not send real email or hit the network — `EmailNotifier` takes an injected SMTP client, `AlpacaAccountReader` takes an injected trading client.
- Run pytest with Linux-local temp: `PYTHONPATH=src python -m pytest -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`.
- **Mount caveat:** modifying an existing file (`config.yaml`, `.env.example`, `README.md`) may not sync through the mount; verify with `wc -l`/`grep` and append/rewrite from the shell if needed. New files persist normally.
- Commits run where git is available (user's Windows machine); stage the listed files per task.

---

## File Structure

```
src/trading_bot/
├── audit/
│   └── audit_log.py          # MODIFY: add recent_decisions(), recent_fills(), recent_events()
├── reporting/
│   ├── __init__.py           # NEW
│   ├── snapshot.py           # NEW: portfolio_snapshot(); AccountSnapshot dataclass
│   ├── account_reader.py     # NEW: AlpacaAccountReader (paper account -> snapshot)
│   └── report_builder.py     # NEW: build_report(kind, snapshot, activity)
├── notify/
│   ├── __init__.py           # NEW
│   ├── base.py               # NEW: Notifier ABC
│   ├── console_notifier.py   # NEW: ConsoleNotifier
│   └── email_notifier.py     # NEW: EmailNotifier (SMTP)
scripts/
└── send_report.py            # NEW: CLI — build + send morning|nightly report
config.yaml                   # MODIFY: add `reporting` section
.env.example                  # MODIFY: add SMTP_* and REPORT_TO_EMAIL
tests/
├── test_audit_queries.py
├── test_snapshot.py
├── test_account_reader.py
├── test_report_builder.py
├── test_console_notifier.py
└── test_email_notifier.py
```

---

### Task 1: Audit query methods

**Files:**
- Modify: `src/trading_bot/audit/audit_log.py` (add three read methods)
- Test: `tests/test_audit_queries.py` (Create)

**Interfaces:**
- Consumes: existing `AuditLog` tables (Phase 2b).
- Produces (append methods to `AuditLog`):
  - `recent_decisions(self, limit: int = 20) -> list[dict]` — most recent rows from `decisions`, newest first, each `{run_id, ts, symbol, action, net_score, consensus_met, rationale}`.
  - `recent_fills(self, limit: int = 20) -> list[dict]` — from `fills`, each `{run_id, ts, order_id, symbol, side, qty, price}`.
  - `recent_events(self, limit: int = 20) -> list[dict]` — from `events`, each `{run_id, ts, kind, detail}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_audit_queries.py
from datetime import datetime
from trading_bot.audit.audit_log import AuditLog
from trading_bot.domain.models import Action, Signal, Decision, Order, OrderSide, Fill


def test_recent_queries_return_rows(tmp_path):
    log = AuditLog(str(tmp_path / "audit.sqlite"))
    log.log_decision("r1", Decision("AAPL", Action.BUY, 0.8, True, "because", []))
    log.log_fill("r1", Fill("o1", "AAPL", OrderSide.BUY, 2.0, 50.0, datetime(2023, 1, 1)))
    log.log_event("r1", "circuit_breaker", "tripped")

    decs = log.recent_decisions(limit=10)
    assert len(decs) == 1
    assert decs[0]["symbol"] == "AAPL"
    assert decs[0]["action"] == "BUY"

    fills = log.recent_fills(limit=10)
    assert fills[0]["qty"] == 2.0

    events = log.recent_events(limit=10)
    assert events[0]["kind"] == "circuit_breaker"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_audit_queries.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `AttributeError: 'AuditLog' object has no attribute 'recent_decisions'`

- [ ] **Step 3: Append methods to `AuditLog`**

```python
    def recent_decisions(self, limit: int = 20) -> list:
        cur = self.conn.execute(
            "SELECT run_id, ts, symbol, action, net_score, consensus_met, rationale "
            "FROM decisions ORDER BY ts DESC LIMIT ?", (limit,))
        cols = ["run_id", "ts", "symbol", "action", "net_score",
                "consensus_met", "rationale"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def recent_fills(self, limit: int = 20) -> list:
        cur = self.conn.execute(
            "SELECT run_id, ts, order_id, symbol, side, qty, price "
            "FROM fills ORDER BY ts DESC LIMIT ?", (limit,))
        cols = ["run_id", "ts", "order_id", "symbol", "side", "qty", "price"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def recent_events(self, limit: int = 20) -> list:
        cur = self.conn.execute(
            "SELECT run_id, ts, kind, detail "
            "FROM events ORDER BY ts DESC LIMIT ?", (limit,))
        cols = ["run_id", "ts", "kind", "detail"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
```

Verify it reached disk: `grep -n "def recent_decisions" src/trading_bot/audit/audit_log.py`. If absent, append from the shell.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_audit_queries.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/audit/audit_log.py tests/test_audit_queries.py
git commit -m "feat: audit log query methods for reporting"
```

---

### Task 2: Portfolio snapshot

**Files:**
- Create: `src/trading_bot/reporting/__init__.py`, `src/trading_bot/reporting/snapshot.py`, `tests/test_snapshot.py`

**Interfaces:**
- Consumes: `Portfolio` (Phase 2a).
- Produces:
  - `@dataclass AccountSnapshot`: `cash: float`, `equity: float`, `exposure: float`, `realized_pnl: float`, `positions: list` (each `{symbol, qty, avg_cost, price, market_value, unrealized_pnl}`).
  - `portfolio_snapshot(portfolio, prices: dict) -> AccountSnapshot` — builds the snapshot from a `Portfolio` and a prices dict.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_snapshot.py
from trading_bot.portfolio.portfolio import Portfolio
from trading_bot.domain.models import OrderSide
from trading_bot.reporting.snapshot import portfolio_snapshot, AccountSnapshot


def test_snapshot_fields():
    pf = Portfolio(1000.0)
    pf.apply_fill("AAPL", OrderSide.BUY, qty=2.0, price=100.0)
    snap = portfolio_snapshot(pf, {"AAPL": 110.0})
    assert isinstance(snap, AccountSnapshot)
    assert snap.cash == 800.0
    assert snap.equity == 800.0 + 220.0
    assert snap.positions[0]["symbol"] == "AAPL"
    assert snap.positions[0]["unrealized_pnl"] == 20.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_snapshot.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.reporting.snapshot'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/reporting/snapshot.py
from dataclasses import dataclass, field


@dataclass
class AccountSnapshot:
    cash: float
    equity: float
    exposure: float
    realized_pnl: float
    positions: list = field(default_factory=list)


def portfolio_snapshot(portfolio, prices: dict) -> AccountSnapshot:
    positions = []
    for symbol, pos in portfolio.positions.items():
        price = prices[symbol]
        positions.append({
            "symbol": symbol,
            "qty": pos.qty,
            "avg_cost": pos.avg_cost,
            "price": price,
            "market_value": pos.market_value(price),
            "unrealized_pnl": pos.unrealized_pnl(price),
        })
    return AccountSnapshot(
        cash=portfolio.cash,
        equity=portfolio.total_equity(prices),
        exposure=portfolio.exposure(prices),
        realized_pnl=portfolio.realized_pnl,
        positions=positions,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_snapshot.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (1 passed)

- [ ] **Step 5: Create `src/trading_bot/reporting/__init__.py`** (empty file)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/reporting/__init__.py src/trading_bot/reporting/snapshot.py tests/test_snapshot.py
git commit -m "feat: account snapshot for reporting"
```

---

### Task 3: Alpaca account reader

**Files:**
- Create: `src/trading_bot/reporting/account_reader.py`, `tests/test_account_reader.py`

**Interfaces:**
- Consumes: `AccountSnapshot` (Task 2).
- Produces: `class AlpacaAccountReader`:
  - `__init__(self, api_key: str, secret_key: str, _client=None)` — production builds `alpaca.trading.client.TradingClient(api_key, secret_key, paper=True)`.
  - `snapshot(self) -> AccountSnapshot` — reads `get_account()` (for `cash`, `equity`) and `get_all_positions()` (each with `symbol, qty, avg_entry_price, current_price, market_value, unrealized_pl`), maps to `AccountSnapshot`. `exposure = sum(market_value) / equity` (0.0 if equity ≤ 0). `realized_pnl` is not available from a point-in-time account read, set `0.0` (the audit log carries realized activity).

- [ ] **Step 1: Write the failing test (injected fake — no network)**

```python
# tests/test_account_reader.py
from types import SimpleNamespace
from trading_bot.reporting.account_reader import AlpacaAccountReader


class _FakeClient:
    def get_account(self):
        return SimpleNamespace(cash="500.0", equity="720.0")

    def get_all_positions(self):
        return [SimpleNamespace(symbol="AAPL", qty="2", avg_entry_price="100.0",
                                current_price="110.0", market_value="220.0",
                                unrealized_pl="20.0")]


def test_snapshot_from_account():
    reader = AlpacaAccountReader("k", "s", _client=_FakeClient())
    snap = reader.snapshot()
    assert snap.cash == 500.0
    assert snap.equity == 720.0
    assert snap.positions[0]["symbol"] == "AAPL"
    assert snap.positions[0]["market_value"] == 220.0
    assert round(snap.exposure, 4) == round(220.0 / 720.0, 4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_account_reader.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.reporting.account_reader'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/reporting/account_reader.py
from trading_bot.reporting.snapshot import AccountSnapshot


class AlpacaAccountReader:
    def __init__(self, api_key: str, secret_key: str, _client=None):
        if _client is not None:
            self._client = _client
        else:
            from alpaca.trading.client import TradingClient
            self._client = TradingClient(api_key, secret_key, paper=True)

    def snapshot(self) -> AccountSnapshot:
        acct = self._client.get_account()
        cash = float(acct.cash)
        equity = float(acct.equity)
        positions = []
        for p in self._client.get_all_positions():
            positions.append({
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_cost": float(p.avg_entry_price),
                "price": float(p.current_price),
                "market_value": float(p.market_value),
                "unrealized_pnl": float(p.unrealized_pl),
            })
        mv = sum(p["market_value"] for p in positions)
        exposure = mv / equity if equity > 0 else 0.0
        return AccountSnapshot(cash=cash, equity=equity, exposure=exposure,
                               realized_pnl=0.0, positions=positions)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_account_reader.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/reporting/account_reader.py tests/test_account_reader.py
git commit -m "feat: Alpaca paper account reader for snapshots"
```

---

### Task 4: Report builder (morning / nightly)

**Files:**
- Create: `src/trading_bot/reporting/report_builder.py`, `tests/test_report_builder.py`

**Interfaces:**
- Consumes: `AccountSnapshot` (Task 2).
- Produces: `build_report(kind: str, snapshot, activity: dict) -> tuple[str, str, str]` returning `(subject, text_body, html_body)`:
  - `kind` is `"morning"` or `"nightly"` (raises `ValueError` otherwise).
  - `activity` is `{"decisions": [...], "fills": [...], "events": [...]}` (the audit query dicts).
  - Subject includes the kind and the date (e.g. `"[Trading Bot] Morning report — 2026-06-19"`); the date is read from `activity.get("date")` if present else today.
  - Text body includes: equity, cash, exposure %, realized P&L, a positions table (symbol, qty, avg cost, price, unrealized P&L), and a "what the bot did" section listing recent fills and decisions. Morning emphasizes current positions + any overnight alerts (events); nightly emphasizes the day's fills + realized P&L.
  - HTML body is a simple table-based version of the same content (no external CSS).
  - Alerts: if `activity["events"]` is non-empty, include an "⚠ Alerts" section listing them (use the word "Alerts", no emoji required).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report_builder.py
import pytest
from trading_bot.reporting.snapshot import AccountSnapshot
from trading_bot.reporting.report_builder import build_report


def _snap():
    return AccountSnapshot(
        cash=300.0, equity=520.0, exposure=0.42, realized_pnl=15.0,
        positions=[{"symbol": "AAPL", "qty": 2.0, "avg_cost": 100.0,
                    "price": 110.0, "market_value": 220.0, "unrealized_pnl": 20.0}],
    )


def _activity():
    return {
        "date": "2026-06-19",
        "decisions": [{"symbol": "AAPL", "action": "BUY", "rationale": "consensus"}],
        "fills": [{"symbol": "AAPL", "side": "BUY", "qty": 2.0, "price": 100.0}],
        "events": [{"kind": "circuit_breaker", "detail": "tripped"}],
    }


def test_morning_report_has_subject_and_positions():
    subject, text, html = build_report("morning", _snap(), _activity())
    assert "Morning" in subject
    assert "2026-06-19" in subject
    assert "AAPL" in text
    assert "520" in text          # equity present
    assert "Alerts" in text       # events surfaced
    assert "<table" in html.lower()


def test_nightly_report_mentions_realized_pnl():
    subject, text, html = build_report("nightly", _snap(), _activity())
    assert "Nightly" in subject
    assert "15" in text           # realized pnl present


def test_invalid_kind_raises():
    with pytest.raises(ValueError):
        build_report("weekly", _snap(), _activity())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_report_builder.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.reporting.report_builder'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/reporting/report_builder.py
from datetime import date

_KINDS = {"morning": "Morning", "nightly": "Nightly"}


def build_report(kind: str, snapshot, activity: dict):
    if kind not in _KINDS:
        raise ValueError(f"unknown report kind: {kind}")
    label = _KINDS[kind]
    day = activity.get("date") or date.today().isoformat()
    subject = f"[Trading Bot] {label} report — {day}"

    decisions = activity.get("decisions", [])
    fills = activity.get("fills", [])
    events = activity.get("events", [])

    lines = [
        f"{label} report for {day}",
        "",
        f"Equity: ${snapshot.equity:,.2f}",
        f"Cash: ${snapshot.cash:,.2f}",
        f"Exposure: {snapshot.exposure * 100:.1f}%",
        f"Realized P&L: ${snapshot.realized_pnl:,.2f}",
        "",
        "Positions:",
    ]
    if snapshot.positions:
        for p in snapshot.positions:
            lines.append(
                f"  {p['symbol']}: qty {p['qty']:.4f} @ avg ${p['avg_cost']:.2f}, "
                f"price ${p['price']:.2f}, unrealized ${p['unrealized_pnl']:,.2f}")
    else:
        lines.append("  (none)")

    lines += ["", "What the bot did:"]
    if fills:
        for f in fills:
            lines.append(f"  FILL {f['side']} {f['qty']:.4f} {f['symbol']} @ ${f['price']:.2f}")
    else:
        lines.append("  (no fills)")
    for d in decisions:
        lines.append(f"  DECISION {d['action']} {d['symbol']} — {d.get('rationale', '')}")

    if events:
        lines += ["", "Alerts:"]
        for e in events:
            lines.append(f"  {e['kind']}: {e['detail']}")

    text = "\n".join(lines)

    rows = "".join(
        f"<tr><td>{p['symbol']}</td><td>{p['qty']:.4f}</td>"
        f"<td>${p['avg_cost']:.2f}</td><td>${p['price']:.2f}</td>"
        f"<td>${p['unrealized_pnl']:,.2f}</td></tr>"
        for p in snapshot.positions
    ) or "<tr><td colspan='5'>(none)</td></tr>"
    alerts_html = ""
    if events:
        items = "".join(f"<li>{e['kind']}: {e['detail']}</li>" for e in events)
        alerts_html = f"<h3>Alerts</h3><ul>{items}</ul>"
    html = (
        f"<h2>{label} report — {day}</h2>"
        f"<p>Equity: ${snapshot.equity:,.2f} | Cash: ${snapshot.cash:,.2f} | "
        f"Exposure: {snapshot.exposure * 100:.1f}% | "
        f"Realized P&amp;L: ${snapshot.realized_pnl:,.2f}</p>"
        f"<h3>Positions</h3>"
        f"<table border='1' cellpadding='4'><tr><th>Symbol</th><th>Qty</th>"
        f"<th>Avg cost</th><th>Price</th><th>Unrealized</th></tr>{rows}</table>"
        f"{alerts_html}"
    )
    return subject, text, html
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_report_builder.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/reporting/report_builder.py tests/test_report_builder.py
git commit -m "feat: morning/nightly report builder"
```

---

### Task 5: Notifier interface + Console + Email

**Files:**
- Create: `src/trading_bot/notify/__init__.py`, `src/trading_bot/notify/base.py`, `src/trading_bot/notify/console_notifier.py`, `src/trading_bot/notify/email_notifier.py`, `tests/test_console_notifier.py`, `tests/test_email_notifier.py`

**Interfaces:**
- Produces:
  - `class Notifier(ABC)`: `@abstractmethod send(self, subject: str, text_body: str, html_body: str) -> None`.
  - `class ConsoleNotifier(Notifier)`: `__init__(self, stream=None)` (default `sys.stdout`); `send` prints subject + text body. Records `self.sent: list` of `(subject, text)` for testability.
  - `class EmailNotifier(Notifier)`: `__init__(self, host, port, username, password, sender, recipient, _smtp_factory=None, use_tls=True)`. `send` builds a `MIMEMultipart("alternative")` with text + html parts and sends via SMTP. `_smtp_factory()` returns an SMTP-like object (with `starttls`, `login`, `sendmail`, `quit`); production default is `lambda: smtplib.SMTP(host, port)`. Never logs the password.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_console_notifier.py
import io
from trading_bot.notify.console_notifier import ConsoleNotifier


def test_console_records_and_prints():
    buf = io.StringIO()
    n = ConsoleNotifier(stream=buf)
    n.send("subj", "the body", "<p>the body</p>")
    assert n.sent == [("subj", "the body")]
    assert "subj" in buf.getvalue()
```

```python
# tests/test_email_notifier.py
from trading_bot.notify.email_notifier import EmailNotifier


class _FakeSMTP:
    def __init__(self):
        self.calls = []

    def starttls(self): self.calls.append(("starttls",))
    def login(self, u, p): self.calls.append(("login", u))
    def sendmail(self, frm, to, msg): self.calls.append(("sendmail", frm, to, msg))
    def quit(self): self.calls.append(("quit",))


def test_email_sends_via_smtp():
    fake = _FakeSMTP()
    n = EmailNotifier(host="smtp.test", port=587, username="u@test",
                      password="secret", sender="u@test", recipient="me@test",
                      _smtp_factory=lambda: fake)
    n.send("subj", "text body", "<p>html body</p>")
    kinds = [c[0] for c in fake.calls]
    assert "login" in kinds and "sendmail" in kinds and "quit" in kinds
    sendmail_call = [c for c in fake.calls if c[0] == "sendmail"][0]
    assert sendmail_call[1] == "u@test"          # from
    assert sendmail_call[2] == "me@test"         # to
    assert "subj" in sendmail_call[3]            # subject in payload
    assert "secret" not in sendmail_call[3]      # password never in payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/test_console_notifier.py tests/test_email_notifier.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError` for the notify modules.

- [ ] **Step 3: Write the base + console**

```python
# src/trading_bot/notify/base.py
from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, subject: str, text_body: str, html_body: str) -> None:
        ...
```

```python
# src/trading_bot/notify/console_notifier.py
import sys
from trading_bot.notify.base import Notifier


class ConsoleNotifier(Notifier):
    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self.sent: list = []

    def send(self, subject: str, text_body: str, html_body: str) -> None:
        self.sent.append((subject, text_body))
        print(f"=== {subject} ===\n{text_body}", file=self.stream)
```

- [ ] **Step 4: Write the email notifier**

```python
# src/trading_bot/notify/email_notifier.py
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from trading_bot.notify.base import Notifier


class EmailNotifier(Notifier):
    def __init__(self, host: str, port: int, username: str, password: str,
                 sender: str, recipient: str, _smtp_factory=None, use_tls: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self._password = password
        self.sender = sender
        self.recipient = recipient
        self.use_tls = use_tls
        self._smtp_factory = _smtp_factory or (lambda: smtplib.SMTP(host, port))

    def send(self, subject: str, text_body: str, html_body: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = self.recipient
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        smtp = self._smtp_factory()
        try:
            if self.use_tls:
                smtp.starttls()
            smtp.login(self.username, self._password)
            smtp.sendmail(self.sender, self.recipient, msg.as_string())
        finally:
            smtp.quit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/test_console_notifier.py tests/test_email_notifier.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (2 passed)

- [ ] **Step 6: Create `src/trading_bot/notify/__init__.py`** (empty file)

- [ ] **Step 7: Commit**

```bash
git add src/trading_bot/notify tests/test_console_notifier.py tests/test_email_notifier.py
git commit -m "feat: notifier interface with console and email delivery"
```

---

### Task 6: send_report CLI + config/.env wiring + README

**Files:**
- Create: `scripts/send_report.py`
- Modify: `config.yaml` (add `reporting` section), `.env.example` (add SMTP vars), `README.md` (reporting section)

**Interfaces:**
- Consumes: `load_config`, `load_secrets` (Phase 1); `AlpacaAccountReader` (Task 3); `AuditLog` (Phase 2b + Task 1); `build_report` (Task 4); `ConsoleNotifier`/`EmailNotifier` (Task 5).
- Produces: `scripts/send_report.py` — usage `python scripts/send_report.py [morning|nightly]`. Reads config + secrets; builds the snapshot from `AlpacaAccountReader` when keys are present and `reporting.delivery == "email"`, otherwise prints to console; pulls `activity` from `AuditLog` (`recent_decisions/fills/events`); calls `build_report`; delivers via the configured notifier.

- [ ] **Step 1: Append `reporting` section to `config.yaml`**

```yaml
reporting:
  delivery: "console"   # "console" or "email"
  morning_hour: 8       # local hour for the scheduler (Phase 6) to send the morning report
  nightly_hour: 18
  recent_limit: 20
```

Append from the shell if the editor write doesn't sync; verify keys with the yaml load one-liner from Phase 2b.

- [ ] **Step 2: Append SMTP vars to `.env.example`**

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@example.com
SMTP_PASS=your_app_password_here
REPORT_FROM_EMAIL=you@example.com
REPORT_TO_EMAIL=you@example.com
```

- [ ] **Step 3: Extend `load_secrets` to include SMTP keys**

In `src/trading_bot/config/loader.py`, add SMTP keys to the returned dict. Append/modify the function so it also returns: `SMTP_HOST, SMTP_PORT (int, default 587), SMTP_USER, SMTP_PASS, REPORT_FROM_EMAIL, REPORT_TO_EMAIL`. Keep existing Alpaca keys. Verify the modification synced (`grep -n SMTP_HOST src/trading_bot/config/loader.py`); append from shell if needed. Add a focused test in `tests/test_config_loader.py`:

```python
def test_load_secrets_includes_smtp(tmp_path):
    from trading_bot.config.loader import load_secrets
    env = tmp_path / ".env"
    env.write_text("SMTP_HOST=smtp.x\nSMTP_PORT=2525\nSMTP_USER=u\n"
                   "SMTP_PASS=p\nREPORT_FROM_EMAIL=f@x\nREPORT_TO_EMAIL=t@x\n")
    s = load_secrets(str(env))
    assert s["SMTP_HOST"] == "smtp.x"
    assert s["SMTP_PORT"] == 2525
    assert s["REPORT_TO_EMAIL"] == "t@x"
```

- [ ] **Step 4: Write the CLI**

```python
# scripts/send_report.py
import sys
from datetime import date

from trading_bot.config.loader import load_config, load_secrets
from trading_bot.audit.audit_log import AuditLog
from trading_bot.reporting.account_reader import AlpacaAccountReader
from trading_bot.reporting.report_builder import build_report
from trading_bot.notify.console_notifier import ConsoleNotifier
from trading_bot.notify.email_notifier import EmailNotifier


def main(kind: str) -> None:
    cfg = load_config("config.yaml")
    secrets = load_secrets(".env")
    rep = cfg["reporting"]
    limit = rep["recent_limit"]

    audit = AuditLog(cfg["execution"]["audit_db"])
    activity = {
        "date": date.today().isoformat(),
        "decisions": audit.recent_decisions(limit),
        "fills": audit.recent_fills(limit),
        "events": audit.recent_events(limit),
    }

    reader = AlpacaAccountReader(secrets["ALPACA_API_KEY"], secrets["ALPACA_SECRET_KEY"])
    snapshot = reader.snapshot()

    subject, text, html = build_report(kind, snapshot, activity)

    if rep["delivery"] == "email":
        notifier = EmailNotifier(
            host=secrets["SMTP_HOST"], port=secrets["SMTP_PORT"],
            username=secrets["SMTP_USER"], password=secrets["SMTP_PASS"],
            sender=secrets["REPORT_FROM_EMAIL"], recipient=secrets["REPORT_TO_EMAIL"],
        )
    else:
        notifier = ConsoleNotifier()
    notifier.send(subject, text, html)
    print(f"sent {kind} report: {subject}")


if __name__ == "__main__":
    kind = sys.argv[1] if len(sys.argv) > 1 else "morning"
    main(kind)
```

- [ ] **Step 5: Append a "Reporting" section to `README.md`**

```markdown
## Reporting (Phase 3a)

Generate and deliver the morning or nightly portfolio report:

```bash
PYTHONPATH=src python scripts/send_report.py morning
PYTHONPATH=src python scripts/send_report.py nightly
```

- Delivery channel is set by `reporting.delivery` in `config.yaml` (`console` or `email`).
- For email, set `SMTP_*` and `REPORT_*` in `.env` (Gmail: use an App Password, not your account password).
- Report content: equity, cash, exposure, realized P&L, current positions, what the bot did (fills + decisions), and any alerts (circuit breaker / kill switch).
```

- [ ] **Step 6: Run the focused config test, then the FULL suite**

Run: `PYTHONPATH=src python -m pytest tests/test_config_loader.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (includes the new SMTP test).

Run: `PYTHONPATH=src python -m pytest -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (all phases).

- [ ] **Step 7: Smoke-test the CLI in console mode**

With `reporting.delivery: console` and no email configured, but valid Alpaca keys in `.env`:
Run: `PYTHONPATH=src python scripts/send_report.py morning`
Expected: prints a morning report to the console. (Requires Alpaca keys for the account read; without keys the account read raises — document that keys are required to run, and that unit tests cover the logic without them.)

- [ ] **Step 8: Commit**

```bash
git add scripts/send_report.py config.yaml .env.example README.md src/trading_bot/config/loader.py tests/test_config_loader.py
git commit -m "feat: report delivery CLI and SMTP config wiring"
```

---

## Self-Review (completed by plan author)

**Spec coverage (Phase 3a scope):**
- Reporting module — morning and nightly reports with positions, P&L, risk exposure, what the bot did and why, and alerts (Tasks 2–4). ✓
- Delivery channel = email (spec: user provided), pluggable via `Notifier`; console fallback for keyless runs (Task 5). ✓
- Reads "what the bot did" from the audit trail (Task 1) and current state from the broker account (Task 3) — matching the spec's reconcile-against-broker intent. ✓
- Config-driven (delivery channel, schedule hours, recipient), no secrets in code, password never logged or placed in payload (Tasks 5–6). ✓
- Deferred to later: the scheduler that triggers morning/nightly automatically (Phase 6); the React dashboard + FastAPI API (Phase 3b); Slack channel (future Notifier impl).

**Placeholder scan:** No TBD/TODO; every code step is complete and runnable.

**Type consistency:** `AccountSnapshot` (Task 2) produced by both `portfolio_snapshot` and `AlpacaAccountReader.snapshot` (Task 3) and consumed by `build_report` (Task 4) with the same field names. `build_report(kind, snapshot, activity) -> (subject, text, html)` matches the CLI and notifier usage. `Notifier.send(subject, text_body, html_body)` consistent across console, email, and CLI call sites. `activity` dict keys (`date/decisions/fills/events`) produced by the audit query methods (Task 1) and consumed by `build_report`. `load_secrets` SMTP additions (Task 6) match the CLI's `EmailNotifier` construction.
