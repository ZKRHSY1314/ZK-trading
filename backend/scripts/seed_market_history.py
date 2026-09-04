from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.config import settings
from app.data.market_history import DEFAULT_MARKET_HISTORY_PATH, MarketHistoryStore


SHANGHAI = ZoneInfo("Asia/Shanghai")
SESSION_FINALIZATION_TIME = time(15, 15)
RULE_REGIME_BOUNDARY = date(2026, 7, 6)
DEFAULT_CANDIDATE_LIMIT = 200
DEFAULT_BARS_PER_SYMBOL = 500
MAX_CANDIDATE_LIMIT = 500
MAX_FULL_MARKET_SYMBOLS = 10_000
MAX_BARS_PER_SYMBOL = 1_000
SCHEMA_VERSION = "market_history_seed.v1"
UNIT_VERIFIED_QFQ_SOURCE = (
    "tencent.fqkline.raw+sina.qfq_factor.unit_verified"
)
TRUSTED_QFQ_SOURCE_SQL = (
    "(lower(COALESCE(source, '')) NOT LIKE '%sina%' "
    f"OR lower(COALESCE(source, '')) = '{UNIT_VERIFIED_QFQ_SOURCE}')"
)

SOURCE_TABLES = (
    "daily_bar_cache",
    "candidate_lifecycle",
    "stock_profiles",
    "auto_discovered_candidates",
    "potential_search_items",
    "candidate_scores",
)
SOURCE_BAR_COLUMNS = {
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "source",
    "adjustment_mode",
    "volume_unit",
    "quality_status",
    "created_at",
    "updated_at",
}


