from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings
from app.data.akshare_provider import AkshareProvider, MarketDataProvider
from app.data.market_history import DEFAULT_MARKET_HISTORY_PATH, MarketHistoryStore


SEGMENTS = (
    ("sh_main", "akshare.stock_info_sh_name_code.main", "get_sh_main_code_name"),
    ("sh_star", "akshare.stock_info_sh_name_code.star", "get_sh_star_code_name"),
    ("sz_a", "akshare.stock_info_sz_name_code.a", "get_sz_a_code_name"),
    ("bj", "akshare.stock_info_bj_name_code", "get_bj_code_name"),
)
DISCOVERY_SOURCE = "akshare.segmented_exchange_code_name_catalog"
COMBINED_FALLBACK_SOURCE = "akshare.stock_info_a_code_name"
DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[2] / "logs" / "current_a_share_universe.json"
)


class InstrumentCatalogRefreshService:
    """Refresh the research-only A-share instrument catalog from complete sources."""

    def __init__(
        self,
        *,
        provider: MarketDataProvider | None = None,
        database_path: str | Path = DEFAULT_MARKET_HISTORY_PATH,
        minimum_member_count: int = 4_000,
        minimum_retained_ratio: float = 0.9,
    ) -> None:
        self.provider = provider or AkshareProvider()
        self.database_path = Path(database_path)
        self.minimum_member_count = max(1, int(minimum_member_count))
        self.minimum_retained_ratio = min(1.0, max(0.5, float(minimum_retained_ratio)))

    def run(
        self,
        *,
        apply: bool = False,
        manifest_path: str | Path | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        observed_at = (now or datetime.now().astimezone()).isoformat(timespec="seconds")
        if apply and settings.enable_live_trading:
            return {
                "status": "blocked",
                "reason": "live_trading_enabled",
                "mode": "apply",
                "observed_at": observed_at,
                "member_count": 0,
                "discovery_complete": False,
                "attempts": [],
                "writes_enabled": False,
                "safety": self._safety(writes_enabled=False),
            }
        members_by_segment: dict[str, list[dict[str, Any]]] = {}
        attempts: list[dict[str, Any]] = []
        for segment, source, method_name in SEGMENTS:
            loader = getattr(self.provider, method_name, None)
            if not callable(loader):
                attempts.append(
                    {"segment": segment, "source": source, "status": "unsupported", "count": 0}
                )
                continue
            try:
                frame = loader()
                segment_members = self._extract_members(frame, segment=segment)
            except Exception as exc:
                attempts.append(
                    {
                        "segment": segment,
                        "source": source,
                        "status": "error",
                        "count": 0,
                        "error": str(exc),
                    }
                )
                continue
            if segment_members:
                members_by_segment[segment] = segment_members
            attempts.append(
                {
                    "segment": segment,
                    "source": source,
                    "status": "success" if segment_members else "empty",
                    "count": len(segment_members),
                }
            )

        missing_segments = [
            segment for segment, _, _ in SEGMENTS if segment not in members_by_segment
        ]
        fallback_used = False
        if missing_segments:
            combined_loader = getattr(self.provider, "get_a_share_code_name", None)
            if not callable(combined_loader):
                attempts.extend(
                    {
                        "segment": segment,
                        "source": COMBINED_FALLBACK_SOURCE,
                        "status": "unsupported",
                        "count": 0,
                    }
                    for segment in missing_segments
                )
            else:
                try:
                    combined_frame = combined_loader()
                except Exception as exc:
                    attempts.extend(
                        {
                            "segment": segment,
                            "source": COMBINED_FALLBACK_SOURCE,
                            "status": "error",
                            "count": 0,
                            "error": str(exc),
                        }
                        for segment in missing_segments
                    )
                else:
                    for segment in missing_segments:
                        try:
                            fallback_members = self._extract_members(
                                combined_frame,
                                segment=segment,
                                ignore_out_of_segment=True,
                            )
                        except Exception as exc:
                            attempts.append(
                                {
                                    "segment": segment,
                                    "source": COMBINED_FALLBACK_SOURCE,
                                    "status": "error",
                                    "count": 0,
                                    "error": str(exc),
                                }
                            )
                            continue
                        if fallback_members:
                            members_by_segment[segment] = fallback_members
                            fallback_used = True
                        attempts.append(
                            {
                                "segment": segment,
                                "source": COMBINED_FALLBACK_SOURCE,
                                "status": (
                                    "success_fallback" if fallback_members else "empty"
                                ),
                                "count": len(fallback_members),
                            }
                        )

        members = [
            member
            for segment, _, _ in SEGMENTS
            for member in members_by_segment.get(segment, [])
        ]
        discovery_complete = (
            len(members_by_segment) == len(SEGMENTS)
            and len(members) >= self.minimum_member_count
        )
        discovery_status = (
            "complete_external_with_combined_fallback"
            if discovery_complete and fallback_used
            else "complete_external"
            if discovery_complete
            else "partial_external"
        )
        if not discovery_complete:
            return {
                "status": "partial",
                "reason": "incomplete_external_catalog",
                "mode": "apply" if apply else "dry_run",
                "observed_at": observed_at,
                "member_count": len(members),
                "discovery_complete": False,
                "discovery_status": discovery_status,
                "attempts": attempts,
                "writes_enabled": False,
                "safety": self._safety(writes_enabled=False),
            }
        try:
            canonical_members = self._canonicalize_members(members)
        except ValueError as exc:
            return {
                "status": "partial",
                "mode": "apply" if apply else "dry_run",
                "observed_at": observed_at,
                "member_count": len(members),
                "discovery_complete": False,
                "attempts": [
                    *attempts,
                    {"segment": "validation", "status": "error", "error": str(exc)},
                ],
                "writes_enabled": False,
                "safety": self._safety(writes_enabled=False),
            }
        universe_symbols = [member["symbol"] for member in canonical_members]
        try:
            baseline_member_count, baseline_segment_counts = self._latest_catalog_baseline()
        except sqlite3.Error as exc:
            return {
                "status": "partial",
                "reason": "catalog_baseline_unavailable",
                "mode": "apply" if apply else "dry_run",
                "observed_at": observed_at,
                "member_count": len(canonical_members),
                "discovery_complete": False,
                "external_discovery_complete": True,
                "attempts": attempts,
                "error": str(exc),
                "writes_enabled": False,
                "safety": self._safety(writes_enabled=False),
            }
        incoming_segment_counts = {
            segment: len(members_by_segment.get(segment, []))
            for segment, _, _ in SEGMENTS
        }
        retained_ratio = (
            len(canonical_members) / baseline_member_count
            if baseline_member_count
            else 1.0
        )
        if baseline_member_count and retained_ratio < self.minimum_retained_ratio:
            return {
                "status": "partial",
                "reason": "suspicious_member_count_drop",
                "mode": "apply" if apply else "dry_run",
                "observed_at": observed_at,
                "member_count": len(canonical_members),
                "baseline_member_count": baseline_member_count,
                "retained_ratio": round(retained_ratio, 6),
                "minimum_retained_ratio": self.minimum_retained_ratio,
                "discovery_complete": False,
                "external_discovery_complete": True,
                "attempts": attempts,
                "writes_enabled": False,
                "safety": self._safety(writes_enabled=False),
            }
        for segment, _, _ in SEGMENTS:
            segment_baseline_count = baseline_segment_counts.get(segment, 0)
            if not segment_baseline_count:
                continue
            segment_member_count = incoming_segment_counts[segment]
            segment_retained_ratio = segment_member_count / segment_baseline_count
            if segment_retained_ratio >= self.minimum_retained_ratio:
                continue
            return {
                "status": "partial",
                "reason": "suspicious_segment_count_drop",
                "segment": segment,
                "mode": "apply" if apply else "dry_run",
                "observed_at": observed_at,
                "member_count": len(canonical_members),
                "baseline_member_count": baseline_member_count,
                "retained_ratio": round(retained_ratio, 6),
                "segment_member_count": segment_member_count,
                "segment_baseline_count": segment_baseline_count,
                "segment_retained_ratio": round(segment_retained_ratio, 6),
                "minimum_retained_ratio": self.minimum_retained_ratio,
                "discovery_complete": False,
                "external_discovery_complete": True,
                "attempts": attempts,
                "writes_enabled": False,
                "safety": self._safety(writes_enabled=False),
            }
        universe_hash = hashlib.sha256(
            "\n".join(universe_symbols).encode("utf-8")
        ).hexdigest()
        catalog_hash = self._stable_hash(canonical_members)
        target_manifest = Path(manifest_path or DEFAULT_MANIFEST_PATH)
        manifest = {
            "schema_version": 2,
            "manifest_kind": "a_share_instrument_catalog",
            "observed_at": observed_at,
            "discovery_source": DISCOVERY_SOURCE,
            "discovery_status": discovery_status,
            "discovery_complete": True,
            "discovery_attempts": attempts,
            "universe_count": len(canonical_members),
            "universe_symbols": universe_symbols,
            # Compatibility contract for CandidateHistorySeeder v1 manifests.
            "universe_hash": universe_hash,
            "catalog_hash": catalog_hash,
            "members": canonical_members,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        if not apply:
            return {
                "status": "planned",
                "mode": "dry_run",
                "observed_at": observed_at,
                "member_count": len(canonical_members),
                "discovery_complete": True,
                "discovery_status": discovery_status,
                "attempts": attempts,
                "universe_hash": universe_hash,
                "catalog_hash": catalog_hash,
                "manifest_path": str(target_manifest.resolve()),
                "writes_enabled": False,
                "safety": self._safety(writes_enabled=False),
            }

        store = MarketHistoryStore(self.database_path)
        store.initialize()
        changes, snapshot_id = self._persist_complete_catalog(
            store,
            members=canonical_members,
            observed_at=observed_at,
            catalog_hash=catalog_hash,
            attempts=attempts,
        )
        self._write_manifest_atomic(target_manifest, manifest)
        return {
            "status": "completed",
            "mode": "apply",
            "observed_at": observed_at,
            "member_count": len(canonical_members),
            "discovery_complete": True,
            "discovery_status": discovery_status,
            "attempts": attempts,
            "universe_hash": universe_hash,
            "catalog_hash": catalog_hash,
            "snapshot_id": snapshot_id,
            "changes": changes,
            "manifest_path": str(target_manifest.resolve()),
            "writes_enabled": True,
            "safety": self._safety(writes_enabled=True),
        }

    @classmethod
    def _extract_members(
        cls,
        frame: pd.DataFrame,
        *,
        segment: str,
        ignore_out_of_segment: bool = False,
    ) -> list[dict[str, Any]]:
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            return []
        code_column = cls._first_column(
            frame,
            ("证券代码", "A股代码", "代码", "symbol", "code"),
        )
        name_column = cls._first_column(
            frame,
            ("证券简称", "A股简称", "名称", "name"),
        )
        if code_column is None or name_column is None:
            raise ValueError(f"catalog has no code/name columns: {list(frame.columns)}")
        members: list[dict[str, Any]] = []
        for row in frame.to_dict(orient="records"):
            symbol = cls._normalize_symbol(row.get(code_column), segment=segment)
            if symbol is None and ignore_out_of_segment:
                continue
            raw_name = row.get(name_column)
            name = "" if raw_name is None or pd.isna(raw_name) else str(raw_name).strip()
            if symbol is None or not name:
                raise ValueError(f"invalid code/name row in {segment}")
            list_date_column = cls._first_column(
                frame,
                ("上市日期", "A股上市日期", "list_date"),
            )
            members.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "exchange": symbol[:2],
                    "board": cls._board(symbol, segment=segment),
                    "list_date": cls._normalize_date(
                        row.get(list_date_column) if list_date_column else None
                    ),
                    "status": "active",
                }
            )
        return members

    @staticmethod
    def _board(symbol: str, *, segment: str) -> str:
        if segment == "sh_main":
            return "sh_main"
        if segment == "sh_star":
            return "star"
        if segment == "bj":
            return "beijing"
        return "chi_next" if symbol[2:].startswith(("300", "301", "302")) else "sz_main"

    @staticmethod
    def _normalize_date(value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date().isoformat()

    @classmethod
    def _canonicalize_members(cls, members: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_symbol: dict[str, dict[str, Any]] = {}
        for member in members:
            symbol = str(member["symbol"])
            previous = by_symbol.get(symbol)
            if previous is not None and previous != member:
                raise ValueError(f"conflicting duplicate instrument: {symbol}")
            if previous is not None:
                raise ValueError(f"duplicate instrument: {symbol}")
            by_symbol[symbol] = member
        return [by_symbol[symbol] for symbol in sorted(by_symbol)]

    def _persist_complete_catalog(
        self,
        store: MarketHistoryStore,
        *,
        members: list[dict[str, Any]],
        observed_at: str,
        catalog_hash: str,
        attempts: list[dict[str, Any]],
    ) -> tuple[dict[str, int], int]:
        with store.connect() as connection:
            existing = {
                str(row["symbol"]): dict(row)
                for row in connection.execute(
                    "SELECT symbol, name, status FROM instruments "
                    "WHERE asset_type = 'stock' AND exchange IN ('SH', 'SZ', 'BJ')"
                ).fetchall()
            }
            incoming = {str(member["symbol"]): member for member in members}
            changes = {
                "added": sum(symbol not in existing for symbol in incoming),
                "renamed": sum(
                    symbol in existing
                    and str(existing[symbol].get("name") or "") != str(member["name"])
                    for symbol, member in incoming.items()
                ),
                "reactivated": sum(
                    symbol in existing and existing[symbol].get("status") != "active"
                    for symbol in incoming
                ),
                "inactivated": sum(
                    symbol not in incoming and row.get("status") == "active"
                    for symbol, row in existing.items()
                ),
            }

            connection.execute(
                "CREATE TEMP TABLE incoming_catalog_symbols(symbol TEXT PRIMARY KEY)"
            )
            connection.executemany(
                "INSERT INTO incoming_catalog_symbols(symbol) VALUES (?)",
                [(member["symbol"],) for member in members],
            )
            connection.executemany(
                """
                INSERT INTO instruments(
                    symbol, name, exchange, asset_type, board, currency,
                    list_date, delist_date, status, provider, fetched_at, updated_at
                ) VALUES (?, ?, ?, 'stock', ?, 'CNY', ?, NULL, 'active', ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    exchange = excluded.exchange,
                    asset_type = 'stock',
                    board = excluded.board,
                    currency = 'CNY',
                    list_date = COALESCE(excluded.list_date, instruments.list_date),
                    delist_date = NULL,
                    status = 'active',
                    provider = excluded.provider,
                    fetched_at = excluded.fetched_at,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        member["symbol"],
                        member["name"],
                        member["exchange"],
                        member["board"],
                        member["list_date"],
                        DISCOVERY_SOURCE,
                        observed_at,
                        observed_at,
                    )
                    for member in members
                ],
            )
            connection.execute(
                """
                UPDATE instruments
                SET status = 'inactive', updated_at = ?
                WHERE asset_type = 'stock'
                  AND exchange IN ('SH', 'SZ', 'BJ')
                  AND status = 'active'
                  AND NOT EXISTS (
                      SELECT 1 FROM incoming_catalog_symbols AS incoming
                      WHERE incoming.symbol = instruments.symbol
                  )
                """,
                (observed_at,),
            )
            snapshot_date = observed_at[:10]
            metadata_json = json.dumps(
                {
                    "schema_version": 2,
                    "catalog_hash": catalog_hash,
                    "discovery_complete": True,
                    "discovery_attempts": attempts,
                    "research_only": True,
                    "simulation_only": True,
                    "live_trading_enabled": False,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            connection.execute(
                """
                INSERT INTO universe_snapshots(
                    universe_name, snapshot_date, provider, fetched_at,
                    member_count, source_hash, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(universe_name, snapshot_date, provider, source_hash) DO NOTHING
                """,
                (
                    "a_share_official_catalog",
                    snapshot_date,
                    DISCOVERY_SOURCE,
                    observed_at,
                    len(members),
                    catalog_hash,
                    metadata_json,
                ),
            )
            snapshot_id = int(
                connection.execute(
                    """
                    SELECT id FROM universe_snapshots
                    WHERE universe_name = ? AND snapshot_date = ?
                      AND provider = ? AND source_hash = ?
                    """,
                    (
                        "a_share_official_catalog",
                        snapshot_date,
                        DISCOVERY_SOURCE,
                        catalog_hash,
                    ),
                ).fetchone()["id"]
            )
            connection.executemany(
                """
                INSERT INTO universe_members(snapshot_id, symbol, member_metadata_json)
                VALUES (?, ?, ?)
                ON CONFLICT(snapshot_id, symbol) DO NOTHING
                """,
                [
                    (
                        snapshot_id,
                        member["symbol"],
                        json.dumps(
                            member,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    )
                    for member in members
                ],
            )
            connection.execute("DROP TABLE incoming_catalog_symbols")
        return changes, snapshot_id

    def _latest_catalog_baseline(self) -> tuple[int | None, dict[str, int]]:
        if not self.database_path.exists():
            return None, {}
        store = MarketHistoryStore(self.database_path)
        with store.connect(read_only=True) as connection:
            row = connection.execute(
                """
                SELECT id, member_count
                FROM universe_snapshots
                WHERE universe_name = 'a_share_official_catalog'
                  AND provider = ?
                ORDER BY snapshot_date DESC, id DESC
                LIMIT 1
                """,
                (DISCOVERY_SOURCE,),
            ).fetchone()
            if row is None:
                return None, {}
            symbols = [
                str(member["symbol"])
                for member in connection.execute(
                    "SELECT symbol FROM universe_members WHERE snapshot_id = ?",
                    (int(row["id"]),),
                ).fetchall()
            ]
        member_count = int(row["member_count"])
        if len(symbols) != member_count:
            raise sqlite3.DatabaseError("latest official catalog snapshot is incomplete")
        segment_counts = {segment: 0 for segment, _, _ in SEGMENTS}
        for symbol in symbols:
            segment = self._segment_for_symbol(symbol)
            if segment is None:
                raise sqlite3.DatabaseError(
                    f"latest official catalog contains unsupported symbol: {symbol}"
                )
            segment_counts[segment] += 1
        return member_count, segment_counts

    @staticmethod
    def _segment_for_symbol(symbol: str) -> str | None:
        if symbol.startswith(("SH688", "SH689")):
            return "sh_star"
        if symbol.startswith("SH"):
            return "sh_main"
        if symbol.startswith("SZ"):
            return "sz_a"
        if symbol.startswith("BJ"):
            return "bj"
        return None

    @staticmethod
    def _stable_hash(payload: Any) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _write_manifest_atomic(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _first_column(frame: pd.DataFrame, names: tuple[str, ...]) -> str | None:
        return next((name for name in names if name in frame.columns), None)

    @staticmethod
    def _normalize_symbol(value: Any, *, segment: str) -> str | None:
        text = str(value or "").strip().upper()
        if text.endswith(".0") and text[:-2].isdigit():
            text = text[:-2]
        digits = "".join(character for character in text if character.isdigit())
        if len(digits) != 6:
            return None
        exchange = "SH" if segment.startswith("sh_") else "SZ" if segment == "sz_a" else "BJ"
        symbol = f"{exchange}{digits}"
        valid = {
            "sh_main": digits.startswith(("600", "601", "603", "605")),
            "sh_star": digits.startswith(("688", "689")),
            "sz_a": digits.startswith(("000", "001", "002", "003", "300", "301", "302")),
            "bj": digits.startswith(("43", "82", "83", "87", "88", "92")),
        }
        return symbol if valid[segment] else None

    @staticmethod
    def _safety(*, writes_enabled: bool) -> dict[str, Any]:
        return {
            "research_only": True,
            "simulation_only": True,
            "live_trading_enabled": bool(settings.enable_live_trading),
            "broker_or_order_capability": False,
            "writes_enabled": writes_enabled,
        }
