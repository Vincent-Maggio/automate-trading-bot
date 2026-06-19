# Phase 3b: FastAPI Backend + React Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the bot's state and controls over a small HTTP API and a dashboard — positions, P&L, exposure, recent decisions, alerts, and a working kill switch / resume button — so the user can watch and control the bot from a browser.

**Architecture:** A persistent `ControlStore` (SQLite) holds the kill-switch flag; the API writes it and the runtime consults it before each cycle (via a small `apply_controls` bridge — the cycle code itself is unchanged). A FastAPI app is built by a `create_app(...)` factory with its data sources injected (audit log, a snapshot provider, the control store) so it is fully testable with Starlette's `TestClient` and no network. The dashboard is a single self-contained `index.html` (React via CDN — no build step) that the API serves at `/` and which calls the JSON endpoints.

**Tech Stack:** Python 3.10+, FastAPI, Starlette `TestClient` (+ httpx), `pytest`. React 18 + Babel via CDN for the dashboard (no npm build). Builds on Phases 1–3a.

## Global Constraints

- Python 3.10+ (sandbox 3.10.12; no 3.11+ syntax).
- No secrets in code or in API responses; the API never returns API keys or SMTP creds.
- The cycle/runtime must consult the persistent kill switch before trading; the dashboard button must set it.
- Tests must not hit the network — `create_app` takes an injected snapshot provider (a callable) and an `AuditLog`/`ControlStore` on temp paths.
- Run pytest with Linux-local temp: `PYTHONPATH=src python -m pytest -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`.
- **Mount caveat:** modifying existing files (`requirements.txt`, `README.md`) may not sync through the mount; verify and append from the shell if needed. New files persist normally.
- The React dashboard is intentionally a single CDN-based file (no npm toolchain) to stay simple and reviewable; a Vite build can replace it later without API changes.
- Commits run where git is available (user's Windows machine); stage the listed files per task.

---

## File Structure

```
src/trading_bot/
├── control/
│   ├── __init__.py          # NEW
│   └── control_store.py     # NEW: ControlStore (SQLite kill flag) + apply_controls()
└── api/
    ├── __init__.py          # NEW
    ├── app.py               # NEW: create_app(audit, control_store, snapshot_provider)
    └── static/
        └── index.html       # NEW: single-file React dashboard (CDN React)
scripts/
└── run_api.py               # NEW: uvicorn entry wiring real sources
requirements.txt             # MODIFY: add fastapi, uvicorn, httpx
README.md                    # MODIFY: dashboard run instructions
tests/
├── test_control_store.py
├── test_api_read.py
├── test_api_controls.py
└── test_api_dashboard.py
```

---

### Task 1: Persistent control store + apply_controls bridge

**Files:**
- Create: `src/trading_bot/control/__init__.py`, `src/trading_bot/control/control_store.py`, `tests/test_control_store.py`

**Interfaces:**
- Consumes: `SafetyState` (Phase 2a) for the bridge.
- Produces:
  - `class ControlStore`: `__init__(self, db_path: str)` creates a `controls` table (`key TEXT PRIMARY KEY, value TEXT`). `is_killed() -> bool`, `kill(reason: str = "") -> None` (stores `killed=1` and the reason), `clear_kill() -> None`, `kill_reason() -> str`.
  - `apply_controls(control_store, safety) -> None` — if `control_store.is_killed()`, call `safety.kill()`; else `safety.reset_kill()`. This is the bridge the runtime calls before each cycle; the cycle code stays unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_control_store.py
from trading_bot.control.control_store import ControlStore, apply_controls
from trading_bot.risk.safety import SafetyState


def test_kill_persists_and_clears(tmp_path):
    cs = ControlStore(str(tmp_path / "ctl.sqlite"))
    assert cs.is_killed() is False
    cs.kill("manual from dashboard")
    assert cs.is_killed() is True
    assert cs.kill_reason() == "manual from dashboard"
    cs.clear_kill()
    assert cs.is_killed() is False


def test_persists_across_instances(tmp_path):
    path = str(tmp_path / "ctl.sqlite")
    ControlStore(path).kill("x")
    assert ControlStore(path).is_killed() is True


def test_apply_controls_sets_safety(tmp_path):
    cs = ControlStore(str(tmp_path / "ctl.sqlite"))
    safety = SafetyState(0.03)
    cs.kill("halt")
    apply_controls(cs, safety)
    assert safety.can_trade() is False
    cs.clear_kill()
    apply_controls(cs, safety)
    assert safety.can_trade() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_control_store.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL with `ModuleNotFoundError: No module named 'trading_bot.control.control_store'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/control/control_store.py
import sqlite3


class ControlStore:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS controls (key TEXT PRIMARY KEY, value TEXT)")
        self.conn.commit()

    def _get(self, key: str, default: str = "") -> str:
        cur = self.conn.execute("SELECT value FROM controls WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

    def _set(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO controls (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def is_killed(self) -> bool:
        return self._get("killed", "0") == "1"

    def kill(self, reason: str = "") -> None:
        self._set("killed", "1")
        self._set("kill_reason", reason)

    def clear_kill(self) -> None:
        self._set("killed", "0")
        self._set("kill_reason", "")

    def kill_reason(self) -> str:
        return self._get("kill_reason", "")


def apply_controls(control_store, safety) -> None:
    if control_store.is_killed():
        safety.kill()
    else:
        safety.reset_kill()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_control_store.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (3 passed)

- [ ] **Step 5: Create `src/trading_bot/control/__init__.py`** (empty file)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/control tests/test_control_store.py
git commit -m "feat: persistent control store and safety bridge"
```

---

### Task 2: FastAPI app factory + read endpoints

**Files:**
- Modify: `requirements.txt` (add `fastapi`, `uvicorn`, `httpx`)
- Create: `src/trading_bot/api/__init__.py`, `src/trading_bot/api/app.py`, `tests/test_api_read.py`

**Interfaces:**
- Consumes: `AuditLog` (Phase 2b + 3a queries), `ControlStore` (Task 1), `AccountSnapshot` (Phase 3a).
- Produces: `create_app(audit, control_store, snapshot_provider, recent_limit: int = 20) -> FastAPI`:
  - `snapshot_provider` is a zero-arg callable returning an `AccountSnapshot` (prod: `AlpacaAccountReader.snapshot`; tests: a lambda returning a fixed snapshot). If it raises, the portfolio endpoint returns `{"error": "...", "positions": []}` with HTTP 200 (dashboard stays up even if the broker read fails).
  - Endpoints (all JSON):
    - `GET /api/portfolio` → `{cash, equity, exposure, realized_pnl, positions}` from `snapshot_provider()`.
    - `GET /api/decisions` → `audit.recent_decisions(recent_limit)`.
    - `GET /api/fills` → `audit.recent_fills(recent_limit)`.
    - `GET /api/events` → `audit.recent_events(recent_limit)`.
    - `GET /api/status` → `{"killed": control_store.is_killed(), "kill_reason": control_store.kill_reason()}`.

- [ ] **Step 1: Add deps to `requirements.txt`**

Append (verify reached disk; append from shell if needed):
```
fastapi==0.111.0
uvicorn==0.30.1
httpx==0.27.0
```
Then install: `pip install -q -r requirements.txt`.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_api_read.py
from starlette.testclient import TestClient
from trading_bot.api.app import create_app
from trading_bot.audit.audit_log import AuditLog
from trading_bot.control.control_store import ControlStore
from trading_bot.reporting.snapshot import AccountSnapshot
from trading_bot.domain.models import Action, Decision


def _snap():
    return AccountSnapshot(cash=300.0, equity=520.0, exposure=0.42,
                           realized_pnl=15.0,
                           positions=[{"symbol": "AAPL", "qty": 2.0,
                                       "avg_cost": 100.0, "price": 110.0,
                                       "market_value": 220.0, "unrealized_pnl": 20.0}])


def _client(tmp_path, provider=None):
    audit = AuditLog(str(tmp_path / "audit.sqlite"))
    audit.log_decision("r1", Decision("AAPL", Action.BUY, 0.8, True, "consensus", []))
    cs = ControlStore(str(tmp_path / "ctl.sqlite"))
    app = create_app(audit, cs, provider or _snap)
    return TestClient(app), cs


def test_portfolio_endpoint(tmp_path):
    client, _ = _client(tmp_path)
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert body["equity"] == 520.0
    assert body["positions"][0]["symbol"] == "AAPL"


def test_decisions_endpoint(tmp_path):
    client, _ = _client(tmp_path)
    r = client.get("/api/decisions")
    assert r.status_code == 200
    assert r.json()[0]["symbol"] == "AAPL"


def test_status_endpoint_reports_kill(tmp_path):
    client, cs = _client(tmp_path)
    cs.kill("test")
    r = client.get("/api/status")
    assert r.json()["killed"] is True
    assert r.json()["kill_reason"] == "test"


def test_portfolio_survives_provider_error(tmp_path):
    def _boom():
        raise RuntimeError("broker down")
    client, _ = _client(tmp_path, provider=_boom)
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    assert r.json()["positions"] == []
    assert "error" in r.json()
```

- [ ] **Step 3: Write minimal implementation**

```python
# src/trading_bot/api/app.py
from dataclasses import asdict
from fastapi import FastAPI


def create_app(audit, control_store, snapshot_provider, recent_limit: int = 20):
    app = FastAPI(title="Trading Bot API")

    @app.get("/api/portfolio")
    def portfolio():
        try:
            snap = snapshot_provider()
        except Exception as exc:  # broker read failed — keep dashboard alive
            return {"error": str(exc), "cash": 0.0, "equity": 0.0,
                    "exposure": 0.0, "realized_pnl": 0.0, "positions": []}
        return asdict(snap)

    @app.get("/api/decisions")
    def decisions():
        return audit.recent_decisions(recent_limit)

    @app.get("/api/fills")
    def fills():
        return audit.recent_fills(recent_limit)

    @app.get("/api/events")
    def events():
        return audit.recent_events(recent_limit)

    @app.get("/api/status")
    def status():
        return {"killed": control_store.is_killed(),
                "kill_reason": control_store.kill_reason()}

    return app
```

Note: `AccountSnapshot` is a dataclass, so `asdict` serializes it (positions are plain dicts already).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_api_read.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (4 passed)

- [ ] **Step 5: Create `src/trading_bot/api/__init__.py`** (empty file)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt src/trading_bot/api/__init__.py src/trading_bot/api/app.py tests/test_api_read.py
git commit -m "feat: FastAPI app factory with read endpoints"
```

---

### Task 3: Kill / resume control endpoints

**Files:**
- Modify: `src/trading_bot/api/app.py` (add two POST routes)
- Create: `tests/test_api_controls.py`

**Interfaces:**
- Produces (add to `create_app`):
  - `POST /api/kill` (optional JSON `{"reason": "..."}`) → calls `control_store.kill(reason)`, returns `{"killed": True, "kill_reason": reason}`.
  - `POST /api/resume` → calls `control_store.clear_kill()`, returns `{"killed": False}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_controls.py
from starlette.testclient import TestClient
from trading_bot.api.app import create_app
from trading_bot.audit.audit_log import AuditLog
from trading_bot.control.control_store import ControlStore
from trading_bot.reporting.snapshot import AccountSnapshot


def _client(tmp_path):
    audit = AuditLog(str(tmp_path / "audit.sqlite"))
    cs = ControlStore(str(tmp_path / "ctl.sqlite"))
    snap = lambda: AccountSnapshot(0, 0, 0, 0, [])
    return TestClient(create_app(audit, cs, snap)), cs


def test_kill_then_resume(tmp_path):
    client, cs = _client(tmp_path)
    r = client.post("/api/kill", json={"reason": "panic"})
    assert r.status_code == 200
    assert r.json()["killed"] is True
    assert cs.is_killed() is True

    r2 = client.post("/api/resume")
    assert r2.status_code == 200
    assert r2.json()["killed"] is False
    assert cs.is_killed() is False


def test_kill_without_body(tmp_path):
    client, cs = _client(tmp_path)
    r = client.post("/api/kill")
    assert r.status_code == 200
    assert cs.is_killed() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_api_controls.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL (404 on POST /api/kill — route not defined yet).

- [ ] **Step 3: Add the routes to `create_app`** (in `src/trading_bot/api/app.py`, before `return app`)

```python
    from fastapi import Request

    @app.post("/api/kill")
    async def kill(request: Request):
        reason = ""
        try:
            data = await request.json()
            reason = data.get("reason", "") if isinstance(data, dict) else ""
        except Exception:
            reason = ""
        control_store.kill(reason)
        return {"killed": True, "kill_reason": reason}

    @app.post("/api/resume")
    def resume():
        control_store.clear_kill()
        return {"killed": False}
```

(If editing the existing file doesn't sync through the mount, rewrite `app.py` from the shell with the full content including these routes.)

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_api_controls.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/trading_bot/api/app.py tests/test_api_controls.py
git commit -m "feat: kill and resume control endpoints"
```

---

### Task 4: React dashboard (single-file) served by the API

**Files:**
- Create: `src/trading_bot/api/static/index.html`
- Modify: `src/trading_bot/api/app.py` (mount static + serve index at `/`)
- Create: `tests/test_api_dashboard.py`

**Interfaces:**
- Produces:
  - `index.html` — a single-file React 18 app (loaded from `cdnjs`/`unpkg` CDN with Babel standalone) that on load fetches `/api/status`, `/api/portfolio`, `/api/decisions`, `/api/fills`, `/api/events`, renders: a header with equity/cash/exposure/realized-P&L, a positions table, a recent-decisions list, an events/alerts panel, and a Kill / Resume button that POSTs to `/api/kill` and `/api/resume` and refreshes status. Polls every 15s.
  - `create_app` serves `index.html` at `GET /` (read the file and return `HTMLResponse`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_dashboard.py
from starlette.testclient import TestClient
from trading_bot.api.app import create_app
from trading_bot.audit.audit_log import AuditLog
from trading_bot.control.control_store import ControlStore
from trading_bot.reporting.snapshot import AccountSnapshot


def test_dashboard_served_at_root(tmp_path):
    audit = AuditLog(str(tmp_path / "audit.sqlite"))
    cs = ControlStore(str(tmp_path / "ctl.sqlite"))
    app = create_app(audit, cs, lambda: AccountSnapshot(0, 0, 0, 0, []))
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text.lower()
    assert "<div id=\"root\"" in body or "<div id='root'" in body
    assert "trading bot" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_api_dashboard.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: FAIL (404 on `/`).

- [ ] **Step 3: Create `src/trading_bot/api/static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Trading Bot Dashboard</title>
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<style>
  body { font-family: system-ui, Arial, sans-serif; margin: 0; background: #0f1115; color: #e6e6e6; }
  .wrap { max-width: 960px; margin: 0 auto; padding: 24px; }
  .cards { display: flex; gap: 16px; flex-wrap: wrap; }
  .card { background: #1a1d24; border: 1px solid #2a2f3a; border-radius: 8px; padding: 16px; flex: 1; min-width: 140px; }
  .card h3 { margin: 0 0 4px; font-size: 12px; color: #8a93a3; text-transform: uppercase; }
  .card .v { font-size: 22px; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  th, td { text-align: left; padding: 8px; border-bottom: 1px solid #2a2f3a; font-size: 14px; }
  .killbtn { background: #b3261e; color: #fff; border: 0; padding: 10px 16px; border-radius: 6px; cursor: pointer; font-size: 15px; }
  .resumebtn { background: #1e7d34; color: #fff; border: 0; padding: 10px 16px; border-radius: 6px; cursor: pointer; font-size: 15px; }
  .banner { background: #4a1410; border: 1px solid #b3261e; padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; }
  h1 { font-size: 20px; }
  .muted { color: #8a93a3; }
</style>
</head>
<body>
<div id="root"></div>
<script type="text/babel">
const { useState, useEffect, useCallback } = React;

function money(n) { return "$" + Number(n || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}); }

function App() {
  const [status, setStatus] = useState({killed: false, kill_reason: ""});
  const [pf, setPf] = useState({cash:0, equity:0, exposure:0, realized_pnl:0, positions:[]});
  const [decisions, setDecisions] = useState([]);
  const [events, setEvents] = useState([]);

  const load = useCallback(async () => {
    const j = async (u) => (await fetch(u)).json();
    setStatus(await j("/api/status"));
    setPf(await j("/api/portfolio"));
    setDecisions(await j("/api/decisions"));
    setEvents(await j("/api/events"));
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  const kill = async () => { await fetch("/api/kill", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({reason:"manual from dashboard"})}); load(); };
  const resume = async () => { await fetch("/api/resume", {method:"POST"}); load(); };

  return (
    <div className="wrap">
      <h1>Trading Bot Dashboard</h1>
      {status.killed && <div className="banner">KILL SWITCH ACTIVE — {status.kill_reason || "trading halted"}</div>}
      <div style={{margin:"12px 0"}}>
        {status.killed
          ? <button className="resumebtn" onClick={resume}>Resume trading</button>
          : <button className="killbtn" onClick={kill}>Kill switch — halt trading</button>}
      </div>
      <div className="cards">
        <div className="card"><h3>Equity</h3><div className="v">{money(pf.equity)}</div></div>
        <div className="card"><h3>Cash</h3><div className="v">{money(pf.cash)}</div></div>
        <div className="card"><h3>Exposure</h3><div className="v">{(pf.exposure*100).toFixed(1)}%</div></div>
        <div className="card"><h3>Realized P&amp;L</h3><div className="v">{money(pf.realized_pnl)}</div></div>
      </div>

      <h2>Positions</h2>
      <table><thead><tr><th>Symbol</th><th>Qty</th><th>Avg cost</th><th>Price</th><th>Unrealized</th></tr></thead>
      <tbody>
        {(pf.positions||[]).map((p,i) => (
          <tr key={i}><td>{p.symbol}</td><td>{Number(p.qty).toFixed(4)}</td><td>{money(p.avg_cost)}</td><td>{money(p.price)}</td><td>{money(p.unrealized_pnl)}</td></tr>
        ))}
        {(!pf.positions || pf.positions.length===0) && <tr><td colSpan="5" className="muted">No open positions</td></tr>}
      </tbody></table>

      <h2>Recent decisions</h2>
      <table><thead><tr><th>Time</th><th>Symbol</th><th>Action</th><th>Why</th></tr></thead>
      <tbody>
        {decisions.map((d,i) => (<tr key={i}><td className="muted">{d.ts}</td><td>{d.symbol}</td><td>{d.action}</td><td>{d.rationale}</td></tr>))}
        {decisions.length===0 && <tr><td colSpan="4" className="muted">No decisions yet</td></tr>}
      </tbody></table>

      <h2>Alerts &amp; events</h2>
      <table><thead><tr><th>Time</th><th>Kind</th><th>Detail</th></tr></thead>
      <tbody>
        {events.map((e,i) => (<tr key={i}><td className="muted">{e.ts}</td><td>{e.kind}</td><td>{e.detail}</td></tr>))}
        {events.length===0 && <tr><td colSpan="3" className="muted">No events</td></tr>}
      </tbody></table>
    </div>
  );
}
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
</script>
</body>
</html>
```

- [ ] **Step 4: Serve it from `create_app`** (add to `app.py` before `return app`)

```python
    import os
    from fastapi.responses import HTMLResponse

    _static_dir = os.path.join(os.path.dirname(__file__), "static")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        with open(os.path.join(_static_dir, "index.html"), "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
```

(If the mount won't sync the `app.py` edit, rewrite the whole file from the shell.)

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_api_dashboard.py -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add src/trading_bot/api/app.py src/trading_bot/api/static/index.html tests/test_api_dashboard.py
git commit -m "feat: single-file React dashboard served by the API"
```

---

### Task 5: API run entry + README + full suite

**Files:**
- Create: `scripts/run_api.py`
- Modify: `README.md` (dashboard section)

**Interfaces:**
- Produces: `scripts/run_api.py` — wires real sources (`AuditLog` from config, `ControlStore` on a configured path, and a `snapshot_provider` that calls `AlpacaAccountReader(...).snapshot` when keys exist else returns an empty snapshot) and runs `uvicorn`. Reads host/port from env with sane defaults (`127.0.0.1:8000`).

- [ ] **Step 1: Write the run entry**

```python
# scripts/run_api.py
import os
import uvicorn

from trading_bot.config.loader import load_config, load_secrets
from trading_bot.audit.audit_log import AuditLog
from trading_bot.control.control_store import ControlStore
from trading_bot.reporting.snapshot import AccountSnapshot
from trading_bot.reporting.account_reader import AlpacaAccountReader
from trading_bot.api.app import create_app


def build_app():
    cfg = load_config("config.yaml")
    secrets = load_secrets(".env")
    audit = AuditLog(cfg["execution"]["audit_db"])
    control_store = ControlStore(cfg.get("control", {}).get("db", "control.sqlite"))

    def snapshot_provider():
        if secrets["ALPACA_API_KEY"]:
            return AlpacaAccountReader(secrets["ALPACA_API_KEY"],
                                       secrets["ALPACA_SECRET_KEY"]).snapshot()
        return AccountSnapshot(0.0, 0.0, 0.0, 0.0, [])

    return create_app(audit, control_store, snapshot_provider,
                      recent_limit=cfg["reporting"]["recent_limit"])


app = build_app()

if __name__ == "__main__":
    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
```

- [ ] **Step 2: Append a "Dashboard" section to `README.md`**

```markdown
## Dashboard & API (Phase 3b)

Run the dashboard + API:

```bash
PYTHONPATH=src python scripts/run_api.py
# then open http://127.0.0.1:8000/
```

- The dashboard shows equity, cash, exposure, realized P&L, open positions, recent decisions, and alerts, and has a **Kill switch / Resume** button.
- The kill switch is persistent (stored via `ControlStore`); the runtime consults it before each cycle, so halting from the dashboard stops new trading.
- Portfolio data reflects the live Alpaca paper account when keys are set; otherwise it shows zeros.
```

- [ ] **Step 3: Wire the kill switch into the paper-cycle runtime**

In `scripts/run_paper_cycle.py`, before calling `cycle.run_once(...)`, consult the control store so a dashboard kill halts the cycle. Add near the top imports `from trading_bot.control.control_store import ControlStore, apply_controls`, and after `safety.start_day(...)` add:

```python
    control_store = ControlStore(cfg.get("control", {}).get("db", "control.sqlite"))
    apply_controls(control_store, safety)
```

(If editing the existing script doesn't sync, rewrite it from the shell with this addition.)

- [ ] **Step 4: Run the FULL suite**

Run: `PYTHONPATH=src python -m pytest -q --basetemp=/tmp/pt -p no:cacheprovider -o cache_dir=/tmp/ptcache`
Expected: PASS (all phases).

- [ ] **Step 5: Smoke-test the API boots**

Run: `PYTHONPATH=src python -c "import scripts.run_api as r; print('app routes:', [route.path for route in r.app.routes])"`
Expected: prints routes including `/`, `/api/portfolio`, `/api/status`, `/api/kill`, `/api/resume`. (Import works without keys; snapshot provider returns zeros.)

- [ ] **Step 6: Commit**

```bash
git add scripts/run_api.py scripts/run_paper_cycle.py README.md
git commit -m "feat: API run entry, dashboard docs, kill-switch runtime wiring"
```

---

## Self-Review (completed by plan author)

**Spec coverage (Phase 3b scope):**
- React dashboard showing positions, P&L, risk exposure, recent decisions, and controls (Task 4). ✓
- Kill switch as a dashboard button AND persistent so the runtime honors it (Tasks 1, 3, 4, 5-step3). ✓ (CLI kill switch + circuit breaker already exist from Phase 2a/2b.)
- API exposing portfolio, decisions, fills, events, status (Task 2) and controls (Task 3), all testable without network via injected snapshot provider. ✓
- No secrets in responses; broker-read failure degrades gracefully (Task 2). ✓
- Deferred: scheduler loop that runs cycles on a cadence + auto-sends reports and consults controls each tick (Phase 6); live trading (Phase 5); richer charts (future dashboard iteration).

**Placeholder scan:** No TBD/TODO; every code step is complete and runnable. The dashboard is a complete single file.

**Type consistency:** `create_app(audit, control_store, snapshot_provider, recent_limit)` consistent across Tasks 2–5 and all tests. `ControlStore.is_killed/kill/clear_kill/kill_reason` (Task 1) used identically by the API (Tasks 2–3) and `apply_controls` (Tasks 1, 5). `snapshot_provider() -> AccountSnapshot` (Phase 3a dataclass) serialized via `asdict`; the dashboard reads the same field names (`cash/equity/exposure/realized_pnl/positions[*].symbol/qty/avg_cost/price/unrealized_pnl`). Audit query dict keys (`ts/symbol/action/rationale`, `kind/detail`) match the dashboard's rendering.