class CandidateHistorySeeder:
    """Bounded, source-read-only import of current candidate daily history."""

    def __init__(
        self,
        source_database: str | Path,
        target_database: str | Path = DEFAULT_MARKET_HISTORY_PATH,
    ) -> None:
        self.source_database = Path(source_database)
        self.target_database = Path(target_database)

    def run(
        self,
        *,
        apply: bool = False,
        candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
        bars_per_symbol: int = DEFAULT_BARS_PER_SYMBOL,
        universe_scope: str = "candidate_hot_cache",
        universe_manifest_path: str | Path | None = None,
        resume_after: str | None = None,
        symbol_limit: int | None = None,
        as_of: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        mode = "apply" if apply else "dry_run"
        universe_scope = str(universe_scope or "candidate_hot_cache").strip().lower()
        if universe_scope not in {"candidate_hot_cache", "full_market_cache"}:
            raise ValueError(f"unsupported universe scope: {universe_scope}")
        candidate_limit = max(
            1,
            min(
                int(candidate_limit),
                (
                    MAX_CANDIDATE_LIMIT
                    if universe_scope == "candidate_hot_cache"
                    else MAX_FULL_MARKET_SYMBOLS
                ),
            ),
        )
        if universe_scope == "full_market_cache":
            candidate_limit = MAX_FULL_MARKET_SYMBOLS
        bars_per_symbol = max(1, min(int(bars_per_symbol), MAX_BARS_PER_SYMBOL))
        safety = self._safety(apply=apply)

        if settings.enable_live_trading:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "blocked",
                "mode": mode,
                "reason": "live_trading_enabled",
                "writes_enabled": False,
                "safety": safety,
            }
        if self.source_database.resolve() == self.target_database.resolve():
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "blocked",
                "mode": mode,
                "reason": "source_and_target_database_must_be_distinct",
                "writes_enabled": False,
                "safety": safety,
            }

        universe_manifest = None
        if universe_scope == "full_market_cache":
            universe_manifest = self._load_universe_manifest(universe_manifest_path)

        current = self._local_now(now)
        completed_cutoff = self._completed_cutoff(current)
        requested_as_of = self._parse_as_of(as_of)
        if requested_as_of is not None and requested_as_of > completed_cutoff:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "blocked",
                "mode": mode,
                "reason": "as_of_is_not_a_completed_session",
                "requested_as_of": requested_as_of.isoformat(),
                "completed_cutoff": completed_cutoff.isoformat(),
                "writes_enabled": False,
                "safety": safety,
            }

        with self._source_connection() as source:
            self._assert_source_schema(source)
            resolved_as_of = self._resolve_as_of(
                source,
                requested_as_of=requested_as_of,
                completed_cutoff=completed_cutoff,
                current=current,
            )
            if resolved_as_of is None:
                return self._empty_result(
                    mode=mode,
                    candidate_limit=candidate_limit,
                    bars_per_symbol=bars_per_symbol,
                    requested_as_of=requested_as_of,
                    completed_cutoff=completed_cutoff,
                    safety=safety,
                )
            universe_candidates = (
                self._load_candidates(source, limit=candidate_limit)
                if universe_scope == "candidate_hot_cache"
                else self._load_full_market_cache_universe(
                    source,
                    symbols=universe_manifest["symbols"],
                    official_members=universe_manifest.get("members_by_symbol"),
                )
            )
            candidates = universe_candidates
            normalized_resume = None
            if resume_after:
                normalized_resume = self._normalize_symbol(resume_after)
                if normalized_resume is None:
                    raise ValueError(f"unsupported resume symbol: {resume_after}")
                candidates = [
                    item
                    for item in candidates
                    if str(item["symbol"]) > normalized_resume
                ]
            normalized_symbol_limit = None
            if symbol_limit is not None:
                normalized_symbol_limit = max(1, min(int(symbol_limit), 500))
                candidates = candidates[:normalized_symbol_limit]
            bars, excluded_invalid = self._load_bars(
                source,
                candidates=candidates,
                as_of=resolved_as_of,
                bars_per_symbol=bars_per_symbol,
                current=current,
            )
            excluded = self._exclusion_stats(
                source,
                candidates=candidates,
                current=current,
            )
            excluded["invalid_ready_qfq_rows"] = excluded_invalid
            ready_universe_symbols = (
                self._load_ready_qfq_symbols(
                    source,
                    symbols=universe_manifest["symbols"],
                    as_of=resolved_as_of,
                    current=current,
                )
                if universe_manifest
                else set()
            )
            latest_raw_newer_than_qfq_symbols = (
                self._load_latest_raw_qfq_gaps(
                    source,
                    symbols=universe_manifest["symbols"],
                    as_of=resolved_as_of,
                    current=current,
                )
                if universe_manifest
                else []
            )

        target = MarketHistoryStore(self.target_database)
        target_status = target.inspect()
        batch_bar_symbols = {str(bar["symbol"]) for bar in bars}
        batch_missing_symbols = sorted(
            str(candidate["symbol"])
            for candidate in candidates
            if str(candidate["symbol"]) not in batch_bar_symbols
        )
        missing_qfq_symbols = (
            sorted(set(universe_manifest["symbols"]) - ready_universe_symbols)
            if universe_manifest
            else []
        )
        qfq_symbol_coverage = (
            self._symbol_coverage_by_exchange(
                universe_manifest["symbols"],
                ready_universe_symbols,
            )
            if universe_manifest
            else None
        )
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": (
                "partial"
                if universe_manifest and missing_qfq_symbols
                else "planned"
                if bars
                else "empty"
            ),
            "mode": mode,
            "source_database": str(self.source_database.resolve()),
            "target_database": str(self.target_database.resolve()),
            "requested_as_of": requested_as_of.isoformat() if requested_as_of else None,
            "completed_cutoff": completed_cutoff.isoformat(),
            "as_of": resolved_as_of.isoformat(),
            "universe_scope": universe_scope,
            "universe_name": (
                "candidate_hot_cache"
                if universe_scope == "candidate_hot_cache"
                else "a_share_full_market_cache"
            ),
            "universe_count": len(universe_candidates),
            "universe_hash": (
                universe_manifest["universe_hash"] if universe_manifest else None
            ),
            "universe_manifest": (
                {
                    "path": universe_manifest["path"],
                    "observed_at": universe_manifest["observed_at"],
                    "discovery_source": universe_manifest["discovery_source"],
                }
                if universe_manifest
                else None
            ),
            "resume_after": normalized_resume,
            "symbol_limit": normalized_symbol_limit,
            "last_processed_symbol": (
                str(candidates[-1]["symbol"]) if candidates else normalized_resume
            ),
            "candidate_count": len(candidates),
            "candidate_symbols_with_bars": len({bar["symbol"] for bar in bars}),
            "batch_missing_bar_symbols": batch_missing_symbols,
            "missing_qfq_symbols": missing_qfq_symbols,
            "qfq_symbol_coverage": qfq_symbol_coverage,
            "latest_raw_newer_than_qfq_symbols": latest_raw_newer_than_qfq_symbols,
            "latest_raw_newer_than_qfq_count": len(
                latest_raw_newer_than_qfq_symbols
            ),
            "training_scope": (
                "official_universe_membership_with_partial_qfq_bars"
                if universe_manifest and missing_qfq_symbols
                else "official_universe_qfq_bars"
                if universe_manifest
                else "candidate_qfq_bars"
            ),
            "bar_count": len(bars),
            "limits": {
                "candidate_limit": candidate_limit,
                "bars_per_symbol": bars_per_symbol,
                "maximum_bar_rows": candidate_limit * bars_per_symbol,
            },
            "filters": {
                "quality_status": "ready",
                "adjustment_mode": "qfq",
                "generic_sina_rows_allowed": False,
                "unit_factor_verified_composite_allowed": True,
                "incomplete_current_session_allowed": False,
            },
            "excluded": excluded,
            "target_status": target_status["status"],
            "planned_writes": {
                "instruments": len(universe_candidates),
                "universe_snapshots": 1 if universe_candidates else 0,
                "universe_members": len(universe_candidates),
                "ingest_runs": 1 if bars else 0,
                "daily_bars": len(bars),
            },
            "write_stats": self._zero_write_stats(),
            "writes_enabled": False,
            "safety": safety,
        }
        if apply:
            if target_status["status"] != "ready":
                result.update(
                    {
                        "status": "blocked",
                        "reason": "target_market_history_not_ready",
                        "writes_enabled": False,
                    }
                )
                result["safety"] = {**safety, "writes_enabled": False}
                return result
            applied = self._apply(
                target,
                universe_candidates=universe_candidates,
                candidates=candidates,
                bars=bars,
                as_of=resolved_as_of,
                candidate_limit=candidate_limit,
                bars_per_symbol=bars_per_symbol,
                excluded_invalid=excluded_invalid,
                run_at=current,
                universe_scope=universe_scope,
                universe_manifest=universe_manifest,
                missing_qfq_symbols=missing_qfq_symbols,
                batch_missing_symbols=batch_missing_symbols,
                resume_after=normalized_resume,
                symbol_limit=normalized_symbol_limit,
            )
            result.update(applied)
            result["status"] = str(applied["ingest_status"])
            result["writes_enabled"] = True
        return result

    def _apply(
        self,
        target: MarketHistoryStore,
        *,
        universe_candidates: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        bars: list[dict[str, Any]],
        as_of: date,
        candidate_limit: int,
        bars_per_symbol: int,
        excluded_invalid: int,
        run_at: datetime,
        universe_scope: str,
        universe_manifest: dict[str, Any] | None,
        missing_qfq_symbols: list[str],
        batch_missing_symbols: list[str],
        resume_after: str | None,
        symbol_limit: int | None,
    ) -> dict[str, Any]:
        run_timestamp = run_at.isoformat(timespec="seconds")
        universe_name = (
            "candidate_hot_cache"
            if universe_scope == "candidate_hot_cache"
            else "a_share_full_market_cache"
        )
        universe_provider = "trading_local.candidate_pool"
        if universe_scope == "full_market_cache":
            if universe_manifest is None:
                raise ValueError("full-market seed requires an official universe manifest")
            universe_provider = str(universe_manifest["discovery_source"])
        dataset_name = (
            "candidate_hot_cache_daily_bars"
            if universe_scope == "candidate_hot_cache"
            else "a_share_full_market_daily_bars"
        )
        snapshot_payload = [
            {
                "symbol": candidate["symbol"],
                "name": candidate["name"],
                "rank_score": candidate["rank_score"],
                "evidence_at": candidate["evidence_at"],
                "evidence_sources": candidate["evidence_sources"],
            }
            for candidate in sorted(
                universe_candidates,
                key=lambda item: str(item["symbol"]),
            )
        ]
        source_hash = (
            str(universe_manifest["universe_hash"])
            if universe_manifest is not None
            else self._stable_hash(
                {
                    "universe_name": universe_name,
                    "snapshot_date": as_of.isoformat(),
                    "members": snapshot_payload,
                }
            )
        )
        snapshot_metadata = json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "universe_scope": universe_scope,
                "candidate_limit": candidate_limit,
                "bars_per_symbol": bars_per_symbol,
                "resume_after": resume_after,
                "symbol_limit": symbol_limit,
                "adjustment_mode": "qfq",
                "source_read_only": True,
                "official_universe": (
                    {
                        "manifest_path": universe_manifest["path"],
                        "observed_at": universe_manifest["observed_at"],
                        "discovery_source": universe_manifest["discovery_source"],
                        "universe_hash": universe_manifest["universe_hash"],
                        "universe_count": len(universe_manifest["symbols"]),
                    }
                    if universe_manifest is not None
                    else None
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        ingest_parameters = json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "universe_scope": universe_scope,
                "source_database": str(self.source_database.resolve()),
                "as_of": as_of.isoformat(),
                "candidate_limit": candidate_limit,
                "bars_per_symbol": bars_per_symbol,
                "resume_after": resume_after,
                "symbol_limit": symbol_limit,
                "universe_source_hash": source_hash,
                "missing_qfq_symbol_count": len(missing_qfq_symbols),
                "filters": {
                    "quality_status": "ready",
                    "adjustment_mode": "qfq",
                    "exclude_sina": True,
                },
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        with target.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(
                """
                INSERT INTO instruments(
                    symbol, name, exchange, asset_type, board, currency, status,
                    provider, fetched_at, updated_at
                ) VALUES (?, ?, ?, 'stock', ?, 'CNY', ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = CASE
                        WHEN excluded.name IS NOT NULL AND excluded.name != ''
                        THEN excluded.name ELSE instruments.name
                    END,
                    exchange = excluded.exchange,
                    board = COALESCE(excluded.board, instruments.board),
                    status = excluded.status,
                    provider = excluded.provider,
                    fetched_at = excluded.fetched_at,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        candidate["symbol"],
                        candidate["name"],
                        str(candidate["symbol"])[:2],
                        candidate.get("board"),
                        str(candidate.get("status") or "active"),
                        universe_provider,
                        run_timestamp,
                        run_timestamp,
                    )
                    for candidate in universe_candidates
                ],
            )

            snapshot_cursor = connection.execute(
                """
                INSERT INTO universe_snapshots(
                    universe_name, snapshot_date, provider, fetched_at,
                    member_count, source_hash, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(universe_name, snapshot_date, provider, source_hash)
                DO NOTHING
                """,
                (
                    universe_name,
                    as_of.isoformat(),
                    universe_provider,
                    run_timestamp,
                    len(universe_candidates),
                    source_hash,
                    snapshot_metadata,
                ),
            )
            snapshot_inserted = max(0, int(snapshot_cursor.rowcount))
            snapshot_id = int(
                connection.execute(
                    """
                    SELECT id FROM universe_snapshots
                    WHERE universe_name = ? AND snapshot_date = ?
                      AND provider = ? AND source_hash = ?
                    """,
                    (
                        universe_name,
                        as_of.isoformat(),
                        universe_provider,
                        source_hash,
                    ),
                ).fetchone()[0]
            )
            connection.executemany(
                """
                INSERT INTO universe_members(
                    snapshot_id, symbol, weight, member_metadata_json
                ) VALUES (?, ?, NULL, ?)
                ON CONFLICT(snapshot_id, symbol) DO UPDATE SET
                    member_metadata_json = excluded.member_metadata_json
                """,
                [
                    (
                        snapshot_id,
                        candidate["symbol"],
                        json.dumps(
                            {
                                "rank_score": candidate["rank_score"],
                                "evidence_at": candidate["evidence_at"],
                                "evidence_sources": candidate["evidence_sources"],
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    )
                    for candidate in universe_candidates
                ],
            )

            existing = self._existing_bars(connection, bars)
            inserted = 0
            updated = 0
            unchanged = 0
            for bar in bars:
                key = (bar["symbol"], bar["trade_date"], bar["adjustment_mode"])
                previous = existing.get(key)
                if previous is None:
                    inserted += 1
                elif (
                    previous["row_hash"] == bar["row_hash"]
                    and previous["fetched_at"] == bar["fetched_at"]
                    and previous["available_at"] == bar["available_at"]
                    and previous["updated_at"] == bar["updated_at"]
                ):
                    unchanged += 1
                else:
                    updated += 1

            ingest_cursor = connection.execute(
                """
                INSERT INTO ingest_runs(
                    dataset_name, provider, adjustment_mode, status,
                    requested_at, started_at, requested_symbol_count,
                    parameters_json, research_only, live_trading_enabled
                ) VALUES (?, ?, 'qfq', 'running', ?, ?, ?, ?, 1, 0)
                """,
                (
                    dataset_name,
                    "trading_local.daily_bar_cache",
                    run_timestamp,
                    run_timestamp,
                    len(candidates),
                    ingest_parameters,
                ),
            )
            ingest_run_id = int(ingest_cursor.lastrowid)
            connection.executemany(
                """
                INSERT INTO daily_bars(
                    symbol, trade_date, adjustment_mode,
                    open, high, low, close, volume, volume_unit, amount,
                    rule_regime, provider, fetched_at, available_at,
                    ingest_run_id, row_hash, quality_status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trade_date, adjustment_mode) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    volume_unit = excluded.volume_unit,
                    amount = excluded.amount,
                    rule_regime = excluded.rule_regime,
                    provider = excluded.provider,
                    fetched_at = excluded.fetched_at,
                    available_at = excluded.available_at,
                    ingest_run_id = excluded.ingest_run_id,
                    row_hash = excluded.row_hash,
                    quality_status = excluded.quality_status,
                    updated_at = excluded.updated_at
                WHERE daily_bars.row_hash IS NOT excluded.row_hash
                   OR daily_bars.fetched_at IS NOT excluded.fetched_at
                   OR daily_bars.available_at IS NOT excluded.available_at
                   OR daily_bars.updated_at IS NOT excluded.updated_at
                """,
                [
                    (
                        bar["symbol"],
                        bar["trade_date"],
                        bar["adjustment_mode"],
                        bar["open"],
                        bar["high"],
                        bar["low"],
                        bar["close"],
                        bar["volume"],
                        bar["volume_unit"],
                        bar["amount"],
                        bar["rule_regime"],
                        bar["provider"],
                        bar["fetched_at"],
                        bar["available_at"],
                        ingest_run_id,
                        bar["row_hash"],
                        bar["quality_status"],
                        bar["updated_at"],
                    )
                    for bar in bars
                ],
            )
            processed_symbols = len({bar["symbol"] for bar in bars})
            ingest_status = "partial" if missing_qfq_symbols else "completed"
            error_json = json.dumps(
                {
                    "missing_qfq_symbol_count": len(missing_qfq_symbols),
                    "missing_qfq_symbols": missing_qfq_symbols,
                    "batch_missing_bar_symbols": batch_missing_symbols,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            connection.execute(
                """
                UPDATE ingest_runs
                SET status = ?, completed_at = ?,
                    processed_symbol_count = ?, inserted_row_count = ?,
                    updated_row_count = ?, rejected_row_count = ?, error_json = ?
                WHERE id = ?
                """,
                (
                    ingest_status,
                    run_timestamp,
                    processed_symbols,
                    inserted,
                    updated,
                    excluded_invalid,
                    error_json,
                    ingest_run_id,
                ),
            )

        return {
            "snapshot_id": snapshot_id,
            "universe_source_hash": source_hash,
            "ingest_run_id": ingest_run_id,
            "ingest_status": ingest_status,
            "write_stats": {
                "instruments": len(universe_candidates),
                "universe_snapshots": snapshot_inserted,
                "universe_members": len(universe_candidates),
                "ingest_runs": 1,
                "bars_inserted": inserted,
                "bars_updated": updated,
                "bars_unchanged": unchanged,
            },
        }

    @staticmethod
    def _existing_bars(
        connection: sqlite3.Connection,
        bars: list[dict[str, Any]],
    ) -> dict[tuple[str, str, str], dict[str, Any]]:
        symbols = sorted({str(bar["symbol"]) for bar in bars})
        if not symbols:
            return {}
        placeholders = ",".join("?" for _ in symbols)
        rows = connection.execute(
            f"""
            SELECT symbol, trade_date, adjustment_mode, row_hash,
                   fetched_at, available_at, updated_at
            FROM daily_bars
            WHERE symbol IN ({placeholders}) AND adjustment_mode = 'qfq'
            """,
            tuple(symbols),
        ).fetchall()
        return {
            (str(row["symbol"]), str(row["trade_date"]), str(row["adjustment_mode"])): dict(row)
            for row in rows
        }

    @staticmethod
    def _stable_hash(value: Any) -> str:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @contextmanager
    def _source_connection(self) -> Iterator[sqlite3.Connection]:
        if not self.source_database.exists():
            raise FileNotFoundError(f"source database does not exist: {self.source_database}")
        connection = sqlite3.connect(
            f"{self.source_database.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=5,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("BEGIN")
        try:
            yield connection
        finally:
            connection.rollback()
            connection.close()

    @staticmethod
    def _assert_source_schema(connection: sqlite3.Connection) -> None:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing_tables = sorted(set(SOURCE_TABLES).difference(tables))
        if missing_tables:
            raise ValueError(f"source database missing tables: {missing_tables}")
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(daily_bar_cache)").fetchall()
        }
        missing_columns = sorted(SOURCE_BAR_COLUMNS.difference(columns))
        if missing_columns:
            raise ValueError(f"daily_bar_cache missing columns: {missing_columns}")

    @staticmethod
    def _resolve_as_of(
        connection: sqlite3.Connection,
        *,
        requested_as_of: date | None,
        completed_cutoff: date,
        current: datetime,
    ) -> date | None:
        upper_bound = requested_as_of or completed_cutoff
        threshold = CandidateHistorySeeder._session_finalization_threshold(current)
        row = connection.execute(
            f"""
            SELECT MAX(trade_date) AS latest_date
            FROM daily_bar_cache
            WHERE quality_status = 'ready'
              AND adjustment_mode = 'qfq'
              AND {TRUSTED_QFQ_SOURCE_SQL}
              AND trade_date != 'ERROR'
              AND date(trade_date) <= date(?)
              AND (
                  date(trade_date) < date(?)
                  OR datetime(updated_at) >= datetime(?)
              )
            """,
            (
                upper_bound.isoformat(),
                current.date().isoformat(),
                threshold.isoformat(timespec="seconds"),
            ),
        ).fetchone()
        value = row["latest_date"] if row else None
        return date.fromisoformat(str(value)[:10]) if value else None

    @classmethod
    def _load_candidates(
        cls,
        connection: sqlite3.Connection,
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            WITH latest_auto AS (
                SELECT symbol, MAX(id) AS latest_id
                FROM auto_discovered_candidates
                WHERE symbol IS NOT NULL
                GROUP BY symbol
            ),
            latest_potential AS (
                SELECT symbol, MAX(id) AS latest_id
                FROM potential_search_items
                WHERE symbol IS NOT NULL
                GROUP BY symbol
            ),
            latest_score AS (
                SELECT symbol, MAX(id) AS latest_id
                FROM candidate_scores
                WHERE symbol IS NOT NULL
                GROUP BY symbol
            ),
            evidence AS (
                SELECT symbol, name, COALESCE(score, 0) AS rank_score,
                       COALESCE(updated_at, '') AS evidence_at,
                       'candidate_lifecycle' AS evidence_source
                FROM candidate_lifecycle
                UNION ALL
                SELECT symbol, name, COALESCE(score, 0), '', 'stock_profiles'
                FROM stock_profiles
                WHERE symbol IS NOT NULL
                UNION ALL
                SELECT item.symbol, item.name, COALESCE(item.priority, 0),
                       COALESCE(item.created_at, ''), 'auto_discovered_candidates'
                FROM auto_discovered_candidates item
                JOIN latest_auto ON latest_auto.latest_id = item.id
                UNION ALL
                SELECT item.symbol, item.name, COALESCE(item.potential_score, 0),
                       COALESCE(item.created_at, ''), 'potential_search_items'
                FROM potential_search_items item
                JOIN latest_potential ON latest_potential.latest_id = item.id
                UNION ALL
                SELECT item.symbol, item.name, COALESCE(item.total_score, 0),
                       COALESCE(item.created_at, ''), 'candidate_scores'
                FROM candidate_scores item
                JOIN latest_score ON latest_score.latest_id = item.id
            )
            SELECT symbol, MAX(name) AS name, MAX(rank_score) AS rank_score,
                   MAX(evidence_at) AS evidence_at,
                   GROUP_CONCAT(DISTINCT evidence_source) AS evidence_sources
            FROM evidence
            WHERE symbol IS NOT NULL
            GROUP BY symbol
            ORDER BY rank_score DESC, evidence_at DESC, symbol ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        candidates: list[dict[str, Any]] = []
        for row in rows:
            symbol = cls._normalize_symbol(row["symbol"])
            if symbol is None:
                continue
            candidates.append(
                {
                    "symbol": symbol,
                    "name": str(row["name"] or symbol),
                    "rank_score": float(row["rank_score"] or 0),
                    "evidence_at": str(row["evidence_at"] or ""),
                    "evidence_sources": sorted(
                        item
                        for item in str(row["evidence_sources"] or "").split(",")
                        if item
                    ),
                }
            )
        return candidates

    @classmethod
    def _load_full_market_cache_universe(
        cls,
        connection: sqlite3.Connection,
        *,
        symbols: list[str],
        official_members: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT bars.symbol,
                   COALESCE(MAX(NULLIF(profiles.name, '')), bars.symbol) AS name,
                   MAX(COALESCE(bars.updated_at, bars.created_at, '')) AS evidence_at
            FROM daily_bar_cache AS bars
            LEFT JOIN stock_profiles AS profiles ON profiles.symbol = bars.symbol
            WHERE bars.symbol IS NOT NULL
            GROUP BY bars.symbol
            ORDER BY bars.symbol
            LIMIT ?
            """,
            (MAX_FULL_MARKET_SYMBOLS,),
        ).fetchall()
        official_symbols = set(symbols)
        cached: dict[str, dict[str, Any]] = {}
        for row in rows:
            symbol = cls._normalize_symbol(row["symbol"])
            if symbol is None or symbol not in official_symbols:
                continue
            cached[symbol] = {
                "symbol": symbol,
                "name": str(row["name"] or symbol),
                "rank_score": 0.0,
                "evidence_at": str(row["evidence_at"] or ""),
                "evidence_sources": ["daily_bar_cache"],
            }
        official_members = official_members or {}
        result: list[dict[str, Any]] = []
        for symbol in symbols:
            candidate = cached.get(
                symbol,
                {
                    "symbol": symbol,
                    "name": symbol,
                    "rank_score": 0.0,
                    "evidence_at": "",
                    "evidence_sources": ["official_universe_manifest"],
                },
            )
            official = official_members.get(symbol) or {}
            if official:
                candidate = {
                    **candidate,
                    "name": str(official["name"]),
                    "board": official.get("board"),
                    "status": str(official.get("status") or "active"),
                    "evidence_sources": sorted(
                        {
                            *candidate.get("evidence_sources", []),
                            "official_instrument_catalog",
                        }
                    ),
                }
            result.append(candidate)
        return result

    @classmethod
    def _load_universe_manifest(
        cls,
        path: str | Path | None,
    ) -> dict[str, Any]:
        if path is None:
            raise ValueError("full-market seed requires an official universe manifest")
        target = Path(path).resolve()
        payload = json.loads(target.read_text(encoding="utf-8"))
        raw_symbols = payload.get("universe_symbols")
        if not isinstance(raw_symbols, list) or not raw_symbols:
            raise ValueError("universe manifest has no universe_symbols")
        normalized: list[str] = []
        for raw_symbol in raw_symbols:
            symbol = cls._normalize_symbol(raw_symbol)
            if symbol is None:
                raise ValueError(f"universe manifest contains invalid symbol: {raw_symbol}")
            normalized.append(symbol)
        symbols = sorted(dict.fromkeys(normalized))
        if len(symbols) != len(normalized):
            raise ValueError("universe manifest contains duplicate symbols")
        expected_count = payload.get("universe_count")
        if int(expected_count or 0) != len(symbols):
            raise ValueError("universe manifest count does not match universe_symbols")
        computed_hash = hashlib.sha256("\n".join(symbols).encode("utf-8")).hexdigest()
        if payload.get("universe_hash") != computed_hash:
            raise ValueError("universe manifest hash does not match universe_symbols")
        discovery_source = str(payload.get("discovery_source") or "").strip()
        if not discovery_source:
            raise ValueError("universe manifest has no discovery_source")
        if payload.get("discovery_complete") is not True:
            raise ValueError("universe manifest is not a complete discovery")
        if payload.get("live_trading_enabled") is not False:
            raise ValueError("universe manifest is not proven live-trading-disabled")
        members_by_symbol: dict[str, dict[str, Any]] = {}
        raw_members = payload.get("members")
        if raw_members is not None:
            if not isinstance(raw_members, list) or not raw_members:
                raise ValueError("universe manifest members must be a non-empty list")
            official_symbol_set = set(symbols)
            for raw_member in raw_members:
                if not isinstance(raw_member, dict):
                    raise ValueError("universe manifest member must be an object")
                symbol = cls._normalize_symbol(raw_member.get("symbol"))
                name = str(raw_member.get("name") or "").strip()
                if symbol is None or symbol not in official_symbol_set or not name:
                    raise ValueError("universe manifest contains invalid catalog member")
                if symbol in members_by_symbol:
                    raise ValueError("universe manifest contains duplicate catalog members")
                members_by_symbol[symbol] = {
                    "symbol": symbol,
                    "name": name,
                    "exchange": str(raw_member.get("exchange") or symbol[:2]),
                    "board": raw_member.get("board"),
                    "status": str(raw_member.get("status") or "active"),
                }
            if set(members_by_symbol) != set(symbols):
                raise ValueError("universe manifest catalog members do not match symbols")
        return {
            "path": str(target),
            "symbols": symbols,
            "universe_hash": computed_hash,
            "observed_at": str(payload.get("observed_at") or ""),
            "discovery_source": discovery_source,
            "members_by_symbol": members_by_symbol,
        }

    @staticmethod
    def _load_ready_qfq_symbols(
        connection: sqlite3.Connection,
        *,
        symbols: list[str],
        as_of: date,
        current: datetime,
    ) -> set[str]:
        if not symbols:
            return set()
        placeholders = ",".join("?" for _ in symbols)
        threshold = CandidateHistorySeeder._session_finalization_threshold(current)
        rows = connection.execute(
            f"""
            SELECT DISTINCT symbol
            FROM daily_bar_cache
            WHERE symbol IN ({placeholders})
              AND quality_status = 'ready'
              AND adjustment_mode = 'qfq'
              AND {TRUSTED_QFQ_SOURCE_SQL}
              AND trade_date != 'ERROR'
              AND date(trade_date) <= date(?)
              AND (
                  date(trade_date) < date(?)
                  OR datetime(updated_at) >= datetime(?)
              )
              AND open IS NOT NULL AND high IS NOT NULL
              AND low IS NOT NULL AND close IS NOT NULL
              AND open >= 0 AND high >= 0 AND low >= 0 AND close >= 0
              AND high >= open AND high >= close AND high >= low
              AND low <= open AND low <= close
              AND (volume IS NULL OR volume >= 0)
              AND (amount IS NULL OR amount >= 0)
            """,
            (
                *symbols,
                as_of.isoformat(),
                current.date().isoformat(),
                threshold.isoformat(timespec="seconds"),
            ),
        ).fetchall()
        return {str(row["symbol"]) for row in rows}

    @staticmethod
    def _symbol_coverage_by_exchange(
        symbols: list[str],
        available: set[str],
    ) -> dict[str, dict[str, int | float]]:
        result: dict[str, dict[str, int | float]] = {}
        for exchange in ("SH", "SZ", "BJ", "ALL"):
            universe_members = (
                symbols
                if exchange == "ALL"
                else [symbol for symbol in symbols if symbol.startswith(exchange)]
            )
            available_count = sum(symbol in available for symbol in universe_members)
            universe_count = len(universe_members)
            result[exchange] = {
                "available": available_count,
                "universe": universe_count,
                "pct": (
                    round(available_count / universe_count * 100.0, 2)
                    if universe_count
                    else 0.0
                ),
            }
        return result

    @staticmethod
    def _load_latest_raw_qfq_gaps(
        connection: sqlite3.Connection,
        *,
        symbols: list[str],
        as_of: date,
        current: datetime,
    ) -> list[str]:
        if not symbols:
            return []
        placeholders = ",".join("?" for _ in symbols)
        threshold = CandidateHistorySeeder._session_finalization_threshold(current)
        rows = connection.execute(
            f"""
            WITH latest AS (
                SELECT symbol,
                       MAX(CASE
                           WHEN quality_status = 'ready'
                            AND adjustment_mode = 'qfq'
                            AND {TRUSTED_QFQ_SOURCE_SQL}
                           THEN date(trade_date)
                       END) AS latest_qfq_date,
                       MAX(CASE
                           WHEN adjustment_mode != 'qfq'
                            AND quality_status != 'error'
                            AND close IS NOT NULL
                           THEN date(trade_date)
                       END) AS latest_raw_date
                FROM daily_bar_cache
                WHERE symbol IN ({placeholders})
                  AND trade_date != 'ERROR'
                  AND date(trade_date) <= date(?)
                  AND (
                      date(trade_date) < date(?)
                      OR datetime(updated_at) >= datetime(?)
                  )
                GROUP BY symbol
            )
            SELECT symbol
            FROM latest
            WHERE latest_qfq_date IS NOT NULL
              AND latest_raw_date > latest_qfq_date
            ORDER BY symbol
            """,
            (
                *symbols,
                as_of.isoformat(),
                current.date().isoformat(),
                threshold.isoformat(timespec="seconds"),
            ),
        ).fetchall()
        return [str(row["symbol"]) for row in rows]

    @staticmethod
    def _exclusion_stats(
        connection: sqlite3.Connection,
        *,
        candidates: list[dict[str, Any]],
        current: datetime,
    ) -> dict[str, int]:
        symbols = [str(candidate["symbol"]) for candidate in candidates]
        if not symbols:
            return {
                "unknown_adjustment_rows": 0,
                "sina_rows": 0,
                "non_ready_rows": 0,
                "incomplete_current_session_rows": 0,
            }
        placeholders = ",".join("?" for _ in symbols)
        threshold = CandidateHistorySeeder._session_finalization_threshold(current)
        row = connection.execute(
            f"""
            SELECT
                SUM(CASE
                    WHEN adjustment_mode IS NULL OR adjustment_mode != 'qfq' THEN 1
                    ELSE 0
                END) AS unknown_adjustment_rows,
                SUM(CASE
                    WHEN NOT {TRUSTED_QFQ_SOURCE_SQL} THEN 1 ELSE 0
                END) AS sina_rows,
                SUM(CASE
                    WHEN quality_status != 'ready' THEN 1 ELSE 0
                END) AS non_ready_rows,
                SUM(CASE
                    WHEN quality_status = 'ready'
                     AND adjustment_mode = 'qfq'
                     AND {TRUSTED_QFQ_SOURCE_SQL}
                     AND date(trade_date) = date(?)
                     AND (
                         datetime(?) < datetime(?)
                         OR updated_at IS NULL
                         OR datetime(updated_at) < datetime(?)
                     )
                    THEN 1 ELSE 0
                END) AS incomplete_current_session_rows
            FROM daily_bar_cache
            WHERE symbol IN ({placeholders})
              AND trade_date != 'ERROR'
              AND date(trade_date) <= date(?)
            """,
            (
                current.date().isoformat(),
                current.isoformat(timespec="seconds"),
                threshold.isoformat(timespec="seconds"),
                threshold.isoformat(timespec="seconds"),
                *symbols,
                current.date().isoformat(),
            ),
        ).fetchone()
        return {
            key: int(row[key] or 0)
            for key in (
                "unknown_adjustment_rows",
                "sina_rows",
                "non_ready_rows",
                "incomplete_current_session_rows",
            )
        }

    @classmethod
    def _load_bars(
        cls,
        connection: sqlite3.Connection,
        *,
        candidates: list[dict[str, Any]],
        as_of: date,
        bars_per_symbol: int,
        current: datetime,
    ) -> tuple[list[dict[str, Any]], int]:
        if not candidates:
            return [], 0
        symbols = [str(candidate["symbol"]) for candidate in candidates]
        placeholders = ",".join("?" for _ in symbols)
        threshold = cls._session_finalization_threshold(current)
        rows = connection.execute(
            f"""
            WITH ranked AS (
                SELECT symbol, trade_date, open, high, low, close, volume, amount,
                       source, adjustment_mode, volume_unit, quality_status,
                       created_at, updated_at,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol ORDER BY date(trade_date) DESC, id DESC
                       ) AS row_number
                FROM daily_bar_cache
                WHERE symbol IN ({placeholders})
                  AND quality_status = 'ready'
                  AND adjustment_mode = 'qfq'
                  AND {TRUSTED_QFQ_SOURCE_SQL}
                  AND trade_date != 'ERROR'
                  AND date(trade_date) <= date(?)
                  AND (
                      date(trade_date) < date(?)
                      OR datetime(updated_at) >= datetime(?)
                  )
            )
            SELECT * FROM ranked
            WHERE row_number <= ?
            ORDER BY symbol, trade_date
            """,
            (
                *symbols,
                as_of.isoformat(),
                current.date().isoformat(),
                threshold.isoformat(timespec="seconds"),
                bars_per_symbol,
            ),
        ).fetchall()
        bars: list[dict[str, Any]] = []
        invalid = 0
        for row in rows:
            normalized = cls._normalize_bar(dict(row))
            if normalized is None:
                invalid += 1
                continue
            bars.append(normalized)
        return bars, invalid

    @staticmethod
    def _normalize_bar(row: dict[str, Any]) -> dict[str, Any] | None:
        try:
            trade_date = date.fromisoformat(str(row["trade_date"])[:10])
            prices = [float(row[field]) for field in ("open", "high", "low", "close")]
        except (TypeError, ValueError):
            return None
        open_price, high, low, close = prices
        if (
            not all(math.isfinite(value) for value in prices)
            or min(prices) < 0
            or high < max(open_price, close, low)
            or low > min(open_price, close)
        ):
            return None
        try:
            volume = float(row["volume"]) if row.get("volume") is not None else None
            amount = float(row["amount"]) if row.get("amount") is not None else None
        except (TypeError, ValueError):
            return None
        if any(
            value is not None and (not math.isfinite(value) or value < 0)
            for value in (volume, amount)
        ):
            return None
        volume_unit = str(row.get("volume_unit") or "unknown").lower()
        if volume_unit not in {"hand", "share", "unknown"}:
            return None
        source_updated_at = str(
            row.get("updated_at") or row.get("created_at") or trade_date.isoformat()
        )
        normalized = {
            "symbol": str(row["symbol"]),
            "trade_date": trade_date.isoformat(),
            "adjustment_mode": "qfq",
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "amount": amount,
            "volume_unit": volume_unit,
            "rule_regime": (
                "cn_a_share_2026_07_06_onward"
                if trade_date >= RULE_REGIME_BOUNDARY
                else "cn_a_share_pre_2026_07_06"
            ),
            "provider": str(row["source"]),
            "fetched_at": source_updated_at,
            "available_at": source_updated_at,
            "updated_at": source_updated_at,
            "quality_status": "ready",
        }
        normalized["row_hash"] = CandidateHistorySeeder._row_hash(normalized)
        return normalized

    @staticmethod
    def _row_hash(bar: dict[str, Any]) -> str:
        stable_fields = {
            key: bar.get(key)
            for key in (
                "symbol",
                "trade_date",
                "adjustment_mode",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "volume_unit",
                "rule_regime",
                "provider",
                "quality_status",
            )
        }
        payload = json.dumps(
            stable_fields,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_symbol(value: Any) -> str | None:
        raw = str(value or "").strip().upper()
        match = re.fullmatch(r"(?:SH|SZ|BJ)?(\d{6})", raw)
        if match:
            code = match.group(1)
            explicit_exchange = raw[:2] if raw[:2] in {"SH", "SZ", "BJ"} else None
            if code.startswith(("600", "601", "603", "605", "688", "689")):
                return f"SH{code}" if explicit_exchange in {None, "SH"} else None
            if code.startswith(("000", "001", "002", "003", "300", "301", "302")):
                return f"SZ{code}" if explicit_exchange in {None, "SZ"} else None
            if code.startswith(("43", "82", "83", "87", "88", "92")):
                return f"BJ{code}" if explicit_exchange in {None, "BJ"} else None
        return None

    @staticmethod
    def _parse_as_of(value: str | None) -> date | None:
        if value is None:
            return None
        return date.fromisoformat(str(value)[:10])

    @staticmethod
    def _local_now(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(SHANGHAI)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        return value.astimezone(SHANGHAI)

    @staticmethod
    def _completed_cutoff(current: datetime) -> date:
        if current.weekday() < 5 and current.time() < SESSION_FINALIZATION_TIME:
            return current.date() - timedelta(days=1)
        return current.date()

    @staticmethod
    def _session_finalization_threshold(current: datetime) -> datetime:
        return datetime.combine(
            current.date(),
            SESSION_FINALIZATION_TIME,
            tzinfo=SHANGHAI,
        )

    def _empty_result(
        self,
        *,
        mode: str,
        candidate_limit: int,
        bars_per_symbol: int,
        requested_as_of: date | None,
        completed_cutoff: date,
        safety: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "empty",
            "mode": mode,
            "source_database": str(self.source_database.resolve()),
            "target_database": str(self.target_database.resolve()),
            "requested_as_of": requested_as_of.isoformat() if requested_as_of else None,
            "completed_cutoff": completed_cutoff.isoformat(),
            "as_of": None,
            "candidate_count": 0,
            "candidate_symbols_with_bars": 0,
            "bar_count": 0,
            "limits": {
                "candidate_limit": candidate_limit,
                "bars_per_symbol": bars_per_symbol,
                "maximum_bar_rows": candidate_limit * bars_per_symbol,
            },
            "write_stats": self._zero_write_stats(),
            "writes_enabled": False,
            "safety": safety,
        }

    @staticmethod
    def _zero_write_stats() -> dict[str, int]:
        return {
            "instruments": 0,
            "universe_snapshots": 0,
            "universe_members": 0,
            "ingest_runs": 0,
            "bars_inserted": 0,
            "bars_updated": 0,
            "bars_unchanged": 0,
        }

    @staticmethod
    def _safety(*, apply: bool) -> dict[str, Any]:
        return {
            "research_only": True,
            "live_trading_enabled": bool(settings.enable_live_trading),
            "source_read_only": True,
            "single_target_writer": True,
            "broker_or_order_capability": False,
            "writes_enabled": bool(apply and not settings.enable_live_trading),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or apply a bounded, research-only candidate daily-bar seed. "
            "The operational SQLite source is always opened read-only."
        )
    )
    parser.add_argument("--source-database", default=str(settings.database_path))
    parser.add_argument("--target-database", default=str(DEFAULT_MARKET_HISTORY_PATH))
    parser.add_argument("--candidate-limit", type=int, default=DEFAULT_CANDIDATE_LIMIT)
    parser.add_argument(
        "--universe-scope",
        choices=("candidate_hot_cache", "full_market_cache"),
        default="candidate_hot_cache",
        help=(
            "Select the ranked candidate slice or every normalized stock symbol "
            "observed in daily_bar_cache."
        ),
    )
    parser.add_argument(
        "--universe-manifest-path",
        default=None,
        help=(
            "Required for full_market_cache: validated universe-backfill checkpoint "
            "containing the current official symbol list and hash."
        ),
    )
    parser.add_argument("--bars-per-symbol", type=int, default=DEFAULT_BARS_PER_SYMBOL)
    parser.add_argument(
        "--resume-after",
        default=None,
        help="For deterministic batches, continue after this normalized stock symbol.",
    )
    parser.add_argument(
        "--symbol-limit",
        type=int,
        default=None,
        help="Optional per-run symbol batch size (clamped to 1-500).",
    )
    parser.add_argument("--as-of", default=None, help="Optional completed YYYY-MM-DD cutoff.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Explicitly allow the single target-database write transaction.",
    )
    return parser


def main(argv: Sequence[str] | None = None, *, seeder: Any | None = None) -> int:
    args = build_parser().parse_args(argv)
    runner = seeder or CandidateHistorySeeder(
        args.source_database,
        args.target_database,
    )
    try:
        result = runner.run(
            apply=args.apply,
            candidate_limit=args.candidate_limit,
            bars_per_symbol=args.bars_per_symbol,
            universe_scope=args.universe_scope,
            universe_manifest_path=args.universe_manifest_path,
            resume_after=args.resume_after,
            symbol_limit=args.symbol_limit,
            as_of=args.as_of,
        )
    except Exception as exc:
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "mode": "apply" if args.apply else "dry_run",
            "error": str(exc),
            "writes_enabled": False,
            "safety": {
                "research_only": True,
                "live_trading_enabled": bool(settings.enable_live_trading),
                "source_read_only": True,
                "single_target_writer": True,
                "broker_or_order_capability": False,
                "writes_enabled": False,
            },
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    status = str(result.get("status") or "error")
    if status == "error":
        return 1
    if status in {"blocked", "empty"}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
