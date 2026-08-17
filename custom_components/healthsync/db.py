"""A private, append-only archive of every sample HealthSync has ever
received, independent of Home Assistant's own recorder.

Why this exists: HA's regular entity state history is always timestamped at
the moment it was written (there is no supported way to backdate a state
change), and HA's long-term statistics API only stores hourly aggregates
(min/max/mean) — never individual readings. Neither can hold "every reading,
at its own exact Apple-recorded timestamp, completely unaveraged" — which is
the whole point here. This sidesteps both limits by not living in HA's
recorder at all: a small SQLite database of its own, storing every field of
every sample exactly as the app sent it (plus a raw_payload JSON copy, so
nothing is ever lost even if a future metric adds fields this schema
doesn't have a dedicated column for yet). Queryable on demand via the
healthsync.get_readings service — see __init__.py.

Stored under Home Assistant's own .storage directory so it's picked up
automatically by HA's Backup/Snapshot system, the same as everything else
HA considers "its" data.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Generous busy-wait before sqlite3 gives up and raises "database is locked",
# passed to every connection. Python's default is 5s, which sounds like a
# lot but wasn't — a big historical backfill (e.g. Weight/VO2 Max pulling
# full history, added 16 Aug 2026) can fire dozens of webhook POSTs in quick
# succession, each with its own executor-job thread opening its own
# connection; under that burst, 5s of queueing was measurably not always
# enough. 30s costs nothing in the common case (a write that isn't
# contended returns immediately either way) and gives a burst plenty of
# room to drain instead of failing outright.
_CONNECT_TIMEOUT = 30.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL,
    sleep_stage TEXT,
    unit TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    start_epoch REAL,
    source TEXT,
    daily_total INTEGER,
    workout_type TEXT,
    distance REAL,
    raw_payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_lookup
    ON readings (entry_id, metric, start_epoch);
"""


def _parse_epoch(raw: Any) -> float | None:
    """Best-effort parse of the app's ISO8601 start_date into a Unix
    timestamp, used only for fast/robust range queries — start_date itself
    (Apple's exact original string) is always stored and returned as-is
    regardless of whether this parse succeeds."""
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class ReadingsStore:
    """One instance per config entry — a complete, unaveraged archive of
    every sample received for that entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self._path = hass.config.path(".storage", f"healthsync_{entry_id}_readings.db")
        self._conn: sqlite3.Connection | None = None
        # Guards every access to `_conn`. Originally each insert/query opened
        # its own short-lived connection; under a big historical batch (e.g.
        # Weight/VO2 Max's new full-history first sync, 16 Aug 2026) several
        # of those could land close enough together that two connections
        # tried to write at once, and sqlite3 raised "database is locked" —
        # 86 occurrences logged, all archive writes failing, the same day
        # that first-sync change shipped. A single persistent connection,
        # entirely serialized through this lock, removes the race outright
        # rather than just tolerating it with a longer timeout: nothing ever
        # contends for the file in the first place, since only one caller is
        # ever inside SQLite at a time. It also fixes a second symptom from
        # the same root cause — the client-side webhook POST timing out
        # while backfilling a big batch, since each sample was previously
        # paying for its own connection open/journal-init/close cycle;
        # reusing one open connection makes each insert markedly cheaper, so
        # a whole batch's worth no longer risks outrunning the app's request
        # timeout.
        self._lock = asyncio.Lock()

    async def async_setup(self) -> None:
        await self._hass.async_add_executor_job(self._setup)

    async def async_close(self) -> None:
        """Closes the persistent connection cleanly on unload/reload — this
        integration gets restarted often (every update needs one), and with
        a single long-lived connection now (rather than the old
        open-per-call pattern, which had nothing to leak) leaving it open
        across a reload would hold the file handle unnecessarily and risk
        WAL/SHM files not getting merged back into the main db file cleanly.
        Best-effort: never worth blocking unload over."""
        conn, self._conn = self._conn, None
        if conn is not None:
            try:
                await self._hass.async_add_executor_job(conn.close)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("HealthSync: failed to close readings database cleanly")

    def _setup(self) -> None:
        # check_same_thread=False: HA's executor job pool doesn't guarantee
        # the same worker thread runs every call, but `self._lock` already
        # guarantees only one of them is ever inside this connection at a
        # time, which is the actual requirement sqlite3 cares about — so
        # disabling its same-thread check here is safe, not a workaround.
        conn = sqlite3.connect(self._path, timeout=_CONNECT_TIMEOUT, check_same_thread=False)
        # WAL: readers (get_readings) are never blocked waiting on a writer,
        # and writers queue via the lock above rather than colliding.
        # synchronous=NORMAL is WAL's standard pairing — still crash-safe,
        # just without fsync-ing on every single insert, which matters here
        # given how many inserts a big historical batch fires in a row.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(_SCHEMA)
        self._conn = conn

    async def async_insert(self, metric: str, sample: dict[str, Any]) -> None:
        """Archives one sample exactly as received. Best-effort — deliberately
        never allowed to break the webhook response; every other part of the
        integration (sensors, events, statistics) already processed this
        sample regardless of whether the archive write succeeds."""
        try:
            async with self._lock:
                await self._hass.async_add_executor_job(self._insert, metric, sample)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("HealthSync: failed to archive a %s reading", metric)

    def _insert(self, metric: str, sample: dict[str, Any]) -> None:
        if self._conn is None:
            raise RuntimeError("ReadingsStore used before async_setup")
        raw_payload = json.dumps({k: v for k, v in sample.items() if k != "secret"})
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO readings
                    (entry_id, metric, value, sleep_stage, unit, start_date,
                     end_date, start_epoch, source, daily_total, workout_type,
                     distance, raw_payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._entry_id,
                    metric,
                    sample.get("value"),
                    sample.get("sleep_stage"),
                    sample.get("unit"),
                    sample.get("start_date"),
                    sample.get("end_date"),
                    _parse_epoch(sample.get("start_date")),
                    sample.get("source"),
                    sample.get("daily_total"),
                    sample.get("workout_type"),
                    sample.get("distance"),
                    raw_payload,
                ),
            )

    async def async_query(
        self,
        metric: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict[str, Any]]:
        async with self._lock:
            return await self._hass.async_add_executor_job(self._query, metric, start, end)

    def _query(
        self,
        metric: str,
        start: datetime | None,
        end: datetime | None,
    ) -> list[dict[str, Any]]:
        clauses = ["entry_id = ?", "metric = ?"]
        params: list[Any] = [self._entry_id, metric]
        if start is not None:
            clauses.append("start_epoch >= ?")
            params.append(start.timestamp())
        if end is not None:
            clauses.append("start_epoch <= ?")
            params.append(end.timestamp())
        query = (
            "SELECT value, sleep_stage, unit, start_date, end_date, source, "
            "daily_total, workout_type, distance FROM readings WHERE "
            + " AND ".join(clauses)
            + " ORDER BY start_epoch ASC"
        )
        if self._conn is None:
            raise RuntimeError("ReadingsStore used before async_setup")
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(query, params).fetchall()
        self._conn.row_factory = None
        return [dict(row) for row in rows]
