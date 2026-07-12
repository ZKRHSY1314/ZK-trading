from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Callable
from datetime import date, datetime, time as datetime_time, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from app.config import settings
from app.disclosures import DisclosureFact, DisclosureLedger
from app.market_intelligence import SectorExposureResolver
from app.market_intelligence.exposure import membership_hash
from app.market_intelligence.taxonomy import SECTOR_TAXONOMY
from app.reference_data.global_markets import GlobalMarketIngestor
from app.reference_data.provider import AkshareReferenceProvider, ReferenceDataProvider
from app.storage.sqlite_store import SQLiteStore


SHANGHAI = ZoneInfo("Asia/Shanghai")
BUYBACK_SOURCE_URL = "https://data.eastmoney.com/gphg/hglist.html"


# Ordered aliases deliberately map an external board to one stable internal code.
# Short or ambiguous aliases are avoided so an automated mapping cannot silently
# turn a broad board into a high-confidence thematic exposure.
SECTOR_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "semiconductors",
        (
            "\u534a\u5bfc\u4f53",
            "\u82af\u7247",
            "\u5b58\u50a8",
            "\u6676\u5706",
            "\u5149\u523b",
            "\u96c6\u6210\u7535\u8def",
            "\u5148\u8fdb\u5c01\u88c5",
            "\u7535\u5b50\u5668\u4ef6",
        ),
    ),
    (
        "ai_compute",
        (
            "\u4eba\u5de5\u667a\u80fd",
            "\u7b97\u529b",
            "\u5927\u6a21\u578b",
            "\u5149\u6a21\u5757",
            "cpo",
            "aigc",
            "chatgpt",
            "deepseek",
            "\u6570\u636e\u4e2d\u5fc3",
        ),
    ),
    (
        "oil_gas",
        (
            "\u77f3\u6cb9",
            "\u6cb9\u6c14",
            "\u5929\u7136\u6c14",
            "\u9875\u5ca9\u6c14",
            "\u53ef\u71c3\u51b0",
        ),
    ),
    ("gold", ("\u9ec4\u91d1", "\u8d35\u91d1\u5c5e")),
    ("crypto", ("\u6570\u5b57\u8d27\u5e01", "\u533a\u5757\u94fe")),
    ("shipping", ("\u822a\u8fd0", "\u6d77\u8fd0", "\u96c6\u8fd0", "\u6e2f\u53e3")),
    (
        "low_altitude",
        (
            "\u4f4e\u7a7a",
            "\u65e0\u4eba\u673a",
            "evtol",
            "\u98de\u884c\u6c7d\u8f66",
            "\u901a\u7528\u822a\u7a7a",
        ),
    ),
    (
        "new_energy",
        (
            "\u5149\u4f0f",
            "\u50a8\u80fd",
            "\u9502\u7535",
            "\u65b0\u80fd\u6e90",
            "\u98ce\u7535",
            "\u5145\u7535\u6869",
            "\u56fa\u6001\u7535\u6c60",
        ),
    ),
    (
        "digital_economy",
        (
            "\u6570\u636e\u8981\u7d20",
            "\u4fe1\u521b",
            "\u7f51\u7edc\u5b89\u5168",
            "\u9e3f\u8499",
            "\u4e91\u8ba1\u7b97",
            "\u5de5\u4e1a\u4e92\u8054\u7f51",
            "\u6570\u5b57\u7ecf\u6d4e",
        ),
    ),
    (
        "brokerage_finance",
        (
            "\u8bc1\u5238",
            "\u5238\u5546",
            "\u91d1\u878d\u79d1\u6280",
            "\u591a\u5143\u91d1\u878d",
            "\u8d44\u672c\u5e02\u573a",
        ),
    ),
    (
        "state_owned_reform",
        (
            "\u56fd\u4f01\u6539\u9769",
            "\u592e\u4f01",
            "\u5730\u65b9\u56fd\u8d44",
            "\u56fd\u8d44\u4e91",
        ),
    ),
    (
        "medicine",
        (
            "\u533b\u836f",
            "\u533b\u7597",
            "\u521b\u65b0\u836f",
            "\u75ab\u82d7",
            "\u4e2d\u836f",
            "cro",
        ),
    ),
    (
        "consumer",
        (
            "\u98df\u54c1\u996e\u6599",
            "\u767d\u9152",
            "\u65c5\u6e38",
            "\u514d\u7a0e",
            "\u5bb6\u7535",
            "\u6c7d\u8f66\u6574\u8f66",
            "\u6d88\u8d39",
        ),
    ),
    (
        "infrastructure",
        (
            "\u57fa\u5efa",
            "\u6c34\u5229",
            "\u7279\u9ad8\u538b",
            "\u7535\u7f51",
            "\u94c1\u8def",
            "\u5de5\u7a0b\u673a\u68b0",
            "\u57ce\u5e02\u66f4\u65b0",
        ),
    ),
    (
        "defense",
        (
            "\u519b\u5de5",
            "\u536b\u661f",
            "\u5317\u6597",
            "\u822a\u5929",
            "\u822a\u7a7a\u53d1\u52a8\u673a",
            "\u96f7\u8fbe",
        ),
    ),
)


