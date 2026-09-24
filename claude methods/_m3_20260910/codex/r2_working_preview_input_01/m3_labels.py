"""M3 label policy ``m3.labels`` — pure, cutoff-bound behavioural-proxy labels.

Version ``0.2.0-draft`` (output schema ``m3.labels.output.v2``).  This file
supersedes the ``0.1.0-draft`` version pinned by Codex under
``claude methods/_m3_20260910/codex/review_01_input/`` (module sha256
``6a0590cf…``); the eight review findings R1–R8 of
``M3_01_CODEX_REVIEW_20260910.md`` are addressed here as one contract.

Isolated research namespace for milestone M3 (label specification and reviewed
case library).  It is independent of the legacy label producers
(``observable_structure_v1``, ``main_force_phase_replays`` phases,
``agent_learning_outcomes``).  Nothing here reads SQLite, the network, the
clock, or the ``app`` package.  Every function is deterministic in its inputs.

What the labels mean
--------------------
All phase / selection / trade-state labels are *observable behavioural proxies*
computed from daily OHLCVA up to an explicit decision cutoff on an injected
exchange-session calendar.  They are not evidence of a hidden controlling actor
and they are not trade recommendations.  Outputs always carry
``review_only=True`` and ``live_trading_enabled=False``.

Contract in one paragraph
-------------------------
A decision record is identified by ``episode_id`` = hash of (namespace, policy
hash, symbol, decision date, *decision fingerprint*), where the decision
fingerprint covers every consumed input: stock rows, benchmark rows, security
facts, coverage, calendar, universe, cutoff, prior and position state.  The
label core is hashed as ``record_hash``; reviews live in a separate append-only
ledger bound to ``(episode_id, record_hash, policy_hash)``.  Every consumer
(matching, reviews, episodes, counting) recomputes ``record_hash`` before it
trusts a record.  Later-known outcomes are a separate annotation, never a
cutoff-time label input.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# --------------------------------------------------------------------------- #
# Namespace, version and the written policy (hashed, integrity-checked)       #
# --------------------------------------------------------------------------- #

NAMESPACE = "m3.labels"
POLICY_ID = "m3_label_policy"
POLICY_VERSION = "0.2.0-draft"
OUTPUT_SCHEMA = "m3.labels.output.v2"
SUPERSEDES = {"policy_version": "0.1.0-draft", "module_sha256": "6a0590cf2dd9b7acbc9421c818e558e24d6c2877175c8a903d47dab375a99065",
              "tests_sha256": "efa2e21cb70b70fbd0c39e3e4908a7a24f9837bb45889858979f6a99f09f0ab2",
              "review": "claude methods/M3_01_CODEX_REVIEW_20260910.md"}

SESSION_CLOSE_LOCAL = "15:00:00"
SESSION_TZ = timezone(timedelta(hours=8))
STRICT_CUTOFF_MAX_HOURS_AFTER_CLOSE = 72

MODE_STRICT = "strict"
MODE_RETROSPECTIVE = "retrospective"
CUTOFF_MODES = (MODE_STRICT, MODE_RETROSPECTIVE)

PHASE_ACCUMULATION = "accumulation"
PHASE_MARKUP = "markup"
PHASE_DISTRIBUTION = "distribution"
PHASE_FAILED_MARKUP = "failed_markup"
PHASE_INDETERMINATE = "indeterminate"
PHASES = (PHASE_ACCUMULATION, PHASE_MARKUP, PHASE_DISTRIBUTION, PHASE_FAILED_MARKUP, PHASE_INDETERMINATE)

SELECTION_CANDIDATE = "candidate"
SELECTION_NON_CANDIDATE = "non_candidate"
SELECTION_INDETERMINATE = "indeterminate"

ENTRY_SIGNAL_ELIGIBLE = "signal_eligible"
ENTRY_SIGNAL_NOT_ELIGIBLE = "signal_not_eligible"
ENTRY_INDETERMINATE = "indeterminate"

EVENT_NO_TRADE = "no_trade"
EVENT_HOLD = "hold"
EVENT_INVALIDATION = "invalidation_event"
EVENT_STOP = "stop_event"
EVENT_EXIT = "exit_event"
EVENT_REVIEW_REQUIRED = "review_required"
EVENT_UNKNOWN = "unknown"

REGIME_BULL = "bull"
REGIME_BEAR = "bear"
REGIME_RANGE = "range"
REGIME_UNKNOWN = "unknown"
LIQUIDITY_UNKNOWN = "unknown"

CURRENT_OBSERVED = "observed"
CURRENT_SUSPENDED = "suspended"
CURRENT_MISSING = "missing"

REVIEW_PENDING = "pending_review"
REVIEW_SINGLE = "single_review_not_independent"
REVIEW_INDEPENDENT = "independently_reviewed"
REVIEW_DISPUTED = "disputed"

CA_UNKNOWN = "unknown"
CA_PARTIAL_KNOWN = "partial_known"
CA_COMPLETE_KNOWN = "complete_known"
CA_NONE_VERIFIED = "none_verified"
CA_STATUSES = (CA_UNKNOWN, CA_PARTIAL_KNOWN, CA_COMPLETE_KNOWN, CA_NONE_VERIFIED)
ST_STATUSES = ("unknown", "st", "not_st")

ROLE_STOCK = "stock"
ROLE_BENCHMARK = "benchmark"

SPLIT_DEVELOPMENT = "development"
SPLIT_VALIDATION = "validation"
SPLIT_HOLDOUT = "final_holdout"
SPLIT_OUTSIDE = "outside_research_interval"

# Purposes that may consult the chronological split (R8 allowlist).
PURPOSE_INITIAL_LIBRARY = "initial_library_admission"
PURPOSE_TARGET_COUNT = "target_count"
PURPOSE_RULE_SELECTION = "rule_selection"
PURPOSE_THRESHOLD_SELECTION = "threshold_selection"
PURPOSE_PARAMETER_SEARCH = "parameter_search"
PURPOSE_VALIDATION_CHECK = "validation_readonly_check"
PURPOSE_FINAL_REPORT = "final_report"
PURPOSES = (PURPOSE_INITIAL_LIBRARY, PURPOSE_TARGET_COUNT, PURPOSE_RULE_SELECTION, PURPOSE_THRESHOLD_SELECTION,
            PURPOSE_PARAMETER_SEARCH, PURPOSE_VALIDATION_CHECK, PURPOSE_FINAL_REPORT)
_PURPOSE_ALLOWED_ROLES = {
    PURPOSE_INITIAL_LIBRARY: (SPLIT_DEVELOPMENT,),
    PURPOSE_TARGET_COUNT: (SPLIT_DEVELOPMENT,),
    PURPOSE_RULE_SELECTION: (SPLIT_DEVELOPMENT,),
    PURPOSE_THRESHOLD_SELECTION: (SPLIT_DEVELOPMENT,),
    PURPOSE_PARAMETER_SEARCH: (SPLIT_DEVELOPMENT,),
    PURPOSE_VALIDATION_CHECK: (SPLIT_DEVELOPMENT, SPLIT_VALIDATION),
    PURPOSE_FINAL_REPORT: (SPLIT_DEVELOPMENT, SPLIT_VALIDATION, SPLIT_HOLDOUT, SPLIT_OUTSIDE),
}

# The written policy.  Every number below is a *provisional* rule choice taken
# from an existing, cited hypothesis (LABEL_POLICY.md §4) and is subject to Codex
# review before adoption.  None was tuned against M2 prices.  Thresholds are
# unchanged from 0.1.0-draft except where the review required a correction
# (matching window; calendar-based gates).
_POLICY_SOURCE: dict[str, Any] = {
    "namespace": NAMESPACE,
    "policy_id": POLICY_ID,
    "policy_version": POLICY_VERSION,
    "output_schema": OUTPUT_SCHEMA,
    "status": "draft_pending_codex_review",
    "supersedes": SUPERSEDES,
    "distinct_from_legacy": [
        "app.learning.structure_scoring:observable_structure_v1",
        "app.learning.phase_replay:main_force_phase_replays.phase",
        "app.agent_control.outcome_labeling:agent_learning_outcomes.outcome_label",
        "app.research.offhour:_chronological_signal_split",
    ],
    "input_contract": {
        "observation_kinds": ["price", "full_day_suspension"],
        "required_price_fields": ["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount", "available_at", "source_ref"],
        "required_suspension_fields": ["symbol", "trade_date", "available_at", "source_ref"],
        "symbol_pattern_real": "^(SH|SZ|BJ)[0-9]{6}$",
        "symbol_pattern_synthetic": "^SYN[0-9]{6}$",
        "benchmark_pattern_real": "^(SH000|SZ399)[0-9]{3}$",
        "benchmark_pattern_synthetic": "^SYN9[0-9]{5}$",
        "trade_date_format": "YYYY-MM-DD (exchange session date; must be a session of the injected calendar)",
        "historical_close_time": f"trade_date {SESSION_CLOSE_LOCAL}+08:00",
        "available_at_format": "ISO-8601 datetime with UTC offset; when the observation became readable by the research system",
        "price_unit": "CNY, unadjusted (adjustment_mode='none')",
        "volume_unit": "share",
        "amount_unit": "CNY",
        "adjustment_mode_accepted": ["none"],
        "volume_unit_accepted": ["share"],
        "ordering": "strictly increasing trade_date per symbol; duplicates rejected",
        "numeric_rules": "finite float or int; bool rejected; NaN/inf rejected",
        "price_rules": "0 < low <= min(open, close) <= max(open, close) <= high; volume >= 0; amount >= 0; volume == 0 requires amount == 0",
        "vwap_rule": "amount/volume within [0.98*low, 1.02*high] unless (symbol, trade_date) is a listed scope exception",
        "availability_rule": "available_at must not precede the historical close time of its own trade_date",
        "calendar": "SessionCalendar(sessions, source_ref, available_at, synthetic) is mandatory; fingerprint = sha256(canonical sessions); real requests need a non-synthetic calendar",
        "security_context": "every non-unknown fact needs evidence_refs and facts_available_at; enums/dates/numbers/bools validated; unknown stays unknown",
        "coverage": "None = explicit unknown; otherwise finite float in [0, 1] (bool rejected); real requests need evidence_ref and available_at",
        "universe": "FrozenUniverse(symbols, source_ref, sha256) mandatory for real requests; membership recorded, never inferred",
    },
    "cutoff": {
        "modes": list(CUTOFF_MODES),
        "convention": "as_of is recorded relative to the decision session close as close+<seconds>; a series keeps one convention",
        "usable_strict": "close_time(trade_date) <= as_of AND available_at <= as_of; as_of within 72h after the decision session close",
        "usable_retrospective": "close_time(trade_date) <= as_of; availability violations counted; strict_pit_eligible=false",
        "whole_output_pit": "strict_pit_eligible requires strict mode AND every consumed fact class (stock bars, benchmark bars, security facts, coverage, calendar) declared available at or before as_of",
        "wall_clock": "never used; cutoff must be explicit",
        "training_eligible": "always false in this policy version (no reviewed case library)",
    },
    "windows": {
        "warmup_required_sessions": 250,
        "short": 20, "medium": 60, "long": 120, "position": 250,
        "failed_markup_lookback": 20, "distribution_veto_lookback": 20,
        "dependence_window_sessions": 20,
        "max_stale_sessions": 1, "long_gap_sessions": 10, "max_suspensions_in_window": 10,
        "min_episode_sessions": 3,
        "unit": "exchange sessions from the injected calendar (never calendar days)",
    },
    "phase_rules": {
        "precedence": [PHASE_INDETERMINATE + "(quality gates)", PHASE_DISTRIBUTION, PHASE_MARKUP, PHASE_FAILED_MARKUP, PHASE_ACCUMULATION, PHASE_INDETERMINATE + "(no rule)"],
        "distribution": {"position_250_gt": 0.78, "volume_ratio_20_gt": 1.45, "close_to_high_lt": 0.97, "or_return_20_lt": -0.03,
                          "hypothesis": "phase_replay._classify_row:306-315 distribution branch (position_120 -> position_250)"},
        "markup": {"return_20_gt": 0.18, "or_return_60_gt": 0.35, "volume_ratio_20_gt": 1.05,
                    "hypothesis": "phase_replay._classify_row:317-322 markup branch"},
        "failed_markup": {"requires_markup_within_lookback": True, "drawdown_from_lookback_high_le": -0.10,
                           "hypothesis": "transition after an observed markup; threshold from phase_replay:303-304 post-distribution -0.08 and 2x offhour:6478 stop 0.05"},
        "accumulation": {"position_250_lt": 0.65, "ma_spread_20_60_lt": 0.09, "return_120_lt": 0.25,
                          "hypothesis": "phase_replay._classify_row:334-342 accumulation branch (position_120 -> position_250)"},
    },
    "selection_rules": {
        "candidate": "current_state == observed AND phase == accumulation AND no rule-level distribution or failed_markup within distribution_veto_lookback AND liquidity band known",
        "non_candidate": "phase in {markup, distribution, failed_markup} OR accumulation with recent distribution/failed_markup",
        "indeterminate": "current_state != observed OR phase indeterminate OR liquidity unknown",
        "matched_non_candidate_role": "assigned only by match_controls, never by the selector",
    },
    "trade_rules": {
        "entry_signal": {"requires_selection": SELECTION_CANDIDATE, "close_gt_ma20": True, "volume_ratio_20_ge": 1.5,
                          "limit_like_possible_blocks": True, "limit_down_possible_blocks": True, "zero_volume_blocks": True,
                          "hypothesis": "dengzhan.has_forced_divergence:153 min_volume_ratio=1.5; dengzhan.SignalResult:12 three-state pass/fail/unknown"},
        "stop_loss_pct": 0.05, "take_profit_pct": 0.08, "max_holding_sessions": 20,
        "event_precedence": [EVENT_INVALIDATION, EVENT_STOP, EVENT_EXIT, EVENT_HOLD],
        "determinate_price_events_require": "current_state == observed AND reference verified against a consumed bar AND corporate_action_status in {none_verified, complete_known} AND no known ex-date inside (reference_date, decision_date]",
        "otherwise": "review_required (price condition reported but not claimed) or unknown (current data missing/suspended)",
        "evaluation_basis": "close of the decision bar; no intraday fill is claimed",
        "tradability": "always 'unverified' in this policy version",
        "hypothesis": "offhour._signal_exit_plan:6478-6479 stop_loss_pct=0.05 take_profit_pct=0.08 (defaults)",
    },
    "liquidity_bands_amount_20_cny": [
        {"band": "L1_thin", "lt": 3.0e7}, {"band": "L2_low", "lt": 1.0e8}, {"band": "L3_mid", "lt": 5.0e8}, {"band": "L4_deep", "lt": None},
    ],
    "regime_rules": {
        "benchmark_required_sessions": 60,
        "bull": "close > ma60 AND return_60 > +0.05", "bear": "close < ma60 AND return_60 < -0.05", "range": "otherwise",
        "unknown": "benchmark missing/insufficient, benchmark bar missing on the decision session, coverage unknown or < 0.90",
        "universe_coverage_min": 0.90,
    },
    "limit_thresholds_pct": {
        "main": 9.8, "st": 4.8, "chinext": 19.5, "star": 19.5, "bse": 29.0,
        "hypothesis": "app/data/price_limits.py:31-37 DEFAULT_LIMIT_UP_THRESHOLDS (re-declared; not imported)",
        "st_unknown_rule": "when ST status is unknown the lowest plausible threshold (st) is used for main-board codes; limit-like is then 'possible', not 'confirmed'",
    },
    "corporate_actions": {
        "status_values": list(CA_STATUSES),
        "unknown_rule": "returns and positions carry adjustment_uncertainty=true; phase labels are conditional proxies; no realized-return claim; price-based position events are review_required",
        "partial_known_rule": "known events gate windows; completeness stays unknown (adjustment_uncertainty=true)",
        "known_in_window_rule": "a known ex-date inside the position window makes phase indeterminate (known_corporate_action_in_window)",
        "none_verified_rule": "requires evidence_refs and facts_available_at; never inferred from a smooth chart or a missing record",
        "m2_partial_facts": "frozen r06_basis_unit_controls.json: SH600011 ex-dates 2024-07-11/2025-07-10/2026-07-03 and BJ920000 ex-dates 2023-07-05/2024-06-05/2024-09-30/2025-05-15/2025-09-18/2026-05-25 with retained cninfo/bse documents — a partial known set with capture provenance, not a complete register",
    },
    "scope_exceptions": [
        {"symbol": "BJ920006", "trade_date": "2023-12-04", "kind": "bse_block_trade_total_scope_interpretation",
         "handling": "volume and amount of this bar are excluded from volume-ratio means; if it is the decision bar, volume_ratio_20 is None",
         "reference": "M2_FINAL_ACCEPTANCE_20260910.md §5.3; bounded to its frozen evidence, not a general vwap waiver"},
    ],
    "matching": {
        "k_min": 3, "k_max": 5,
        "same_decision_date": True,
        "same_cutoff_mode_and_convention": True,
        "same_policy_hash_and_version": True,
        "same_liquidity_band": True, "same_broad_regime": True, "bands_and_regimes_must_be_known": True,
        "distinct_control_symbols": True, "stock_role_only": True, "same_universe_membership": True, "same_synthetic_flag": True,
        "control_selection_label": SELECTION_NON_CANDIDATE,
        "record_verification": "full records: record_hash recomputed; summaries: must carry episode_id, record_hash and every matching field",
        "duplicates": "identical duplicates collapse to one control (counted); conflicting duplicates (same symbol+date, different record_hash) are rejected",
        "ranking": "(|ln(amount_20 ratio)|, symbol) ascending; deterministic",
        "outcome_fields_forbidden": True,
        "split_admission": "positive and controls must be admissible for the declared purpose (default initial_library_admission = development only)",
        "supersedes_draft_window": "0.1.0-draft ±10-session window is withdrawn (Codex review §2); this same-date rule is the reviewed correction",
    },
    "case_library": {
        "episode_id": "sha256(canonical{namespace, policy_hash, symbol, decision_date, decision_fingerprint})[:32]",
        "decision_fingerprint": "sha256(canonical{stock rows consumed, benchmark rows consumed, security_context, coverage, calendar fingerprint, universe fingerprint, cutoff, prior_state, position_state, synthetic})",
        "record_hash": "sha256(canonical core record) excluding review_ledger and request_diagnostics",
        "review_ledger": "append-only; each entry bound to (episode_id, record_hash, policy_hash) with non-empty evidence_refs and execution_ref; ledger_hash separate from record_hash",
        "review_status_at_generation": REVIEW_PENDING,
        "independent_review": "two distinct reviewer_ids of kind agent/human with bound, evidenced, non-conflicting current verdicts; disagreement preserved as disputed; the generator never asserts that two names are two executions",
        "targets": {"min_reviewed_positives": 50, "controls_per_positive": [3, 5]},
        "counting": "library_counts distinguishes records_total, positively_reviewed_episodes, qualified_positives (development-only, in-universe, observed, non-synthetic, matched 3-5 distinct controls), effective_dependence_groups; synthetic never counts",
    },
    "split_proposal": {
        "status": "proposal_requires_codex_review",
        "development": ["2023-09-04", "2025-03-31"], "validation": ["2025-04-01", "2025-12-31"], "final_holdout": ["2026-01-01", "2026-09-04"],
        "rule": "final_holdout may not be used for rule/threshold selection or target counting; initial library = development only; validation is a separate read-only check",
        "purpose_allowlist": list(PURPOSES),
        "distinct_from": "offhour._chronological_signal_split:5370-5378 (70/30 by signal count, no holdout)",
    },
    "seed_context": [
        {"symbol": "SZ002115", "name": "三维通信", "status": "legacy_unverified", "in_frozen_universe": False,
         "source": "phase_replay.CORE_REPLAY_TARGETS:27-30", "case_count_contribution": 0},
        {"symbol": "SZ002081", "name": "金螳螂", "status": "legacy_unverified", "in_frozen_universe": False,
         "source": "phase_replay.CORE_REPLAY_TARGETS:27-30", "case_count_contribution": 0},
    ],
    "frozen_universe": {
        "manifest": "claude methods/_m1_closure/pilot_symbols.csv",
        "sha256": "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe",
        "stocks": 50, "benchmarks": 2,
        "extension_rule": "any symbol outside the manifest is a separate universe decision; never silently added",
    },
    "safety": {"review_only": True, "live_trading_enabled": False, "simulation_only": True, "hidden_actor_claim": False},
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


POLICY_HASH = sha256_text(canonical_json(_POLICY_SOURCE))
# Public, exported copy (documentation) and private rule configuration.  Rules
# read only ``_RULES``; ``policy_document()`` returns a fresh deep copy; every
# entry point re-checks that neither copy drifted from POLICY_HASH.
POLICY: dict[str, Any] = copy.deepcopy(_POLICY_SOURCE)
_RULES: dict[str, Any] = copy.deepcopy(_POLICY_SOURCE)


def assert_policy_integrity() -> str:
    """Fail closed if the live rule configuration or the exported policy no longer hashes to POLICY_HASH."""
    live = sha256_text(canonical_json(_RULES))
    if live != POLICY_HASH:
        raise LabelInputError("policy_hash_mismatch", f"live rules {live[:12]} != declared {POLICY_HASH[:12]}")
    exported = sha256_text(canonical_json(POLICY))
    if exported != POLICY_HASH:
        raise LabelInputError("policy_hash_mismatch", f"exported policy {exported[:12]} != declared {POLICY_HASH[:12]}")
    return POLICY_HASH


_PRODUCER_CACHE: dict[str, str] = {}


def producer_sha256() -> str:
    """SHA-256 of this module's own bytes (provenance of the generator)."""
    if "sha256" not in _PRODUCER_CACHE:
        _PRODUCER_CACHE["sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return _PRODUCER_CACHE["sha256"]


# --------------------------------------------------------------------------- #
# Errors and parsing helpers                                                  #
# --------------------------------------------------------------------------- #


class LabelInputError(ValueError):
    """Fail-closed input rejection.  ``code`` is a stable reason identifier."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


_REAL_SYMBOL = re.compile(_POLICY_SOURCE["input_contract"]["symbol_pattern_real"])
_SYN_SYMBOL = re.compile(_POLICY_SOURCE["input_contract"]["symbol_pattern_synthetic"])
_REAL_BENCH = re.compile(_POLICY_SOURCE["input_contract"]["benchmark_pattern_real"])
_SYN_BENCH = re.compile(_POLICY_SOURCE["input_contract"]["benchmark_pattern_synthetic"])
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _parse_date(text: Any, code: str) -> date:
    if not isinstance(text, str) or not _DATE.match(text):
        raise LabelInputError(code, f"not an ISO date: {text!r}")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise LabelInputError(code, f"invalid calendar date: {text!r}") from exc


def _parse_datetime(text: Any, code: str) -> datetime:
    if not isinstance(text, str):
        raise LabelInputError(code, f"not an ISO datetime string: {text!r}")
    try:
        value = datetime.fromisoformat(text)
    except ValueError as exc:
        raise LabelInputError(code, f"invalid datetime: {text!r}") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise LabelInputError(code, f"datetime without UTC offset: {text!r}")
    return value


def _str_tuple(value: Any, code: str, allow_empty: bool) -> tuple[str, ...]:
    if value is None:
        value = ()
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise LabelInputError(code, f"expected a list/tuple of strings: {value!r}")
    out = tuple(value)
    if any(not isinstance(v, str) or not v for v in out):
        raise LabelInputError(code, f"empty or non-string entry in {value!r}")
    if not allow_empty and not out:
        raise LabelInputError(code, "at least one entry required")
    return out


def close_time(trade_date: str) -> datetime:
    """Historical session close of ``trade_date`` (15:00 Asia/Shanghai)."""
    d = _parse_date(trade_date, "invalid_trade_date")
    h, mi, s = (int(x) for x in SESSION_CLOSE_LOCAL.split(":"))
    return datetime(d.year, d.month, d.day, h, mi, s, tzinfo=SESSION_TZ)


# --------------------------------------------------------------------------- #
# Input records                                                               #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Observation:
    """One daily observation: a full-day price bar or a full-day suspension."""

    symbol: str
    trade_date: str
    kind: str  # "price" | "full_day_suspension"
    available_at: str
    source_ref: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    amount: float | None = None
    adjustment_mode: str = "none"
    volume_unit: str = "share"

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "Observation":
        return cls(
            symbol=row.get("symbol"), trade_date=row.get("trade_date"), kind=row.get("kind", "price"),
            available_at=row.get("available_at"), source_ref=row.get("source_ref"),
            open=row.get("open"), high=row.get("high"), low=row.get("low"), close=row.get("close"),
            volume=row.get("volume"), amount=row.get("amount"),
            adjustment_mode=row.get("adjustment_mode", "none"), volume_unit=row.get("volume_unit", "share"),
        )

    def record(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "trade_date": self.trade_date, "kind": self.kind, "available_at": self.available_at,
                "source_ref": self.source_ref, "open": self.open, "high": self.high, "low": self.low, "close": self.close,
                "volume": self.volume, "amount": self.amount, "adjustment_mode": self.adjustment_mode, "volume_unit": self.volume_unit}


@dataclass(frozen=True)
class SessionCalendar:
    """Injected exchange-session calendar with provenance.  Never inferred from prices."""

    sessions: tuple[str, ...]
    source_ref: str
    available_at: str
    synthetic: bool = False

    def validated(self) -> "SessionCalendar":
        sessions = _str_tuple(self.sessions, "invalid_calendar", allow_empty=False)
        previous: date | None = None
        for s in sessions:
            d = _parse_date(s, "invalid_calendar")
            if previous is not None and d <= previous:
                raise LabelInputError("invalid_calendar", f"sessions must be strictly increasing at {s}")
            previous = d
        if not isinstance(self.source_ref, str) or not self.source_ref:
            raise LabelInputError("invalid_calendar", "source_ref required")
        _parse_datetime(self.available_at, "invalid_calendar")
        if not _is_bool(self.synthetic):
            raise LabelInputError("invalid_calendar", "synthetic must be bool")
        return self

    def fingerprint(self) -> str:
        return sha256_text(canonical_json(list(self.sessions)))

    def index(self) -> dict[str, int]:
        return {s: i for i, s in enumerate(self.sessions)}

    def record(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint(), "source_ref": self.source_ref, "available_at": self.available_at,
                "synthetic": self.synthetic, "sessions": len(self.sessions), "first": self.sessions[0], "last": self.sessions[-1]}


@dataclass(frozen=True)
class FrozenUniverse:
    symbols: frozenset[str]
    source_ref: str
    sha256: str

    def validated(self) -> "FrozenUniverse":
        if not isinstance(self.symbols, frozenset) or not self.symbols or any(not isinstance(s, str) for s in self.symbols):
            raise LabelInputError("invalid_universe", "symbols must be a non-empty frozenset of strings")
        if not isinstance(self.source_ref, str) or not self.source_ref or not isinstance(self.sha256, str) or len(self.sha256) != 64:
            raise LabelInputError("invalid_universe", "source_ref and 64-hex sha256 required")
        return self

    def record(self) -> dict[str, Any]:
        return {"source_ref": self.source_ref, "sha256": self.sha256, "size": len(self.symbols)}


@dataclass(frozen=True)
class Coverage:
    """Universe coverage ratio on the decision session, with provenance."""

    ratio: float
    evidence_ref: str
    available_at: str

    def validated(self) -> "Coverage":
        _validate_coverage_ratio(self.ratio)
        if not isinstance(self.evidence_ref, str) or not self.evidence_ref:
            raise LabelInputError("invalid_universe_coverage", "evidence_ref required")
        _parse_datetime(self.available_at, "invalid_universe_coverage")
        return self

    def record(self) -> dict[str, Any]:
        return {"ratio": self.ratio, "evidence_ref": self.evidence_ref, "available_at": self.available_at}


def _validate_coverage_ratio(value: Any) -> float:
    if _is_bool(value) or not _is_number(value) or not (0.0 <= float(value) <= 1.0):
        raise LabelInputError("invalid_universe_coverage", f"coverage must be a finite number in [0, 1], got {value!r}")
    return float(value)


@dataclass(frozen=True)
class Cutoff:
    decision_date: str
    as_of: str
    mode: str = MODE_STRICT

    def as_of_dt(self) -> datetime:
        return _parse_datetime(self.as_of, "invalid_cutoff_as_of")

    def convention_seconds(self) -> int:
        return int((self.as_of_dt() - close_time(self.decision_date)).total_seconds())

    def convention(self) -> str:
        return f"close+{self.convention_seconds()}s"

    def record(self) -> dict[str, Any]:
        return {"decision_date": self.decision_date, "as_of": self.as_of, "mode": self.mode,
                "convention": self.convention(), "convention_seconds": self.convention_seconds()}


@dataclass(frozen=True)
class SecurityContext:
    """Per-symbol facts that are *not* derivable from OHLCVA.  Unknown stays unknown.

    Any non-unknown fact must carry ``evidence_refs`` and ``facts_available_at``.
    ``corporate_action_status``: unknown | partial_known | complete_known | none_verified.
    """

    listing_date: str | None = None
    name: str | None = None
    st_status: str = "unknown"
    corporate_action_status: str = CA_UNKNOWN
    known_ex_dates: tuple[str, ...] = ()
    float_shares: float | None = None
    turnover_available: bool = False
    evidence_refs: tuple[str, ...] = ()
    facts_available_at: str | None = None

    def has_non_unknown_facts(self) -> bool:
        return (self.listing_date is not None or self.name is not None or self.st_status != "unknown"
                or self.corporate_action_status != CA_UNKNOWN or bool(self.known_ex_dates)
                or self.float_shares is not None or bool(self.turnover_available))

    def validated(self) -> "SecurityContext":
        if self.listing_date is not None:
            _parse_date(self.listing_date, "invalid_security_context")
        if self.name is not None and not isinstance(self.name, str):
            raise LabelInputError("invalid_security_context", f"name must be str or None: {self.name!r}")
        if self.st_status not in ST_STATUSES:
            raise LabelInputError("invalid_security_context", f"st_status {self.st_status!r} not in {ST_STATUSES}")
        if self.corporate_action_status not in CA_STATUSES:
            raise LabelInputError("invalid_security_context", f"corporate_action_status {self.corporate_action_status!r} not in {CA_STATUSES}")
        ex_dates = _str_tuple(self.known_ex_dates, "invalid_security_context", allow_empty=True)
        previous: date | None = None
        for d in ex_dates:
            parsed = _parse_date(d, "invalid_security_context")
            if previous is not None and parsed <= previous:
                raise LabelInputError("invalid_security_context", "known_ex_dates must be strictly increasing and unique")
            previous = parsed
        if self.corporate_action_status == CA_UNKNOWN and ex_dates:
            raise LabelInputError("invalid_security_context", "known_ex_dates require partial_known or complete_known status")
        if self.corporate_action_status == CA_NONE_VERIFIED and ex_dates:
            raise LabelInputError("invalid_security_context", "none_verified cannot carry ex-dates")
        if self.float_shares is not None and (not _is_number(self.float_shares) or self.float_shares <= 0):
            raise LabelInputError("invalid_security_context", f"float_shares must be a positive finite number or None: {self.float_shares!r}")
        if not _is_bool(self.turnover_available):
            raise LabelInputError("invalid_security_context", "turnover_available must be bool")
        refs = _str_tuple(self.evidence_refs, "invalid_security_context", allow_empty=True)
        if self.has_non_unknown_facts():
            if not refs:
                raise LabelInputError("security_facts_without_evidence", "non-unknown facts require evidence_refs")
            if self.facts_available_at is None:
                raise LabelInputError("security_facts_without_availability", "non-unknown facts require facts_available_at")
        if self.facts_available_at is not None:
            _parse_datetime(self.facts_available_at, "invalid_security_context")
        return self

    def record(self) -> dict[str, Any]:
        return {"listing_date": self.listing_date, "name": self.name, "st_status": self.st_status,
                "corporate_action_status": self.corporate_action_status, "known_ex_dates": list(self.known_ex_dates),
                "float_shares": self.float_shares, "turnover_available": self.turnover_available,
                "evidence_refs": list(self.evidence_refs), "facts_available_at": self.facts_available_at}


@dataclass(frozen=True)
class PriorState:
    """A phase label produced earlier by this policy, offered as an input; re-derived before trust."""

    symbol: str
    decision_date: str
    as_of: str
    policy_hash: str
    phase: str
    episode_id: str | None = None

    def record(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "decision_date": self.decision_date, "as_of": self.as_of,
                "policy_hash": self.policy_hash, "phase": self.phase, "episode_id": self.episode_id}


@dataclass(frozen=True)
class PositionState:
    """A hypothetical review-only position opened at an earlier cutoff.

    ``reference_basis``: next_session_open | session_close | declared.  The
    reference is verified against the consumed bar whenever the basis is observable.
    """

    symbol: str
    policy_hash: str
    entry_decision_date: str
    reference_date: str
    reference_price: float
    reference_basis: str = "next_session_open"
    evidence_ref: str = ""
    available_at: str | None = None

    def record(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "policy_hash": self.policy_hash, "entry_decision_date": self.entry_decision_date,
                "reference_date": self.reference_date, "reference_price": self.reference_price,
                "reference_basis": self.reference_basis, "evidence_ref": self.evidence_ref, "available_at": self.available_at}


@dataclass(frozen=True)
class LabelRequest:
    symbol: str
    observations: Sequence[Observation]
    cutoff: Cutoff
    calendar: SessionCalendar | None = None
    security: SecurityContext = field(default_factory=SecurityContext)
    benchmark_symbol: str | None = None
    benchmark_observations: Sequence[Observation] = ()
    universe_coverage_on_decision_date: Coverage | float | None = None
    prior_state: PriorState | None = None
    position_state: PositionState | None = None
    synthetic: bool = False
    universe: FrozenUniverse | None = None


# --------------------------------------------------------------------------- #
# Validation (fail closed)                                                    #
# --------------------------------------------------------------------------- #


def infer_board(symbol: str) -> str:
    code = symbol[-6:]
    if code.startswith(("300", "301", "302")):
        return "chinext"
    if code.startswith("688"):
        return "star"
    if symbol.startswith("BJ") or code.startswith(("8", "4", "9")):
        return "bse"
    return "main"


def instrument_role(symbol: str, synthetic: bool) -> str:
    pattern = _SYN_BENCH if synthetic else _REAL_BENCH
    return ROLE_BENCHMARK if pattern.match(symbol) else ROLE_STOCK


def _scope_exception(symbol: str, trade_date: str) -> dict[str, Any] | None:
    for item in _RULES["scope_exceptions"]:
        if item["symbol"] == symbol and item["trade_date"] == trade_date:
            return item
    return None


def validate_symbol(symbol: Any, synthetic: bool, role: str = ROLE_STOCK) -> str:
    if not _is_bool(synthetic):
        raise LabelInputError("invalid_synthetic_flag", f"synthetic must be bool, got {synthetic!r}")
    if not isinstance(symbol, str):
        raise LabelInputError("invalid_symbol", repr(symbol))
    if synthetic:
        if not _SYN_SYMBOL.match(symbol):
            raise LabelInputError("synthetic_symbol_pattern", f"synthetic inputs must use SYN###### symbols: {symbol}")
    elif not _REAL_SYMBOL.match(symbol):
        raise LabelInputError("invalid_symbol", symbol)
    actual = instrument_role(symbol, synthetic)
    if actual != role:
        raise LabelInputError("instrument_role_mismatch", f"{symbol} is a {actual}, expected {role}")
    return symbol


def validate_observations(observations: Iterable[Observation], symbol: str, synthetic: bool,
                          role: str = ROLE_STOCK, calendar: SessionCalendar | None = None) -> list[Observation]:
    """Reject wrong identity, duplicates, unsorted input, non-finite/bool numerics, invalid
    prices/volumes/amounts, impossible availability, unknown units and non-session dates."""
    rows = list(observations)
    if not rows:
        raise LabelInputError("no_observations", symbol)
    validate_symbol(symbol, synthetic, role)
    sessions = set(calendar.sessions) if calendar is not None else None
    seen: set[str] = set()
    previous: date | None = None
    for row in rows:
        if not isinstance(row, Observation):
            raise LabelInputError("not_an_observation", repr(type(row)))
        if row.symbol != symbol:
            raise LabelInputError("wrong_security_identity", f"expected {symbol}, got {row.symbol!r}")
        d = _parse_date(row.trade_date, "invalid_trade_date")
        if row.trade_date in seen:
            raise LabelInputError("duplicate_key", f"{symbol} {row.trade_date}")
        seen.add(row.trade_date)
        if previous is not None and d <= previous:
            raise LabelInputError("unsorted_input", f"{row.trade_date} after {previous.isoformat()}")
        previous = d
        if sessions is not None and row.trade_date not in sessions:
            raise LabelInputError("observation_not_a_session", f"{symbol} {row.trade_date} is not in the injected calendar")
        if row.kind not in _RULES["input_contract"]["observation_kinds"]:
            raise LabelInputError("unknown_observation_kind", repr(row.kind))
        if not isinstance(row.source_ref, str) or not row.source_ref:
            raise LabelInputError("missing_source_ref", f"{symbol} {row.trade_date}")
        avail = _parse_datetime(row.available_at, "invalid_available_at")
        if avail < close_time(row.trade_date):
            raise LabelInputError("availability_before_close", f"{symbol} {row.trade_date} available_at {row.available_at}")
        if row.kind == "full_day_suspension":
            if any(v is not None for v in (row.open, row.high, row.low, row.close, row.volume, row.amount)):
                raise LabelInputError("suspension_with_prices", f"{symbol} {row.trade_date}")
            continue
        if row.adjustment_mode not in _RULES["input_contract"]["adjustment_mode_accepted"]:
            raise LabelInputError("unsupported_adjustment_mode", repr(row.adjustment_mode))
        if row.volume_unit not in _RULES["input_contract"]["volume_unit_accepted"]:
            raise LabelInputError("unsupported_volume_unit", repr(row.volume_unit))
        for name in ("open", "high", "low", "close", "volume", "amount"):
            value = getattr(row, name)
            if not _is_number(value):
                raise LabelInputError("nonfinite_or_missing_numeric", f"{symbol} {row.trade_date} {name}={value!r}")
        o, h, lo, c, v, a = (float(getattr(row, n)) for n in ("open", "high", "low", "close", "volume", "amount"))
        if lo <= 0 or not (lo <= min(o, c) <= max(o, c) <= h):
            raise LabelInputError("invalid_price", f"{symbol} {row.trade_date} o={o} h={h} l={lo} c={c}")
        if v < 0 or a < 0:
            raise LabelInputError("invalid_volume_or_amount", f"{symbol} {row.trade_date} v={v} a={a}")
        if v == 0 and a != 0:
            raise LabelInputError("invalid_volume_or_amount", f"{symbol} {row.trade_date} zero volume with amount {a}")
        if v > 0:
            vwap = a / v
            if not (0.98 * lo <= vwap <= 1.02 * h) and _scope_exception(symbol, row.trade_date) is None:
                raise LabelInputError("vwap_outside_range", f"{symbol} {row.trade_date} vwap={vwap:.6f} low={lo} high={h}")
    return rows


def validate_cutoff(cutoff: Cutoff) -> datetime:
    if cutoff.mode not in CUTOFF_MODES:
        raise LabelInputError("invalid_cutoff_mode", repr(cutoff.mode))
    decision = _parse_date(cutoff.decision_date, "invalid_cutoff_decision_date")
    as_of = cutoff.as_of_dt()
    if as_of < close_time(cutoff.decision_date):
        raise LabelInputError("cutoff_before_decision_close", f"as_of {cutoff.as_of} precedes close of {decision.isoformat()}")
    if cutoff.mode == MODE_STRICT and as_of > close_time(cutoff.decision_date) + timedelta(hours=STRICT_CUTOFF_MAX_HOURS_AFTER_CLOSE):
        # A strict decision "at D" must be taken shortly after D's close; otherwise
        # "available_at <= as_of" would let a 2026 capture pretend to be 2024 knowledge.
        raise LabelInputError("strict_cutoff_too_late", f"as_of {cutoff.as_of} is more than {STRICT_CUTOFF_MAX_HOURS_AFTER_CLOSE}h after the close of {decision.isoformat()}")
    return as_of


def select_usable(rows: Sequence[Observation], cutoff: Cutoff) -> tuple[list[Observation], dict[str, Any], dict[str, Any]]:
    """Return (usable rows in order, availability summary of the *consumed* rows, request diagnostics)."""
    as_of = validate_cutoff(cutoff)
    usable: list[Observation] = []
    excluded_after_cutoff = excluded_late = violations_consumed = 0
    max_available_at: datetime | None = None
    for row in rows:
        ct = close_time(row.trade_date)
        avail = _parse_datetime(row.available_at, "invalid_available_at")
        if ct > as_of or row.trade_date > cutoff.decision_date:
            excluded_after_cutoff += 1
            continue
        if avail > as_of:
            if cutoff.mode == MODE_STRICT:
                excluded_late += 1
                continue
            violations_consumed += 1
        usable.append(row)
        if max_available_at is None or avail > max_available_at:
            max_available_at = avail
    summary = {
        "rows_consumed": len(usable),
        "availability_violations_consumed": violations_consumed,
        "max_trade_date_consumed": usable[-1].trade_date if usable else None,
        "max_available_at_consumed": max_available_at.isoformat() if max_available_at else None,
        "all_consumed_available_at_cutoff": violations_consumed == 0 and bool(usable),
    }
    diagnostics = {"rows_offered": len(rows), "rows_excluded_after_cutoff": excluded_after_cutoff,
                   "rows_excluded_late_availability": excluded_late}
    return usable, summary, diagnostics


def input_fingerprint(usable: Sequence[Observation]) -> str:
    return sha256_text(canonical_json([row.record() for row in usable]))


# --------------------------------------------------------------------------- #
# Calendar view of the consumed data                                          #
# --------------------------------------------------------------------------- #


def session_view(calendar: SessionCalendar, usable: Sequence[Observation], decision_date: str) -> dict[str, Any]:
    """Classify the decision session and the interior of the consumed window on the injected calendar."""
    index = calendar.index()
    if decision_date not in index:
        raise LabelInputError("decision_date_not_a_session", f"{decision_date} is not a session of calendar {calendar.fingerprint()[:12]}")
    by_date = {row.trade_date: row for row in usable}
    decision_row = by_date.get(decision_date)
    if decision_row is None:
        current = CURRENT_MISSING
    elif decision_row.kind == "price":
        current = CURRENT_OBSERVED
    else:
        current = CURRENT_SUSPENDED
    bars = [row for row in usable if row.kind == "price"]
    w = _RULES["windows"]
    view: dict[str, Any] = {"current_state": current, "decision_session_index": index[decision_date],
                            "sessions_since_last_price": None, "interior_missing_sessions": 0,
                            "suspensions_in_window": 0, "longest_no_price_run_in_window": 0, "window_first_session": None}
    if not bars:
        return view
    last_bar_idx = index[bars[-1].trade_date]
    view["sessions_since_last_price"] = index[decision_date] - last_bar_idx
    window_bars = bars[-w["position"] :]
    first_idx = index[window_bars[0].trade_date]
    view["window_first_session"] = window_bars[0].trade_date
    missing = suspensions = run = longest = 0
    for s in calendar.sessions[first_idx : index[decision_date] + 1]:
        row = by_date.get(s)
        if row is None:
            missing += 1
            run += 1
        elif row.kind == "full_day_suspension":
            suspensions += 1
            run += 1
        else:
            run = 0
        longest = max(longest, run)
    view.update({"interior_missing_sessions": missing, "suspensions_in_window": suspensions, "longest_no_price_run_in_window": longest})
    return view


# --------------------------------------------------------------------------- #
# Features (pure arithmetic over the usable window)                           #
# --------------------------------------------------------------------------- #


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _volume_for_ratio(bar: Observation) -> float | None:
    if _scope_exception(bar.symbol, bar.trade_date) is not None:
        return None
    if bar.volume is None or float(bar.volume) <= 0:
        return None
    return float(bar.volume)


def bar_features(bars: Sequence[Observation], index: int) -> dict[str, Any]:
    """Features for the price bar at ``bars[index]`` using bars[:index+1] only."""
    w = _RULES["windows"]
    bar = bars[index]
    closes = [float(b.close) for b in bars[: index + 1]]
    highs = [float(b.high) for b in bars[: index + 1]]
    lows = [float(b.low) for b in bars[: index + 1]]
    n = index + 1
    close = closes[-1]

    def ret(k: int) -> float | None:
        return close / closes[-1 - k] - 1.0 if n > k else None

    prev_close = closes[-2] if n > 1 else None
    vols = [_volume_for_ratio(b) for b in bars[max(0, index - w["short"]) : index]]
    vols_known = [v for v in vols if v is not None]
    own_volume = _volume_for_ratio(bar)
    volume_ratio = None
    if own_volume is not None and len(vols_known) >= w["short"] // 2 and len(vols) == w["short"]:
        mean_v = _mean(vols_known)
        volume_ratio = own_volume / mean_v if mean_v else None
    ma20 = _mean(closes[-w["short"] :]) if n >= w["short"] else None
    ma60 = _mean(closes[-w["medium"] :]) if n >= w["medium"] else None
    ma_spread = abs(ma20 - ma60) / ma60 if ma20 is not None and ma60 is not None and ma60 > 0 else None
    pos_window = w["position"]
    position = high_pos = None
    if n >= pos_window:
        lo = min(lows[-pos_window:])
        hi = max(highs[-pos_window:])
        high_pos = hi
        position = (close - lo) / (hi - lo) if hi > lo else None
    amounts = [float(b.amount) for b in bars[max(0, index - w["short"] + 1) : index + 1] if _scope_exception(b.symbol, b.trade_date) is None]
    amount_20 = _mean(amounts) if n >= w["short"] and len(amounts) >= w["short"] // 2 else None
    lookback_high = max(highs[-w["failed_markup_lookback"] :]) if n >= w["failed_markup_lookback"] else None
    return {
        "trade_date": bar.trade_date, "close": close, "prev_close": prev_close,
        "pct_change": (close / prev_close - 1.0) if prev_close else None,
        "close_to_high": close / float(bar.high) if float(bar.high) > 0 else None,
        "range_pct": (float(bar.high) - float(bar.low)) / prev_close if prev_close else None,
        "return_20": ret(w["short"]), "return_60": ret(w["medium"]), "return_120": ret(w["long"]),
        "volume_ratio_20": volume_ratio, "volume_ratio_20_known_days": len(vols_known),
        "zero_volume_session": float(bar.volume) == 0,
        "ma20": ma20, "ma60": ma60, "ma_spread_20_60": ma_spread,
        "position_250": position, "high_250": high_pos,
        "drawdown_from_lookback_high": (close / lookback_high - 1.0) if lookback_high else None,
        "amount_20_mean_cny": amount_20, "bars_available": n,
        "scope_exception_on_bar": _scope_exception(bar.symbol, bar.trade_date) is not None,
    }


_EMPTY_FEATURES = {"bars_available": 0, "close": None, "ma20": None, "volume_ratio_20": None, "pct_change": None,
                   "zero_volume_session": None, "amount_20_mean_cny": None, "scope_exception_on_bar": False, "trade_date": None}


def _markup_rule(f: Mapping[str, Any]) -> bool:
    r = _RULES["phase_rules"]["markup"]
    vr = f.get("volume_ratio_20")
    if vr is None:
        return False
    r20, r60 = f.get("return_20"), f.get("return_60")
    return ((r20 is not None and r20 > r["return_20_gt"]) or (r60 is not None and r60 > r["or_return_60_gt"])) and vr > r["volume_ratio_20_gt"]


def _distribution_rule(f: Mapping[str, Any]) -> bool:
    r = _RULES["phase_rules"]["distribution"]
    pos, vr, c2h, r20 = f.get("position_250"), f.get("volume_ratio_20"), f.get("close_to_high"), f.get("return_20")
    if pos is None or vr is None or c2h is None:
        return False
    rejection = c2h < r["close_to_high_lt"] or (r20 is not None and r20 < r["or_return_20_lt"])
    return pos > r["position_250_gt"] and vr > r["volume_ratio_20_gt"] and rejection


def _accumulation_rule(f: Mapping[str, Any]) -> bool:
    r = _RULES["phase_rules"]["accumulation"]
    pos, spread, r120 = f.get("position_250"), f.get("ma_spread_20_60"), f.get("return_120")
    if pos is None or spread is None or r120 is None:
        return False
    return pos < r["position_250_lt"] and spread < r["ma_spread_20_60_lt"] and r120 < r["return_120_lt"]


# --------------------------------------------------------------------------- #
# Label families                                                              #
# --------------------------------------------------------------------------- #


def _quality_gates(view: Mapping[str, Any], bars: Sequence[Observation], security: SecurityContext,
                   context_usable: bool, features: Mapping[str, Any]) -> list[str]:
    """Reasons that force phase=indeterminate.  Unknown is never zero; all gaps are in sessions."""
    w = _RULES["windows"]
    reasons: list[str] = []
    if not bars:
        return ["no_price_bars_before_cutoff"]
    if view["current_state"] == CURRENT_MISSING:
        reasons.append("decision_session_evidence_missing")
    elif view["current_state"] == CURRENT_SUSPENDED:
        reasons.append("suspension_on_decision_session")
    if features["bars_available"] < w["warmup_required_sessions"]:
        reasons.append(f"insufficient_warmup:{features['bars_available']}<{w['warmup_required_sessions']}")
    if view["sessions_since_last_price"] is not None and view["sessions_since_last_price"] > w["max_stale_sessions"]:
        reasons.append(f"stale_last_price:{view['sessions_since_last_price']}_sessions")
    if view["interior_missing_sessions"] > 0:
        reasons.append(f"interior_missing_sessions:{view['interior_missing_sessions']}")
    if view["longest_no_price_run_in_window"] > w["long_gap_sessions"]:
        reasons.append(f"long_no_price_run_in_window:{view['longest_no_price_run_in_window']}_sessions")
    if view["suspensions_in_window"] > w["max_suspensions_in_window"]:
        reasons.append(f"many_suspensions_in_window:{view['suspensions_in_window']}")
    if context_usable and security.corporate_action_status in (CA_PARTIAL_KNOWN, CA_COMPLETE_KNOWN):
        first_in_window = view["window_first_session"]
        last_bar_date = bars[-1].trade_date
        if any(first_in_window <= ex <= last_bar_date for ex in security.known_ex_dates):
            reasons.append("known_corporate_action_in_window")
    for key in ("position_250", "ma_spread_20_60", "return_120", "volume_ratio_20"):
        if features.get(key) is None:
            reasons.append(f"missing_feature:{key}")
    if features.get("scope_exception_on_bar"):
        reasons.append("scope_exception_on_decision_bar")
    return reasons


def rule_phase(bars: Sequence[Observation], index: int) -> dict[str, Any]:
    """Rule-only phase for ``bars[index]`` (no quality gates) using bars[:index+1]."""
    lookback = _RULES["windows"]["failed_markup_lookback"]
    features = bar_features(bars, index)
    markup_seen = any(_markup_rule(bar_features(bars, i)) for i in range(max(0, index - lookback), index))
    if _distribution_rule(features):
        return {"label": PHASE_DISTRIBUTION, "rule": "distribution", "reasons": ["high_position_volume_rejection"], "markup_within_lookback": markup_seen}
    if _markup_rule(features):
        return {"label": PHASE_MARKUP, "rule": "markup", "reasons": ["return_expansion_with_volume"], "markup_within_lookback": markup_seen}
    dd = features.get("drawdown_from_lookback_high")
    if markup_seen and dd is not None and dd <= _RULES["phase_rules"]["failed_markup"]["drawdown_from_lookback_high_le"]:
        return {"label": PHASE_FAILED_MARKUP, "rule": "failed_markup", "reasons": ["prior_markup_then_drawdown_at_cutoff"], "markup_within_lookback": True}
    if _accumulation_rule(features):
        return {"label": PHASE_ACCUMULATION, "rule": "accumulation", "reasons": ["range_bound_converged_averages"], "markup_within_lookback": markup_seen}
    return {"label": PHASE_INDETERMINATE, "rule": "no_rule_matched", "reasons": ["no_rule_matched"], "markup_within_lookback": markup_seen}


def label_phase(bars: Sequence[Observation], gate_reasons: Sequence[str]) -> dict[str, Any]:
    if gate_reasons:
        return {"label": PHASE_INDETERMINATE, "rule": "quality_gate", "reasons": list(gate_reasons), "markup_within_lookback": None}
    return rule_phase(bars, len(bars) - 1)


def label_liquidity(features: Mapping[str, Any]) -> dict[str, Any]:
    amount = features.get("amount_20_mean_cny")
    if amount is None:
        return {"band": LIQUIDITY_UNKNOWN, "amount_20_mean_cny": None, "reasons": ["amount_20_unavailable"]}
    for item in _RULES["liquidity_bands_amount_20_cny"]:
        if item["lt"] is None or amount < item["lt"]:
            return {"band": item["band"], "amount_20_mean_cny": amount, "reasons": []}
    return {"band": LIQUIDITY_UNKNOWN, "amount_20_mean_cny": amount, "reasons": ["band_table_exhausted"]}


def label_regime(benchmark_bars: Sequence[Observation], decision_date: str, coverage_ratio: float | None,
                 coverage_reason: str | None) -> dict[str, Any]:
    r = _RULES["regime_rules"]
    reasons: list[str] = []
    if coverage_reason:
        reasons.append(coverage_reason)
    elif coverage_ratio is None:
        reasons.append("universe_coverage_unknown")
    elif coverage_ratio < r["universe_coverage_min"]:
        reasons.append(f"market_wide_missingness:{coverage_ratio:.3f}")
    if len(benchmark_bars) < r["benchmark_required_sessions"]:
        reasons.append(f"benchmark_insufficient:{len(benchmark_bars)}<{r['benchmark_required_sessions']}")
    if benchmark_bars and benchmark_bars[-1].trade_date != decision_date:
        reasons.append("benchmark_bar_missing_on_decision_session")
    if reasons:
        return {"regime": REGIME_UNKNOWN, "reasons": reasons, "benchmark_return_60": None, "benchmark_close_vs_ma60": None}
    f = bar_features(benchmark_bars, len(benchmark_bars) - 1)
    r60, ma60, close = f["return_60"], f["ma60"], f["close"]
    if r60 is None or ma60 is None:
        return {"regime": REGIME_UNKNOWN, "reasons": ["benchmark_features_unavailable"], "benchmark_return_60": None, "benchmark_close_vs_ma60": None}
    if close > ma60 and r60 > 0.05:
        regime = REGIME_BULL
    elif close < ma60 and r60 < -0.05:
        regime = REGIME_BEAR
    else:
        regime = REGIME_RANGE
    return {"regime": regime, "reasons": [], "benchmark_return_60": r60, "benchmark_close_vs_ma60": close / ma60 - 1.0}


def _veto_within_lookback(bars: Sequence[Observation]) -> list[str]:
    lookback = _RULES["windows"]["distribution_veto_lookback"]
    index = len(bars) - 1
    found: set[str] = set()
    for i in range(max(0, index - lookback), index):
        label = rule_phase(bars, i)["label"]
        if label in (PHASE_DISTRIBUTION, PHASE_FAILED_MARKUP):
            found.add(label)
    return sorted(found)


def label_selection(current_state: str, phase: Mapping[str, Any], liquidity: Mapping[str, Any], bars: Sequence[Observation]) -> dict[str, Any]:
    if current_state != CURRENT_OBSERVED:
        return {"label": SELECTION_INDETERMINATE, "reasons": [f"current_state_{current_state}"]}
    if phase["label"] == PHASE_INDETERMINATE:
        return {"label": SELECTION_INDETERMINATE, "reasons": ["phase_indeterminate"] + list(phase["reasons"])}
    if liquidity["band"] == LIQUIDITY_UNKNOWN:
        return {"label": SELECTION_INDETERMINATE, "reasons": ["liquidity_unknown"]}
    if phase["label"] in (PHASE_MARKUP, PHASE_DISTRIBUTION, PHASE_FAILED_MARKUP):
        return {"label": SELECTION_NON_CANDIDATE, "reasons": [f"phase_{phase['label']}"]}
    vetoes = _veto_within_lookback(bars)
    if vetoes:
        return {"label": SELECTION_NON_CANDIDATE, "reasons": [f"{v}_within_veto_lookback" for v in vetoes]}
    return {"label": SELECTION_CANDIDATE, "reasons": ["accumulation_without_recent_distribution_or_failed_markup"]}


def limit_assessment(symbol: str, security: SecurityContext, pct_change: float | None) -> dict[str, Any]:
    thresholds = _RULES["limit_thresholds_pct"]
    board = infer_board(symbol)
    if security.st_status == "st":
        threshold, confidence = thresholds["st"], "st_declared"
    elif security.st_status == "not_st":
        threshold, confidence = thresholds[board], "board_inferred_not_st"
    else:
        threshold = min(thresholds[board], thresholds["st"]) if board == "main" else thresholds[board]
        confidence = "board_inferred_st_unknown_lowest_threshold"
    if pct_change is None:
        return {"board": board, "threshold_pct": threshold, "confidence": confidence, "limit_like_possible": None, "limit_down_possible": None}
    move = pct_change * 100.0
    return {"board": board, "threshold_pct": threshold, "confidence": confidence,
            "limit_like_possible": move >= threshold, "limit_down_possible": move <= -threshold}


def label_entry(selection: Mapping[str, Any], features: Mapping[str, Any], limit: Mapping[str, Any]) -> dict[str, Any]:
    r = _RULES["trade_rules"]["entry_signal"]
    base = {"tradability": "unverified",
            "execution": {"legal_next_session": "unknown", "basis": "next-session open/limit/suspension state is not observable at the cutoff"}}
    if selection["label"] == SELECTION_INDETERMINATE:
        return {"label": ENTRY_INDETERMINATE, "reasons": ["selection_indeterminate"], **base}
    reasons: list[str] = []
    if selection["label"] != r["requires_selection"]:
        reasons.append("not_a_candidate")
    if features.get("ma20") is None or features.get("close") is None or features["close"] <= features["ma20"]:
        reasons.append("close_not_above_ma20")
    vr = features.get("volume_ratio_20")
    if vr is None:
        reasons.append("volume_ratio_unknown")
    elif vr < r["volume_ratio_20_ge"]:
        reasons.append("volume_ratio_below_min")
    if limit["limit_like_possible"] is None:
        reasons.append("limit_state_unknown")
    else:
        if limit["limit_like_possible"]:
            reasons.append("limit_like_possible")
        if limit["limit_down_possible"]:
            reasons.append("limit_down_possible")
    if features.get("zero_volume_session"):
        reasons.append("zero_volume_session")
    if reasons:
        return {"label": ENTRY_SIGNAL_NOT_ELIGIBLE, "reasons": reasons, **base}
    return {"label": ENTRY_SIGNAL_ELIGIBLE, "reasons": ["candidate_close_above_ma20_volume_confirmed"], **base}


def validate_position_state(position: PositionState, symbol: str, cutoff: Cutoff, calendar: SessionCalendar) -> None:
    if position.symbol != symbol or position.policy_hash != POLICY_HASH:
        raise LabelInputError("position_state_binding_mismatch", f"{position.symbol}/{str(position.policy_hash)[:12]} vs {symbol}/{POLICY_HASH[:12]}")
    entry = _parse_date(position.entry_decision_date, "position_state_invalid_date")
    ref = _parse_date(position.reference_date, "position_state_invalid_date")
    if position.reference_basis not in ("next_session_open", "session_close", "declared"):
        raise LabelInputError("position_state_invalid_basis", repr(position.reference_basis))
    if ref < entry or (position.reference_basis == "next_session_open" and ref <= entry):
        raise LabelInputError("position_reference_before_entry", f"reference {position.reference_date} not after entry decision {position.entry_decision_date}")
    if not (position.entry_decision_date < cutoff.decision_date) or position.reference_date > cutoff.decision_date:
        raise LabelInputError("position_state_not_earlier", f"entry {position.entry_decision_date} ref {position.reference_date} cutoff {cutoff.decision_date}")
    sessions = set(calendar.sessions)
    if position.entry_decision_date not in sessions or position.reference_date not in sessions:
        raise LabelInputError("position_state_not_a_session", f"{position.entry_decision_date}/{position.reference_date}")
    if not _is_number(position.reference_price) or position.reference_price <= 0:
        raise LabelInputError("position_state_invalid_reference_price", repr(position.reference_price))
    if not isinstance(position.evidence_ref, str) or not position.evidence_ref:
        raise LabelInputError("position_state_without_evidence", "evidence_ref required")
    if position.available_at is None:
        raise LabelInputError("position_state_without_availability", "available_at required")
    if _parse_datetime(position.available_at, "position_state_invalid_available_at") > cutoff.as_of_dt():
        raise LabelInputError("position_state_not_available_at_cutoff", f"{position.available_at} > {cutoff.as_of}")


def label_position_event(position: PositionState | None, symbol: str, cutoff: Cutoff, calendar: SessionCalendar,
                         usable: Sequence[Observation], bars: Sequence[Observation], view: Mapping[str, Any],
                         phase: Mapping[str, Any], security: SecurityContext, context_usable: bool) -> dict[str, Any]:
    t = _RULES["trade_rules"]
    if position is None:
        return {"label": EVENT_NO_TRADE, "reasons": ["no_open_position_state"], "basis_verified": False,
                "reference_price": None, "holding_sessions": None, "price_condition": None}
    validate_position_state(position, symbol, cutoff, calendar)
    ref = float(position.reference_price)
    by_date = {row.trade_date: row for row in usable}
    ref_row = by_date.get(position.reference_date)
    reasons: list[str] = []
    verified = True
    if ref_row is None or ref_row.kind != "price":
        verified = False
        reasons.append("reference_bar_not_consumed")
    elif position.reference_basis == "next_session_open" and abs(float(ref_row.open) - ref) > 1e-6 * max(1.0, ref):
        raise LabelInputError("position_reference_price_mismatch", f"declared {ref} vs consumed open {ref_row.open} on {position.reference_date}")
    elif position.reference_basis == "session_close" and abs(float(ref_row.close) - ref) > 1e-6 * max(1.0, ref):
        raise LabelInputError("position_reference_price_mismatch", f"declared {ref} vs consumed close {ref_row.close} on {position.reference_date}")
    index = calendar.index()
    holding = index[cutoff.decision_date] - index[position.reference_date]
    if view["current_state"] != CURRENT_OBSERVED:
        return {"label": EVENT_UNKNOWN, "reasons": [f"current_state_{view['current_state']}"] + reasons, "basis_verified": False,
                "reference_price": ref, "holding_sessions": holding, "price_condition": None}
    close = float(bars[-1].close)
    condition = {"close_at_cutoff": close,
                 "close_le_stop_level": close <= ref * (1.0 - t["stop_loss_pct"]),
                 "close_ge_target_level": close >= ref * (1.0 + t["take_profit_pct"]),
                 "holding_ge_max": holding >= t["max_holding_sessions"]}
    if not context_usable or security.corporate_action_status not in (CA_NONE_VERIFIED, CA_COMPLETE_KNOWN):
        verified = False
        reasons.append(f"corporate_action_status_{security.corporate_action_status if context_usable else 'not_available_at_cutoff'}")
    if context_usable and any(position.reference_date < ex <= cutoff.decision_date for ex in security.known_ex_dates):
        verified = False
        reasons.append("known_corporate_action_in_holding_window")
    if phase["label"] in (PHASE_DISTRIBUTION, PHASE_FAILED_MARKUP):
        return {"label": EVENT_INVALIDATION, "reasons": [f"phase_{phase['label']}_at_cutoff"] + reasons, "basis_verified": verified,
                "reference_price": ref, "holding_sessions": holding, "price_condition": condition,
                "evaluation_basis": "phase proxy (conditional on adjustment uncertainty), not a price comparison"}
    if not verified:
        return {"label": EVENT_REVIEW_REQUIRED, "reasons": reasons, "basis_verified": False, "reference_price": ref,
                "holding_sessions": holding, "price_condition": condition,
                "evaluation_basis": "unadjusted price comparison reported, not claimed as an event"}
    if condition["close_le_stop_level"]:
        label, why = EVENT_STOP, [f"close_le_reference_minus_{t['stop_loss_pct']}"]
    elif condition["close_ge_target_level"]:
        label, why = EVENT_EXIT, [f"close_ge_reference_plus_{t['take_profit_pct']}"]
    elif condition["holding_ge_max"]:
        label, why = EVENT_EXIT, [f"holding_sessions_ge_{t['max_holding_sessions']}"]
    else:
        label, why = EVENT_HOLD, ["no_event_rule_triggered"]
    return {"label": label, "reasons": why, "basis_verified": True, "reference_price": ref, "holding_sessions": holding,
            "price_condition": condition, "evaluation_basis": t["evaluation_basis"]}


# --------------------------------------------------------------------------- #
# Identity                                                                    #
# --------------------------------------------------------------------------- #

_CORE_EXCLUDED = ("record_hash", "review_ledger", "request_diagnostics")


def record_hash(output: Mapping[str, Any]) -> str:
    """Stable hash of the label core (excludes the review ledger, the diagnostics and itself)."""
    core = {k: v for k, v in output.items() if k not in _CORE_EXCLUDED}
    return sha256_text(canonical_json(core))


def verify_record(output: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless the record is a schema-v2 record whose record_hash recomputes."""
    if not isinstance(output, Mapping) or output.get("schema") != OUTPUT_SCHEMA:
        raise LabelInputError("unsupported_record", f"schema {output.get('schema') if isinstance(output, Mapping) else type(output)!r}")
    for key in ("episode_id", "record_hash", "policy_hash", "symbol", "cutoff", "labels", "identity", "synthetic", "universe"):
        if key not in output:
            raise LabelInputError("malformed_record", f"missing {key}")
    if output["policy_hash"] != POLICY_HASH:
        raise LabelInputError("policy_hash_mismatch", f"record {str(output['policy_hash'])[:12]} vs live {POLICY_HASH[:12]}")
    if record_hash(output) != output["record_hash"]:
        raise LabelInputError("record_hash_mismatch", output.get("episode_id", "?"))
    if not _is_bool(output["synthetic"]):
        raise LabelInputError("invalid_synthetic_flag", "record synthetic flag must be bool")
    return dict(output)


def episode_id(symbol: str, decision_date: str, decision_fingerprint: str) -> str:
    return sha256_text(canonical_json({"namespace": NAMESPACE, "policy_hash": POLICY_HASH, "symbol": symbol,
                                       "decision_date": decision_date, "decision_fingerprint": decision_fingerprint}))[:32]


# --------------------------------------------------------------------------- #
# Generator                                                                   #
# --------------------------------------------------------------------------- #


def _coverage_inputs(request: LabelRequest, as_of: datetime) -> tuple[float | None, str | None, dict[str, Any]]:
    raw = request.universe_coverage_on_decision_date
    if raw is None:
        return None, None, {"ratio": None, "evidence_ref": None, "available_at": None, "usable": False, "status": "unknown"}
    if isinstance(raw, Coverage):
        cov = raw.validated()
        avail = _parse_datetime(cov.available_at, "invalid_universe_coverage")
        if avail > as_of:
            if request.cutoff.mode == MODE_STRICT:
                return None, "universe_coverage_not_available_at_cutoff", {**cov.record(), "usable": False, "status": "not_available_at_cutoff"}
            return cov.ratio, None, {**cov.record(), "usable": True, "status": "consumed_with_availability_violation"}
        return cov.ratio, None, {**cov.record(), "usable": True, "status": "available"}
    ratio = _validate_coverage_ratio(raw)
    if not request.synthetic:
        raise LabelInputError("coverage_without_evidence", "real requests must supply Coverage(ratio, evidence_ref, available_at)")
    return ratio, None, {"ratio": ratio, "evidence_ref": None, "available_at": None, "usable": True, "status": "synthetic_declared_without_availability"}


def _context_inputs(request: LabelRequest, as_of: datetime) -> tuple[bool, dict[str, Any]]:
    sec = request.security.validated()
    if not sec.has_non_unknown_facts():
        return False, {"status": "all_unknown", "usable": False, "available_at": None}
    avail = _parse_datetime(sec.facts_available_at, "invalid_security_context")
    if avail > as_of:
        if request.cutoff.mode == MODE_STRICT:
            return False, {"status": "not_available_at_cutoff", "usable": False, "available_at": sec.facts_available_at}
        return True, {"status": "consumed_with_availability_violation", "usable": True, "available_at": sec.facts_available_at}
    return True, {"status": "available", "usable": True, "available_at": sec.facts_available_at}


def generate_labels(request: LabelRequest) -> dict[str, Any]:
    """Produce the full pending-review label record for one symbol at one cutoff."""
    assert_policy_integrity()
    if not _is_bool(request.synthetic):
        raise LabelInputError("invalid_synthetic_flag", repr(request.synthetic))
    symbol = validate_symbol(request.symbol, request.synthetic, ROLE_STOCK)
    if request.calendar is None:
        raise LabelInputError("calendar_required", "an injected SessionCalendar is mandatory")
    calendar = request.calendar.validated()
    if not request.synthetic and calendar.synthetic:
        raise LabelInputError("synthetic_calendar_for_real_request", calendar.source_ref)
    if not request.synthetic and request.universe is None:
        raise LabelInputError("universe_required", "real requests must carry the frozen universe")
    universe = request.universe.validated() if request.universe is not None else None
    as_of = validate_cutoff(request.cutoff)
    rows = validate_observations(request.observations, symbol, request.synthetic, ROLE_STOCK, calendar)
    usable, availability, diagnostics = select_usable(rows, request.cutoff)
    bars = [row for row in usable if row.kind == "price"]
    view = session_view(calendar, usable, request.cutoff.decision_date)
    context_usable, context_pit = _context_inputs(request, as_of)
    coverage_ratio, coverage_reason, coverage_pit = _coverage_inputs(request, as_of)
    security = request.security

    if request.prior_state is not None:
        _check_prior_state(request.prior_state, symbol, rows, request)

    features = bar_features(bars, len(bars) - 1) if bars else dict(_EMPTY_FEATURES)
    gates = _quality_gates(view, bars, security, context_usable, features)
    phase = label_phase(bars, gates)
    liquidity = label_liquidity(features)
    selection = label_selection(view["current_state"], phase, liquidity, bars)
    limit = limit_assessment(symbol, security if context_usable else SecurityContext(), features.get("pct_change"))
    entry = label_entry(selection, features, limit)
    position_event = label_position_event(request.position_state, symbol, request.cutoff, calendar, usable, bars, view,
                                          phase, security, context_usable)

    bench_usable: list[Observation] = []
    bench_availability: dict[str, Any] | None = None
    if request.benchmark_observations:
        if request.benchmark_symbol is None:
            raise LabelInputError("benchmark_symbol_required", "benchmark observations without benchmark_symbol")
        bench_rows = validate_observations(request.benchmark_observations, request.benchmark_symbol, request.synthetic, ROLE_BENCHMARK, calendar)
        bench_usable, bench_availability, bench_diag = select_usable(bench_rows, request.cutoff)
        bench_usable = [row for row in bench_usable if row.kind == "price"]
        diagnostics["benchmark"] = bench_diag
    elif request.benchmark_symbol is not None:
        validate_symbol(request.benchmark_symbol, request.synthetic, ROLE_BENCHMARK)
    regime = label_regime(bench_usable, request.cutoff.decision_date, coverage_ratio, coverage_reason)

    calendar_pit = _parse_datetime(calendar.available_at, "invalid_calendar") <= as_of
    strict = request.cutoff.mode == MODE_STRICT
    pit_facts = {
        "stock_bars": availability["all_consumed_available_at_cutoff"],
        "benchmark_bars": (bench_availability["all_consumed_available_at_cutoff"] if bench_availability else None),
        "security_context": (context_pit["status"] == "available") if security.has_non_unknown_facts() else None,
        "coverage": (coverage_pit["status"] == "available") if coverage_pit["ratio"] is not None or coverage_pit["evidence_ref"] else None,
        "calendar": calendar_pit,
    }
    strict_pit = strict and bool(usable) and all(v is not False for v in pit_facts.values())
    pit = {
        "mode": request.cutoff.mode,
        "strict_pit_eligible": strict_pit,
        "retrospective": not strict,
        "facts": pit_facts,
        "consumed_fact_classes": [k for k, v in pit_facts.items() if v is not None],
        "training_eligible": False,
        "training_eligible_reason": "M3-01-R2 draft policy; no independently reviewed case library",
        "provenance_kind": "declared_availability" if strict_pit else "retrospective_capture_not_point_in_time",
    }

    data_quality = sorted(set(gates + liquidity["reasons"] + regime["reasons"]))
    adjustment_uncertainty = not (context_usable and security.corporate_action_status in (CA_NONE_VERIFIED, CA_COMPLETE_KNOWN))
    if adjustment_uncertainty:
        data_quality.append("adjustment_uncertainty:corporate_action_status=" + (security.corporate_action_status if context_usable else "not_available_at_cutoff"))
    if not (context_usable and security.turnover_available):
        data_quality.append("turnover_unavailable")
    if not (context_usable and security.float_shares is not None):
        data_quality.append("float_shares_unavailable")
    if not (context_usable and security.listing_date is not None):
        data_quality.append("listing_date_unavailable")
    if security.has_non_unknown_facts() and not context_usable:
        data_quality.append("security_facts_not_available_at_cutoff")

    if request.synthetic:
        universe_block = {"in_frozen_universe": False, "universe_sha256": universe.sha256 if universe else None,
                          "counts_toward_case_library": False, "reason": "synthetic_fixture"}
    else:
        inside = symbol in universe.symbols
        universe_block = {"in_frozen_universe": inside, "universe_sha256": universe.sha256, "counts_toward_case_library": False,
                          "reason": "pending_review" if inside else "outside_frozen_universe_separate_decision"}

    stock_fp = input_fingerprint(usable)
    bench_fp = input_fingerprint(bench_usable) if bench_usable else None
    decision_inputs = {
        "stock_rows": stock_fp, "benchmark_symbol": request.benchmark_symbol if bench_usable else None, "benchmark_rows": bench_fp,
        "security_context": security.record(), "context_usable": context_usable,
        "coverage": coverage_pit, "calendar": calendar.fingerprint(), "universe": universe.sha256 if universe else None,
        "cutoff": request.cutoff.record(), "prior_state": request.prior_state.record() if request.prior_state else None,
        "position_state": request.position_state.record() if request.position_state else None, "synthetic": request.synthetic,
    }
    decision_fp = sha256_text(canonical_json(decision_inputs))
    source_refs = sorted({row.source_ref for row in usable} | {row.source_ref for row in bench_usable})
    record = {
        "schema": OUTPUT_SCHEMA, "namespace": NAMESPACE, "policy_id": POLICY_ID, "policy_version": POLICY_VERSION,
        "policy_hash": POLICY_HASH, "producer_sha256": producer_sha256(),
        "symbol": symbol, "role": ROLE_STOCK, "synthetic": bool(request.synthetic),
        "universe": universe_block,
        "cutoff": request.cutoff.record(),
        "split_role": split_role(request.cutoff.decision_date),
        "calendar": calendar.record(),
        "current_state": view["current_state"],
        "session_view": view,
        "input_availability": availability,
        "benchmark_availability": bench_availability,
        "context_availability": context_pit,
        "pit": pit,
        "provenance": {"input_fingerprint": stock_fp, "benchmark_fingerprint": bench_fp, "source_refs": source_refs,
                       "benchmark_symbol": request.benchmark_symbol if bench_usable else None,
                       "context_evidence_refs": list(security.evidence_refs), "coverage_evidence_ref": coverage_pit.get("evidence_ref"),
                       "calendar_source_ref": calendar.source_ref, "universe_source_ref": universe.source_ref if universe else None},
        "identity": {"decision_fingerprint": decision_fp, "decision_inputs": decision_inputs},
        "episode_id": episode_id(symbol, request.cutoff.decision_date, decision_fp),
        "security_context": security.record(),
        "features": features,
        "labels": {"phase": phase, "selection": selection, "entry": entry, "position_event": position_event,
                   "liquidity": liquidity, "regime": regime, "limit": limit},
        "data_quality": data_quality,
        "semantics": {"observable_behavioural_proxy": True, "hidden_actor_claim": False, "trade_recommendation": False,
                      "realized_return_claim": False, "adjustment_uncertainty": adjustment_uncertainty,
                      "strict_pit_eligible": strict_pit, "training_eligible": False},
        "review_only": True, "live_trading_enabled": False,
    }
    record["record_hash"] = record_hash(record)
    record["review_ledger"] = _empty_ledger(record)
    record["request_diagnostics"] = diagnostics
    return record


def _check_prior_state(prior: PriorState, symbol: str, rows: Sequence[Observation], request: LabelRequest) -> None:
    if prior.symbol != symbol or prior.policy_hash != POLICY_HASH:
        raise LabelInputError("prior_state_binding_mismatch", f"{prior.symbol}/{str(prior.policy_hash)[:12]}")
    if not (prior.decision_date < request.cutoff.decision_date):
        raise LabelInputError("prior_state_not_earlier", f"{prior.decision_date} >= {request.cutoff.decision_date}")
    if prior.phase not in PHASES:
        raise LabelInputError("prior_state_unknown_phase", prior.phase)
    earlier = Cutoff(prior.decision_date, prior.as_of, request.cutoff.mode)
    if earlier.as_of_dt() > request.cutoff.as_of_dt():
        raise LabelInputError("prior_state_not_earlier", f"prior as_of {prior.as_of} after cutoff as_of {request.cutoff.as_of}")
    replay = LabelRequest(symbol=symbol, observations=rows, cutoff=earlier, calendar=request.calendar, security=request.security,
                          synthetic=request.synthetic, universe=request.universe)
    recomputed = generate_labels(replay)
    if recomputed["labels"]["phase"]["label"] != prior.phase:
        raise LabelInputError("prior_state_inconsistent", f"offered {prior.phase}, recomputed {recomputed['labels']['phase']['label']} at {prior.decision_date}")
    if prior.episode_id is not None and prior.episode_id != recomputed["episode_id"]:
        raise LabelInputError("prior_state_inconsistent", f"episode_id {prior.episode_id} != recomputed {recomputed['episode_id']}")


def label_series(request: LabelRequest, decision_dates: Sequence[str]) -> list[dict[str, Any]]:
    """Evaluate the policy at several cutoffs with the request's own cutoff convention
    (as_of = session close + the same offset) and mode; each consumes only data <= its cutoff."""
    offset = timedelta(seconds=request.cutoff.convention_seconds())
    outputs = []
    for d in decision_dates:
        cutoff = Cutoff(d, (close_time(d) + offset).isoformat(), request.cutoff.mode)
        outputs.append(generate_labels(LabelRequest(
            symbol=request.symbol, observations=request.observations, cutoff=cutoff, calendar=request.calendar,
            security=request.security, benchmark_symbol=request.benchmark_symbol, benchmark_observations=request.benchmark_observations,
            universe_coverage_on_decision_date=request.universe_coverage_on_decision_date,
            synthetic=request.synthetic, universe=request.universe)))
    return outputs


# --------------------------------------------------------------------------- #
# Episodes and dependence                                                     #
# --------------------------------------------------------------------------- #


def build_episodes(outputs: Sequence[Mapping[str, Any]], calendar: SessionCalendar) -> list[dict[str, Any]]:
    """Group consecutive-session, same-phase records of one symbol into episodes.

    Every record is verified (record_hash, policy, mode/convention, calendar and
    universe identity).  A series gap or a phase change closes the episode; the
    minimum-duration rule records the cutoff at which it became known."""
    assert_policy_integrity()
    calendar = calendar.validated()
    index = calendar.index()
    min_sessions = _RULES["windows"]["min_episode_sessions"]
    if not outputs:
        return []
    verified = [verify_record(o) for o in outputs]
    symbols = {o["symbol"] for o in verified}
    if len(symbols) > 1:
        raise LabelInputError("mixed_symbols_in_series", ",".join(sorted(symbols)))
    dates = [o["cutoff"]["decision_date"] for o in verified]
    if len(set(dates)) != len(dates):
        raise LabelInputError("duplicate_decision_dates", "a series may contain one record per decision date")
    if any(b <= a for a, b in zip(dates, dates[1:])):
        raise LabelInputError("series_not_chronological", "decision dates must be strictly increasing")
    for key, name in (("mode", "mixed_modes_in_series"), ("convention", "mixed_conventions_in_series")):
        if len({o["cutoff"][key] for o in verified}) > 1:
            raise LabelInputError(name, key)
    if len({o["calendar"]["fingerprint"] for o in verified}) > 1 or verified[0]["calendar"]["fingerprint"] != calendar.fingerprint():
        raise LabelInputError("calendar_mismatch_in_series", calendar.fingerprint()[:12])
    if len({o["universe"]["universe_sha256"] for o in verified}) > 1 or len({o["synthetic"] for o in verified}) > 1:
        raise LabelInputError("mixed_universe_in_series", "records must share universe and synthetic flag")
    if any(d not in index for d in dates):
        raise LabelInputError("decision_date_not_a_session", "series date outside the calendar")

    episodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for out in verified:
        d = out["cutoff"]["decision_date"]
        phase = out["labels"]["phase"]["label"]
        selection = out["labels"]["selection"]["label"]
        continuous = current is not None and index[d] == index[current["end"]] + 1
        if current is not None and current["phase"] == phase and continuous:
            current["end"] = d
            current["sessions"] += 1
            current["member_episode_ids"].append(out["episode_id"])
            current["member_record_hashes"].append(out["record_hash"])
            if selection != current["selection_path"][-1]["selection"]:
                current["selection_path"].append({"date": d, "selection": selection})
            if selection == SELECTION_CANDIDATE:
                current["candidate_sessions"] += 1
            if current["sessions"] == min_sessions:
                current["min_duration_established_at"] = d
            continue
        if current is not None:
            current["closed_reason"] = "phase_change" if continuous else "series_gap"
            episodes.append(current)
        current = {"symbol": out["symbol"], "phase": phase, "start": d, "end": d, "sessions": 1,
                   "member_episode_ids": [out["episode_id"]], "member_record_hashes": [out["record_hash"]],
                   "selection_path": [{"date": d, "selection": selection}], "candidate_sessions": 1 if selection == SELECTION_CANDIDATE else 0,
                   "min_duration_established_at": d if min_sessions == 1 else None,
                   "synthetic": out["synthetic"], "policy_hash": out["policy_hash"], "policy_version": out["policy_version"],
                   "mode": out["cutoff"]["mode"], "convention": out["cutoff"]["convention"],
                   "calendar_fingerprint": out["calendar"]["fingerprint"], "universe_sha256": out["universe"]["universe_sha256"],
                   "split_role": out["split_role"]}
    if current is not None:
        current["closed_reason"] = None
        episodes.append(current)
    for ep in episodes:
        ep["selection_at_start"] = ep["selection_path"][0]["selection"]
        ep["selection_at_end"] = ep["selection_path"][-1]["selection"]
        ep["eligibility_changes"] = len(ep["selection_path"]) - 1
        ep["open_at_last_cutoff"] = ep["closed_reason"] is None
        ep["status"] = "open_censored" if ep["open_at_last_cutoff"] else "closed"
        ep["meets_min_sessions"] = ep["min_duration_established_at"] is not None
        ep["kind"] = {PHASE_INDETERMINATE: "ambiguous", PHASE_FAILED_MARKUP: "failed"}.get(ep["phase"], ep["phase"])
        ep["start_session_index"] = index[ep["start"]]
        ep["end_session_index"] = index[ep["end"]]
        ep["episode_key"] = sha256_text(canonical_json({"symbol": ep["symbol"], "phase": ep["phase"], "start": ep["start"],
                                                        "policy_hash": ep["policy_hash"], "first_member": ep["member_episode_ids"][0]}))[:32]
        ep["episode_content_hash"] = sha256_text(canonical_json(ep["member_record_hashes"]))
        ep["review"] = {"status": REVIEW_PENDING, "note": "episode review is recorded on member records' ledgers"}
        ep["counts_toward_case_library"] = False
    return episodes


def dependence_groups(episodes: Sequence[Mapping[str, Any]], phase: str = PHASE_ACCUMULATION,
                      include_synthetic: bool = False) -> dict[str, Any]:
    """Chain-connect same-symbol episodes whose session intervals overlap or lie within the
    dependence window of each other; each chain is one effective decision group."""
    window = _RULES["windows"]["dependence_window_sessions"]
    selected = [e for e in episodes if e["phase"] == phase and (include_synthetic or not e.get("synthetic"))]
    synthetic_excluded = sum(1 for e in episodes if e["phase"] == phase and e.get("synthetic") and not include_synthetic)
    for e in selected:
        if "start_session_index" not in e or "end_session_index" not in e:
            raise LabelInputError("episode_without_session_indices", e.get("episode_key", "?"))
    groups: list[dict[str, Any]] = []
    by_symbol: dict[str, list[Mapping[str, Any]]] = {}
    for e in sorted(selected, key=lambda x: (x["symbol"], x["start_session_index"], x["end_session_index"])):
        by_symbol.setdefault(e["symbol"], []).append(e)
    for symbol, eps in sorted(by_symbol.items()):
        chain: dict[str, Any] | None = None
        for e in eps:
            if chain is not None and e["start_session_index"] - chain["end_session_index"] <= window:
                chain["end_session_index"] = max(chain["end_session_index"], e["end_session_index"])
                chain["members"].append(e["episode_key"])
                continue
            if chain is not None:
                groups.append(chain)
            chain = {"symbol": symbol, "start_session_index": e["start_session_index"], "end_session_index": e["end_session_index"],
                     "members": [e["episode_key"]]}
        if chain is not None:
            groups.append(chain)
    real_groups = 0 if (include_synthetic and any(e.get("synthetic") for e in selected)) else len(groups)
    return {"phase": phase, "episodes_considered": len(selected), "synthetic_excluded": synthetic_excluded,
            "synthetic_included_for_arithmetic_only": include_synthetic, "dependence_window_sessions": window,
            "groups": groups, "effective_decision_groups": real_groups, "effective_decision_groups_arithmetic": len(groups)}


# --------------------------------------------------------------------------- #
# Matching                                                                    #
# --------------------------------------------------------------------------- #

_OUTCOME_FIELD = re.compile(r"^(outcome|future|forward|realized|max_return|min_return|close_return)")
_SUMMARY_FIELDS = ("episode_id", "record_hash", "symbol", "role", "decision_date", "policy_hash", "policy_version", "mode", "convention",
                   "selection", "phase", "liquidity_band", "regime", "amount_20_mean_cny", "synthetic", "in_frozen_universe",
                   "universe_sha256", "split_role", "current_state")


def _leak_check(record: Mapping[str, Any]) -> None:
    for key in record:
        if _OUTCOME_FIELD.match(str(key)):
            raise LabelInputError("outcome_leakage", f"field {key!r} is a later-known outcome and cannot enter matching")


def case_summary(output: Mapping[str, Any]) -> dict[str, Any]:
    """Compact cutoff-time view used for matching.  Full records are verified first;
    summaries must carry every matching field including record_hash."""
    _leak_check(output)
    if "labels" in output:
        out = verify_record(output)
        return {
            "episode_id": out["episode_id"], "record_hash": out["record_hash"], "symbol": out["symbol"], "role": out["role"],
            "decision_date": out["cutoff"]["decision_date"], "policy_hash": out["policy_hash"], "policy_version": out["policy_version"],
            "mode": out["cutoff"]["mode"], "convention": out["cutoff"]["convention"],
            "selection": out["labels"]["selection"]["label"], "phase": out["labels"]["phase"]["label"],
            "liquidity_band": out["labels"]["liquidity"]["band"], "regime": out["labels"]["regime"]["regime"],
            "amount_20_mean_cny": out["features"].get("amount_20_mean_cny"), "synthetic": out["synthetic"],
            "in_frozen_universe": out["universe"]["in_frozen_universe"], "universe_sha256": out["universe"]["universe_sha256"],
            "split_role": out["split_role"], "current_state": out["current_state"],
        }
    missing = [k for k in _SUMMARY_FIELDS if k not in output]
    if missing:
        raise LabelInputError("malformed_summary", "missing " + ",".join(missing))
    if not _is_bool(output["synthetic"]):
        raise LabelInputError("invalid_synthetic_flag", "summary synthetic flag must be bool")
    if not isinstance(output["record_hash"], str) or len(output["record_hash"]) != 64:
        raise LabelInputError("malformed_summary", "record_hash must be a 64-hex string")
    return {k: output[k] for k in _SUMMARY_FIELDS}


def match_controls(positive: Mapping[str, Any], pool: Sequence[Mapping[str, Any]],
                   purpose: str = PURPOSE_INITIAL_LIBRARY) -> dict[str, Any]:
    """Deterministic same-date control matching using cutoff-time information only.

    Controls: distinct other stocks with selection non_candidate on the same
    decision date, same mode/convention, same policy hash/version, same known
    liquidity band and known regime, same universe membership and synthetic
    flag, current state observed.  Identical duplicates collapse; conflicting
    duplicates are rejected.  The split purpose is enforced on admission."""
    assert_policy_integrity()
    m = _RULES["matching"]
    p = case_summary(positive)
    if p["selection"] != SELECTION_CANDIDATE:
        raise LabelInputError("positive_not_candidate", p["selection"])
    if p["role"] != ROLE_STOCK:
        raise LabelInputError("positive_not_a_stock", p["role"])
    if p["policy_hash"] != POLICY_HASH or p["policy_version"] != POLICY_VERSION:
        raise LabelInputError("policy_hash_mismatch", "positive was produced by another policy")
    if not p["synthetic"] and not p["in_frozen_universe"]:
        raise LabelInputError("outside_frozen_universe", p["symbol"])
    if p["liquidity_band"] == LIQUIDITY_UNKNOWN or p["regime"] == REGIME_UNKNOWN:
        raise LabelInputError("positive_context_unknown", f"band={p['liquidity_band']} regime={p['regime']}")
    guard_final_holdout([p], purpose)
    seen: dict[tuple[str, str], str] = {}
    candidates: dict[str, dict[str, Any]] = {}
    rejected: dict[str, int] = {}
    duplicates = 0
    for item in pool:
        c = case_summary(item)
        key = (c["symbol"], c["decision_date"])
        if key in seen:
            if seen[key] != c["record_hash"]:
                raise LabelInputError("conflicting_duplicate_control", f"{c['symbol']} {c['decision_date']}")
            duplicates += 1
            continue
        seen[key] = c["record_hash"]
        why = None
        if c["policy_hash"] != POLICY_HASH or c["policy_version"] != POLICY_VERSION:
            why = "policy_mismatch"
        elif c["symbol"] == p["symbol"]:
            why = "same_symbol"
        elif c["role"] != ROLE_STOCK:
            why = "not_a_stock"
        elif c["decision_date"] != p["decision_date"]:
            why = "different_decision_date"
        elif c["mode"] != p["mode"] or c["convention"] != p["convention"]:
            why = "cutoff_convention_mismatch"
        elif c["synthetic"] != p["synthetic"]:
            why = "synthetic_real_mixing"
        elif c["in_frozen_universe"] != p["in_frozen_universe"] or c["universe_sha256"] != p["universe_sha256"]:
            why = "universe_mismatch"
        elif c["current_state"] != CURRENT_OBSERVED:
            why = "control_current_state_not_observed"
        elif c["selection"] != m["control_selection_label"]:
            why = "not_non_candidate"
        elif c["liquidity_band"] != p["liquidity_band"] or c["liquidity_band"] == LIQUIDITY_UNKNOWN:
            why = "liquidity_band_mismatch_or_unknown"
        elif c["regime"] != p["regime"] or c["regime"] == REGIME_UNKNOWN:
            why = "regime_mismatch_or_unknown"
        elif c["split_role"] != p["split_role"]:
            why = "split_role_mismatch"
        if why:
            rejected[why] = rejected.get(why, 0) + 1
            continue
        if c["symbol"] in candidates:
            rejected["symbol_already_selected"] = rejected.get("symbol_already_selected", 0) + 1
            continue
        candidates[c["symbol"]] = c
    amt_p = p["amount_20_mean_cny"]
    ranked = sorted(candidates.values(), key=lambda c: (abs(math.log(c["amount_20_mean_cny"] / amt_p)) if amt_p and c["amount_20_mean_cny"] else float("inf"), c["symbol"]))
    chosen = ranked[: m["k_max"]]
    return {
        "positive_episode_id": p["episode_id"], "positive_record_hash": p["record_hash"], "decision_date": p["decision_date"],
        "purpose": purpose, "split_role": p["split_role"],
        "controls": [{"episode_id": c["episode_id"], "record_hash": c["record_hash"], "symbol": c["symbol"], "role": "matched_non_candidate"} for c in chosen],
        "control_count": len(chosen), "distinct_control_symbols": len(chosen),
        "unmatched": len(chosen) < m["k_min"], "k_min": m["k_min"], "k_max": m["k_max"],
        "identical_duplicates_collapsed": duplicates, "rejected_pool_counts": dict(sorted(rejected.items())),
        "matching_inputs": "cutoff-time only: same decision date, mode/convention, policy, band, regime, universe; ranked by |ln amount ratio|, symbol",
        "synthetic": p["synthetic"], "counts_toward_case_library": False,
    }


def control_reuse_counts(matches: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    unmatched = 0
    for match in matches:
        if match["unmatched"]:
            unmatched += 1
        for c in match["controls"]:
            counts[c["episode_id"]] = counts.get(c["episode_id"], 0) + 1
    return {"positives": len(matches), "unmatched_positives": unmatched, "distinct_controls": len(counts),
            "max_reuse": max(counts.values(), default=0), "reused_controls": sum(1 for v in counts.values() if v > 1)}


# --------------------------------------------------------------------------- #
# Reviews (append-only ledger; never fabricated by the generator)             #
# --------------------------------------------------------------------------- #

VERDICTS = ("positive", "negative", "ambiguous", "failed", "reject_data")
REVIEWER_KINDS = ("agent", "human")


@dataclass(frozen=True)
class ReviewRecord:
    reviewer_id: str
    reviewer_kind: str
    reviewed_at: str
    verdict: str
    evidence_refs: tuple[str, ...]
    execution_ref: str
    case_episode_id: str
    case_record_hash: str
    case_policy_hash: str
    synthetic: bool = False
    supersedes: str | None = None
    supersede_reason: str = ""
    notes: str = ""

    def validated(self) -> dict[str, Any]:
        if not isinstance(self.reviewer_id, str) or not self.reviewer_id:
            raise LabelInputError("missing_reviewer_id")
        if self.reviewer_kind not in REVIEWER_KINDS:
            raise LabelInputError("invalid_reviewer_kind", self.reviewer_kind)
        if self.verdict not in VERDICTS:
            raise LabelInputError("invalid_review_verdict", self.verdict)
        _parse_datetime(self.reviewed_at, "invalid_reviewed_at")
        refs = _str_tuple(self.evidence_refs, "review_without_evidence", allow_empty=False)
        if not isinstance(self.execution_ref, str) or not self.execution_ref:
            raise LabelInputError("review_without_execution_ref", "external execution/evidence reference required")
        for name in ("case_episode_id", "case_record_hash", "case_policy_hash"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise LabelInputError("review_without_case_binding", name)
        if not _is_bool(self.synthetic):
            raise LabelInputError("invalid_synthetic_flag", "review synthetic flag must be bool")
        if self.supersedes is not None and (not isinstance(self.supersedes, str) or not self.supersedes or not self.supersede_reason):
            raise LabelInputError("invalid_supersede", "supersedes needs the earlier entry hash and a reason")
        entry = {"reviewer_id": self.reviewer_id, "reviewer_kind": self.reviewer_kind, "reviewed_at": self.reviewed_at,
                 "verdict": self.verdict, "evidence_refs": list(refs), "execution_ref": self.execution_ref,
                 "case_episode_id": self.case_episode_id, "case_record_hash": self.case_record_hash,
                 "case_policy_hash": self.case_policy_hash, "synthetic": self.synthetic, "supersedes": self.supersedes,
                 "supersede_reason": self.supersede_reason, "notes": self.notes}
        entry["entry_hash"] = sha256_text(canonical_json(entry))
        return entry


def _empty_ledger(record: Mapping[str, Any]) -> dict[str, Any]:
    ledger = {"bound_episode_id": record["episode_id"], "bound_record_hash": record["record_hash"], "bound_policy_hash": record["policy_hash"],
              "status": REVIEW_PENDING, "entries": [], "reviewer_ids": [], "current_verdicts": {}, "agreement": None,
              "consensus_verdict": None, "approved": False, "reviewed_at": None,
              "independence_asserted_by_generator": False,
              "note": "two reviewer names never prove two review executions; the coordinator records actual individual reviews"}
    ledger["ledger_hash"] = _ledger_hash(ledger)
    return ledger


def _ledger_hash(ledger: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json({k: v for k, v in ledger.items() if k != "ledger_hash"}))


def review_status(ledger: Mapping[str, Any]) -> dict[str, Any]:
    current: dict[str, str] = {}
    superseded = {e["supersedes"] for e in ledger["entries"] if e.get("supersedes")}
    for e in ledger["entries"]:
        if e["entry_hash"] in superseded:
            continue
        current[e["reviewer_id"]] = e["verdict"]
    reviewers = sorted(current)
    verdicts = sorted(set(current.values()))
    if not reviewers:
        status, agreement, consensus = REVIEW_PENDING, None, None
    elif len(reviewers) < 2:
        status, agreement, consensus = REVIEW_SINGLE, None, None
    elif len(verdicts) == 1:
        status, agreement, consensus = REVIEW_INDEPENDENT, "agree", verdicts[0]
    else:
        status, agreement, consensus = REVIEW_DISPUTED, "disagree", None
    return {"status": status, "reviewer_ids": reviewers, "current_verdicts": dict(sorted(current.items())),
            "agreement": agreement, "consensus_verdict": consensus}


def attach_review(case: Mapping[str, Any], review: ReviewRecord) -> dict[str, Any]:
    """Return a new case with the review appended to its ledger; the label core is untouched."""
    assert_policy_integrity()
    verified = verify_record(case)
    entry = review.validated()
    ledger = copy.deepcopy(verified.get("review_ledger") or _empty_ledger(verified))
    if _ledger_hash(ledger) != ledger.get("ledger_hash"):
        raise LabelInputError("ledger_hash_mismatch", verified["episode_id"])
    if (entry["case_episode_id"], entry["case_record_hash"], entry["case_policy_hash"]) != (verified["episode_id"], verified["record_hash"], verified["policy_hash"]):
        raise LabelInputError("review_case_binding_mismatch", f"review bound to {entry['case_episode_id'][:12]}/{entry['case_record_hash'][:12]}")
    if entry["synthetic"] != verified["synthetic"]:
        raise LabelInputError("review_synthetic_flag_mismatch", "synthetic reviews only on synthetic cases and vice versa")
    hashes = {e["entry_hash"] for e in ledger["entries"]}
    if entry["entry_hash"] in hashes:
        raise LabelInputError("duplicate_review", entry["entry_hash"][:12])
    if entry["supersedes"] is not None:
        target = next((e for e in ledger["entries"] if e["entry_hash"] == entry["supersedes"]), None)
        if target is None or target["reviewer_id"] != entry["reviewer_id"]:
            raise LabelInputError("invalid_supersede", "can only supersede this reviewer's own earlier entry on this case")
    else:
        superseded = {x.get("supersedes") for x in ledger["entries"]}
        for e in ledger["entries"]:
            if e["reviewer_id"] != entry["reviewer_id"] or e["entry_hash"] in superseded:
                continue
            if e["verdict"] != entry["verdict"]:
                raise LabelInputError("conflicting_duplicate_review", f"{entry['reviewer_id']} already recorded {e['verdict']}; supersede explicitly")
            raise LabelInputError("duplicate_review", f"{entry['reviewer_id']} already recorded {e['verdict']}")
    ledger["entries"].append(entry)
    ledger.update(review_status(ledger))
    ledger["approved"] = False
    ledger["reviewed_at"] = max(e["reviewed_at"] for e in ledger["entries"])
    ledger["ledger_hash"] = _ledger_hash(ledger)
    updated = copy.deepcopy(verified)
    updated["review_ledger"] = ledger
    if "request_diagnostics" in case:
        updated["request_diagnostics"] = copy.deepcopy(case["request_diagnostics"])
    if record_hash(updated) != verified["record_hash"]:
        raise LabelInputError("record_hash_mismatch", "attaching a review must not change the label core")
    return updated


# --------------------------------------------------------------------------- #
# Library counting (fail closed)                                              #
# --------------------------------------------------------------------------- #


def admit_cases(cases: Sequence[Mapping[str, Any]], purpose: str = PURPOSE_INITIAL_LIBRARY) -> dict[str, Any]:
    """Partition verified records by split role for a declared purpose; never silently drop."""
    if purpose not in PURPOSES:
        raise LabelInputError("unknown_purpose", purpose)
    allowed = _PURPOSE_ALLOWED_ROLES[purpose]
    admitted, excluded = [], {}
    for case in cases:
        rec = verify_record(case)
        role = split_role(rec["cutoff"]["decision_date"])
        if role in allowed:
            admitted.append(rec)
        else:
            excluded[role] = excluded.get(role, 0) + 1
    return {"purpose": purpose, "admitted": admitted, "excluded_by_split_role": dict(sorted(excluded.items())), "allowed_roles": list(allowed)}


def library_counts(cases: Sequence[Mapping[str, Any]], matches: Sequence[Mapping[str, Any]], calendar: SessionCalendar,
                   purpose: str = PURPOSE_TARGET_COUNT) -> dict[str, Any]:
    """Counting contract: records != positives != qualified positives != effective groups."""
    assert_policy_integrity()
    admission = admit_cases(cases, purpose)
    admitted = admission["admitted"]
    guard_final_holdout(admitted, purpose)
    match_by_positive = {}
    for mt in matches:
        key = (mt["positive_episode_id"], mt["positive_record_hash"])
        if key in match_by_positive:
            raise LabelInputError("duplicate_match_record", mt["positive_episode_id"])
        match_by_positive[key] = mt
    counts = {"purpose": purpose, "records_total": len(cases), "records_admitted": len(admitted),
              "excluded_by_split_role": admission["excluded_by_split_role"],
              "records_synthetic": 0, "records_real": 0, "pending_review": 0, "single_review": 0, "disputed": 0,
              "independently_reviewed": 0, "positively_reviewed_episodes": 0, "qualified_positives": 0,
              "disqualified": {}, "matched_controls_total": 0}
    qualified_records = []
    for rec in admitted:
        if rec["synthetic"]:
            counts["records_synthetic"] += 1
        else:
            counts["records_real"] += 1
        ledger = rec.get("review_ledger") or {"entries": []}
        state = review_status(ledger)
        counts[{REVIEW_PENDING: "pending_review", REVIEW_SINGLE: "single_review", REVIEW_DISPUTED: "disputed", REVIEW_INDEPENDENT: "independently_reviewed"}[state["status"]]] += 1
        if state["status"] != REVIEW_INDEPENDENT or state["consensus_verdict"] != "positive":
            continue
        if any(e["synthetic"] for e in ledger["entries"]):
            _bump(counts["disqualified"], "synthetic_review")
            continue
        counts["positively_reviewed_episodes"] += 1
        why = None
        mt = match_by_positive.get((rec["episode_id"], rec["record_hash"]))
        if rec["synthetic"]:
            why = "synthetic_case"
        elif not rec["universe"]["in_frozen_universe"]:
            why = "outside_frozen_universe"
        elif rec["current_state"] != CURRENT_OBSERVED:
            why = "current_state_not_observed"
        elif rec["labels"]["selection"]["label"] != SELECTION_CANDIDATE:
            why = "selection_not_candidate"
        elif rec["pit"]["training_eligible"]:
            why = "training_eligible_must_be_false"
        elif mt is None:
            why = "no_match_record"
        elif mt["unmatched"] or mt["purpose"] != PURPOSE_INITIAL_LIBRARY:
            why = "unmatched_or_wrong_purpose"
        elif len({c["symbol"] for c in mt["controls"]}) < mt["k_min"]:
            why = "controls_not_distinct"
        if why:
            _bump(counts["disqualified"], why)
            continue
        counts["qualified_positives"] += 1
        counts["matched_controls_total"] += mt["control_count"]
        qualified_records.append(rec)
    episodes = []
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for rec in qualified_records:
        by_symbol.setdefault(rec["symbol"], []).append(rec)
    for symbol, recs in sorted(by_symbol.items()):
        episodes.extend(build_episodes(sorted(recs, key=lambda r: r["cutoff"]["decision_date"]), calendar))
    groups = dependence_groups(episodes, PHASE_ACCUMULATION)
    counts["effective_dependence_groups"] = groups["effective_decision_groups"]
    counts["target_min_reviewed_positives"] = _RULES["case_library"]["targets"]["min_reviewed_positives"]
    counts["target_met"] = counts["effective_dependence_groups"] >= counts["target_min_reviewed_positives"]
    counts["note"] = "qualified_positives require development-only admission, frozen-universe membership, observed decision session, candidate selection, non-synthetic independent positive review and 3-5 distinct matched controls"
    return counts


def _bump(table: dict[str, int], key: str) -> None:
    table[key] = table.get(key, 0) + 1


# --------------------------------------------------------------------------- #
# Later-known outcome annotation (separate from labels)                       #
# --------------------------------------------------------------------------- #


def annotate_outcome(case: Mapping[str, Any], later_observations: Sequence[Observation], later_cutoff: Cutoff,
                     calendar: SessionCalendar, horizon_sessions: int = 20) -> dict[str, Any]:
    """Compute what became known *after* the case cutoff.  Returned separately; never merged
    into the case labels and never usable for matching."""
    rec = verify_record(case)
    symbol = rec["symbol"]
    rows = validate_observations(later_observations, symbol, rec["synthetic"], ROLE_STOCK, calendar.validated())
    usable, availability, _diag = select_usable(rows, later_cutoff)
    if later_cutoff.decision_date <= rec["cutoff"]["decision_date"]:
        raise LabelInputError("outcome_cutoff_not_later", later_cutoff.decision_date)
    after = [r for r in usable if r.kind == "price" and r.trade_date > rec["cutoff"]["decision_date"]]
    window = after[:horizon_sessions]
    base = {"annotation_kind": "later_known_outcome", "not_a_label": True, "episode_id": rec["episode_id"],
            "record_hash": rec["record_hash"], "policy_hash": rec["policy_hash"], "later_cutoff": later_cutoff.record(),
            "input_availability": availability, "realized_return_claim": False, "adjustment_uncertainty": True}
    if not window:
        return {**base, "status": "pending_future_data", "sessions_observed": 0}
    ref = float(window[0].open)
    closes = [float(b.close) for b in window]
    return {**base, "status": "observed" if len(window) >= horizon_sessions else "partial", "sessions_observed": len(window),
            "horizon_sessions": horizon_sessions,
            "reference": {"basis": "next_session_open_unadjusted", "date": window[0].trade_date, "price": ref},
            "close_return_unadjusted": closes[-1] / ref - 1.0, "max_close_return_unadjusted": max(closes) / ref - 1.0,
            "min_low_return_unadjusted": min(float(b.low) for b in window) / ref - 1.0,
            "note": "unadjusted prices; corporate actions inside the horizon are not resolved; not a training target"}


# --------------------------------------------------------------------------- #
# Chronological protection, seed context, universe, policy export             #
# --------------------------------------------------------------------------- #


def split_role(decision_date: str) -> str:
    _parse_date(decision_date, "invalid_decision_date")
    s = _RULES["split_proposal"]
    for role in (SPLIT_DEVELOPMENT, SPLIT_VALIDATION, SPLIT_HOLDOUT):
        lo, hi = s[role]
        if lo <= decision_date <= hi:
            return role
    return SPLIT_OUTSIDE


def guard_final_holdout(records: Iterable[Mapping[str, Any]], purpose: str) -> dict[str, Any]:
    """Purpose allowlist; raise when records outside the purpose's allowed split roles are consumed."""
    if purpose not in PURPOSES:
        raise LabelInputError("unknown_purpose", f"{purpose!r} not in {PURPOSES}")
    allowed = _PURPOSE_ALLOWED_ROLES[purpose]
    roles: dict[str, int] = {}
    for rec in records:
        d = rec["cutoff"]["decision_date"] if "cutoff" in rec else rec["decision_date"]
        role = split_role(d)
        roles[role] = roles.get(role, 0) + 1
    if roles.get(SPLIT_HOLDOUT, 0) and SPLIT_HOLDOUT not in allowed:
        raise LabelInputError("final_holdout_consumed", f"purpose={purpose} touched {roles[SPLIT_HOLDOUT]} holdout records")
    disallowed = {r: n for r, n in roles.items() if r not in allowed}
    if disallowed:
        raise LabelInputError("split_role_not_admissible", f"purpose={purpose} touched {disallowed}")
    return {"purpose": purpose, "roles": dict(sorted(roles.items())), "allowed_roles": list(allowed), "holdout_protected": True}


def seed_context() -> list[dict[str, Any]]:
    return [dict(item, case_data_fabricated=False, reviewed=False) for item in _RULES["seed_context"]]


def assert_in_universe(symbol: str, universe: FrozenUniverse) -> None:
    if symbol not in universe.validated().symbols:
        raise LabelInputError("outside_frozen_universe", f"{symbol}: extension is a separate decision")


def policy_document() -> dict[str, Any]:
    """Machine-readable policy export: an isolated deep copy with its hash."""
    assert_policy_integrity()
    return {"policy": copy.deepcopy(_POLICY_SOURCE), "policy_hash": POLICY_HASH, "hash_rule": "sha256(canonical_json(policy))",
            "export_isolation": "mutating this copy never changes the live rules; live rules are re-hashed on every call"}


__all__ = [
    "NAMESPACE", "POLICY_ID", "POLICY_VERSION", "POLICY", "POLICY_HASH", "OUTPUT_SCHEMA", "SUPERSEDES", "PURPOSES",
    "MODE_STRICT", "MODE_RETROSPECTIVE", "PHASES", "CA_STATUSES",
    "LabelInputError", "Observation", "SessionCalendar", "FrozenUniverse", "Coverage", "Cutoff", "SecurityContext",
    "PriorState", "PositionState", "LabelRequest", "ReviewRecord",
    "assert_policy_integrity", "validate_observations", "validate_symbol", "validate_position_state", "instrument_role",
    "select_usable", "input_fingerprint", "session_view", "bar_features", "rule_phase", "label_phase", "label_selection",
    "label_entry", "label_position_event", "label_liquidity", "label_regime", "limit_assessment",
    "generate_labels", "label_series", "record_hash", "verify_record", "episode_id",
    "build_episodes", "dependence_groups", "match_controls", "control_reuse_counts", "case_summary",
    "review_status", "attach_review", "admit_cases", "library_counts", "annotate_outcome",
    "split_role", "guard_final_holdout", "seed_context", "assert_in_universe", "policy_document",
    "canonical_json", "sha256_text", "producer_sha256", "close_time", "infer_board",
]
