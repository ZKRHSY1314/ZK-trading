from __future__ import annotations

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
        if available.date() < start:
            raise ValueError("membership cannot be available before effective_from")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


class SectorExposureResolver:
    """Point-in-time company-to-sector exposure seam."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.store.init()

    def record(self, membership: SectorMembership) -> dict[str, Any]:
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

    def sectors_for(self, symbol: str, *, as_of: str | datetime) -> list[dict[str, Any]]:
        cutoff = _cutoff(as_of).isoformat()
        rows = self.store.fetch_all(
            """
            SELECT symbol, sector, effective_from, effective_to,
                   source, available_at, confidence
            FROM sector_membership_history
            WHERE symbol = ?
              AND date(effective_from) <= date(?)
              AND (effective_to IS NULL OR date(effective_to) >= date(?))
              AND datetime(available_at) <= datetime(?)
            ORDER BY confidence DESC, sector ASC, effective_from DESC
            """,
            (symbol.strip().upper(), cutoff, cutoff, cutoff),
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
        cutoff = _cutoff(as_of).isoformat()
        placeholders = ",".join("?" for _ in normalized)
        rows = self.store.fetch_all(
            f"""
            SELECT symbol, sector, effective_from, effective_to,
                   source, available_at, confidence
            FROM sector_membership_history
            WHERE symbol IN ({placeholders})
              AND date(effective_from) <= date(?)
              AND (effective_to IS NULL OR date(effective_to) >= date(?))
              AND datetime(available_at) <= datetime(?)
            ORDER BY symbol ASC, confidence DESC, sector ASC, effective_from DESC
            """,
            (*normalized, cutoff, cutoff, cutoff),
        )
        for row in rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol in resolved:
                resolved[symbol].append({**row, "review_only": True})
        return resolved

    def symbols_for(self, sector: str, *, as_of: str | datetime) -> list[dict[str, Any]]:
        cutoff = _cutoff(as_of).isoformat()
        rows = self.store.fetch_all(
            """
            SELECT symbol, sector, effective_from, effective_to,
                   source, available_at, confidence
            FROM sector_membership_history
            WHERE sector = ?
              AND date(effective_from) <= date(?)
              AND (effective_to IS NULL OR date(effective_to) >= date(?))
              AND datetime(available_at) <= datetime(?)
            ORDER BY confidence DESC, symbol ASC, effective_from DESC
            """,
            (sector.strip(), cutoff, cutoff, cutoff),
        )
        return [{**row, "review_only": True} for row in rows]


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
