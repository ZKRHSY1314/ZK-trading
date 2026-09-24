from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
import json
import math
from typing import Any

from app.forecasting.ledger import (
    FORECAST_HORIZONS,
    ForecastDecision,
    ForecastLedger,
    ForecastOutcome,
)
from app.market_intelligence import SectorExposureResolver
from app.forecasting.canonical import (
    CANONICAL_POLICY_VERSION,
    CANONICAL_SELECTION_PREDICATE,
    SELECTION_INFERRED,
    canonical_join,
    canonical_snapshot_cte,
)
from app.storage.sqlite_store import SQLiteStore


_CHINA_TZ = timezone(timedelta(hours=8))
# A daily bar is not final before this local time; used only for the weekday
# maturity proxy below, which is not an exchange calendar.
_DAILY_BAR_FINAL_LOCAL_TIME = time(15, 15)
MATURITY_BASIS = "weekday_proxy_not_exchange_calendar"
_BENCHMARK_PRIORITY = ("SH000300", "SH000001")
_MAX_FORECAST_HORIZON = max(FORECAST_HORIZONS)
_MAX_DAILY_BAR_SYMBOLS_PER_QUERY = 800


@dataclass
class _FeedbackLookupCache:
    """Per-label_due cache; never shared across runs or cutoff timestamps."""

    stock_bars: dict[tuple[str, str, str], list[dict[str, Any]]] = field(default_factory=dict)
    sector_members: dict[tuple[str, str], list[dict[str, Any]]] = field(default_factory=dict)
    sector_bars: dict[
        tuple[tuple[str, ...], str, str],
        dict[str, list[dict[str, Any]]],
    ] = field(default_factory=dict)
    aligned_windows: dict[
        tuple[str, str, str],
        dict[str, Any] | None,
    ] = field(default_factory=dict)


def _datetime(value: str | datetime) -> datetime:
    parsed = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )
    if parsed.tzinfo is None:
        raise ValueError("forecast feedback timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _decision_date(value: str | datetime) -> date:
    """Shanghai calendar date of a decision cutoff: the unit of an independent fold."""

    return _datetime(value).astimezone(_CHINA_TZ).date()


def _add_weekdays(day: date, count: int) -> date:
    current = day
    added = 0
    while added < count:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def _is_due(decision_day: date, horizon_days: int, as_of_local: datetime) -> bool:
    """Weekday proxy: entry next session, exit h sessions later, bar final at 15:15.

    Holidays make the real exit later than this proxy, so the proxy can call a
    forecast due that is still pending; it never calls one pending that is due.
    """

    exit_day = _add_weekdays(decision_day, horizon_days)
    today = as_of_local.date()
    return exit_day < today or (
        exit_day == today and as_of_local.time() >= _DAILY_BAR_FINAL_LOCAL_TIME
    )


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 8)


def _roll_up_status(statuses) -> str:
    """degraded > ready > insufficient_data.

    A container is only as trustworthy as its weakest included child: if any
    child rests on inferred evidence the whole result is degraded, and reporting
    "ready" because some other child happened to qualify would hide exactly the
    thing the caller needs to see.
    """

    seen = {str(status) for status in statuses}
    if "degraded" in seen:
        return "degraded"
    if "ready" in seen:
        return "ready"
    return "insufficient_data"


def _roll_up_evidence(qualities) -> str:
    """exploratory wins: one inferred child taints the aggregate."""

    return (
        "exploratory"
        if any(str(quality) == "exploratory" for quality in qualities)
        else "official"
    )


