from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from app.config import settings
from app.forecasting import FORECAST_HORIZONS, ForecastDecision, ForecastLedger
from app.market_intelligence.models import EventFact
from app.market_intelligence.service import MarketIntelligenceService
from app.market_intelligence.taxonomy import SECTOR_TAXONOMY
from app.storage.sqlite_store import SQLiteStore


@dataclass(frozen=True)
class PublicOpinionSource:
    id: str
    name: str
    url: str
    category: str = "market"
    parser: str = "auto"
    source_tier: str = "market_media"


DEFAULT_SOURCES: tuple[PublicOpinionSource, ...] = (
    PublicOpinionSource(
        id="eastmoney_kuaixun",
        name="Eastmoney 7x24 market news",
        url="https://kuaixun.eastmoney.com/",
        category="market",
        parser="html",
    ),
    PublicOpinionSource(
        id="sina_stock",
        name="Sina stock channel",
        url="https://finance.sina.com.cn/stock/",
        category="market",
        parser="html",
    ),
    PublicOpinionSource(
        id="stcn_flash",
        name="Securities Times flash news",
        url="https://www.stcn.com/article/list/kx.html",
        category="market",
        parser="html",
    ),
    PublicOpinionSource(
        id="csrc_policy",
        name="CSRC policy headlines",
        url="https://www.csrc.gov.cn/csrc/c100028/common_xq_list.shtml",
        category="policy",
        parser="html",
        source_tier="official",
    ),
)


POSITIVE_KEYWORDS = [
    "利好",
    "支持",
    "鼓励",
    "加快",
    "推进",
    "发布",
    "方案",
    "规划",
    "增长",
    "突破",
    "上调",
    "中标",
    "回购",
    "增持",
    "大涨",
    "走强",
    "景气",
]
RISK_KEYWORDS = [
    "风险",
    "监管",
    "问询",
    "调查",
    "处罚",
    "下跌",
    "暴跌",
    "减持",
    "亏损",
    "终止",
    "过热",
    "调整",
    "走弱",
    "承压",
    "退潮",
    "下调",
    "警示",
    "急挫",
]
POLICY_KEYWORDS = ["政策", "国务院", "证监会", "发改委", "财政部", "央行", "办法", "通知", "意见"]
MARKET_KEYWORDS = [
    "A股",
    "股市",
    "市场",
    "板块",
    "涨停",
    "涨幅",
    "指数",
    "上市公司",
    "行情",
]

_LINK_RE = re.compile(
    r"<a\b[^>]*href=[\"'](?P<href>[^\"'#]+)[\"'][^>]*>(?P<title>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")

