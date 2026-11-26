"""Relational storage. SQLite by default, PostgreSQL when DATABASE_URL points at it."""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import database_url


@dataclass(frozen=True)
class Reading:
    place_id: str
    ts: datetime
    occupied: int
    capacity: int
    source: str = "mqtt"


_DDL = {
    "sqlite": [
        """CREATE TABLE IF NOT EXISTS readings (
            place_id TEXT NOT NULL, ts TEXT NOT NULL, occupied INTEGER NOT NULL,
            capacity INTEGER NOT NULL, source TEXT NOT NULL DEFAULT 'mqtt',
            PRIMARY KEY (place_id, ts, source))""",
        """CREATE TABLE IF NOT EXISTS forecasts (
            place_id TEXT NOT NULL, target_ts TEXT NOT NULL, predicted INTEGER NOT NULL,
            made_at TEXT NOT NULL, PRIMARY KEY (place_id, target_ts))""",
    ],
    "postgres": [
        """CREATE TABLE IF NOT EXISTS readings (
            place_id TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL, occupied INTEGER NOT NULL,
            capacity INTEGER NOT NULL, source TEXT NOT NULL DEFAULT 'mqtt',
            PRIMARY KEY (place_id, ts, source))""",
        """CREATE TABLE IF NOT EXISTS forecasts (
            place_id TEXT NOT NULL, target_ts TIMESTAMPTZ NOT NULL, predicted INTEGER NOT NULL,
            made_at TIMESTAMPTZ NOT NULL, PRIMARY KEY (place_id, target_ts))""",
    ],
}


def _to_dt(v) -> datetime:
    return v if isinstance(v, datetime) else datetime.fromisoformat(str(v))


class Database:
    def __init__(self, url: str | None = None):
        self.url = url or database_url()
        self.kind = "postgres" if self.url.startswith(("postgres://", "postgresql://")) else "sqlite"
        self._lock = threading.Lock()
        if self.kind == "sqlite":
            path = self.url.split("///", 1)[1] if "///" in self.url else ":memory:"
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(path, check_same_thread=False)
        else:
            import psycopg2  # imported lazily so SQLite users don't need it

            self.conn = psycopg2.connect(self.url)
        for stmt in _DDL[self.kind]:
            self._run(stmt)

    def _run(self, sql: str, params: tuple = ()):
        if self.kind == "postgres":
            sql = sql.replace("?", "%s")
        with self._lock:
            cur = self.conn.cursor()
            try:
                cur.execute(sql, params)
                rows = cur.fetchall() if cur.description else []
                self.conn.commit()
                return rows
            except Exception:
                self.conn.rollback()
                raise
            finally:
                cur.close()

    def add_reading(self, r: Reading) -> None:
        self._run(
            """INSERT INTO readings (place_id, ts, occupied, capacity, source) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (place_id, ts, source) DO UPDATE SET occupied = excluded.occupied,
               capacity = excluded.capacity""",
            (r.place_id, r.ts.isoformat(), r.occupied, r.capacity, r.source),
        )

    def readings(self, place_id: str, limit: int = 500) -> list[Reading]:
        rows = self._run(
            "SELECT place_id, ts, occupied, capacity, source FROM readings WHERE place_id = ? "
            "ORDER BY ts DESC LIMIT ?",
            (place_id, int(limit)),
        )
        return [Reading(p, _to_dt(t), o, c, s) for p, t, o, c, s in reversed(rows)]

    def latest(self) -> dict[str, Reading]:
        out: dict[str, Reading] = {}
        for (pid,) in self._run("SELECT DISTINCT place_id FROM readings"):
            got = self.readings(pid, limit=1)
            if got:
                out[pid] = got[-1]
        return out

    def add_forecast(self, place_id: str, target: datetime, predicted: int, made_at: datetime) -> None:
        self._run(
            """INSERT INTO forecasts (place_id, target_ts, predicted, made_at) VALUES (?, ?, ?, ?)
               ON CONFLICT (place_id, target_ts) DO UPDATE SET predicted = excluded.predicted,
               made_at = excluded.made_at""",
            (place_id, target.isoformat(), int(predicted), made_at.isoformat()),
        )

    def count(self, table: str = "readings") -> int:
        if table not in {"readings", "forecasts"}:
            raise ValueError("unknown table")
        return int(self._run(f"SELECT COUNT(*) FROM {table}")[0][0])

    def close(self) -> None:
        self.conn.close()
