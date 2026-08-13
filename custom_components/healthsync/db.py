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

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

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

    async def async_setup(self) -> None:
        await self._hass.async_add_executor_job(self._setup)

    def _setup(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.executescript(_SCHEMA)

    async def async_insert(self, metric: str, sample: dict[str, Any]) -> None:
        """Archives one sample exactly as received. Best-effort — deliberately
        never allowed to break the webhook response; every other part of the
        integration (sensors, events, statistics) already processed this
        sample regardless of whether the archive write succeeds."""
        try:
            await self._hass.async_add_executor_job(self._insert, metric, sample)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("HealthSync: failed to archive a %s reading", metric)

    def _insert(self, metric: str, sample: dict[str, Any]) -> None:
        raw_payload = json.dumps({k: v for k, v in sample.items() if k != "secret"})
        with sqlite3.connect(self._path) as conn:
            conn.execute(
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
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
