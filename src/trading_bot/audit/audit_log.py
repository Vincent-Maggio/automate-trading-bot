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
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
