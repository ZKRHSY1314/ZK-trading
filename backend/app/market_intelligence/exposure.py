from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.storage.sqlite_store import SQLiteStore


SHANGHAI = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class SectorMembership:
    symbol: str
    sector: str
    effective_from: str
    effective_to: str | None
    source: str
    available_at: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.sector.strip() or not self.source.strip():
            raise ValueError("symbol, sector, and source are required")
        start = date.fromisoformat(self.effective_from[:10])
        if self.effective_to and date.fromisoformat(self.effective_to[:10]) < start:
            raise ValueError("effective_to cannot be before effective_from")
        available = _cutoff(self.available_at)
        if available.astimezone(SHANGHAI).date() < start:
            raise ValueError("membership cannot be available before effective_from")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


def membership_hash(symbols: list[str] | tuple[str, ...] | set[str]) -> str:
    """Return a stable hash for a normalized, order-independent member set."""
    normalized = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
    if not normalized:
        raise ValueError("a membership snapshot must contain at least one symbol")
    return hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()


class SectorExposureResolver:
    """Resolve legacy intervals and immutable full-member snapshots point in time."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.store.init()

    def record(self, membership: SectorMembership) -> dict[str, Any]:
        """Record a legacy interval membership for backward-compatible imports."""
        values = (
            membership.symbol.strip().upper(),
            membership.sector.strip(),
            membership.effective_from[:10],
            membership.effective_to[:10] if membership.effective_to else None,
            membership.source.strip(),
            _cutoff(membership.available_at).isoformat(),
            float(membership.confidence),
        )
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sector_membership_history(
                    symbol, sector, effective_from, effective_to,
                    source, available_at, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            row = conn.execute(
                """
                SELECT symbol, sector, effective_from, effective_to,
                       source, available_at, confidence
                FROM sector_membership_history
                WHERE symbol = ? AND sector = ? AND effective_from = ? AND source = ?
                """,
                (values[0], values[1], values[2], values[4]),
            ).fetchone()
        persisted = dict(row)
        comparable = {
            "symbol": values[0],
            "sector": values[1],
            "effective_from": values[2],
            "effective_to": values[3],
            "source": values[4],
            "available_at": values[5],
            "confidence": values[6],
        }
        if persisted != comparable:
            raise ValueError("sector membership identity is immutable; record a new effective date")
        return {**persisted, "review_only": True}

    def latest_snapshot(
        self,
        *,
        source: str,
        sector: str,
        as_of: str | datetime,
    ) -> dict[str, Any] | None:
        cutoff = _cutoff(as_of)
        return self.store.fetch_one(
            """
            SELECT id, source, sector, member_hash, member_count,
                   observed_at, effective_date, confidence
            FROM sector_membership_snapshots
            WHERE source = ? AND lower(sector) = lower(?)
              AND observed_at <= ?
              AND effective_date <= ?
            ORDER BY observed_at DESC, id DESC
            LIMIT 1
            """,
            (
                source.strip(),
                sector.strip(),
                cutoff.isoformat(),
                cutoff.astimezone(SHANGHAI).date().isoformat(),
            ),
        )

    def record_snapshot(
        self,
        *,
        source: str,
        sector: str,
        symbols: list[str] | tuple[str, ...] | set[str],
        member_hash: str,
        observed_at: str | datetime,
        effective_date: str,
        confidence: float,
    ) -> dict[str, Any]:
        return self.record_snapshots(
            [
                {
                    "source": source,
                    "sector": sector,
                    "symbols": symbols,
                    "member_hash": member_hash,
                    "observed_at": observed_at,
                    "effective_date": effective_date,
                    "confidence": confidence,
                }
            ]
        )[0]

    def record_snapshots(self, snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Append complete board snapshots in one atomic transaction."""
        prepared = [self._prepare_snapshot(snapshot) for snapshot in snapshots]
        if not prepared:
            return []
        persisted: list[dict[str, Any]] = []
        with self.store.connect() as conn:
            for snapshot in prepared:
                cursor = conn.execute(
                    """
                    INSERT INTO sector_membership_snapshots(
                        source, sector, member_hash, member_count,
                        observed_at, effective_date, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot["source"],
                        snapshot["sector"],
                        snapshot["member_hash"],
                        snapshot["member_count"],
                        snapshot["observed_at"],
                        snapshot["effective_date"],
                        snapshot["confidence"],
                    ),
                )
                snapshot_id = int(cursor.lastrowid)
                conn.executemany(
                    """
                    INSERT INTO sector_membership_snapshot_members(snapshot_id, symbol)
                    VALUES (?, ?)
                    """,
                    [(snapshot_id, symbol) for symbol in snapshot["symbols"]],
                )
                persisted.append(
                    {
                        "id": snapshot_id,
                        **{key: value for key, value in snapshot.items() if key != "symbols"},
                        "review_only": True,
                    }
                )
        return persisted

    @staticmethod
    def _prepare_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        symbols = snapshot.get("symbols") or []
        normalized = sorted(
            {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}
        )
        expected_hash = membership_hash(normalized)
        supplied_hash = str(snapshot.get("member_hash") or "")
        if supplied_hash != expected_hash:
            raise ValueError("member_hash does not match the normalized snapshot members")
        source = str(snapshot.get("source") or "").strip()
        sector = str(snapshot.get("sector") or "").strip()
        if not source or not sector:
            raise ValueError("source and sector are required")
        effective = date.fromisoformat(str(snapshot.get("effective_date") or "")[:10])
        observed = _cutoff(snapshot.get("observed_at"))
        if effective > observed.astimezone(SHANGHAI).date():
            raise ValueError(
                "snapshot effective_date cannot be after its Shanghai observation date"
            )
        confidence = float(snapshot.get("confidence") or 0.0)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return {
            "source": source,
            "sector": sector,
            "symbols": normalized,
            "member_hash": supplied_hash,
            "member_count": len(normalized),
            "observed_at": observed.isoformat(),
            "effective_date": effective.isoformat(),
            "confidence": confidence,
        }

    def sectors_for(self, symbol: str, *, as_of: str | datetime) -> list[dict[str, Any]]:
        rows = self._resolved_rows(
            as_of=as_of,
            where_sql="upper(symbol) = upper(?)",
            where_params=(symbol.strip().upper(),),
            order_sql="confidence DESC, sector ASC, effective_from DESC, source ASC",
        )
        return [{**row, "review_only": True} for row in rows]

    def sectors_for_many(
        self,
        symbols: list[str],
        *,
        as_of: str | datetime,
    ) -> dict[str, list[dict[str, Any]]]:
        """Resolve a selection universe with one point-in-time query."""
        normalized = sorted({str(symbol).strip().upper() for symbol in symbols if symbol})
        resolved = {symbol: [] for symbol in normalized}
        if not normalized:
            return resolved
        placeholders = ",".join("?" for _ in normalized)
        rows = self._resolved_rows(
            as_of=as_of,
            where_sql=f"upper(symbol) IN ({placeholders})",
            where_params=tuple(normalized),
            order_sql=("symbol ASC, confidence DESC, sector ASC, effective_from DESC, source ASC"),
        )
        for row in rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol in resolved:
                resolved[symbol].append({**row, "review_only": True})
        return resolved

    def symbols_for(self, sector: str, *, as_of: str | datetime) -> list[dict[str, Any]]:
        rows = self._resolved_rows(
            as_of=as_of,
            where_sql="lower(sector) = lower(?)",
            where_params=(sector.strip(),),
            order_sql="confidence DESC, symbol ASC, effective_from DESC, source ASC",
        )
        return [{**row, "review_only": True} for row in rows]

    def _resolved_rows(
        self,
        *,
        as_of: str | datetime,
        where_sql: str,
        where_params: tuple[Any, ...],
        order_sql: str,
    ) -> list[dict[str, Any]]:
        cutoff = _cutoff(as_of)
        cutoff_iso = cutoff.isoformat()
        local_date = cutoff.astimezone(SHANGHAI).date().isoformat()
        return self.store.fetch_all(
            f"""
            WITH ranked_snapshots AS (
                SELECT id, source, sector, member_hash, member_count,
                       observed_at, effective_date, confidence,
                        ROW_NUMBER() OVER (
                            PARTITION BY source, lower(sector)
                            ORDER BY observed_at DESC, id DESC
                        ) AS snapshot_rank
                FROM sector_membership_snapshots
                WHERE observed_at <= ?
                  AND effective_date <= ?
            ),
            latest_snapshots AS (
                SELECT * FROM ranked_snapshots WHERE snapshot_rank = 1
            ),
            legacy_rows AS (
                SELECT upper(history.symbol) AS symbol,
                       history.sector AS sector,
                       history.effective_from AS effective_from,
                       history.effective_to AS effective_to,
                       history.source AS source,
                       history.available_at AS available_at,
                       history.confidence AS confidence,
                       'legacy_interval' AS membership_mode,
                       NULL AS snapshot_id,
                       NULL AS member_hash
                FROM sector_membership_history AS history
                WHERE history.effective_from <= ?
                  AND (
                      history.effective_to IS NULL
                      OR history.effective_to >= ?
                  )
                  AND history.available_at <= ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM latest_snapshots AS snapshot
                      WHERE snapshot.source = history.source
                        AND lower(snapshot.sector) = lower(history.sector)
                  )
            ),
            snapshot_rows AS (
                SELECT upper(member.symbol) AS symbol,
                       snapshot.sector AS sector,
                       snapshot.effective_date AS effective_from,
                       NULL AS effective_to,
                       snapshot.source AS source,
                       snapshot.observed_at AS available_at,
                       snapshot.confidence AS confidence,
                       'snapshot' AS membership_mode,
                       snapshot.id AS snapshot_id,
                       snapshot.member_hash AS member_hash
                FROM latest_snapshots AS snapshot
                JOIN sector_membership_snapshot_members AS member
                  ON member.snapshot_id = snapshot.id
            ),
            resolved AS (
                SELECT * FROM legacy_rows
                UNION ALL
                SELECT * FROM snapshot_rows
            )
            SELECT symbol, sector, effective_from, effective_to,
                   source, available_at, confidence,
                   membership_mode, snapshot_id, member_hash
            FROM resolved
            WHERE {where_sql}
            ORDER BY {order_sql}
            """,
            (
                cutoff_iso,
                local_date,
                local_date,
                local_date,
                cutoff_iso,
                *where_params,
            ),
        )


def _cutoff(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        if len(text) == 10:
            parsed = datetime.combine(date.fromisoformat(text), time.max, tzinfo=SHANGHAI)
        else:
            parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(timezone.utc)