class ForecastFeedback:
    """Mature stock and sector forecasts and evaluate immutable decisions."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.store.init()
        self.ledger = ForecastLedger(store)
        self.sector_exposure = SectorExposureResolver(store)

    def label_due(
        self,
        as_of: str | datetime,
        *,
        limit: int = 1000,
        include_inferred: bool = False,
    ) -> dict[str, Any]:
        """Persist matured outcomes for canonical, guard-confirmed snapshots.

        This WRITES, so its default is the strict one. An orphaned snapshot, a
        duplicate, or one whose claim is still open must never receive an
        official outcome label - once written, those rows look exactly like real
        evidence. include_inferred=True is for exploratory backfill of legacy
        vintages that predate the guard.
        """

        cutoff = _datetime(as_of)
        normalized_cutoff = cutoff.isoformat().replace("+00:00", "Z")
        safe_limit = max(1, min(int(limit), 10_000))
        scan_limit = min(10_000, max(100, safe_limit * 10))
        by_scope: dict[str, dict[str, Any]] = {
            scope: {
                "eligible_count": 0,
                "scanned_count": 0,
                "labelled": [],
                "pending": [],
            }
            for scope in ("stock", "sector")
        }
        lookup = _FeedbackLookupCache()
        # A sector backlog does not consume the stock budget.  Within each
        # scope, scan beyond the write limit and persist mature labels first so
        # an old permanently-unready row cannot starve later usable forecasts.
        for scope, scope_result in by_scope.items():
            rows, backlog_count, scan_offset = self._pending_label_rows(
                scope=scope,
                cutoff=normalized_cutoff,
                scan_limit=scan_limit,
                rotation_bucket=int(cutoff.timestamp() // 300),
                include_inferred=include_inferred,
            )
            scope_result["backlog_count"] = backlog_count
            scope_result["scan_offset"] = scan_offset
            scope_result["scanned_count"] = len(rows)
            evaluated = []
            for row in rows:
                forecast = self._forecast(row)
                outcome, reason = self._label(forecast, cutoff, lookup=lookup)
                evaluated.append(
                    (forecast, outcome, reason, str(row["selection_kind"]))
                )
            ready = [item for item in evaluated if item[1] is not None]
            waiting = [item for item in evaluated if item[1] is None]
            selected = ready[:safe_limit]
            selected.extend(waiting[: max(0, safe_limit - len(selected))])
            scope_result["eligible_count"] = len(selected)
            for forecast, outcome, reason, selection_kind in selected:
                if outcome is None:
                    pending_details = reason if isinstance(reason, dict) else {}
                    scope_result["pending"].append(
                        {
                            "decision_id": forecast.decision_id,
                            "subject": forecast.subject,
                            "horizon_days": forecast.horizon_days,
                            "selection_kind": selection_kind,
                            "reason": pending_details.get("reason", reason),
                            **{
                                key: value
                                for key, value in pending_details.items()
                                if key != "reason"
                            },
                        }
                    )
                    continue
                # Provenance is written INTO the outcome, not just reported.
                # Once persisted an exploratory label is indistinguishable from
                # an official one unless the row itself carries how its snapshot
                # was chosen - and the canonical query cannot answer that later,
                # because a vintage's classification can change as claims land.
                outcome = replace(
                    outcome,
                    evidence={
                        **(outcome.evidence or {}),
                        "canonical_selection_kind": selection_kind,
                        "canonical_policy_version": CANONICAL_POLICY_VERSION,
                    },
                )
                persisted = self.ledger.record_outcome(outcome)
                scope_result["labelled"].append(
                    {
                        "decision_id": persisted.decision_id,
                        "subject": persisted.subject,
                        "horizon_days": persisted.horizon_days,
                        "observed_at": persisted.observed_at,
                        "selection_kind": selection_kind,
                    }
                )
        for scope_result in by_scope.values():
            kinds = [item.get("selection_kind") for item in scope_result["labelled"]]
            scope_result["confirmed_labelled_count"] = sum(
                1 for kind in kinds if kind == "confirmed"
            )
            scope_result["inferred_labelled_count"] = sum(
                1 for kind in kinds if kind == "inferred"
            )
            scope_result["evidence_quality"] = (
                "exploratory" if scope_result["inferred_labelled_count"] else "official"
            )
            scope_result["labelled_count"] = len(scope_result["labelled"])
            scope_result["pending_count"] = len(scope_result["pending"])
        stock_result = by_scope["stock"]
        return {
            "status": "completed",
            "schema_version": "forecast_feedback_labels.v1",
            "as_of": cutoff.isoformat().replace("+00:00", "Z"),
            # These legacy fields intentionally remain stock-only.  Callers that
            # need both scopes use the additive total_* and by_scope fields.
            "eligible_count": stock_result["eligible_count"],
            "labelled_count": stock_result["labelled_count"],
            "pending_count": stock_result["pending_count"],
            "labelled": stock_result["labelled"],
            "pending": stock_result["pending"],
            "total_eligible_count": sum(result["eligible_count"] for result in by_scope.values()),
            "canonical_policy_version": CANONICAL_POLICY_VERSION,
            "evidence_quality": _roll_up_evidence(
                result.get("evidence_quality") for result in by_scope.values()
            ),
            "confirmed_labelled_count": sum(
                result["confirmed_labelled_count"] for result in by_scope.values()
            ),
            "inferred_labelled_count": sum(
                result["inferred_labelled_count"] for result in by_scope.values()
            ),
            "total_labelled_count": sum(result["labelled_count"] for result in by_scope.values()),
            "total_pending_count": sum(result["pending_count"] for result in by_scope.values()),
            "by_scope": by_scope,
            "horizon_days": sorted(FORECAST_HORIZONS),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _pending_label_rows(
        self,
        *,
        scope: str,
        cutoff: str,
        scan_limit: int,
        rotation_bucket: int,
        include_inferred: bool = False,
    ) -> tuple[list[dict[str, Any]], int, int]:
        # Labelling writes outcomes, so it must not touch duplicate, orphaned or
        # still-open snapshots. Without the canonical join it scanned raw
        # forecast_decisions: the production ledger has 1,350 unlabelled rows
        # across nine snapshots for a single vintage, so this would have written
        # official outcomes for eight snapshots that are not the day's decision.
        filters = f"""
            FROM forecast_decisions d
            {canonical_join("d")}
            LEFT JOIN forecast_outcomes o
              ON o.decision_id = d.decision_id
             AND o.scope = d.scope
             AND o.subject = d.subject
             AND o.horizon_days = d.horizon_days
            WHERE d.scope = ?
              AND d.review_only = 1
              AND o.id IS NULL
              AND d.decision_cutoff <= ?
              AND d.available_at <= ?
              AND {CANONICAL_SELECTION_PREDICATE}
        """
        inferred_flag = 1 if include_inferred else 0
        count_row = self.store.fetch_one(
            f"WITH {canonical_snapshot_cte()} SELECT COUNT(*) AS count {filters}",
            (scope, cutoff, cutoff, inferred_flag),
        )
        backlog_count = int((count_row or {}).get("count") or 0)
        if backlog_count == 0:
            return [], 0, 0
        offset = (rotation_bucket * scan_limit) % backlog_count
        order = """
            ORDER BY d.decision_cutoff, d.decision_id,
                     d.rank IS NULL, d.rank, d.subject, d.id
        """

        def fetch(*, limit: int, query_offset: int) -> list[dict[str, Any]]:
            return self.store.fetch_all(
                f"WITH {canonical_snapshot_cte()} "
                f"SELECT d.*, cs.selection_kind {filters} {order} LIMIT ? OFFSET ?",
                (scope, cutoff, cutoff, inferred_flag, limit, query_offset),
            )

        rows = fetch(limit=scan_limit, query_offset=offset)
        wrap_limit = min(offset, max(0, scan_limit - len(rows)))
        if wrap_limit:
            rows.extend(fetch(limit=wrap_limit, query_offset=0))
        return rows, backlog_count, offset

    def evaluate(
        self,
        as_of: str | datetime,
        *,
        k: int = 5,
        min_samples: int = 20,
        min_folds: int = 3,
        include_inferred: bool = False,
    ) -> dict[str, Any]:
        """Evaluate forecast quality over canonical snapshots only.

        include_inferred is False by default and that default is the point. An
        `inferred` snapshot is one with no guard record, chosen by shape alone -
        if a single upstream failure truncated every snapshot of a vintage, the
        largest is still incomplete while looking complete beside its siblings.
        The production ledger is currently 1 confirmed against 29 inferred, so
        pooling them silently would let weak evidence dominate every number.

        Turning it on marks the whole evaluation `exploratory`; it never
        produces an official metric.
        """

        cutoff = _datetime(as_of)
        safe_k = max(1, min(int(k), 100))
        safe_min_samples = max(1, int(min_samples))
        safe_min_folds = max(1, int(min_folds))
        by_scope: dict[str, dict[str, Any]] = {}
        for scope in ("stock", "sector"):
            scope_horizons = [
                self._evaluate_horizon(
                    cutoff,
                    horizon,
                    scope=scope,
                    k=safe_k,
                    min_samples=safe_min_samples,
                    min_folds=safe_min_folds,
                    include_inferred=include_inferred,
                )
                for horizon in sorted(FORECAST_HORIZONS)
            ]
            by_scope[scope] = {
                # degraded outranks ready, which outranks insufficient_data. A
                # scope holding even one exploratory child is not a finished
                # result, and previously the roll-up only recognised "ready" so
                # a degraded child silently disappeared into the aggregate.
                "status": _roll_up_status(row["status"] for row in scope_horizons),
                "evidence_quality": _roll_up_evidence(
                    row.get("evidence_quality") for row in scope_horizons
                ),
                "target": self._evaluation_target(scope),
                "horizons": scope_horizons,
            }
        # Preserve the original stock-facing surface while adding independently
        # aggregated sector metrics under by_scope.
        horizons = by_scope["stock"]["horizons"]
        return {
            "status": _roll_up_status(result["status"] for result in by_scope.values()),
            "evidence_quality": _roll_up_evidence(
                result.get("evidence_quality") for result in by_scope.values()
            ),
            "canonical_policy_version": CANONICAL_POLICY_VERSION,
            "schema_version": "forecast_feedback_evaluation.v1",
            "as_of": cutoff.isoformat().replace("+00:00", "Z"),
            "horizon_days": sorted(FORECAST_HORIZONS),
            "k": safe_k,
            "target": "benchmark_neutral_return>0",
            "horizons": horizons,
            "by_scope": by_scope,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _label(
        self,
        forecast: ForecastDecision,
        as_of: datetime,
        *,
        lookup: _FeedbackLookupCache,
    ) -> tuple[ForecastOutcome | None, str | dict[str, Any] | None]:
        if forecast.scope == "sector":
            return self._label_sector(forecast, as_of, lookup=lookup)
        if forecast.scope != "stock":
            return None, "unsupported_feedback_scope"
        return self._label_stock(forecast, as_of, lookup=lookup)

    def _label_stock(
        self,
        forecast: ForecastDecision,
        as_of: datetime,
        *,
        lookup: _FeedbackLookupCache,
    ) -> tuple[ForecastOutcome | None, str | None]:
        decision_date = _datetime(forecast.decision_cutoff).astimezone(_CHINA_TZ).date().isoformat()
        as_of_date = as_of.astimezone(_CHINA_TZ).date().isoformat()
        stock_rows = self._cached_bars_after(
            forecast.subject,
            decision_date=decision_date,
            as_of_date=as_of_date,
            limit=forecast.horizon_days,
            lookup=lookup,
        )
        if len(stock_rows) < forecast.horizon_days:
            return None, "stock_horizon_not_matured"
        entry = stock_rows[0]
        exit_row = stock_rows[forecast.horizon_days - 1]
        observed_at = datetime.combine(
            datetime.fromisoformat(str(exit_row["trade_date"])).date(),
            time(hour=15),
            tzinfo=_CHINA_TZ,
        ).astimezone(timezone.utc)
        if observed_at > as_of:
            return None, "stock_horizon_not_matured"

        benchmark = None
        benchmark_symbol = None
        for symbol in _BENCHMARK_PRIORITY:
            window = self._cached_aligned_window(
                symbol,
                entry_date=str(entry["trade_date"]),
                exit_date=str(exit_row["trade_date"]),
                lookup=lookup,
            )
            if window is not None:
                benchmark_symbol = symbol
                benchmark = window
                break
        if benchmark is None or benchmark_symbol is None:
            return None, "benchmark_window_missing"

        continuous_return = self._return(float(entry["open"]), float(exit_row["close"]))
        benchmark_return = self._return(benchmark["entry_price"], benchmark["exit_price"])
        sector_symbol = self._sector_benchmark_symbol(forecast.features)
        sector_window = (
            self._cached_aligned_window(
                sector_symbol,
                entry_date=str(entry["trade_date"]),
                exit_date=str(exit_row["trade_date"]),
                lookup=lookup,
            )
            if sector_symbol
            else None
        )
        if sector_window is None:
            sector_return = benchmark_return
            sector_return_source = "benchmark_proxy"
            sector_return_is_proxy = True
            sector_evidence: dict[str, Any] = {
                "sector_return_semantics": "benchmark_proxy_not_observed_industry_return",
                "sector_proxy_symbol": benchmark_symbol,
                "sector_proxy_reason": (
                    "industry_benchmark_window_unavailable"
                    if sector_symbol
                    else "industry_benchmark_not_provided"
                ),
            }
        else:
            sector_return = self._return(sector_window["entry_price"], sector_window["exit_price"])
            sector_return_source = "industry_benchmark"
            sector_return_is_proxy = False
            sector_evidence = {
                "sector_return_semantics": "observed_industry_benchmark_return",
                "sector_benchmark_symbol": sector_symbol,
                "sector_entry": sector_window["entry"],
                "sector_exit": sector_window["exit"],
            }

        evidence = {
            "label_policy": "next_session_open_to_hth_session_close",
            "decision_cutoff": forecast.decision_cutoff,
            "horizon_days": forecast.horizon_days,
            "entry": {
                "trade_date": str(entry["trade_date"]),
                "price_field": "open",
                "price": float(entry["open"]),
            },
            "exit": {
                "trade_date": str(exit_row["trade_date"]),
                "price_field": "close",
                "price": float(exit_row["close"]),
            },
            "stock_source": str(entry["source"]),
            "benchmark_symbol": benchmark_symbol,
            "benchmark_entry": benchmark["entry"],
            "benchmark_exit": benchmark["exit"],
            "benchmark_return_source": "market_index",
            "sector_return_source": sector_return_source,
            "sector_return_is_proxy": sector_return_is_proxy,
            **sector_evidence,
        }
        outcome = ForecastOutcome(
            decision_id=forecast.decision_id,
            scope="stock",
            subject=forecast.subject,
            horizon_days=forecast.horizon_days,
            observed_at=observed_at,
            continuous_return=continuous_return,
            benchmark_return=benchmark_return,
            sector_return=sector_return,
            data_version=(
                f"daily_bar_cache:{exit_row['trade_date']}:{entry['source']}:{benchmark['source']}"
            ),
            evidence=evidence,
            review_only=True,
        )
        return outcome, None

    def _label_sector(
        self,
        forecast: ForecastDecision,
        as_of: datetime,
        *,
        lookup: _FeedbackLookupCache,
    ) -> tuple[ForecastOutcome | None, str | dict[str, Any] | None]:
        decision_cutoff = _datetime(forecast.decision_cutoff)
        decision_date = decision_cutoff.astimezone(_CHINA_TZ).date().isoformat()
        as_of_date = as_of.astimezone(_CHINA_TZ).date().isoformat()
        memberships = self._cached_sector_members(
            forecast.subject,
            decision_cutoff=decision_cutoff,
            decision_date=decision_date,
            lookup=lookup,
        )
        required_complete_members = max(2, min(5, len(memberships)))
        minimum_coverage = 0.6
        if len(memberships) < 2:
            return None, self._sector_pending(
                "sector_point_in_time_members_below_2",
                eligible_count=len(memberships),
                complete_count=0,
                required_count=required_complete_members,
                minimum_coverage=minimum_coverage,
            )

        bars_by_symbol = self._cached_sector_bars_after(
            [str(membership["symbol"]) for membership in memberships],
            decision_date=decision_date,
            as_of_date=as_of_date,
            lookup=lookup,
        )
        stock_windows: list[dict[str, Any]] = []
        for membership in memberships:
            symbol = str(membership["symbol"]).strip().upper()
            bars = bars_by_symbol.get(symbol, [])[: forecast.horizon_days]
            if len(bars) < forecast.horizon_days:
                continue
            entry = bars[0]
            exit_row = bars[forecast.horizon_days - 1]
            observed_at = self._session_close(str(exit_row["trade_date"]))
            if observed_at > as_of:
                continue
            stock_windows.append(
                {
                    "membership": membership,
                    "entry": entry,
                    "exit": exit_row,
                    "observed_at": observed_at,
                    "continuous_return": self._return(
                        float(entry["open"]),
                        float(exit_row["close"]),
                    ),
                }
            )
        stock_coverage = len(stock_windows) / len(memberships)
        if len(stock_windows) < required_complete_members:
            reason = (
                "sector_complete_members_below_2"
                if required_complete_members == 2
                else "sector_complete_members_below_required"
            )
            return None, self._sector_pending(
                reason,
                eligible_count=len(memberships),
                complete_count=len(stock_windows),
                required_count=required_complete_members,
                minimum_coverage=minimum_coverage,
            )
        if stock_coverage < minimum_coverage:
            return None, self._sector_pending(
                "sector_member_coverage_below_threshold",
                eligible_count=len(memberships),
                complete_count=len(stock_windows),
                required_count=required_complete_members,
                minimum_coverage=minimum_coverage,
            )

        benchmark_symbol = None
        complete_members: list[dict[str, Any]] = []
        best_benchmark_symbol = None
        best_aligned_members: list[dict[str, Any]] = []
        for symbol in _BENCHMARK_PRIORITY:
            aligned_members = []
            for member in stock_windows:
                benchmark = self._cached_aligned_window(
                    symbol,
                    entry_date=str(member["entry"]["trade_date"]),
                    exit_date=str(member["exit"]["trade_date"]),
                    lookup=lookup,
                )
                if benchmark is None:
                    continue
                aligned_members.append(
                    {
                        **member,
                        "benchmark": benchmark,
                        "benchmark_return": self._return(
                            benchmark["entry_price"],
                            benchmark["exit_price"],
                        ),
                    }
                )
            if len(aligned_members) > len(best_aligned_members):
                best_benchmark_symbol = symbol
                best_aligned_members = aligned_members
            aligned_coverage = len(aligned_members) / len(memberships)
            if (
                len(aligned_members) >= required_complete_members
                and aligned_coverage >= minimum_coverage
            ):
                benchmark_symbol = symbol
                complete_members = aligned_members
                break
        if benchmark_symbol is None:
            return None, {
                **self._sector_pending(
                    "sector_benchmark_coverage_below_threshold",
                    eligible_count=len(memberships),
                    complete_count=len(best_aligned_members),
                    required_count=required_complete_members,
                    minimum_coverage=minimum_coverage,
                ),
                "benchmark_symbol": best_benchmark_symbol,
            }

        continuous_return = sum(
            float(member["continuous_return"]) for member in complete_members
        ) / len(complete_members)
        benchmark_return = sum(
            float(member["benchmark_return"]) for member in complete_members
        ) / len(complete_members)
        observed_at = max(member["observed_at"] for member in complete_members)
        member_evidence = [
            {
                "symbol": str(member["membership"]["symbol"]),
                "membership": {
                    "effective_from": member["membership"]["effective_from"],
                    "effective_to": member["membership"]["effective_to"],
                    "available_at": member["membership"]["available_at"],
                    "source": member["membership"]["source"],
                    "confidence": float(member["membership"]["confidence"]),
                    "membership_mode": member["membership"].get(
                        "membership_mode", "legacy_interval"
                    ),
                    "snapshot_id": member["membership"].get("snapshot_id"),
                    "member_hash": member["membership"].get("member_hash"),
                },
                "entry": {
                    "trade_date": str(member["entry"]["trade_date"]),
                    "price_field": "open",
                    "price": float(member["entry"]["open"]),
                },
                "exit": {
                    "trade_date": str(member["exit"]["trade_date"]),
                    "price_field": "close",
                    "price": float(member["exit"]["close"]),
                },
                "continuous_return": float(member["continuous_return"]),
                "benchmark_return": float(member["benchmark_return"]),
                "benchmark_entry": member["benchmark"]["entry"],
                "benchmark_exit": member["benchmark"]["exit"],
                "stock_source": str(member["entry"]["source"]),
                "benchmark_source": str(member["benchmark"]["source"]),
            }
            for member in complete_members
        ]
        evidence = {
            "label_policy": "sector_members_next_session_open_to_hth_session_close",
            "decision_cutoff": forecast.decision_cutoff,
            "decision_date": decision_date,
            "horizon_days": forecast.horizon_days,
            "membership_source": "sector_exposure_resolver",
            "membership_point_in_time_policy": (
                "legacy intervals union latest immutable snapshot per source and sector; "
                "available_at_or_observed_at<=decision_cutoff; effective_on_decision_date"
            ),
            "aggregation": "equal_weight_complete_members",
            "benchmark_aggregation": "equal_weight_member_aligned_windows",
            "minimum_complete_members": required_complete_members,
            "minimum_coverage": minimum_coverage,
            "eligible_member_count": len(memberships),
            "complete_member_count": len(complete_members),
            "coverage": len(complete_members) / len(memberships),
            "benchmark_symbol": benchmark_symbol,
            "benchmark_return_source": "market_index_same_member_windows",
            "sector_return_semantics": "observed_equal_weight_member_return",
            "forecast_direction": str(forecast.features.get("direction") or "neutral"),
            "probability_semantics": forecast.features.get("probability_semantics"),
            "probability_horizon_days": forecast.features.get("probability_horizon_days"),
            "members": member_evidence,
        }
        latest_exit_date = max(str(member["exit"]["trade_date"]) for member in complete_members)
        outcome = ForecastOutcome(
            decision_id=forecast.decision_id,
            scope="sector",
            subject=forecast.subject,
            horizon_days=forecast.horizon_days,
            observed_at=observed_at,
            continuous_return=continuous_return,
            benchmark_return=benchmark_return,
            sector_return=continuous_return,
            data_version=(
                "daily_bar_cache:sector_equal_weight:"
                f"{latest_exit_date}:{benchmark_symbol}:{len(complete_members)}"
            ),
            evidence=evidence,
            review_only=True,
        )
        return outcome, None

    @staticmethod
    def _sector_pending(
        reason: str,
        *,
        eligible_count: int,
        complete_count: int,
        required_count: int,
        minimum_coverage: float,
    ) -> dict[str, Any]:
        coverage = complete_count / eligible_count if eligible_count else 0.0
        return {
            "reason": reason,
            "eligible_member_count": eligible_count,
            "complete_member_count": complete_count,
            "required_complete_member_count": required_count,
            "coverage": coverage,
            "minimum_coverage": minimum_coverage,
        }

    def _sector_members(
        self,
        sector: str,
        *,
        decision_cutoff: datetime,
        decision_date: str,
    ) -> list[dict[str, Any]]:
        rows = self.sector_exposure.symbols_for(sector, as_of=decision_cutoff)
        # Multiple providers can describe the same company.  The outcome basket
        # is company-equal-weighted, so select the strongest point-in-time row.
        unique: dict[str, dict[str, Any]] = {}
        for row in rows:
            unique.setdefault(str(row["symbol"]), row)
        return list(unique.values())

    def _cached_sector_members(
        self,
        sector: str,
        *,
        decision_cutoff: datetime,
        decision_date: str,
        lookup: _FeedbackLookupCache,
    ) -> list[dict[str, Any]]:
        key = (sector, decision_cutoff.isoformat())
        if key not in lookup.sector_members:
            lookup.sector_members[key] = self._sector_members(
                sector,
                decision_cutoff=decision_cutoff,
                decision_date=decision_date,
            )
        return lookup.sector_members[key]

    def _cached_bars_after(
        self,
        symbol: str,
        *,
        decision_date: str,
        as_of_date: str,
        limit: int,
        lookup: _FeedbackLookupCache,
    ) -> list[dict[str, Any]]:
        key = (symbol.strip().upper(), decision_date, as_of_date)
        if key not in lookup.stock_bars:
            lookup.stock_bars[key] = self._bars_after(
                key[0],
                decision_date=decision_date,
                as_of_date=as_of_date,
                limit=_MAX_FORECAST_HORIZON,
            )
        return lookup.stock_bars[key][:limit]

    def _cached_sector_bars_after(
        self,
        symbols: list[str],
        *,
        decision_date: str,
        as_of_date: str,
        lookup: _FeedbackLookupCache,
    ) -> dict[str, list[dict[str, Any]]]:
        normalized = tuple(sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()}))
        key = (normalized, decision_date, as_of_date)
        if key not in lookup.sector_bars:
            lookup.sector_bars[key] = self._bars_after_many(
                list(normalized),
                decision_date=decision_date,
                as_of_date=as_of_date,
                limit=_MAX_FORECAST_HORIZON,
            )
        return lookup.sector_bars[key]

    def _bars_after_many(
        self,
        symbols: list[str],
        *,
        decision_date: str,
        as_of_date: str,
        limit: int,
    ) -> dict[str, list[dict[str, Any]]]:
        """Load each member's next sessions in bounded, index-friendly batches."""

        normalized = sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()})
        result = {symbol: [] for symbol in normalized}
        safe_limit = max(1, min(int(limit), _MAX_FORECAST_HORIZON))
        for offset in range(0, len(normalized), _MAX_DAILY_BAR_SYMBOLS_PER_QUERY):
            chunk = normalized[offset : offset + _MAX_DAILY_BAR_SYMBOLS_PER_QUERY]
            placeholders = ",".join("?" for _ in chunk)
            rows = self.store.fetch_all(
                f"""
                WITH ranked AS (
                    SELECT symbol, trade_date, open, close, source,
                           ROW_NUMBER() OVER (
                               PARTITION BY symbol
                               ORDER BY trade_date ASC
                           ) AS session_rank
                    FROM daily_bar_cache
                    WHERE symbol IN ({placeholders})
                      AND trade_date > ?
                      AND trade_date <= ?
                      AND quality_status = 'ready'
                      AND open IS NOT NULL AND open > 0
                      AND close IS NOT NULL AND close > 0
                )
                SELECT symbol, trade_date, open, close, source
                FROM ranked
                WHERE session_rank <= ?
                ORDER BY symbol ASC, trade_date ASC
                """,
                (*chunk, decision_date, as_of_date, safe_limit),
            )
            for row in rows:
                symbol = str(row.get("symbol") or "").strip().upper()
                if symbol in result:
                    result[symbol].append(row)
        return result

    def _cached_aligned_window(
        self,
        symbol: str,
        *,
        entry_date: str,
        exit_date: str,
        lookup: _FeedbackLookupCache,
    ) -> dict[str, Any] | None:
        key = (symbol.strip().upper(), entry_date, exit_date)
        if key not in lookup.aligned_windows:
            lookup.aligned_windows[key] = self._aligned_window(
                key[0],
                entry_date=entry_date,
                exit_date=exit_date,
            )
        return lookup.aligned_windows[key]

    @staticmethod
    def _session_close(trade_date: str) -> datetime:
        return datetime.combine(
            datetime.fromisoformat(trade_date).date(),
            time(hour=15),
            tzinfo=_CHINA_TZ,
        ).astimezone(timezone.utc)

    def _bars_after(
        self,
        symbol: str,
        *,
        decision_date: str,
        as_of_date: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        return self.store.fetch_all(
            """
            SELECT symbol, trade_date, open, close, source
            FROM daily_bar_cache
            WHERE upper(symbol) = upper(?)
              AND trade_date > ?
              AND trade_date <= ?
              AND quality_status = 'ready'
              AND open IS NOT NULL AND open > 0
              AND close IS NOT NULL AND close > 0
            ORDER BY trade_date ASC
            LIMIT ?
            """,
            (symbol, decision_date, as_of_date, int(limit)),
        )

    def _aligned_window(
        self,
        symbol: str,
        *,
        entry_date: str,
        exit_date: str,
    ) -> dict[str, Any] | None:
        rows = self.store.fetch_all(
            """
            SELECT symbol, trade_date, open, close, source
            FROM daily_bar_cache
            WHERE upper(symbol) = upper(?)
              AND trade_date IN (?, ?)
              AND quality_status = 'ready'
              AND open IS NOT NULL AND open > 0
              AND close IS NOT NULL AND close > 0
            ORDER BY trade_date ASC
            """,
            (symbol, entry_date, exit_date),
        )
        by_date = {str(row["trade_date"]): row for row in rows}
        if entry_date not in by_date or exit_date not in by_date:
            return None
        entry = by_date[entry_date]
        exit_row = by_date[exit_date]
        return {
            "entry_price": float(entry["open"]),
            "exit_price": float(exit_row["close"]),
            "entry": {
                "trade_date": entry_date,
                "price_field": "open",
                "price": float(entry["open"]),
            },
            "exit": {
                "trade_date": exit_date,
                "price_field": "close",
                "price": float(exit_row["close"]),
            },
            "source": str(exit_row["source"]),
        }

    def _evaluate_horizon(
        self,
        as_of: datetime,
        horizon_days: int,
        *,
        scope: str,
        k: int,
        min_samples: int,
        min_folds: int,
        include_inferred: bool = False,
    ) -> dict[str, Any]:
        cutoff = as_of.isoformat().replace("+00:00", "Z")
        # Each decision_id below becomes a fold, so a re-recorded snapshot does
        # not just inflate the sample - it inflates the fold count, which is
        # exactly what makes a Rank IC look statistically stable. Six trading
        # days of decisions were being reported as 121 folds because a
        # 15-minute loop re-froze the same candidates all day.
        #
        # One whole snapshot per vintage survives, not one row per subject: a
        # snapshot is a ranked list decided at one instant, and mixing rows from
        # different snapshots would build a ranking that was never decided.
        # Which snapshot is canonical is decided by app.forecasting.canonical,
        # shared with the ledger and calibration so the three cannot disagree.
        # The duplicates stay on disk as the audit trail and are excluded on read.
        rows = self.store.fetch_all(
            f"""
            WITH {canonical_snapshot_cte()}
            SELECT
                d.decision_id, d.subject, d.rank, d.score, d.probability,
                d.features_json, d.decision_cutoff,
                cs.selection_kind,
                o.id AS outcome_id,
                o.continuous_return,
                o.benchmark_neutral_return,
                o.observed_at
            FROM forecast_decisions d
            {canonical_join("d")}
            LEFT JOIN forecast_outcomes o
              ON o.decision_id = d.decision_id
             AND o.scope = d.scope
             AND o.subject = d.subject
             AND o.horizon_days = d.horizon_days
             AND o.observed_at <= ?
            WHERE d.scope = ?
              AND d.review_only = 1
              AND d.horizon_days = ?
              AND d.decision_cutoff <= ?
              AND d.available_at <= ?
              AND {CANONICAL_SELECTION_PREDICATE}
            ORDER BY d.decision_id, d.rank IS NULL, d.rank, d.subject
            """,
            (cutoff, scope, horizon_days, cutoff, cutoff, 1 if include_inferred else 0),
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row["decision_id"])].append(row)

        by_decision: list[dict[str, Any]] = []
        all_matured: list[dict[str, Any]] = []
        for decision_id, fold_rows in sorted(grouped.items()):
            matured = [row for row in fold_rows if row.get("outcome_id") is not None]
            all_matured.extend(matured)
            metric_forecasts = [row for row in fold_rows if self._metric_eligible(row, scope=scope)]
            metric_matured = [row for row in matured if self._metric_eligible(row, scope=scope)]
            top = metric_forecasts[:k]
            precision = None
            if len(top) == k and all(row.get("outcome_id") is not None for row in top):
                precision = (
                    sum(1 for row in top if float(self._evaluation_return(row, scope=scope)) > 0)
                    / k
                )
            predictor_actual = [
                (self._rank_predictor(row), self._evaluation_return(row, scope=scope))
                for row in metric_matured
                if self._rank_predictor(row) is not None
            ]
            rank_ic = (
                self._spearman(
                    [pair[0] for pair in predictor_actual],
                    [pair[1] for pair in predictor_actual],
                )
                if len(predictor_actual) >= 2
                else None
            )
            probability_pairs = [
                pair
                for row in metric_matured
                if (pair := self._probability_target(row, scope=scope, horizon_days=horizon_days))
                is not None
            ]
            provided_probability_count = sum(
                1 for row in metric_matured if row.get("probability") is not None
            )
            uncalibrated_probability_count = provided_probability_count - len(probability_pairs)
            brier = self._brier(probability_pairs)
            by_decision.append(
                {
                    "decision_id": decision_id,
                    "decision_date": min(
                        _decision_date(row["decision_cutoff"]) for row in fold_rows
                    ).isoformat(),
                    "forecast_count": len(fold_rows),
                    "sample_count": len(matured),
                    "coverage": _round(len(matured) / len(fold_rows)) if fold_rows else 0.0,
                    "directional_forecast_count": len(metric_forecasts),
                    "directional_sample_count": len(metric_matured),
                    "directional_coverage": (
                        _round(len(metric_matured) / len(metric_forecasts))
                        if metric_forecasts
                        else 0.0
                    ),
                    "precision_at_k": _round(precision),
                    "spearman_rank_ic": _round(rank_ic),
                    "brier_score": _round(brier),
                    "probability_sample_count": len(probability_pairs),
                    "uncalibrated_probability_count": uncalibrated_probability_count,
                    "probability_calibration_status": self._probability_status(
                        len(probability_pairs),
                        uncalibrated_probability_count,
                    ),
                }
            )

        # Independent folds are decision DATES, not snapshots. Canonical
        # selection keeps one snapshot per bar vintage, but two vintages can
        # still be decided on the same day; counting them twice would inflate
        # the fold count exactly as the old repeated snapshots did. Within a
        # date the snapshot metrics are averaged first, so each date weighs once.
        folds_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for fold in by_decision:
            folds_by_date[fold["decision_date"]].append(fold)
        precision_values = []
        rank_ic_values = []
        for date_folds in folds_by_date.values():
            date_precisions = [
                float(fold["precision_at_k"])
                for fold in date_folds
                if fold["precision_at_k"] is not None
            ]
            date_rank_ics = [
                float(fold["spearman_rank_ic"])
                for fold in date_folds
                if fold["spearman_rank_ic"] is not None
            ]
            if date_precisions:
                precision_values.append(sum(date_precisions) / len(date_precisions))
            if date_rank_ics:
                rank_ic_values.append(sum(date_rank_ics) / len(date_rank_ics))
        all_metric_matured = [row for row in all_matured if self._metric_eligible(row, scope=scope)]
        probability_pairs = [
            pair
            for row in all_metric_matured
            if (pair := self._probability_target(row, scope=scope, horizon_days=horizon_days))
            is not None
        ]
        provided_probability_count = sum(
            1 for row in all_metric_matured if row.get("probability") is not None
        )
        uncalibrated_probability_count = provided_probability_count - len(probability_pairs)
        sample_count = len(all_matured)
        forecast_count = len(rows)
        directional_forecast_count = sum(
            1 for row in rows if self._metric_eligible(row, scope=scope)
        )
        directional_sample_count = len(all_metric_matured)
        fold_count = sum(
            1
            for date_folds in folds_by_date.values()
            if any(fold["directional_sample_count"] > 0 for fold in date_folds)
        )
        # Maturity: a forecast that is not yet due is pending, not missing. The
        # legacy `coverage` keeps its all-forecasts denominator; `coverage_of_due`
        # only counts forecasts whose exit session should have closed by as_of.
        as_of_local = as_of.astimezone(_CHINA_TZ)
        metric_rows = [row for row in rows if self._metric_eligible(row, scope=scope)]
        due_rows = [
            row
            for row in metric_rows
            if _is_due(_decision_date(row["decision_cutoff"]), horizon_days, as_of_local)
        ]
        due_count = len(due_rows)
        matured_due_count = sum(1 for row in due_rows if row.get("outcome_id") is not None)
        matured_not_due_count = directional_sample_count - matured_due_count
        excluded_inferred_snapshot_count = (
            0
            if include_inferred
            else self._inferred_snapshot_count(
                scope=scope, horizon_days=horizon_days, cutoff=cutoff
            )
        )
        precision_at_k = sum(precision_values) / len(precision_values) if precision_values else None
        spearman_rank_ic = sum(rank_ic_values) / len(rank_ic_values) if rank_ic_values else None
        brier_score = self._brier(probability_pairs)
        insufficient_reasons = []
        if directional_sample_count < min_samples:
            reason_prefix = "directional_sample_count" if scope == "sector" else "sample_count"
            insufficient_reasons.append(f"{reason_prefix}_below_{min_samples}")
        if fold_count < min_folds:
            insufficient_reasons.append(f"fold_count_below_{min_folds}")
        if all(metric is None for metric in (precision_at_k, spearman_rank_ic, brier_score)):
            insufficient_reasons.append("no_available_evaluation_metric")
        if metric_rows and due_count == 0:
            insufficient_reasons.append("horizon_not_yet_mature")
        # Evidence provenance travels with the numbers. Without this a caller
        # cannot tell an official metric from one resting on snapshots that were
        # chosen by shape alone, and 29 of the 30 canonical snapshots in the
        # production ledger are of the weaker kind.
        confirmed_folds = sorted(
            {
                str(row["decision_id"])
                for row in rows
                if str(row["selection_kind"]) == "confirmed"
            }
        )
        inferred_folds = sorted(
            {
                str(row["decision_id"])
                for row in rows
                if str(row["selection_kind"]) == "inferred"
            }
        )
        inferred_samples = sum(
            1
            for row in rows
            if str(row["selection_kind"]) == "inferred" and row.get("outcome_id") is not None
        )
        if not include_inferred and not confirmed_folds:
            insufficient_reasons.append("no_confirmed_snapshots")
        evidence_quality = "exploratory" if inferred_folds else "official"
        status = "insufficient_data" if insufficient_reasons else "ready"
        if evidence_quality == "exploratory" and status == "ready":
            # Never let an exploratory run read as a finished result.
            status = "degraded"

        return {
            "status": status,
            "evidence_quality": evidence_quality,
            "canonical_policy_version": CANONICAL_POLICY_VERSION,
            "confirmed_fold_count": len(confirmed_folds),
            "inferred_fold_count": len(inferred_folds),
            "confirmed_sample_count": sample_count - inferred_samples,
            "inferred_sample_count": inferred_samples,
            "scope": scope,
            "horizon_days": horizon_days,
            "target": self._evaluation_target(scope),
            "aggregation": "unweighted_mean_across_decision_dates",
            "fold_unit": "decision_date",
            "canonical_snapshot_count": len(by_decision),
            "repeated_snapshot_date_count": sum(
                1 for date_folds in folds_by_date.values() if len(date_folds) > 1
            ),
            "excluded_inferred_snapshot_count": excluded_inferred_snapshot_count,
            "rank_predictor": "negative_rank_then_score",
            "k": k,
            "forecast_count": forecast_count,
            "sample_count": sample_count,
            "fold_count": fold_count,
            "coverage": _round(sample_count / forecast_count) if forecast_count else 0.0,
            "coverage_denominator": "all_canonical_forecasts_including_immature",
            "maturity_basis": MATURITY_BASIS,
            "due_count": due_count,
            "matured_due_count": matured_due_count,
            "matured_not_due_count": matured_not_due_count,
            "pending_count": directional_forecast_count - directional_sample_count,
            # None, not 0.0, when nothing is due yet: absent evidence is not a gap.
            "coverage_of_due": _round(matured_due_count / due_count) if due_count else None,
            "directional_forecast_count": directional_forecast_count,
            "directional_sample_count": directional_sample_count,
            "directional_coverage": (
                _round(directional_sample_count / directional_forecast_count)
                if directional_forecast_count
                else 0.0
            ),
            "precision_at_k": _round(precision_at_k),
            "precision_fold_count": len(precision_values),
            "spearman_rank_ic": _round(spearman_rank_ic),
            "rank_ic_fold_count": len(rank_ic_values),
            "brier_score": _round(brier_score),
            "probability_sample_count": len(probability_pairs),
            "uncalibrated_probability_count": uncalibrated_probability_count,
            "probability_calibration_status": self._probability_status(
                len(probability_pairs),
                uncalibrated_probability_count,
            ),
            "probability_semantics": (
                "directional_thesis_success" if scope == "sector" else "benchmark_outperformance"
            ),
            "by_decision": by_decision,
            "insufficient_reasons": insufficient_reasons,
            "review_only": True,
        }

    def _inferred_snapshot_count(self, *, scope: str, horizon_days: int, cutoff: str) -> int:
        """Canonical snapshots left out of official evidence because they are inferred."""

        row = self.store.fetch_one(
            f"""
            WITH {canonical_snapshot_cte()}
            SELECT COUNT(DISTINCT d.decision_id) AS count
            FROM forecast_decisions d
            {canonical_join("d")}
            WHERE d.scope = ?
              AND d.review_only = 1
              AND d.horizon_days = ?
              AND d.decision_cutoff <= ?
              AND d.available_at <= ?
              AND cs.selection_kind = '{SELECTION_INFERRED}'
            """,
            (scope, horizon_days, cutoff, cutoff),
        )
        return int((row or {}).get("count") or 0)

    @staticmethod
    def _forecast(row: dict[str, Any]) -> ForecastDecision:
        return ForecastDecision(
            decision_id=row["decision_id"],
            scope=row["scope"],
            subject=row["subject"],
            decision_cutoff=row["decision_cutoff"],
            available_at=row["available_at"],
            horizon_days=int(row["horizon_days"]),
            rank=row["rank"],
            score=row["score"],
            probability=row["probability"],
            model_version=row["model_version"],
            prompt_version=row["prompt_version"],
            data_version=row["data_version"],
            features=json.loads(row["features_json"]),
            evidence=json.loads(row["evidence_json"]),
            reasons=json.loads(row["reasons_json"]),
            status=row["status"],
            review_only=bool(row["review_only"]),
        )

    @staticmethod
    def _return(entry_price: float, exit_price: float) -> float:
        if entry_price <= 0 or exit_price <= 0:
            raise ValueError("outcome prices must be positive")
        return round(exit_price / entry_price - 1.0, 10)

    @staticmethod
    def _sector_benchmark_symbol(features: dict[str, Any]) -> str | None:
        for key in ("sector_benchmark_symbol", "industry_benchmark_symbol"):
            value = str(features.get(key) or "").strip().upper()
            if value:
                return value
        return None

    @staticmethod
    def _rank_predictor(row: dict[str, Any]) -> float | None:
        if row.get("rank") is not None:
            return -float(row["rank"])
        if row.get("score") is not None:
            return float(row["score"])
        return None

    @staticmethod
    def _evaluation_target(scope: str) -> str:
        if scope == "sector":
            return "direction_signed_benchmark_neutral_return>0"
        return "benchmark_neutral_return>0"

    @staticmethod
    def _features(row: dict[str, Any]) -> dict[str, Any]:
        value = row.get("features_json")
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @classmethod
    def _metric_eligible(cls, row: dict[str, Any], *, scope: str) -> bool:
        if scope != "sector":
            return True
        return str(cls._features(row).get("direction") or "").lower() in {
            "positive",
            "negative",
        }

    @classmethod
    def _evaluation_return(cls, row: dict[str, Any], *, scope: str) -> float:
        value = float(row["benchmark_neutral_return"])
        if scope != "sector":
            return value
        direction = str(cls._features(row).get("direction") or "").lower()
        if direction == "positive":
            return value
        if direction == "negative":
            return -value
        raise ValueError("non-directional sector forecast is not metric eligible")

    @classmethod
    def _probability_target(
        cls,
        row: dict[str, Any],
        *,
        scope: str,
        horizon_days: int,
    ) -> tuple[float, float] | None:
        probability = row.get("probability")
        if probability is None:
            return None
        features = cls._features(row)
        expected_semantics = (
            "directional_thesis_success" if scope == "sector" else "benchmark_outperformance"
        )
        if str(features.get("probability_semantics") or "") != expected_semantics:
            return None
        try:
            configured_horizon = int(features.get("probability_horizon_days"))
        except (TypeError, ValueError):
            return None
        if configured_horizon != horizon_days:
            return None
        actual_return = cls._evaluation_return(row, scope=scope)
        return float(probability), 1.0 if actual_return > 0 else 0.0

    @staticmethod
    def _probability_status(calibrated_count: int, uncalibrated_count: int) -> str:
        if calibrated_count and uncalibrated_count:
            return "partially_calibrated"
        if calibrated_count:
            return "calibrated"
        if uncalibrated_count:
            return "uncalibrated"
        return "unavailable"

    @staticmethod
    def _brier(probability_targets: list[tuple[float, float]]) -> float | None:
        if not probability_targets:
            return None
        return sum(
            (probability - target) ** 2 for probability, target in probability_targets
        ) / len(probability_targets)

    @classmethod
    def _spearman(cls, left: list[float], right: list[float]) -> float | None:
        if len(left) != len(right) or len(left) < 2:
            return None
        return cls._pearson(cls._ranks(left), cls._ranks(right))

    @staticmethod
    def _ranks(values: list[float]) -> list[float]:
        result = [0.0] * len(values)
        ordered = sorted(range(len(values)), key=lambda index: values[index])
        start = 0
        while start < len(ordered):
            end = start + 1
            while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
                end += 1
            average_rank = (start + 1 + end) / 2.0
            for position in range(start, end):
                result[ordered[position]] = average_rank
            start = end
        return result

    @staticmethod
    def _pearson(left: list[float], right: list[float]) -> float | None:
        left_mean = sum(left) / len(left)
        right_mean = sum(right) / len(right)
        numerator = sum(
            (left_value - left_mean) * (right_value - right_mean)
            for left_value, right_value in zip(left, right, strict=True)
        )
        left_variance = sum((value - left_mean) ** 2 for value in left)
        right_variance = sum((value - right_mean) ** 2 for value in right)
        denominator = math.sqrt(left_variance * right_variance)
        if denominator == 0:
            return None
        return numerator / denominator
