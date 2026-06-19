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