MARKET_ITEM_MAX_AGE_HOURS = 72
POLICY_ITEM_MAX_AGE_HOURS = 168
CONTEXT_MAX_AGE_HOURS = 24
SINGLE_SOURCE_DOMINANCE_RATIO = 0.60
MAX_SOURCE_WORKERS = 8


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(
        self,
        validator: Any,
        *,
        allowed_host: str | None = None,
        allow_proxy_synthetic_dns: bool = False,
    ) -> None:
        super().__init__()
        self.validator = validator
        self.allowed_host = (allowed_host or "").lower()
        self.allow_proxy_synthetic_dns = allow_proxy_synthetic_dns

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        redirected_host = (urllib.parse.urlparse(newurl).hostname or "").lower()
        if self.allowed_host and redirected_host != self.allowed_host:
            raise RuntimeError("redirect_host_not_allowed")
        self.validator(
            newurl,
            resolve_dns=True,
            allow_proxy_synthetic_dns=self.allow_proxy_synthetic_dns,
        )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class CodexPublicOpinionService:
    """Review-only public-opinion capture for policy, market, and sector wind signals."""

    def __init__(
        self,
        store: SQLiteStore | None = None,
        sources: list[PublicOpinionSource] | None = None,
    ) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        if store is None:
            self.store.init()
        self.sources = sources or list(DEFAULT_SOURCES)

    def capabilities(self) -> dict[str, Any]:
        return {
            "schema_version": "codex_public_opinion_capabilities.v1",
            "mode": "review_only_public_opinion_capture",
            "supported_steps": [
                "parallel_fair_source_fetch",
                "rss_or_html_parse",
                "freshness_gating",
                "source_quality_diagnostics",
                "sector_keyword_scoring",
                "policy_market_risk_tagging",
                "sector_signal_persistence",
                "codex_structured_evidence_ingest",
                "event_fact_normalization",
                "point_in_time_cross_market_context",
                "review_only_sector_theses",
                "selection_v2_tailwind_context",
            ],
            "recommended_cadence": ["09:00", "11:30", "13:00", "15:10", "20:30"],
            "sources": [asdict(source) for source in self.sources],
            "sector_taxonomy": {
                key: {
                    "display_name": value["display_name"],
                    "keywords": value["keywords"],
                }
                for key, value in SECTOR_TAXONOMY.items()
            },
            "freshness_policy": {
                "market_max_age_hours": MARKET_ITEM_MAX_AGE_HOURS,
                "policy_max_age_hours": POLICY_ITEM_MAX_AGE_HOURS,
                "context_max_age_hours": CONTEXT_MAX_AGE_HOURS,
                "unknown_publication_time": "retained_with_quality_warning_and_score_discount",
            },
            "safety": self._safety(),
            "forbidden_actions": [
                "broker_login",
                "credential_storage",
                "real_order_placement",
                "real_order_cancellation",
                "live_screen_click_trading",
                "auto_load_strategy_artifact",
            ],
        }

    def run(
        self,
        *,
        limit: int = 60,
        persist: bool = True,
        requested_by: str = "codex",
        source_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 300))
        requested_source_urls = source_urls or []
        sources, validation_errors = self._sources_with_ad_hoc_urls(requested_source_urls)
        run_id = self._start_run(len(sources)) if persist else None
        errors: list[dict[str, str]] = list(validation_errors)

        if settings.enable_live_trading:
            result = {
                "status": "blocked",
                "reason": "live_trading_enabled",
                "items": [],
                "sector_signals": [],
                "safety": self._safety(),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
            if run_id:
                self._finish_run(run_id, result, errors, status="blocked")
            return {"run_id": run_id, **result}

        source_batches: dict[str, list[dict[str, Any]]] = {source.id: [] for source in sources}
        source_diagnostics: dict[str, dict[str, Any]] = {
            source.id: {
                "source_id": source.id,
                "source_name": source.name,
                "category": source.category,
                "url": source.url,
                "status": "pending",
                "attempted": False,
                "fetched_count": 0,
                "relevant_count": 0,
                "accepted_count": 0,
                "fresh_item_count": 0,
                "unknown_time_count": 0,
                "stale_filtered_count": 0,
                "future_filtered_count": 0,
                "error": None,
            }
            for source in sources
        }
        if sources:
            worker_count = min(MAX_SOURCE_WORKERS, len(sources))
            with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="public-opinion") as pool:
                futures = {pool.submit(self._capture_source, source): source for source in sources}
                for future in as_completed(futures):
                    source = futures[future]
                    source_diagnostics[source.id]["attempted"] = True
                    try:
                        capture = future.result()
                    except Exception as exc:
                        error = {
                            "source_id": source.id,
                            "url": source.url,
                            "error": str(exc),
                        }
                        errors.append(error)
                        source_diagnostics[source.id].update(
                            {
                                "status": "failed",
                                "error": str(exc),
                            }
                        )
                        continue
                    source_batches[source.id] = list(capture["items"])
                    source_diagnostics[source.id].update(capture["diagnostics"])

        parsed_items, accepted_counts, duplicate_filtered_count = self._allocate_fair_items(
            sources,
            source_batches,
            safe_limit,
        )
        for source_id, accepted_count in accepted_counts.items():
            source_diagnostics[source_id]["accepted_count"] = accepted_count

        source_stats = self._source_stats(
            sources=sources,
            diagnostics=list(source_diagnostics.values()),
            requested_source_count=len(self.sources) + len(requested_source_urls),
            duplicate_filtered_count=duplicate_filtered_count,
            item_count=len(parsed_items),
        )

        sector_signals = self._sector_signals(parsed_items)
        status = (
            "partial"
            if errors
            else "completed"
            if parsed_items
            else "empty"
        )
        summary = self._summary(
            parsed_items,
            sector_signals,
            errors,
            requested_by,
            source_stats=source_stats,
        )
        result = {
            "status": status,
            "schema_version": "codex_public_opinion_run.v1",
            "requested_by": requested_by,
            "source_count": len(sources),
            "source_stats": source_stats,
            "source_diagnostics": list(source_diagnostics.values()),
            "item_count": len(parsed_items),
            "sector_count": len(sector_signals),
            "items": parsed_items,
            "sector_signals": sector_signals,
            "errors": errors,
            "summary": summary,
            "next_action": summary["next_action"],
            "safety": self._safety(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        if run_id:
            self._persist_items(run_id, parsed_items)
            self._persist_sector_signals(run_id, sector_signals)
            self._finish_run(run_id, result, errors, status=status)
        return {"run_id": run_id, **result}

    def _record_sector_forecasts(
        self,
        intelligence: dict[str, Any],
        *,
        run_id: int | None,
    ) -> dict[str, Any]:
        theses = [
            item
            for item in intelligence.get("sector_theses") or []
            if isinstance(item, dict) and item.get("sector")
        ]
        if run_id is None:
            return {
                "status": "not_persisted",
                "decision_id": None,
                "recorded_count": 0,
                "review_only": True,
            }
        decision_id = f"sector-thesis-run-{run_id}"
        cutoff = str(intelligence.get("as_of") or datetime.now(timezone.utc).isoformat())
        facts = {
            str(item.get("event_id")): item
            for item in intelligence.get("event_facts") or []
            if isinstance(item, dict) and item.get("event_id")
        }
        ledger = ForecastLedger(self.store)
        recorded = 0
        for rank, thesis in enumerate(theses, start=1):
            event_evidence = [
                {
                    "event_id": event_id,
                    "available_at": facts[event_id].get("available_at"),
                    "raw_hash": facts[event_id].get("raw_hash"),
                    "evidence_urls": facts[event_id].get("evidence_urls") or [],
                }
                for event_id in thesis.get("event_ids") or []
                if event_id in facts
            ]
            confidence = max(0.0, min(1.0, float(thesis.get("confidence") or 0.0)))
            direction = str(thesis.get("direction") or "neutral").strip().lower()
            is_directional = direction in {"positive", "negative"}
            probability = confidence if is_directional else None
            probability_semantics = (
                "directional_thesis_success"
                if is_directional
                else "non_directional_thesis_confidence"
            )
            for horizon in sorted(FORECAST_HORIZONS):
                forecast_features = {
                    **thesis,
                    "probability_semantics": probability_semantics,
                    "probability_horizon_days": horizon,
                }
                ledger.record_forecast(
                    ForecastDecision(
                        decision_id=decision_id,
                        scope="sector",
                        subject=str(thesis["sector"]),
                        decision_cutoff=cutoff,
                        available_at=cutoff,
                        horizon_days=horizon,
                        rank=rank,
                        score=round(confidence * 100.0, 4),
                        probability=probability,
                        model_version="market_intelligence_snapshot.v1",
                        prompt_version="codex_market_pulse.v2",
                        data_version=str(
                            (intelligence.get("cross_market_context") or {}).get("as_of")
                            or cutoff
                        ),
                        features=forecast_features,
                        evidence=event_evidence,
                        reasons=[str(item) for item in thesis.get("rationale") or []],
                        status="pending_outcome",
                    )
                )
                recorded += 1
        return {
            "status": "recorded" if recorded else "empty",
            "decision_id": decision_id,
            "recorded_count": recorded,
            "sector_count": len(theses),
            "horizons": sorted(FORECAST_HORIZONS),
            "review_only": True,
        }

    def ingest_evidence(
        self,
        evidence: list[dict[str, Any]],
        *,
        persist: bool = True,
        requested_by: str = "codex",
    ) -> dict[str, Any]:
        """Validate and ingest citation-backed Codex evidence without fetching its URLs."""

        safe_evidence = list(evidence or [])[:300]
        source_ids = {
            str(item.get("source_id") or item.get("source_name") or "codex_search").strip()
            for item in safe_evidence
        }
        source_ids.discard("")
        run_id = self._start_run(max(1, len(source_ids))) if persist else None
        errors: list[dict[str, str]] = []

        if settings.enable_live_trading:
            result = {
                "status": "blocked",
                "reason": "live_trading_enabled",
                "items": [],
                "sector_signals": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
            if run_id:
                self._finish_run(run_id, result, errors, status="blocked")
            return {"run_id": run_id, **result}

        accepted: list[dict[str, Any]] = []
        seen: set[str] = set()
        per_source: dict[str, dict[str, Any]] = {}
        stale_filtered_count = 0
        future_filtered_count = 0
        duplicate_filtered_count = 0
        for index, payload in enumerate(safe_evidence):
            try:
                item = self._normalize_codex_evidence(payload)
            except ValueError as exc:
                errors.append(
                    {
                        "source_id": str(payload.get("source_id") or "codex_search"),
                        "url": str(payload.get("url") or ""),
                        "error": f"evidence_{index + 1}: {exc}",
                    }
                )
                continue
            source_id = str(item["source_id"])
            diag = per_source.setdefault(
                source_id,
                {
                    "source_id": source_id,
                    "source_name": item["source_name"],
                    "category": item["category"],
                    "url": None,
                    "status": "succeeded",
                    "attempted": True,
                    "fetched_count": 0,
                    "relevant_count": 0,
                    "accepted_count": 0,
                    "fresh_item_count": 0,
                    "unknown_time_count": 0,
                    "stale_filtered_count": 0,
                    "future_filtered_count": 0,
                    "error": None,
                },
            )
            diag["fetched_count"] += 1
            freshness = item.get("freshness_status")
            if freshness == "stale":
                stale_filtered_count += 1
                diag["stale_filtered_count"] += 1
                continue
            if freshness == "future":
                future_filtered_count += 1
                diag["future_filtered_count"] += 1
                continue
            if freshness == "fresh":
                diag["fresh_item_count"] += 1
            else:
                diag["unknown_time_count"] += 1
            scored = self._score_item(item)
            scored = self._apply_sector_hints(scored, payload.get("sector_hints") or [])
            if not self._is_relevant(scored):
                continue
            diag["relevant_count"] += 1
            key = self._dedupe_key(scored)
            if key in seen:
                duplicate_filtered_count += 1
                continue
            seen.add(key)
            accepted.append(scored)
            diag["accepted_count"] += 1

        diagnostics = list(per_source.values())
        source_stats = self._source_stats(
            sources=[],
            diagnostics=diagnostics,
            requested_source_count=max(1, len(source_ids)),
            duplicate_filtered_count=duplicate_filtered_count,
            item_count=len(accepted),
        )
        source_stats["stale_filtered_count"] = stale_filtered_count
        source_stats["future_filtered_count"] = future_filtered_count
        source_stats["ingest_mode"] = "codex_structured_evidence"
        sector_signals = self._sector_signals(accepted)
        intelligence = MarketIntelligenceService(store=self.store).build_snapshot(
            accepted,
            as_of=datetime.now(timezone.utc).isoformat(),
        )
        status = "partial" if errors or stale_filtered_count or future_filtered_count else (
            "completed" if accepted else "empty"
        )
        summary = self._summary(
            accepted,
            sector_signals,
            errors,
            requested_by,
            source_stats=source_stats,
        )
        summary["ingest_mode"] = "codex_structured_evidence"
        result = {
            "status": status,
            "schema_version": "codex_public_opinion_evidence_ingest.v1",
            "requested_by": requested_by,
            "source_count": len(diagnostics),
            "source_stats": source_stats,
            "source_diagnostics": diagnostics,
            "item_count": len(accepted),
            "sector_count": len(sector_signals),
            "items": accepted,
            "sector_signals": sector_signals,
            "event_facts": intelligence["event_facts"],
            "cross_market_context": intelligence["cross_market_context"],
            "sector_theses": intelligence["sector_theses"],
            "errors": errors,
            "summary": summary,
            "next_action": summary["next_action"],
            "safety": self._safety(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        result["forecast_ledger"] = self._record_sector_forecasts(
            intelligence,
            run_id=run_id,
        )
        if run_id:
            self._persist_items(run_id, accepted)
            self._persist_sector_signals(run_id, sector_signals)
            self._finish_run(run_id, result, errors, status=status)
        return {"run_id": run_id, **result}

    def latest_run(self) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            """
            SELECT *
            FROM public_opinion_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not row:
            return None
        return self._hydrate_run(row)

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM public_opinion_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        )
        return [self._compact_run(row) for row in rows]

    def latest_context(self, limit: int = 8) -> dict[str, Any]:
        captures = self.store.fetch_all(
            """
            SELECT id, status, item_count, sector_count, summary_json,
                   review_only, simulation_only, live_trading_enabled,
                   created_at, completed_at
            FROM public_opinion_runs
            ORDER BY id DESC
            LIMIT 24
            """
        )
        if not captures:
            return {
                "status": "empty",
                "top_sectors": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        latest_capture = captures[0]
        usable = [
            row
            for row in captures
            if str(row.get("status") or "") in {"completed", "partial"}
            and int(row.get("item_count") or 0) > 0
        ]
        fresh = [
            row
            for row in usable
            if (
                (age := self._timestamp_age_hours(
                    row.get("completed_at") or row.get("created_at"),
                    utc_default=True,
                ))
                is not None
                and age <= CONTEXT_MAX_AGE_HOURS
            )
        ]
        selected = (
            max(
                fresh,
                key=lambda row: (self._context_quality_tier(row), int(row.get("id") or 0)),
            )
            if fresh
            else (usable[0] if usable else latest_capture)
        )
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM public_opinion_sector_signals
            WHERE run_id = ?
            ORDER BY heat_score DESC, item_count DESC, sector ASC
            LIMIT ?
            """,
            (selected["id"], max(1, min(limit, 30))),
        )
        last_known_sectors = [self._hydrate_sector_signal(row) for row in rows]
        completed_at = selected.get("completed_at") or selected.get("created_at")
        context_age_hours = self._timestamp_age_hours(completed_at, utc_default=True)
        stale = context_age_hours is None or context_age_hours > CONTEXT_MAX_AGE_HOURS
        run_status = selected.get("status")
        return {
            "status": "stale" if stale else run_status,
            "run_status": run_status,
            "freshness_status": "stale" if stale else "fresh",
            "context_age_hours": context_age_hours,
            "max_context_age_hours": CONTEXT_MAX_AGE_HOURS,
            "run_id": selected.get("id"),
            "latest_capture_run_id": latest_capture.get("id"),
            "latest_capture_status": latest_capture.get("status"),
            "selection_reason": "highest_quality_fresh_run" if fresh else "latest_usable_fallback",
            "selected_quality_tier": self._context_quality_tier(selected),
            "item_count": selected.get("item_count"),
            "sector_count": 0 if stale else selected.get("sector_count"),
            "recorded_sector_count": selected.get("sector_count"),
            "summary": self._json_loads(selected.get("summary_json"), {}),
            "top_sectors": [] if stale else last_known_sectors,
            "last_known_top_sectors": last_known_sectors if stale else [],
            "review_only": bool(selected.get("review_only")),
            "simulation_only": bool(selected.get("simulation_only")),
            "live_trading_enabled": bool(selected.get("live_trading_enabled")),
            "created_at": selected.get("created_at"),
            "completed_at": selected.get("completed_at"),
        }

    def _context_quality_tier(self, row: dict[str, Any]) -> int:
        summary = self._json_loads(row.get("summary_json"), {})
        source_stats = summary.get("source_stats") or {}
        warnings = summary.get("quality_warnings") or source_stats.get("quality_warnings") or []
        status = str(row.get("status") or "")
        contributing = int(source_stats.get("contributing_count") or 0)
        if status == "completed" and not warnings and contributing >= 2:
            return 3
        if status == "completed" and int(row.get("item_count") or 0) > 0:
            return 2
        if status == "partial" and int(row.get("item_count") or 0) > 0:
            return 1
        return 0

    def _sources_with_ad_hoc_urls(
        self,
        source_urls: list[str],
    ) -> tuple[list[PublicOpinionSource], list[dict[str, str]]]:
        sources = list(self.sources)
        errors: list[dict[str, str]] = []
        for index, url in enumerate(source_urls):
            normalized = str(url or "").strip()
            if not normalized:
                continue
            source_id = f"ad_hoc_{index + 1}"
            try:
                self._validate_public_url(normalized, resolve_dns=False)
            except ValueError as exc:
                errors.append(
                    {
                        "source_id": source_id,
                        "url": normalized,
                        "error": f"unsafe_ad_hoc_url: {exc}",
                    }
                )
                continue
            errors.append(
                {
                    "source_id": source_id,
                    "url": normalized,
                    "error": "ad_hoc_network_fetch_disabled_use_codex_evidence_ingest",
                }
            )
        return sources, errors

    def _fetch_source(self, source: PublicOpinionSource) -> bytes:
        trusted_default = any(
            source.id == configured.id and source.url == configured.url
            for configured in DEFAULT_SOURCES
        )
        self._validate_public_url(
            source.url,
            resolve_dns=True,
            allow_proxy_synthetic_dns=trusted_default,
        )
        source_host = urllib.parse.urlparse(source.url).hostname or ""
        redirect_handler = _SafeRedirectHandler(
            self._validate_public_url,
            allowed_host=source_host,
            allow_proxy_synthetic_dns=trusted_default,
        )
        opener = urllib.request.build_opener(redirect_handler)
        request = urllib.request.Request(
            source.url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "CodexPublicOpinion/1.0"
                )
            },
        )
        try:
            with opener.open(request, timeout=12) as response:
                return response.read(2_000_000)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"http_{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(str(exc.reason or exc)) from exc

    def _capture_source(self, source: PublicOpinionSource) -> dict[str, Any]:
        content = self._fetch_source(source)
        source_items = self._parse_source(source, content)
        relevant: list[dict[str, Any]] = []
        fresh_item_count = 0
        unknown_time_count = 0
        stale_filtered_count = 0
        future_filtered_count = 0
        for item in source_items:
            if not self._usable_title(str(item.get("title") or "")):
                continue
            annotated = self._annotate_freshness(item)
            freshness = annotated.get("freshness_status")
            if freshness == "stale":
                stale_filtered_count += 1
                continue
            if freshness == "future":
                future_filtered_count += 1
                continue
            if freshness == "fresh":
                fresh_item_count += 1
            else:
                unknown_time_count += 1
            scored = self._score_item(annotated)
            if self._is_relevant(scored):
                relevant.append(scored)
        relevant.sort(
            key=lambda item: (
                item.get("freshness_status") == "fresh",
                float(item.get("score") or 0),
                str(item.get("published_at") or ""),
            ),
            reverse=True,
        )
        return {
            "items": relevant,
            "diagnostics": {
                "status": "succeeded",
                "attempted": True,
                "fetched_count": len(source_items),
                "relevant_count": len(relevant),
                "fresh_item_count": fresh_item_count,
                "unknown_time_count": unknown_time_count,
                "stale_filtered_count": stale_filtered_count,
                "future_filtered_count": future_filtered_count,
                "error": None,
            },
        }

    def _allocate_fair_items(
        self,
        sources: list[PublicOpinionSource],
        source_batches: dict[str, list[dict[str, Any]]],
        limit: int,
    ) -> tuple[list[dict[str, Any]], dict[str, int], int]:
        if not sources:
            return [], {}, 0
        quota = max(1, limit // len(sources))
        positions = {source.id: 0 for source in sources}
        accepted_counts = {source.id: 0 for source in sources}
        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        duplicate_filtered_count = 0

        def take_one(source: PublicOpinionSource) -> bool:
            nonlocal duplicate_filtered_count
            items = source_batches.get(source.id) or []
            while positions[source.id] < len(items):
                item = items[positions[source.id]]
                positions[source.id] += 1
                key = self._dedupe_key(item)
                if key in seen:
                    duplicate_filtered_count += 1
                    continue
                seen.add(key)
                selected.append(item)
                accepted_counts[source.id] += 1
                return True
            return False

        for source in sources:
            while accepted_counts[source.id] < quota and len(selected) < limit:
                if not take_one(source):
                    break
        while len(selected) < limit:
            progressed = False
            for source in sources:
                if len(selected) >= limit:
                    break
                progressed = take_one(source) or progressed
            if not progressed:
                break
        return selected, accepted_counts, duplicate_filtered_count

    def _source_stats(
        self,
        *,
        sources: list[PublicOpinionSource],
        diagnostics: list[dict[str, Any]],
        requested_source_count: int,
        duplicate_filtered_count: int,
        item_count: int,
    ) -> dict[str, Any]:
        attempted = [item for item in diagnostics if item.get("attempted")]
        succeeded = [item for item in attempted if item.get("status") == "succeeded"]
        accepted = [item for item in diagnostics if int(item.get("accepted_count") or 0) > 0]
        shares = {
            str(item.get("source_id")): round(int(item.get("accepted_count") or 0) / item_count, 4)
            for item in accepted
            if item_count
        }
        max_share = max(shares.values(), default=0.0)
        warnings: list[str] = []
        if item_count and max_share > SINGLE_SOURCE_DOMINANCE_RATIO:
            warnings.append("single_source_dominance")
        if len(succeeded) < min(2, max(1, len(diagnostics))):
            warnings.append("insufficient_successful_sources")
        unknown_time_count = sum(int(item.get("unknown_time_count") or 0) for item in diagnostics)
        if unknown_time_count:
            warnings.append("unknown_publication_time_present")
        return {
            "requested_count": requested_source_count,
            "configured_count": len(sources) if sources else len(diagnostics),
            "attempted_count": len(attempted),
            "succeeded_count": len(succeeded),
            "failed_count": len(attempted) - len(succeeded),
            "contributing_count": len(accepted),
            "source_item_shares": shares,
            "max_single_source_share": max_share,
            "dominance_threshold": SINGLE_SOURCE_DOMINANCE_RATIO,
            "fresh_item_count": sum(int(item.get("fresh_item_count") or 0) for item in diagnostics),
            "unknown_time_count": unknown_time_count,
            "stale_filtered_count": sum(
                int(item.get("stale_filtered_count") or 0) for item in diagnostics
            ),
            "future_filtered_count": sum(
                int(item.get("future_filtered_count") or 0) for item in diagnostics
            ),
            "duplicate_filtered_count": duplicate_filtered_count,
            "quality_warnings": warnings,
        }

    def _parse_source(self, source: PublicOpinionSource, content: bytes) -> list[dict[str, Any]]:
        text = self._decode(content)
        stripped = text.lstrip()
        if source.parser in {"rss", "atom"} or stripped.startswith(("<rss", "<feed", "<?xml")):
            try:
                return self._parse_xml_feed(source, text)
            except ET.ParseError:
                if source.parser in {"rss", "atom"}:
                    raise
        return self._parse_html_links(source, text)

    def _parse_xml_feed(self, source: PublicOpinionSource, text: str) -> list[dict[str, Any]]:
        root = ET.fromstring(text)
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        parsed: list[dict[str, Any]] = []
        for item in items:
            title = self._node_text(item, ["title", "{http://www.w3.org/2005/Atom}title"])
            if not title:
                continue
            link = self._node_text(item, ["link"])
            if not link:
                link_node = item.find("{http://www.w3.org/2005/Atom}link")
                link = link_node.get("href") if link_node is not None else None
            parsed.append(
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "source_tier": source.source_tier,
                    "category": source.category,
                    "title": self._clean_text(title),
                    "url": urllib.parse.urljoin(source.url, link or ""),
                    "published_at": self._node_text(
                        item,
                        ["pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}updated"],
                    ),
                    "summary": self._clean_text(
                        self._node_text(
                            item,
                            [
                                "description",
                                "summary",
                                "{http://www.w3.org/2005/Atom}summary",
                            ],
                        )
                        or ""
                    ),
                    "raw": {"parser": "xml"},
                }
            )
        return parsed

    def _parse_html_links(self, source: PublicOpinionSource, text: str) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for match in _LINK_RE.finditer(text):
            title = self._clean_text(match.group("title"))
            if not self._usable_title(title):
                continue
            href = unescape(match.group("href"))
            url = urllib.parse.urljoin(source.url, href)
            nearby = text[max(0, match.start() - 120) : min(len(text), match.end() + 120)]
            parsed.append(
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "source_tier": source.source_tier,
                    "category": source.category,
                    "title": title,
                    "url": url,
                    "published_at": self._extract_date_near(nearby),
                    "summary": "",
                    "raw": {"parser": "html"},
                }
            )
        if parsed:
            return parsed

        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        if not title_match:
            return []
        title = self._clean_text(title_match.group(1))
        return [
            {
                "source_id": source.id,
                "source_name": source.name,
                "source_tier": source.source_tier,
                "category": source.category,
                "title": title,
                "url": source.url,
                "published_at": None,
                "summary": "",
                "raw": {"parser": "html_title_fallback"},
            }
        ]

    def _score_item(self, item: dict[str, Any]) -> dict[str, Any]:
        text = f"{item.get('title') or ''} {item.get('summary') or ''}"
        matched_sectors: list[dict[str, Any]] = []
        for sector, payload in SECTOR_TAXONOMY.items():
            hits = self._keyword_hits(text, payload["keywords"])
            if hits:
                matched_sectors.append(
                    {
                        "sector": sector,
                        "display_name": payload["display_name"],
                        "keywords": hits,
                    }
                )

        positive_hits = self._keyword_hits(text, POSITIVE_KEYWORDS)
        risk_hits = self._keyword_hits(text, RISK_KEYWORDS)
        policy_hits = self._keyword_hits(text, POLICY_KEYWORDS)
        market_hits = self._keyword_hits(text, MARKET_KEYWORDS)
        tags = []
        if positive_hits:
            tags.append("positive")
        if risk_hits:
            tags.append("risk")
        if policy_hits or item.get("category") == "policy":
            tags.append("policy")
        if market_hits or item.get("category") == "market":
            tags.append("market")

        sector_score = sum(max(1, len(match["keywords"])) for match in matched_sectors) * 6.0
        score = (
            sector_score
            + len(positive_hits) * 2.0
            + len(policy_hits) * 2.0
            + len(market_hits) * 1.0
            - len(risk_hits) * 4.0
        )
        if item.get("category") == "policy":
            score += 5.0
        if item.get("category") == "market":
            score += 2.0
        freshness_status = str(item.get("freshness_status") or "unknown")
        if freshness_status == "unknown":
            score *= 0.65
        direction = "neutral"
        if positive_hits and risk_hits:
            direction = "mixed"
        elif risk_hits:
            direction = "negative"
        elif positive_hits:
            direction = "positive"
        scored = {
            **item,
            "source_domain": self._publisher_domain(str(item.get("url") or "")),
            "matched_sectors": matched_sectors,
            "tags": sorted(set(tags)),
            "score": round(max(0.0, score), 2),
            "positive_keywords": positive_hits,
            "risk_keywords": risk_hits,
            "policy_keywords": policy_hits,
            "market_keywords": market_hits,
            "direction": direction,
        }
        return scored

    def _sector_signals(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        aggregate: dict[str, dict[str, Any]] = {}
        for item in items:
            for match in item.get("matched_sectors") or []:
                sector = match["sector"]
                bucket = aggregate.setdefault(
                    sector,
                    {
                        "sector": sector,
                        "display_name": match.get("display_name"),
                        "heat_score": 0.0,
                        "item_count": 0,
                        "positive_count": 0,
                        "policy_count": 0,
                        "market_count": 0,
                        "risk_count": 0,
                        "keywords": [],
                        "evidence": [],
                        "source_ids": [],
                        "source_domains": [],
                        "fresh_item_count": 0,
                        "fresh_positive_count": 0,
                        "fresh_risk_count": 0,
                        "fresh_official_policy_count": 0,
                        "fresh_official_positive_policy_count": 0,
                        "fresh_source_domains": [],
                        "fresh_positive_source_domains": [],
                        "unknown_time_count": 0,
                    },
                )
                bucket["heat_score"] += float(item.get("score") or 0)
                bucket["item_count"] += 1
                tags = set(item.get("tags") or [])
                if "positive" in tags:
                    bucket["positive_count"] += 1
                if "policy" in tags:
                    bucket["policy_count"] += 1
                if "market" in tags:
                    bucket["market_count"] += 1
                if "risk" in tags:
                    bucket["risk_count"] += 1
                bucket["keywords"].extend(match.get("keywords") or [])
                bucket["source_ids"].append(item.get("source_id"))
                bucket["source_domains"].append(item.get("source_domain"))
                if item.get("freshness_status") == "fresh":
                    bucket["fresh_item_count"] += 1
                    bucket["fresh_source_domains"].append(item.get("source_domain"))
                    if "positive" in tags:
                        bucket["fresh_positive_count"] += 1
                        bucket["fresh_positive_source_domains"].append(
                            item.get("source_domain")
                        )
                    if "risk" in tags:
                        bucket["fresh_risk_count"] += 1
                    if "policy" in tags and item.get("source_tier") == "official":
                        bucket["fresh_official_policy_count"] += 1
                        if "positive" in tags:
                            bucket["fresh_official_positive_policy_count"] += 1
                elif item.get("freshness_status") == "unknown":
                    bucket["unknown_time_count"] += 1
                bucket["evidence"].append(
                    {
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "source_id": item.get("source_id"),
                        "source_name": item.get("source_name"),
                        "source_tier": item.get("source_tier"),
                        "source_domain": item.get("source_domain"),
                        "score": item.get("score"),
                        "tags": item.get("tags"),
                        "published_at": item.get("published_at"),
                        "freshness_status": item.get("freshness_status"),
                        "direction": item.get("direction"),
                    }
                )
        signals = []
        for bucket in aggregate.values():
            heat_score = round(float(bucket["heat_score"]), 2)
            signal = {
                "sector": bucket["sector"],
                "display_name": bucket["display_name"],
                "heat_score": heat_score,
                "item_count": bucket["item_count"],
                "positive_count": bucket["positive_count"],
                "policy_count": bucket["policy_count"],
                "official_policy_count": sum(
                    1
                    for evidence in bucket["evidence"]
                    if evidence.get("source_tier") == "official"
                    and "policy" in set(evidence.get("tags") or [])
                ),
                "fresh_official_policy_count": bucket["fresh_official_policy_count"],
                "fresh_official_positive_policy_count": bucket[
                    "fresh_official_positive_policy_count"
                ],
                "market_count": bucket["market_count"],
                "risk_count": bucket["risk_count"],
                "independent_source_count": len(
                    {domain for domain in bucket["source_domains"] if domain}
                ),
                "fresh_item_count": bucket["fresh_item_count"],
                "fresh_positive_count": bucket["fresh_positive_count"],
                "fresh_risk_count": bucket["fresh_risk_count"],
                "fresh_independent_source_count": len(
                    {domain for domain in bucket["fresh_source_domains"] if domain}
                ),
                "fresh_positive_source_count": len(
                    {
                        domain
                        for domain in bucket["fresh_positive_source_domains"]
                        if domain
                    }
                ),
                "unknown_time_count": bucket["unknown_time_count"],
                "keywords": sorted(set(bucket["keywords"])),
                "evidence": sorted(
                    bucket["evidence"],
                    key=lambda row: (
                        row.get("freshness_status") == "fresh",
                        row.get("source_tier") == "official",
                        float(row.get("score") or 0),
                    ),
                    reverse=True,
                )[:5],
                "suggested_action": self._suggested_action(bucket, heat_score),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
            signals.append(signal)
        signals.sort(key=lambda row: (row["heat_score"], row["item_count"]), reverse=True)
        return signals

    def _summary(
        self,
        items: list[dict[str, Any]],
        sector_signals: list[dict[str, Any]],
        errors: list[dict[str, str]],
        requested_by: str,
        *,
        source_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        top = sector_signals[:5]
        quality = source_stats or {}
        if top:
            next_action = (
                "Feed top sector signals into selection-v2 review, then validate with daily_bar_cache "
                "and simulated training outcomes before any human-reviewed action."
            )
        elif errors:
            next_action = "Review source fetch errors, add working sources, then rerun public opinion capture."
        else:
            next_action = "Keep scheduled capture running; no sector signal met the keyword evidence gate."
        return {
            "requested_by": requested_by,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "item_count": len(items),
            "sector_count": len(sector_signals),
            "top_sectors": [
                {
                    "sector": signal["sector"],
                    "display_name": signal["display_name"],
                    "heat_score": signal["heat_score"],
                    "item_count": signal["item_count"],
                    "suggested_action": signal["suggested_action"],
                }
                for signal in top
            ],
            "error_count": len(errors),
            "source_stats": quality,
            "quality_warnings": list(quality.get("quality_warnings") or []),
            "next_action": next_action,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _start_run(self, source_count: int) -> int:
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO public_opinion_runs(
                    status, source_count, review_only, simulation_only, live_trading_enabled
                )
                VALUES (?, ?, 1, 1, ?)
                """,
                ("running", source_count, int(settings.enable_live_trading)),
            )
            return int(cursor.lastrowid)

    def _finish_run(
        self,
        run_id: int,
        result: dict[str, Any],
        errors: list[dict[str, str]],
        *,
        status: str,
    ) -> None:
        with self.store.connect() as conn:
            conn.execute(
                """
                UPDATE public_opinion_runs
                SET status = ?,
                    item_count = ?,
                    sector_count = ?,
                    errors_json = ?,
                    summary_json = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    status,
                    int(result.get("item_count") or 0),
                    int(result.get("sector_count") or 0),
                    json.dumps(errors, ensure_ascii=False),
                    json.dumps(result.get("summary") or {}, ensure_ascii=False, default=str),
                    run_id,
                ),
            )

    def _persist_items(self, run_id: int, items: list[dict[str, Any]]) -> None:
        with self.store.connect() as conn:
            for item in items:
                conn.execute(
                    """
                    INSERT INTO public_opinion_items(
                        run_id, source_id, source_name, category, title, url,
                        published_at, summary, matched_sectors_json, tags_json,
                        score, raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        item.get("source_id"),
                        item.get("source_name"),
                        item.get("category") or "market",
                        item.get("title"),
                        item.get("url"),
                        item.get("published_at"),
                        item.get("summary"),
                        json.dumps(item.get("matched_sectors") or [], ensure_ascii=False),
                        json.dumps(item.get("tags") or [], ensure_ascii=False),
                        float(item.get("score") or 0),
                        json.dumps(item, ensure_ascii=False, default=str),
                    ),
                )

    def _persist_sector_signals(self, run_id: int, signals: list[dict[str, Any]]) -> None:
        with self.store.connect() as conn:
            for signal in signals:
                conn.execute(
                    """
                    INSERT INTO public_opinion_sector_signals(
                        run_id, sector, heat_score, item_count, positive_count,
                        policy_count, market_count, risk_count, keywords_json,
                        evidence_json, suggested_action
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        signal["sector"],
                        float(signal.get("heat_score") or 0),
                        int(signal.get("item_count") or 0),
                        int(signal.get("positive_count") or 0),
                        int(signal.get("policy_count") or 0),
                        int(signal.get("market_count") or 0),
                        int(signal.get("risk_count") or 0),
                        json.dumps(signal.get("keywords") or [], ensure_ascii=False),
                        json.dumps(signal.get("evidence") or [], ensure_ascii=False),
                        signal.get("suggested_action") or "keep_monitoring_review_only",
                    ),
                )

    def _hydrate_run(self, row: dict[str, Any]) -> dict[str, Any]:
        result = self._compact_run(row)
        items = self.store.fetch_all(
            """
            SELECT *
            FROM public_opinion_items
            WHERE run_id = ?
            ORDER BY score DESC, id ASC
            LIMIT 60
            """,
            (row["id"],),
        )
        sectors = self.store.fetch_all(
            """
            SELECT *
            FROM public_opinion_sector_signals
            WHERE run_id = ?
            ORDER BY heat_score DESC, item_count DESC, sector ASC
            """,
            (row["id"],),
        )
        result["items"] = [self._hydrate_item(item) for item in items]
        result["sector_signals"] = [self._hydrate_sector_signal(sector) for sector in sectors]
        return result

    def _compact_run(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "status": row.get("status"),
            "source_count": int(row.get("source_count") or 0),
            "item_count": int(row.get("item_count") or 0),
            "sector_count": int(row.get("sector_count") or 0),
            "errors": self._json_loads(row.get("errors_json"), []),
            "summary": self._json_loads(row.get("summary_json"), {}),
            "review_only": bool(row.get("review_only")),
            "simulation_only": bool(row.get("simulation_only")),
            "live_trading_enabled": bool(row.get("live_trading_enabled")),
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
        }

    def _hydrate_item(self, row: dict[str, Any]) -> dict[str, Any]:
        raw = self._json_loads(row.get("raw_json"), {})
        return {
            "id": row.get("id"),
            "run_id": row.get("run_id"),
            "source_id": row.get("source_id"),
            "source_name": row.get("source_name"),
            "source_tier": raw.get("source_tier", "market_media"),
            "category": row.get("category"),
            "title": row.get("title"),
            "url": row.get("url"),
            "published_at": row.get("published_at"),
            "summary": row.get("summary"),
            "score": row.get("score"),
            "created_at": row.get("created_at"),
            "matched_sectors": self._json_loads(row.get("matched_sectors_json"), []),
            "tags": self._json_loads(row.get("tags_json"), []),
            "freshness_status": raw.get("freshness_status", "unknown"),
            "published_at_status": raw.get("published_at_status", "unknown"),
            "age_hours": raw.get("age_hours"),
            "direction": raw.get("direction", "neutral"),
            "retrieved_at": raw.get("retrieved_at"),
            "raw": raw,
        }

    def _hydrate_sector_signal(self, row: dict[str, Any]) -> dict[str, Any]:
        sector = str(row.get("sector") or "")
        evidence = self._json_loads(row.get("evidence_json"), [])
        return {
            "id": row.get("id"),
            "run_id": row.get("run_id"),
            "sector": sector,
            "display_name": SECTOR_TAXONOMY.get(sector, {}).get("display_name", sector),
            "heat_score": row.get("heat_score"),
            "item_count": row.get("item_count"),
            "positive_count": row.get("positive_count"),
            "policy_count": row.get("policy_count"),
            "official_policy_count": sum(
                1
                for item in evidence
                if item.get("source_tier") == "official"
                and "policy" in set(item.get("tags") or [])
            ),
            "fresh_official_policy_count": sum(
                1
                for item in evidence
                if item.get("freshness_status") == "fresh"
                and item.get("source_tier") == "official"
                and "policy" in set(item.get("tags") or [])
            ),
            "fresh_official_positive_policy_count": sum(
                1
                for item in evidence
                if item.get("freshness_status") == "fresh"
                and item.get("source_tier") == "official"
                and "policy" in set(item.get("tags") or [])
                and "positive" in set(item.get("tags") or [])
            ),
            "market_count": row.get("market_count"),
            "risk_count": row.get("risk_count"),
            "keywords": self._json_loads(row.get("keywords_json"), []),
            "evidence": evidence,
            "independent_source_count": len(
                {
                    str(
                        item.get("source_domain")
                        or self._publisher_domain(str(item.get("url") or ""))
                    )
                    for item in evidence
                    if item.get("source_domain") or item.get("url")
                }
            ),
            "fresh_item_count": sum(
                1 for item in evidence if item.get("freshness_status") == "fresh"
            ),
            "fresh_positive_count": sum(
                1
                for item in evidence
                if item.get("freshness_status") == "fresh"
                and "positive" in set(item.get("tags") or [])
            ),
            "fresh_risk_count": sum(
                1
                for item in evidence
                if item.get("freshness_status") == "fresh"
                and "risk" in set(item.get("tags") or [])
            ),
            "fresh_independent_source_count": len(
                {
                    str(
                        item.get("source_domain")
                        or self._publisher_domain(str(item.get("url") or ""))
                    )
                    for item in evidence
                    if item.get("freshness_status") == "fresh"
                    and (item.get("source_domain") or item.get("url"))
                }
            ),
            "fresh_positive_source_count": len(
                {
                    str(
                        item.get("source_domain")
                        or self._publisher_domain(str(item.get("url") or ""))
                    )
                    for item in evidence
                    if item.get("freshness_status") == "fresh"
                    and "positive" in set(item.get("tags") or [])
                    and (item.get("source_domain") or item.get("url"))
                }
            ),
            "unknown_time_count": sum(
                1 for item in evidence if item.get("freshness_status") == "unknown"
            ),
            "suggested_action": row.get("suggested_action"),
            "created_at": row.get("created_at"),
        }

    def _suggested_action(self, bucket: dict[str, Any], heat_score: float) -> str:
        risk_count = int(bucket.get("risk_count") or 0)
        positive_count = int(bucket.get("positive_count") or 0)
        policy_count = int(bucket.get("policy_count") or 0)
        item_count = int(bucket.get("item_count") or 0)
        if risk_count and risk_count >= positive_count:
            return "risk_review_only"
        if risk_count:
            return "mixed_review_only"
        if positive_count == 0 and policy_count == 0:
            return "continue_monitoring_review_only" if item_count >= 2 else "single_item_watch_review_only"
        if heat_score >= 45 or (policy_count >= 1 and item_count >= 2):
            return "sector_watch_review_only"
        if item_count >= 2:
            return "continue_monitoring_review_only"
        return "single_item_watch_review_only"

    def _is_relevant(self, item: dict[str, Any]) -> bool:
        if item.get("matched_sectors"):
            return True
        text = f"{item.get('title') or ''} {item.get('summary') or ''}"
        return bool(
            self._keyword_hits(text, MARKET_KEYWORDS)
            or self._keyword_hits(text, POLICY_KEYWORDS)
            or item.get("category") == "policy"
        )

    def _dedupe_key(self, item: dict[str, Any]) -> str:
        url = str(item.get("url") or "").strip().lower()
        title = str(item.get("title") or "").strip().lower()
        if url:
            parsed = urllib.parse.urlsplit(url)
            query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            query = [
                (key, value)
                for key, value in query
                if not key.lower().startswith("utm_") and key.lower() not in {"spm", "from"}
            ]
            return urllib.parse.urlunsplit(
                (
                    parsed.scheme.lower(),
                    parsed.netloc.lower(),
                    parsed.path.rstrip("/"),
                    urllib.parse.urlencode(query),
                    "",
                )
            )
        return title

    def _normalize_codex_evidence(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = self._clean_text(str(payload.get("title") or ""))
        summary = self._clean_text(str(payload.get("summary") or ""))
        source_name = self._clean_text(str(payload.get("source_name") or payload.get("source") or ""))
        url = str(payload.get("url") or "").strip()
        retrieved_at = self._parse_timestamp(payload.get("retrieved_at"))
        publication_status = str(payload.get("published_at_status") or "").strip().lower()
        if not self._usable_title(title):
            raise ValueError("title_missing_or_unusable")
        if not summary:
            raise ValueError("summary_required")
        if not source_name:
            raise ValueError("source_name_required")
        if not url:
            raise ValueError("url_required")
        self._validate_public_url(url, resolve_dns=False)
        if retrieved_at is None:
            raise ValueError("retrieved_at_invalid")
        if retrieved_at > datetime.now(timezone.utc) + timedelta(minutes=15):
            raise ValueError("retrieved_at_in_future")
        if publication_status not in {"known", "unknown"}:
            raise ValueError("published_at_status_must_be_known_or_unknown")
        published_at = payload.get("published_at")
        if publication_status == "known" and self._parse_timestamp(published_at) is None:
            raise ValueError("published_at_required_when_status_known")
        if publication_status == "unknown":
            published_at = None
        category = str(payload.get("category") or "market").strip().lower()
        if category not in {"market", "policy", "sector"}:
            raise ValueError("category_must_be_market_policy_or_sector")
        source_id = str(payload.get("source_id") or "").strip()
        if not source_id:
            source_id = urllib.parse.urlparse(url).hostname or "codex_search"
        source_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", source_id).strip("_") or "codex_search"
        validated_source_tier = self._validated_source_tier(payload.get("source_tier"), url)
        event_fact = EventFact.from_evidence(
            {
                **payload,
                "source_tier": validated_source_tier,
                "evidence_urls": payload.get("evidence_urls") or [url],
            }
        ).to_dict()
        item = {
            "source_id": source_id,
            "source_name": source_name,
            "source_tier": validated_source_tier,
            "category": "market" if category == "sector" else category,
            "title": title,
            "url": url,
            "published_at": published_at,
            "summary": summary,
            "retrieved_at": retrieved_at.isoformat(),
            "published_at_status": publication_status,
            "event_fact": event_fact,
            "raw": {
                "parser": "codex_structured_evidence",
                "retrieved_at": retrieved_at.isoformat(),
                "published_at_status": publication_status,
                "source_tier": validated_source_tier,
                "claims": payload.get("claims") or [],
                "event_fact": event_fact,
            },
        }
        return self._annotate_freshness(item)

    def _apply_sector_hints(
        self,
        item: dict[str, Any],
        hints: list[Any],
    ) -> dict[str, Any]:
        if not isinstance(hints, list):
            return item
        matches = list(item.get("matched_sectors") or [])
        existing = {str(match.get("sector")) for match in matches}
        added_count = 0
        for hint in hints:
            value = str(hint.get("sector") if isinstance(hint, dict) else hint or "").strip()
            if not value:
                continue
            lowered = value.lower()
            for sector, payload in SECTOR_TAXONOMY.items():
                candidates = [sector, str(payload["display_name"]), *payload["keywords"]]
                if lowered not in {candidate.lower() for candidate in candidates} or sector in existing:
                    continue
                matches.append(
                    {
                        "sector": sector,
                        "display_name": payload["display_name"],
                        "keywords": [value],
                        "source": "codex_sector_hint",
                    }
                )
                existing.add(sector)
                added_count += 1
        if not added_count:
            return item
        return {
            **item,
            "matched_sectors": matches,
            "score": round(float(item.get("score") or 0) + 6.0 * added_count, 2),
        }

    def _annotate_freshness(self, item: dict[str, Any]) -> dict[str, Any]:
        published_at = item.get("published_at")
        parsed = self._parse_timestamp(published_at)
        status = str(item.get("published_at_status") or "").lower()
        now = datetime.now(timezone.utc)
        if published_at in (None, ""):
            return {
                **item,
                "published_at_status": "unknown",
                "freshness_status": "unknown",
                "age_hours": None,
                "retrieved_at": item.get("retrieved_at") or now.isoformat(),
            }
        if parsed is None:
            return {
                **item,
                "published_at_status": "invalid",
                "freshness_status": "unknown",
                "age_hours": None,
                "retrieved_at": item.get("retrieved_at") or now.isoformat(),
            }
        age_hours = (now - parsed).total_seconds() / 3600
        max_age = (
            POLICY_ITEM_MAX_AGE_HOURS
            if item.get("category") == "policy"
            else MARKET_ITEM_MAX_AGE_HOURS
        )
        freshness_status = "fresh"
        if age_hours < -6:
            freshness_status = "future"
        elif age_hours > max_age:
            freshness_status = "stale"
        return {
            **item,
            "published_at_status": "known" if status != "invalid" else status,
            "freshness_status": freshness_status,
            "age_hours": round(age_hours, 2),
            "retrieved_at": item.get("retrieved_at") or now.isoformat(),
        }

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value).strip()
            normalized = (
                text.replace("年", "-")
                .replace("月", "-")
                .replace("日", "")
                .replace("/", "-")
            )
            try:
                parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
            except ValueError:
                try:
                    parsed = parsedate_to_datetime(text)
                except (TypeError, ValueError, OverflowError):
                    return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _timestamp_age_hours(self, value: Any, *, utc_default: bool = False) -> float | None:
        parsed = self._parse_timestamp(value)
        if parsed is None:
            return None
        now = datetime.now(timezone.utc)
        return round((now - parsed).total_seconds() / 3600, 2)

    @staticmethod
    def _validate_public_url(
        url: str,
        *,
        resolve_dns: bool,
        allow_proxy_synthetic_dns: bool = False,
    ) -> None:
        parsed = urllib.parse.urlsplit(str(url or "").strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("scheme_not_allowed")
        if parsed.username or parsed.password:
            raise ValueError("url_credentials_not_allowed")
        host = (parsed.hostname or "").strip().lower().rstrip(".")
        if not host:
            raise ValueError("host_required")
        if host == "localhost" or host.endswith((".localhost", ".local")):
            raise ValueError("local_host_not_allowed")

        def ensure_global(address_text: str, *, allow_synthetic: bool = False) -> None:
            try:
                address = ipaddress.ip_address(address_text)
            except ValueError:
                return
            if allow_synthetic and address in ipaddress.ip_network("198.18.0.0/15"):
                return
            if not address.is_global:
                raise ValueError("private_or_non_global_address_not_allowed")

        ensure_global(host)
        if not resolve_dns:
            return
        try:
            addresses = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError("host_resolution_failed") from exc
        if not addresses:
            raise ValueError("host_resolution_failed")
        for address in addresses:
            ensure_global(
                str(address[4][0]),
                allow_synthetic=allow_proxy_synthetic_dns,
            )

    @staticmethod
    def _node_text(node: ET.Element, names: list[str]) -> str | None:
        for name in names:
            child = node.find(name)
            if child is not None and child.text:
                return child.text.strip()
        return None

    @staticmethod
    def _decode(content: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")

    @staticmethod
    def _clean_text(value: str) -> str:
        text = _TAG_RE.sub("", value or "")
        text = unescape(text)
        return _SPACE_RE.sub(" ", text).strip()

    @staticmethod
    def _usable_title(title: str) -> bool:
        if not title:
            return False
        if len(title) < 6 or len(title) > 160:
            return False
        normalized = _SPACE_RE.sub("", title).strip("-—_|>》")
        nav_terms = {
            "首页",
            "更多",
            "登录",
            "注册",
            "搜索",
            "广告",
            "专题",
            "视频",
            "行情中心",
            "进入行情中心",
            "环球市场",
            "点击查看",
            "股票首页",
            "返回顶部",
        }
        if normalized in nav_terms:
            return False
        if title.endswith((">>", "》》")) and len(normalized) <= 12:
            return False
        return True

    @staticmethod
    def _extract_date_near(text: str) -> str | None:
        match = re.search(r"20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}", text)
        return match.group(0) if match else None

    @staticmethod
    def _keyword_hits(text: str, keywords: list[str]) -> list[str]:
        lowered = text.lower()
        hits: list[str] = []
        for keyword in keywords:
            normalized = keyword.lower()
            if re.fullmatch(r"[a-z0-9.+-]+", normalized):
                if re.search(
                    rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])",
                    lowered,
                ):
                    hits.append(keyword)
            elif normalized in lowered:
                hits.append(keyword)
        return hits

    @staticmethod
    def _validated_source_tier(value: Any, url: str) -> str:
        tier = str(value or "market_media").strip().lower()
        if tier not in {"official", "primary_media", "market_media"}:
            raise ValueError("source_tier_invalid")
        if tier != "official":
            return tier
        host = (urllib.parse.urlsplit(url).hostname or "").lower().rstrip(".")
        official_hosts = (
            "gov.cn",
            "csrc.gov.cn",
            "pbc.gov.cn",
            "ndrc.gov.cn",
            "mof.gov.cn",
            "sse.com.cn",
            "szse.cn",
            "bse.cn",
        )
        if not any(host == suffix or host.endswith(f".{suffix}") for suffix in official_hosts):
            raise ValueError("official_source_domain_unverified")
        return tier

    @staticmethod
    def _publisher_domain(url: str) -> str:
        host = (urllib.parse.urlsplit(url).hostname or "").lower().rstrip(".")
        if not host:
            return ""
        labels = host.split(".")
        if len(labels) <= 2:
            return host
        compound_suffixes = {"com.cn", "net.cn", "org.cn", "gov.cn"}
        suffix = ".".join(labels[-2:])
        return ".".join(labels[-3:]) if suffix in compound_suffixes else suffix

    @staticmethod
    def _json_loads(value: Any, default: Any) -> Any:
        if value in (None, ""):
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _safety() -> dict[str, Any]:
        return {
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "allow_live_order": False,
            "execution_allowed": False,
            "model_artifact_write_enabled": False,
        }
