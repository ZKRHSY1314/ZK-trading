from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from html import unescape
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


@dataclass(frozen=True)
class PublicOpinionSource:
    id: str
    name: str
    url: str
    category: str = "market"
    parser: str = "auto"


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
    ),
)


SECTOR_TAXONOMY: dict[str, dict[str, Any]] = {
    "ai_compute": {
        "display_name": "AI computing",
        "keywords": [
            "人工智能",
            "AI",
            "大模型",
            "算力",
            "数据中心",
            "光模块",
            "CPO",
            "半导体",
            "芯片",
            "存储",
            "机器人",
        ],
    },
    "digital_economy": {
        "display_name": "Digital economy",
        "keywords": ["数字经济", "数据要素", "信创", "网络安全", "鸿蒙", "云计算", "工业互联网"],
    },
    "brokerage_finance": {
        "display_name": "Brokerage and capital market",
        "keywords": ["券商", "证券", "资本市场", "交易所", "融资融券", "并购重组", "注册制", "印花税"],
    },
    "state_owned_reform": {
        "display_name": "SOE reform",
        "keywords": ["国企改革", "央企", "市值管理", "资产注入", "混改", "重组"],
    },
    "new_energy": {
        "display_name": "New energy",
        "keywords": ["新能源", "光伏", "储能", "锂电", "电池", "风电", "充电桩", "固态电池"],
    },
    "low_altitude": {
        "display_name": "Low-altitude economy",
        "keywords": ["低空经济", "无人机", "通航", "eVTOL", "飞行汽车", "空管"],
    },
    "medicine": {
        "display_name": "Medicine",
        "keywords": ["创新药", "医药", "医疗器械", "CRO", "疫苗", "中药"],
    },
    "consumer": {
        "display_name": "Consumer",
        "keywords": ["消费", "食品饮料", "白酒", "旅游", "免税", "家电", "汽车"],
    },
    "infrastructure": {
        "display_name": "Infrastructure",
        "keywords": ["基建", "水利", "特高压", "电网", "铁路", "工程机械", "城市更新"],
    },
    "defense": {
        "display_name": "Defense",
        "keywords": ["军工", "航空发动机", "卫星", "北斗", "航天", "雷达"],
    },
}

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