BOARD_NAME_COLUMNS = (
    "board_name",
    "name",
    "\u677f\u5757\u540d\u79f0",
    "\u677f\u5757",
    "\u540d\u79f0",
)
BOARD_CODE_COLUMNS = (
    "board_code",
    "code",
    "label",
    "\u677f\u5757\u4ee3\u7801",
    "\u4ee3\u7801",
)
MEMBER_CODE_COLUMNS = ("stock_code", "symbol", "code", "\u80a1\u7968\u4ee3\u7801", "\u4ee3\u7801")
BUYBACK_CODE_COLUMNS = ("stock_code", "symbol", "code", "\u80a1\u7968\u4ee3\u7801")
BUYBACK_START_COLUMNS = (
    "repurchase_start_date",
    "start_date",
    "\u56de\u8d2d\u8d77\u59cb\u65f6\u95f4",
)
BUYBACK_PUBLISHED_COLUMNS = (
    "announcement_date",
    "published_at",
    "\u6700\u65b0\u516c\u544a\u65e5\u671f",
)


class ReferenceIngestService:
    """Populate point-in-time reference ledgers without enabling execution."""

    def __init__(
        self,
        *,
        store: SQLiteStore | None = None,
        provider: ReferenceDataProvider | None = None,
        clock: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        self.store.init()
        self.provider = provider or AkshareReferenceProvider()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.sleep_fn = sleep_fn
        self.exposure = SectorExposureResolver(self.store)
        self.disclosures = DisclosureLedger(self.store)
        self.global_markets = GlobalMarketIngestor(
            store=self.store,
            provider=self.provider,
            clock=self._utc_now,
        )

    def run(
        self,
        *,
        apply: bool = False,
        board_limit: int | None = None,
        disclosure_limit: int | None = None,
        rate_limit_seconds: float = 0.2,
        global_days: int = 30,
        include_global: bool = True,
        include_sox: bool = True,
        global_symbol_limit: int | None = None,
    ) -> dict[str, Any]:
        now = self._utc_now()
        if settings.enable_live_trading:
            return {
                "schema_version": "reference_ingest.v1",
                "status": "blocked",
                "mode": "apply" if apply else "dry_run",
                "as_of": now.isoformat().replace("+00:00", "Z"),
                "reason": "live_trading_enabled",
                "safety": self._safety(apply=False),
                "sectors": {"status": "not_run"},
                "disclosures": {"status": "not_run"},
                "global_markets": {"status": "not_run"},
            }
        if board_limit is not None and board_limit < 1:
            raise ValueError("board_limit must be positive")
        if disclosure_limit is not None and disclosure_limit < 1:
            raise ValueError("disclosure_limit must be positive")
        if rate_limit_seconds < 0:
            raise ValueError("rate_limit_seconds cannot be negative")
        if include_global and not 6 <= global_days <= 3660:
            raise ValueError("global_days must be between 6 and 3660")
        if global_symbol_limit is not None and global_symbol_limit < 1:
            raise ValueError("global_symbol_limit must be positive")

        sectors = self._ingest_sectors(
            apply=apply,
            now=now,
            board_limit=board_limit,
            rate_limit_seconds=rate_limit_seconds,
        )
        disclosures = self._ingest_buybacks(
            apply=apply,
            now=now,
            limit=disclosure_limit,
        )
        global_markets = (
            self.global_markets.run(
                apply=apply,
                now=now,
                days=global_days,
                include_sox=include_sox,
                symbol_limit=global_symbol_limit,
            )
            if include_global
            else {
                "status": "disabled",
                "requested_days": global_days,
                "include_sox": include_sox,
                "reason": "disabled_by_operator",
            }
        )
        status = self._overall_status(
            apply=apply,
            sections=(sectors, disclosures, global_markets),
        )
        return {
            "schema_version": "reference_ingest.v1",
            "status": status,
            "mode": "apply" if apply else "dry_run",
            "as_of": now.isoformat().replace("+00:00", "Z"),
            "safety": self._safety(apply=apply),
            "sectors": sectors,
            "disclosures": disclosures,
            "global_markets": global_markets,
        }

    def _ingest_sectors(
        self,
        *,
        apply: bool,
        now: datetime,
        board_limit: int | None,
        rate_limit_seconds: float,
    ) -> dict[str, Any]:
        errors: list[dict[str, Any]] = []
        external_boards: list[dict[str, str]] = []
        source_specs = (
            (
                "industry",
                "akshare.stock_board_industry_name_em",
                self.provider.get_industry_boards,
                self.provider.get_industry_members,
                0.90,
                "akshare.stock_board_industry_cons_em",
            ),
            (
                "concept",
                "akshare.stock_board_concept_name_em",
                self.provider.get_concept_boards,
                self.provider.get_concept_members,
                0.75,
                "akshare.stock_board_concept_cons_em",
            ),
            (
                "sina_industry",
                "akshare.stock_sector_spot[sina_industry]",
                self.provider.get_sina_industry_boards,
                self.provider.get_sina_industry_members,
                0.65,
                "akshare.stock_sector_detail",
            ),
        )
        source_success = 0
        member_fetchers: dict[str, tuple[Callable[[str], pd.DataFrame], float, str]] = {}
        for kind, source_name, list_fn, member_fn, confidence, member_source in source_specs:
            member_fetchers[kind] = (member_fn, confidence, member_source)
            try:
                frame = self._frame(list_fn(), source=source_name)
                name_column = self._column(frame, BOARD_NAME_COLUMNS)
                code_column = self._column(frame, BOARD_CODE_COLUMNS, required=False)
                source_success += 1
                for _, row in frame.iterrows():
                    name = self._text(row.get(name_column))
                    if not name:
                        continue
                    code = self._text(row.get(code_column)) if code_column else ""
                    external_boards.append(
                        {
                            "kind": kind,
                            "name": name,
                            "code": code,
                            "source": source_name,
                        }
                    )
            except Exception as exc:
                errors.append(self._error("board_list", source_name, exc, kind=kind))

        mapped: list[dict[str, Any]] = []
        unmapped: list[dict[str, str]] = []
        for board in external_boards:
            sector = self._map_sector(board["name"])
            if sector is None:
                unmapped.append(board)
                continue
            mapped.append({**board, "sector": sector})
        attempted = mapped[:board_limit] if board_limit is not None else mapped

        member_rows = 0
        valid_member_rows = 0
        member_boards_completed = 0
        snapshot_plans: list[dict[str, Any]] = []
        symbols: set[str] = set()
        for index, board in enumerate(attempted):
            member_fn, confidence, member_source = member_fetchers[board["kind"]]
            board_selector = board["code"] or board["name"]
            try:
                frame = self._frame(
                    member_fn(board_selector),
                    source=member_source,
                )
                if frame.empty:
                    raise ValueError("member frame is empty")
                code_column = self._column(frame, MEMBER_CODE_COLUMNS)
                member_rows += len(frame)
                board_symbols: set[str] = set()
                source = self._membership_source(board)
                for raw in frame[code_column].tolist():
                    symbol = self._normalize_a_share_symbol(raw)
                    if symbol is None:
                        continue
                    board_symbols.add(symbol)
                    valid_member_rows += 1
                    symbols.add(symbol)
                if not board_symbols:
                    raise ValueError(
                        "member frame contains no supported Shanghai/Shenzhen A shares"
                    )
                retrieved_at = self._utc_now()
                current_hash = membership_hash(board_symbols)
                latest = self.exposure.latest_snapshot(
                    source=source,
                    sector=board["sector"],
                    as_of=retrieved_at,
                )
                snapshot_plans.append(
                    {
                        "source": source,
                        "sector": board["sector"],
                        "symbols": sorted(board_symbols),
                        "member_hash": current_hash,
                        "observed_at": retrieved_at,
                        "effective_date": retrieved_at.astimezone(SHANGHAI).date().isoformat(),
                        "confidence": confidence,
                        "disposition": (
                            "unchanged"
                            if latest is not None and latest["member_hash"] == current_hash
                            else "changed"
                        ),
                    }
                )
                member_boards_completed += 1
            except Exception as exc:
                errors.append(
                    self._error(
                        "board_members",
                        member_source,
                        exc,
                        kind=board["kind"],
                        board_name=board["name"],
                        board_code=board["code"],
                    )
                )
            if rate_limit_seconds > 0 and index < len(attempted) - 1:
                self.sleep_fn(rate_limit_seconds)

        written = 0
        existing = sum(
            len(plan["symbols"])
            for plan in snapshot_plans
            if plan["disposition"] == "unchanged"
        )
        snapshots_written = 0
        write_error: dict[str, Any] | None = None
        changed_plans = [
            plan for plan in snapshot_plans if plan["disposition"] == "changed"
        ]
        if apply and changed_plans:
            try:
                persisted = self.exposure.record_snapshots(changed_plans)
                snapshots_written = len(persisted)
                written = sum(int(snapshot["member_count"]) for snapshot in persisted)
            except Exception as exc:
                write_error = self._error(
                    "sector_membership_snapshots_write",
                    "sqlite",
                    exc,
                    records_attempted=len(changed_plans),
                    transaction_rolled_back=True,
                )
                errors.append(write_error)

        if write_error is not None:
            status = "error"
        elif source_success == 0:
            status = "error"
        elif errors:
            status = "partial"
        elif not external_boards or not mapped:
            status = "empty"
        else:
            status = "completed" if apply else "planned"
        return {
            "status": status,
            "external_board_count": len(external_boards),
            "mapped_board_count": len(mapped),
            "attempted_mapped_board_count": len(attempted),
            "mapped_board_rate_pct": self._pct(len(mapped), len(external_boards)),
            "member_board_coverage_pct": self._pct(member_boards_completed, len(attempted)),
            "member_rows": member_rows,
            "valid_member_rows": valid_member_rows,
            "unique_member_symbols": len(symbols),
            "membership_records_planned": sum(
                len(plan["symbols"]) for plan in changed_plans
            ),
            "membership_records_written": written,
            "membership_records_existing": existing,
            "membership_snapshots_planned": len(changed_plans),
            "membership_snapshots_written": snapshots_written,
            "membership_snapshots_unchanged": len(snapshot_plans) - len(changed_plans),
            "mapped_boards": mapped,
            "unmapped_board_count": len(unmapped),
            "unmapped_boards": unmapped,
            "errors": errors,
        }

    def _ingest_buybacks(
        self,
        *,
        apply: bool,
        now: datetime,
        limit: int | None,
    ) -> dict[str, Any]:
        source = "akshare.stock_repurchase_em"
        try:
            frame = self._frame(self.provider.get_share_buybacks(), source=source)
            retrieved_at = self._utc_now()
            if limit is not None:
                frame = frame.head(limit)
            code_column = self._column(frame, BUYBACK_CODE_COLUMNS)
            start_column = self._column(frame, BUYBACK_START_COLUMNS, required=False)
            published_column = self._column(frame, BUYBACK_PUBLISHED_COLUMNS)
        except Exception as exc:
            return {
                "status": "error",
                "source": source,
                "rows_received": 0,
                "valid_rows": 0,
                "unique_symbols": 0,
                "facts_planned": 0,
                "facts_written": 0,
                "facts_unchanged": 0,
                "new_revisions": 0,
                "freshness": self._freshness([], now),
                "errors": [self._error("share_buybacks", source, exc)],
            }

        facts: list[tuple[DisclosureFact, str]] = []
        errors: list[dict[str, Any]] = []
        published_dates: list[date] = []
        symbols: set[str] = set()
        fact_ids: set[str] = set()
        for row_index, (_, row) in enumerate(frame.iterrows()):
            try:
                symbol = self._normalize_a_share_symbol(row.get(code_column))
                if symbol is None:
                    raise ValueError("unsupported Shanghai/Shenzhen A-share symbol")
                published_date = self._date_value(row.get(published_column))
                start_date = self._date_value(row.get(start_column)) if start_column else None
                if published_date is None:
                    raise ValueError("published date is required")
                fact = self._buyback_fact(
                    row=row,
                    symbol=symbol,
                    start_date=start_date,
                    published_date=published_date,
                    now=retrieved_at,
                )
                if fact[0].fact_id in fact_ids:
                    raise ValueError(
                        "ambiguous duplicate buyback identity; upstream stable plan id is unavailable"
                    )
                fact_ids.add(fact[0].fact_id)
                facts.append(fact)
                symbols.add(symbol)
                published_dates.append(published_date)
            except Exception as exc:
                errors.append(
                    self._error(
                        "share_buyback_row",
                        source,
                        exc,
                        row_index=row_index,
                    )
                )

        written = 0
        unchanged = 0
        revisions = 0
        pending_facts: list[DisclosureFact] = []
        for fact, disposition in facts:
            if disposition == "unchanged":
                unchanged += 1
                continue
            pending_facts.append(fact)
            if fact.revision > 1:
                revisions += 1
        write_error: dict[str, Any] | None = None
        if apply and pending_facts:
            try:
                written = len(self.disclosures.record_many(pending_facts))
            except Exception as exc:
                write_error = self._error(
                    "share_buybacks_write",
                    "sqlite",
                    exc,
                    records_attempted=len(pending_facts),
                    transaction_rolled_back=True,
                )
                errors.append(write_error)

        if write_error is not None:
            status = "error"
        elif errors:
            status = "partial" if facts else "error"
        elif frame.empty or not facts:
            status = "empty"
        else:
            status = "completed" if apply else "planned"
        return {
            "status": status,
            "source": source,
            "source_url": BUYBACK_SOURCE_URL,
            "rows_received": len(frame),
            "valid_rows": len(facts),
            "row_coverage_pct": self._pct(len(facts), len(frame)),
            "unique_symbols": len(symbols),
            "facts_planned": sum(disposition != "unchanged" for _, disposition in facts),
            "facts_written": written,
            "facts_unchanged": unchanged,
            "new_revisions": revisions,
            "freshness": self._freshness(published_dates, retrieved_at),
            "errors": errors,
        }

    def _buyback_fact(
        self,
        *,
        row: pd.Series,
        symbol: str,
        start_date: date | None,
        published_date: date,
        now: datetime,
    ) -> tuple[DisclosureFact, str]:
        clean_row = {str(key): self._clean(value) for key, value in row.items()}
        metrics = self._buyback_metrics(clean_row)
        stable_payload = {
            "symbol": symbol,
            "start_date": start_date.isoformat() if start_date else None,
            "published_date": published_date.isoformat(),
            "metrics": metrics,
        }
        raw_json = json.dumps(
            stable_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        raw_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
        identity_date = start_date or published_date
        fact_id = f"eastmoney-buyback-{symbol}-{identity_date.isoformat()}"
        history = self.store.fetch_all(
            """
            SELECT revision, raw_hash
            FROM disclosure_facts
            WHERE fact_id = ?
            ORDER BY revision DESC
            """,
            (fact_id,),
        )
        matching = next((item for item in history if item["raw_hash"] == raw_hash), None)
        if matching is not None:
            revision = int(matching["revision"])
            disposition = "unchanged"
        else:
            revision = int(history[0]["revision"]) + 1 if history else 1
            disposition = "revision" if history else "new"

        published_at = datetime.combine(
            published_date,
            datetime_time.min,
            tzinfo=SHANGHAI,
        )
        return (
            DisclosureFact(
                fact_id=fact_id,
                symbol=symbol,
                fact_type="share_buyback",
                period_end=None,
                published_at=published_at,
                first_seen_at=now,
                retrieved_at=now,
                available_at=now,
                source_tier="market_data_aggregator",
                source_url=BUYBACK_SOURCE_URL,
                raw_hash=raw_hash,
                revision=revision,
                metrics=metrics,
                evidence=[
                    {
                        "source": "akshare.stock_repurchase_em",
                        "published_date": published_date.isoformat(),
                        "normalized_disclosure": stable_payload,
                        "excluded_volatile_fields": ["序号", "最新价"],
                    }
                ],
                review_only=True,
            ),
            disposition,
        )

    @staticmethod
    def _buyback_metrics(row: dict[str, Any]) -> dict[str, Any]:
        aliases = {
            "planned_price_cap": (
                "planned_price_cap",
                "\u8ba1\u5212\u56de\u8d2d\u4ef7\u683c\u533a\u95f4",
            ),
            "planned_shares_low": (
                "planned_shares_low",
                "\u8ba1\u5212\u56de\u8d2d\u6570\u91cf\u533a\u95f4-\u4e0b\u9650",
            ),
            "planned_shares_high": (
                "planned_shares_high",
                "\u8ba1\u5212\u56de\u8d2d\u6570\u91cf\u533a\u95f4-\u4e0a\u9650",
            ),
            "planned_amount_low": (
                "planned_amount_low",
                "\u8ba1\u5212\u56de\u8d2d\u91d1\u989d\u533a\u95f4-\u4e0b\u9650",
            ),
            "planned_amount_high": (
                "planned_amount_high",
                "\u8ba1\u5212\u56de\u8d2d\u91d1\u989d\u533a\u95f4-\u4e0a\u9650",
            ),
            "announced_capital_ratio_low": (
                "announced_capital_ratio_low",
                "占公告前一日总股本比例-下限",
            ),
            "announced_capital_ratio_high": (
                "announced_capital_ratio_high",
                "占公告前一日总股本比例-上限",
            ),
            "implemented_price_low": (
                "implemented_price_low",
                "已回购股份价格区间-下限",
            ),
            "implemented_price_high": (
                "implemented_price_high",
                "已回购股份价格区间-上限",
            ),
            "implemented_shares": (
                "implemented_shares",
                "\u5df2\u56de\u8d2d\u80a1\u4efd\u6570\u91cf",
            ),
            "implemented_amount": ("implemented_amount", "\u5df2\u56de\u8d2d\u91d1\u989d"),
            "progress": ("progress", "\u5b9e\u65bd\u8fdb\u5ea6"),
        }
        metrics: dict[str, Any] = {}
        for target, candidates in aliases.items():
            value = next((row[key] for key in candidates if key in row), None)
            if value is not None:
                metrics[target] = value
        return metrics

    @staticmethod
    def _membership_source(board: dict[str, Any]) -> str:
        identity = board["code"] or hashlib.sha256(board["name"].encode("utf-8")).hexdigest()[:12]
        vendor = "sina" if board["kind"] == "sina_industry" else "eastmoney"
        return f"akshare.{vendor}.{board['kind']}:{identity}"

    @staticmethod
    def _map_sector(board_name: str) -> str | None:
        normalized = re.sub(r"\s+", "", board_name).casefold()
        for sector, aliases in SECTOR_ALIASES:
            if sector not in SECTOR_TAXONOMY:
                continue
            if any(alias.casefold() in normalized for alias in aliases):
                return sector
        return None

    @staticmethod
    def _normalize_a_share_symbol(raw: Any) -> str | None:
        if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
            return None
        text = str(raw).strip().upper()
        if re.fullmatch(r"\d+(?:\.0+)?", text):
            code = f"{int(float(text)):06d}"
        else:
            match = re.search(r"(\d{6})", text)
            if match is None:
                return None
            code = match.group(1)
        if code.startswith(("600", "601", "603", "605", "688", "689")):
            return f"SH{code}"
        if code.startswith(("000", "001", "002", "003", "300", "301")):
            return f"SZ{code}"
        return None

    @staticmethod
    def _frame(value: Any, *, source: str) -> pd.DataFrame:
        if not isinstance(value, pd.DataFrame):
            raise TypeError(f"{source} returned {type(value).__name__}, expected DataFrame")
        return value

    @staticmethod
    def _column(
        frame: pd.DataFrame,
        candidates: tuple[str, ...],
        *,
        required: bool = True,
    ) -> str | None:
        column = next((candidate for candidate in candidates if candidate in frame.columns), None)
        if column is None and required:
            raise ValueError(
                f"required column missing; expected one of {list(candidates)}, "
                f"received {list(frame.columns)}"
            )
        return column

    @staticmethod
    def _text(value: Any) -> str:
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            return ""
        return str(value).strip()

    @staticmethod
    def _date_value(value: Any) -> date | None:
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()

    @classmethod
    def _clean(cls, value: Any) -> Any:
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @staticmethod
    def _freshness(published_dates: list[date], now: datetime) -> dict[str, Any]:
        if not published_dates:
            return {
                "latest_published_date": None,
                "age_days": None,
                "status": "unknown",
            }
        latest = max(published_dates)
        age_days = max((now.astimezone(SHANGHAI).date() - latest).days, 0)
        if age_days <= 7:
            status = "fresh"
        elif age_days <= 30:
            status = "recent"
        else:
            status = "stale"
        return {
            "latest_published_date": latest.isoformat(),
            "age_days": age_days,
            "status": status,
        }

    def _utc_now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)

    @staticmethod
    def _error(stage: str, source: str, exc: Exception, **context: Any) -> dict[str, Any]:
        return {
            "stage": stage,
            "source": source,
            **context,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    @staticmethod
    def _pct(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator * 100.0, 2)

    @staticmethod
    def _safety(*, apply: bool) -> dict[str, bool]:
        return {
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "writes_enabled": bool(apply),
            "broker_operations_enabled": False,
        }

    @staticmethod
    def _overall_status(*, apply: bool, sections: tuple[dict[str, Any], ...]) -> str:
        statuses = [
            str(section.get("status") or "error")
            for section in sections
            if str(section.get("status") or "error") != "disabled"
        ]
        if not statuses:
            return "empty"
        if all(status == "error" for status in statuses):
            return "error"
        if any(
            status in {"blocked", "degraded", "error", "partial", "unsupported"}
            for status in statuses
        ):
            return "partial"
        if all(status == "empty" for status in statuses):
            return "empty"
        if any(status == "empty" for status in statuses):
            return "partial"
        return "completed" if apply else "planned"


__all__ = ["ReferenceIngestService", "SECTOR_ALIASES"]
