import sqlite3


class ControlStore:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