class CodexPublicOpinionService:
    """Review-only public-opinion capture for policy, market, and sector wind signals."""

    def __init__(
        self,
        store: SQLiteStore | None = None,
        sources: list[PublicOpinionSource] | None = None,
    ) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        self.store.init()
        self.sources = sources or list(DEFAULT_SOURCES)

    def capabilities(self) -> dict[str, Any]:
        return {
            "schema_version": "codex_public_opinion_capabilities.v1",
            "mode": "review_only_public_opinion_capture",
            "supported_steps": [
                "source_fetch",
                "rss_or_html_parse",
                "sector_keyword_scoring",
                "policy_market_risk_tagging",
                "sector_signal_persistence",
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
        sources = self._sources_with_ad_hoc_urls(source_urls or [])
        run_id = self._start_run(len(sources)) if persist else None
        errors: list[dict[str, str]] = []
        parsed_items: list[dict[str, Any]] = []
        seen: set[str] = set()

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

        for source in sources:
            try:
                content = self._fetch_source(source)
                source_items = self._parse_source(source, content)
            except Exception as exc:
                errors.append({"source_id": source.id, "url": source.url, "error": str(exc)})
                continue
            for item in source_items:
                key = self._dedupe_key(item)
                if key in seen:
                    continue
                seen.add(key)
                scored = self._score_item(item)
                if self._is_relevant(scored):
                    parsed_items.append(scored)
                if len(parsed_items) >= safe_limit:
                    break
            if len(parsed_items) >= safe_limit:
                break

        sector_signals = self._sector_signals(parsed_items)
        status = "completed" if parsed_items else ("partial" if errors else "empty")
        summary = self._summary(parsed_items, sector_signals, errors, requested_by)
        result = {
            "status": status,
            "schema_version": "codex_public_opinion_run.v1",
            "requested_by": requested_by,
            "source_count": len(sources),
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
        latest = self.store.fetch_one(
            """
            SELECT id, status, item_count, sector_count, summary_json,
                   review_only, simulation_only, live_trading_enabled,
                   created_at, completed_at
            FROM public_opinion_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not latest:
            return {
                "status": "empty",
                "top_sectors": [],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM public_opinion_sector_signals
            WHERE run_id = ?
            ORDER BY heat_score DESC, item_count DESC, sector ASC
            LIMIT ?
            """,
            (latest["id"], max(1, min(limit, 30))),
        )
        return {
            "status": latest.get("status"),
            "run_id": latest.get("id"),
            "item_count": latest.get("item_count"),
            "sector_count": latest.get("sector_count"),
            "summary": self._json_loads(latest.get("summary_json"), {}),
            "top_sectors": [self._hydrate_sector_signal(row) for row in rows],
            "review_only": bool(latest.get("review_only")),
            "simulation_only": bool(latest.get("simulation_only")),
            "live_trading_enabled": bool(latest.get("live_trading_enabled")),
            "created_at": latest.get("created_at"),
            "completed_at": latest.get("completed_at"),
        }

    def _sources_with_ad_hoc_urls(self, source_urls: list[str]) -> list[PublicOpinionSource]:
        sources = list(self.sources)
        for index, url in enumerate(source_urls):
            normalized = str(url or "").strip()
            if not normalized:
                continue
            parsed = urllib.parse.urlparse(normalized)
            if parsed.scheme not in {"http", "https"}:
                continue
            sources.append(
                PublicOpinionSource(
                    id=f"ad_hoc_{index + 1}",
                    name=f"Ad hoc source {index + 1}",
                    url=normalized,
                    category="market",
                    parser="auto",
                )
            )
        return sources

    def _fetch_source(self, source: PublicOpinionSource) -> bytes:
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
            with urllib.request.urlopen(request, timeout=12) as response:
                return response.read(2_000_000)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"http_{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(str(exc.reason or exc)) from exc

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
            parsed.append(
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "category": source.category,
                    "title": title,
                    "url": url,
                    "published_at": self._extract_date_near(match.group(0)),
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
            hits = [keyword for keyword in payload["keywords"] if keyword.lower() in text.lower()]
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
        scored = {
            **item,
            "matched_sectors": matched_sectors,
            "tags": sorted(set(tags)),
            "score": round(max(0.0, score), 2),
            "positive_keywords": positive_hits,
            "risk_keywords": risk_hits,
            "policy_keywords": policy_hits,
            "market_keywords": market_hits,
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
                bucket["evidence"].append(
                    {
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "source_name": item.get("source_name"),
                        "score": item.get("score"),
                        "tags": item.get("tags"),
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
                "market_count": bucket["market_count"],
                "risk_count": bucket["risk_count"],
                "keywords": sorted(set(bucket["keywords"])),
                "evidence": sorted(
                    bucket["evidence"],
                    key=lambda row: float(row.get("score") or 0),
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
    ) -> dict[str, Any]:
        top = sector_signals[:5]
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
        return {
            "id": row.get("id"),
            "run_id": row.get("run_id"),
            "source_id": row.get("source_id"),
            "source_name": row.get("source_name"),
            "category": row.get("category"),
            "title": row.get("title"),
            "url": row.get("url"),
            "published_at": row.get("published_at"),
            "summary": row.get("summary"),
            "score": row.get("score"),
            "created_at": row.get("created_at"),
            "matched_sectors": self._json_loads(row.get("matched_sectors_json"), []),
            "tags": self._json_loads(row.get("tags_json"), []),
            "raw": self._json_loads(row.get("raw_json"), {}),
        }

    def _hydrate_sector_signal(self, row: dict[str, Any]) -> dict[str, Any]:
        sector = str(row.get("sector") or "")
        return {
            "id": row.get("id"),
            "run_id": row.get("run_id"),
            "sector": sector,
            "display_name": SECTOR_TAXONOMY.get(sector, {}).get("display_name", sector),
            "heat_score": row.get("heat_score"),
            "item_count": row.get("item_count"),
            "positive_count": row.get("positive_count"),
            "policy_count": row.get("policy_count"),
            "market_count": row.get("market_count"),
            "risk_count": row.get("risk_count"),
            "keywords": self._json_loads(row.get("keywords_json"), []),
            "evidence": self._json_loads(row.get("evidence_json"), []),
            "suggested_action": row.get("suggested_action"),
            "created_at": row.get("created_at"),
        }

    def _suggested_action(self, bucket: dict[str, Any], heat_score: float) -> str:
        risk_count = int(bucket.get("risk_count") or 0)
        positive_count = int(bucket.get("positive_count") or 0)
        policy_count = int(bucket.get("policy_count") or 0)
        item_count = int(bucket.get("item_count") or 0)
        if risk_count > positive_count and risk_count >= 2:
            return "risk_review_only"
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
        return url or title

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
        nav_terms = {"首页", "更多", "登录", "注册", "搜索", "广告", "专题", "视频"}
        return title not in nav_terms

    @staticmethod
    def _extract_date_near(text: str) -> str | None:
        match = re.search(r"20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}", text)
        return match.group(0) if match else None

    @staticmethod
    def _keyword_hits(text: str, keywords: list[str]) -> list[str]:
        lowered = text.lower()
        return [keyword for keyword in keywords if keyword.lower() in lowered]

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
