"""M3 label policy ``m3.labels`` — pure, cutoff-bound behavioural-proxy labels.

Isolated research namespace for milestone M3 (label specification and reviewed
case library).  It is deliberately independent of the legacy label producers
(``observable_structure_v1``, ``main_force_phase_replays`` phases,
``agent_learning_outcomes``): different namespace, different version line,
different storage contract.  Nothing here reads SQLite, the network, the
clock, or the ``app`` package.  Every function is deterministic in its inputs.

What the labels mean
--------------------
All phase / selection / trade-state labels are *observable behavioural proxies*
computed from daily OHLCVA up to an explicit decision cutoff.  They are not
evidence of a hidden controlling actor and they are not trade recommendations.
Outputs always carry ``review_only=True`` and ``live_trading_enabled=False``.

Causality
---------
A label at cutoff ``C`` consumes only observations whose historical close time
is at or before ``C.as_of`` and — in ``strict`` mode — whose declared
``available_at`` is also at or before ``C.as_of``.  ``retrospective`` mode
ignores availability for usability but records the violation and can never
claim strict point-in-time or training eligibility (the M2 corpus is
``strict_pit=false``: every row was captured on 2026-09-10).

Later-known outcomes are a separate annotation (``annotate_outcome``), never a
cutoff-time label input.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# --------------------------------------------------------------------------- #
# Namespace, version and the written policy (hashed)                          #
# --------------------------------------------------------------------------- #

NAMESPACE = "m3.labels"
POLICY_ID = "m3_label_policy"
POLICY_VERSION = "0.1.0-draft"
OUTPUT_SCHEMA = "m3.labels.output.v1"

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
PHASES = (
    PHASE_ACCUMULATION,
    PHASE_MARKUP,
    PHASE_DISTRIBUTION,
    PHASE_FAILED_MARKUP,
    PHASE_INDETERMINATE,
)

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

REGIME_BULL = "bull"
REGIME_BEAR = "bear"
REGIME_RANGE = "range"
REGIME_UNKNOWN = "unknown"

LIQUIDITY_UNKNOWN = "unknown"

REVIEW_PENDING = "pending_review"

# The written policy.  Every number below is a *provisional* rule choice taken
# from an existing, cited hypothesis (see LABEL_POLICY.md §4) and is subject to
# Codex review before adoption.  None was tuned against M2 prices.
POLICY: dict[str, Any] = {
    "namespace": NAMESPACE,
    "policy_id": POLICY_ID,
    "policy_version": POLICY_VERSION,
    "output_schema": OUTPUT_SCHEMA,
    "status": "draft_pending_codex_review",
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
        "trade_date_format": "YYYY-MM-DD (exchange session date)",
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
    },
    "cutoff": {
        "modes": list(CUTOFF_MODES),
        "usable_strict": "close_time(trade_date) <= as_of AND available_at <= as_of; as_of must lie within 72h after the decision session close",
        "usable_retrospective": "close_time(trade_date) <= as_of; availability violations counted, strict_pit_eligible=false",
        "wall_clock": "never used; cutoff must be explicit",
        "training_eligible": "always false in this policy version (no reviewed case library exists)",
    },
    "windows": {
        "warmup_required_sessions": 250,
        "short": 20,
        "medium": 60,
        "long": 120,
        "position": 250,
        "failed_markup_lookback": 20,
        "distribution_veto_lookback": 20,
        "dependence_window_sessions": 20,
        "period_match_tolerance_sessions": 10,
        "max_staleness_sessions": 1,
        "long_gap_sessions": 10,
        "min_episode_sessions": 3,
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
        "candidate": "phase == accumulation AND no rule-level distribution or failed_markup within distribution_veto_lookback AND liquidity band known AND no known corporate action in position window",
        "non_candidate": "phase in {markup, distribution, failed_markup} OR accumulation with recent distribution/failed_markup",
        "indeterminate": "phase indeterminate OR liquidity unknown OR corporate-action gate",
        "matched_non_candidate_role": "assigned only by match_controls, never by the selector",
    },
    "trade_rules": {
        "entry_signal": {"requires_selection": SELECTION_CANDIDATE, "close_gt_ma20": True, "volume_ratio_20_ge": 1.5,
                          "limit_like_possible_blocks": True, "limit_down_possible_blocks": True, "zero_volume_blocks": True,
                          "hypothesis": "dengzhan.has_forced_divergence:153 min_volume_ratio=1.5; dengzhan.SignalResult:12 three-state pass/fail/unknown"},
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.08,
        "max_holding_sessions": 20,
        "event_precedence": [EVENT_INVALIDATION, EVENT_STOP, EVENT_EXIT, EVENT_HOLD],
        "evaluation_basis": "close of the last usable bar at the cutoff; no intraday fill is claimed",
        "tradability": "always 'unverified' in this policy version",
        "hypothesis": "offhour._signal_exit_plan:6478-6479 stop_loss_pct=0.05 take_profit_pct=0.08 (defaults)",
    },
    "liquidity_bands_amount_20_cny": [
        {"band": "L1_thin", "lt": 3.0e7},
        {"band": "L2_low", "lt": 1.0e8},
        {"band": "L3_mid", "lt": 5.0e8},
        {"band": "L4_deep", "lt": None},
    ],
    "regime_rules": {
        "benchmark_required_sessions": 60,
        "bull": "close > ma60 AND return_60 > +0.05",
        "bear": "close < ma60 AND return_60 < -0.05",
        "range": "otherwise",
        "unknown": "benchmark missing/insufficient, benchmark bar missing on decision date, or universe coverage on decision date < 0.90",
        "universe_coverage_min": 0.90,
    },
    "limit_thresholds_pct": {
        "main": 9.8, "st": 4.8, "chinext": 19.5, "star": 19.5, "bse": 29.0,
        "hypothesis": "app/data/price_limits.py:31-37 DEFAULT_LIMIT_UP_THRESHOLDS (re-declared; not imported)",
        "st_unknown_rule": "when ST status is unknown the lowest plausible threshold (st) is used for main-board codes; limit-like is then 'possible', not 'confirmed'",
    },
    "corporate_actions": {
        "status_values": ["unknown", "none_verified", "known"],
        "unknown_rule": "returns and positions carry adjustment_uncertainty=true; labels are still produced; no realized-return claim",
        "known_in_window_rule": "a known ex-date inside the position window makes phase indeterminate (reason known_corporate_action_in_window)",
        "smooth_chart_rule": "absence of a visible gap never proves absence of a corporate action",
    },
    "scope_exceptions": [
        {"symbol": "BJ920006", "trade_date": "2023-12-04", "kind": "bse_block_trade_total_scope_interpretation",
         "handling": "volume and amount of this bar are excluded from volume-ratio means; if it is the decision bar, volume_ratio_20 is None",
         "reference": "M2_FINAL_ACCEPTANCE_20260910.md §5.3"},
    ],
    "matching": {
        "k_min": 3, "k_max": 5,
        "same_period": "abs(session_index difference) <= period_match_tolerance_sessions, cutoff dates only",
        "same_liquidity_band": True,
        "same_broad_regime": True,
        "different_symbol": True,
        "control_selection_label": SELECTION_NON_CANDIDATE,
        "ranking": "(|session distance|, |ln(amount_20 ratio)|, symbol) ascending; deterministic",
        "outcome_fields_forbidden": True,
    },
    "case_library": {
        "episode_id": "sha256(canonical{namespace, policy_hash, symbol, decision_date, input_fingerprint})[:32]",
        "input_fingerprint": "sha256(canonical list of consumed observations <= cutoff)",
        "review_status_at_generation": REVIEW_PENDING,
        "independent_review": "at least two distinct reviewer_ids of kind 'agent' or 'human' with recorded verdicts; disagreement is preserved as 'disputed'",
        "targets": {"min_reviewed_positives": 50, "controls_per_positive": [3, 5]},
        "counting": "effective decision dates = symbol groups separated by more than dependence_window_sessions; synthetic never counts",
    },
    "split_proposal": {
        "status": "proposal_requires_codex_review",
        "development": ["2023-09-04", "2025-03-31"],
        "validation": ["2025-04-01", "2025-12-31"],
        "final_holdout": ["2026-01-01", "2026-09-04"],
        "rule": "final_holdout may not be used for rule/threshold selection or target counting",
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


POLICY_HASH = sha256_text(canonical_json(POLICY))


_PRODUCER_CACHE: dict[str, str] = {}


def producer_sha256() -> str:
    """SHA-256 of this module's own bytes (provenance of the generator)."""
    if "sha256" not in _PRODUCER_CACHE:
        _PRODUCER_CACHE["sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return _PRODUCER_CACHE["sha256"]


# --------------------------------------------------------------------------- #
# Errors and input records                                                    #
# --------------------------------------------------------------------------- #


class LabelInputError(ValueError):
    """Fail-closed input rejection.  ``code`` is a stable reason identifier."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


_REAL_SYMBOL = re.compile(POLICY["input_contract"]["symbol_pattern_real"])
_SYN_SYMBOL = re.compile(POLICY["input_contract"]["symbol_pattern_synthetic"])
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


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


def close_time(trade_date: str) -> datetime:
    """Historical session close of ``trade_date`` (15:00 Asia/Shanghai)."""
    d = _parse_date(trade_date, "invalid_trade_date")
    h, m, s = (int(x) for x in SESSION_CLOSE_LOCAL.split(":"))
    return datetime(d.year, d.month, d.day, h, m, s, tzinfo=SESSION_TZ)


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
        kind = row.get("kind", "price")
        return cls(
            symbol=row.get("symbol"), trade_date=row.get("trade_date"), kind=kind,
            available_at=row.get("available_at"), source_ref=row.get("source_ref"),
            open=row.get("open"), high=row.get("high"), low=row.get("low"), close=row.get("close"),
            volume=row.get("volume"), amount=row.get("amount"),
            adjustment_mode=row.get("adjustment_mode", "none"), volume_unit=row.get("volume_unit", "share"),
        )

    def record(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol, "trade_date": self.trade_date, "kind": self.kind,
            "available_at": self.available_at, "source_ref": self.source_ref,
            "open": self.open, "high": self.high, "low": self.low, "close": self.close,
            "volume": self.volume, "amount": self.amount,
            "adjustment_mode": self.adjustment_mode, "volume_unit": self.volume_unit,
        }


@dataclass(frozen=True)
class Cutoff:
    decision_date: str
    as_of: str
    mode: str = MODE_STRICT

    def as_of_dt(self) -> datetime:
        return _parse_datetime(self.as_of, "invalid_cutoff_as_of")

    def record(self) -> dict[str, Any]:
        return {"decision_date": self.decision_date, "as_of": self.as_of, "mode": self.mode}


@dataclass(frozen=True)
class SecurityContext:
    """Per-symbol facts that are *not* derivable from OHLCVA.  Unknown stays unknown."""

    listing_date: str | None = None
    name: str | None = None
    st_status: str = "unknown"  # "unknown" | "st" | "not_st"
    corporate_action_status: str = "unknown"  # "unknown" | "none_verified" | "known"
    known_ex_dates: tuple[str, ...] = ()
    float_shares: float | None = None
    turnover_available: bool = False

    def record(self) -> dict[str, Any]:
        return {
            "listing_date": self.listing_date, "name": self.name, "st_status": self.st_status,
            "corporate_action_status": self.corporate_action_status, "known_ex_dates": list(self.known_ex_dates),
            "float_shares": self.float_shares, "turnover_available": self.turnover_available,
        }


@dataclass(frozen=True)
class PriorState:
    """A phase label produced earlier by this policy, offered as an input.

    It is bound to the earlier cutoff (decision_date + as_of), the symbol and the
    policy hash, and is re-derived from the offered data before it is trusted."""

    symbol: str
    decision_date: str
    as_of: str
    policy_hash: str
    phase: str


@dataclass(frozen=True)
class PositionState:
    """A hypothetical review-only position opened at an earlier cutoff."""

    symbol: str
    policy_hash: str
    entry_decision_date: str
    reference_date: str
    reference_price: float


@dataclass(frozen=True)
class LabelRequest:
    symbol: str
    observations: Sequence[Observation]
    cutoff: Cutoff
    security: SecurityContext = field(default_factory=SecurityContext)
    benchmark_symbol: str | None = None
    benchmark_observations: Sequence[Observation] = ()
    universe_coverage_on_decision_date: float | None = None
    prior_state: PriorState | None = None
    position_state: PositionState | None = None
    synthetic: bool = False
    frozen_universe: frozenset[str] | None = None


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


def _scope_exception(symbol: str, trade_date: str) -> dict[str, Any] | None:
    for item in POLICY["scope_exceptions"]:
        if item["symbol"] == symbol and item["trade_date"] == trade_date:
            return item
    return None


def validate_symbol(symbol: Any, synthetic: bool) -> str:
    if not isinstance(symbol, str):
        raise LabelInputError("invalid_symbol", repr(symbol))
    if synthetic:
        if not _SYN_SYMBOL.match(symbol):
            raise LabelInputError("synthetic_symbol_pattern", f"synthetic inputs must use SYN###### symbols: {symbol}")
        return symbol
    if not _REAL_SYMBOL.match(symbol):
        raise LabelInputError("invalid_symbol", symbol)
    return symbol


def validate_observations(observations: Iterable[Observation], symbol: str, synthetic: bool) -> list[Observation]:
    """Reject wrong identity, duplicates, unsorted input, non-finite/bool numerics,
    invalid prices/volumes/amounts, impossible availability and unknown units."""
    rows = list(observations)
    if not rows:
        raise LabelInputError("no_observations", symbol)
    validate_symbol(symbol, synthetic)
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
        if row.kind not in POLICY["input_contract"]["observation_kinds"]:
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
        if row.adjustment_mode not in POLICY["input_contract"]["adjustment_mode_accepted"]:
            raise LabelInputError("unsupported_adjustment_mode", repr(row.adjustment_mode))
        if row.volume_unit not in POLICY["input_contract"]["volume_unit_accepted"]:
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


# --------------------------------------------------------------------------- #
# Cutoff selection                                                            #
# --------------------------------------------------------------------------- #


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
    """Return (usable rows in order, availability summary of the *consumed* rows, request diagnostics).

    The availability summary depends only on the consumed rows (so it is invariant
    to suffix truncation/mutation); the diagnostics describe what was offered.
    """
    as_of = validate_cutoff(cutoff)
    usable: list[Observation] = []
    excluded_after_cutoff = 0
    excluded_late_availability = 0
    violations_consumed = 0
    max_available_at: datetime | None = None
    for row in rows:
        ct = close_time(row.trade_date)
        avail = _parse_datetime(row.available_at, "invalid_available_at")
        if ct > as_of or row.trade_date > cutoff.decision_date:
            excluded_after_cutoff += 1
            continue
        if avail > as_of:
            if cutoff.mode == MODE_STRICT:
                excluded_late_availability += 1
                continue
            violations_consumed += 1
        usable.append(row)
        if max_available_at is None or avail > max_available_at:
            max_available_at = avail
    strict_ok = cutoff.mode == MODE_STRICT and bool(usable)
    summary = {
        "mode": cutoff.mode,
        "rows_consumed": len(usable),
        "availability_violations_consumed": violations_consumed,
        "max_trade_date_consumed": usable[-1].trade_date if usable else None,
        "max_available_at_consumed": max_available_at.isoformat() if max_available_at else None,
        "strict_pit_eligible": strict_ok,
        "retrospective": cutoff.mode == MODE_RETROSPECTIVE,
        "training_eligible": False,
        "training_eligible_reason": "M3-01 draft policy; no independently reviewed case library",
        "provenance_kind": "declared_availability" if strict_ok else "retrospective_capture_not_point_in_time",
    }
    diagnostics = {
        "rows_offered": len(rows),
        "rows_excluded_after_cutoff": excluded_after_cutoff,
        "rows_excluded_late_availability": excluded_late_availability,
    }
    return usable, summary, diagnostics


def input_fingerprint(usable: Sequence[Observation]) -> str:
    return sha256_text(canonical_json([row.record() for row in usable]))


# --------------------------------------------------------------------------- #
# Features (pure arithmetic over the usable window)                           #
# --------------------------------------------------------------------------- #


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _volume_for_ratio(bar: Observation) -> float | None:
    """Volume usable in ratio means: None for scope exceptions and zero-volume sessions."""
    if _scope_exception(bar.symbol, bar.trade_date) is not None:
        return None
    if bar.volume is None or float(bar.volume) <= 0:
        return None
    return float(bar.volume)


def bar_features(bars: Sequence[Observation], index: int) -> dict[str, Any]:
    """Features for the price bar at ``bars[index]`` using bars[:index+1] only."""
    w = POLICY["windows"]
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
    position = None
    high_pos = None
    if n >= pos_window:
        lo = min(lows[-pos_window:])
        hi = max(highs[-pos_window:])
        high_pos = hi
        position = (close - lo) / (hi - lo) if hi > lo else None
    amounts = [float(b.amount) for b in bars[max(0, index - w["short"] + 1) : index + 1]
               if _scope_exception(b.symbol, b.trade_date) is None]
    amount_20 = _mean(amounts) if n >= w["short"] and len(amounts) >= w["short"] // 2 else None
    lookback_high = max(highs[-w["failed_markup_lookback"] :]) if n >= w["failed_markup_lookback"] else None
    return {
        "trade_date": bar.trade_date,
        "close": close,
        "prev_close": prev_close,
        "pct_change": (close / prev_close - 1.0) if prev_close else None,
        "close_to_high": close / float(bar.high) if float(bar.high) > 0 else None,
        "range_pct": (float(bar.high) - float(bar.low)) / prev_close if prev_close else None,
        "return_20": ret(w["short"]),
        "return_60": ret(w["medium"]),
        "return_120": ret(w["long"]),
        "volume_ratio_20": volume_ratio,
        "volume_ratio_20_known_days": len(vols_known),
        "zero_volume_session": float(bar.volume) == 0,
        "ma20": ma20,
        "ma60": ma60,
        "ma_spread_20_60": ma_spread,
        "position_250": position,
        "high_250": high_pos,
        "drawdown_from_lookback_high": (close / lookback_high - 1.0) if lookback_high else None,
        "amount_20_mean_cny": amount_20,
        "bars_available": n,
        "scope_exception_on_bar": _scope_exception(bar.symbol, bar.trade_date) is not None,
    }


def _markup_rule(f: Mapping[str, Any]) -> bool:
    r = POLICY["phase_rules"]["markup"]
    vr = f.get("volume_ratio_20")
    if vr is None:
        return False
    r20, r60 = f.get("return_20"), f.get("return_60")
    return ((r20 is not None and r20 > r["return_20_gt"]) or (r60 is not None and r60 > r["or_return_60_gt"])) and vr > r["volume_ratio_20_gt"]


def _distribution_rule(f: Mapping[str, Any]) -> bool:
    r = POLICY["phase_rules"]["distribution"]
    pos, vr, c2h, r20 = f.get("position_250"), f.get("volume_ratio_20"), f.get("close_to_high"), f.get("return_20")
    if pos is None or vr is None or c2h is None:
        return False
    rejection = c2h < r["close_to_high_lt"] or (r20 is not None and r20 < r["or_return_20_lt"])
    return pos > r["position_250_gt"] and vr > r["volume_ratio_20_gt"] and rejection


def _accumulation_rule(f: Mapping[str, Any]) -> bool:
    r = POLICY["phase_rules"]["accumulation"]
    pos, spread, r120 = f.get("position_250"), f.get("ma_spread_20_60"), f.get("return_120")
    if pos is None or spread is None or r120 is None:
        return False
    return pos < r["position_250_lt"] and spread < r["ma_spread_20_60_lt"] and r120 < r["return_120_lt"]


# --------------------------------------------------------------------------- #
# Label families                                                              #
# --------------------------------------------------------------------------- #


def _quality_gates(usable: Sequence[Observation], bars: Sequence[Observation], cutoff: Cutoff,
                   security: SecurityContext, features: Mapping[str, Any]) -> list[str]:
    """Reasons that force phase=indeterminate.  Unknown is never zero."""
    w = POLICY["windows"]
    reasons: list[str] = []
    if not bars:
        return ["no_price_bars_before_cutoff"]
    if features["bars_available"] < w["warmup_required_sessions"]:
        reasons.append(f"insufficient_warmup:{features['bars_available']}<{w['warmup_required_sessions']}")
    last = usable[-1]
    if last.kind == "full_day_suspension":
        reasons.append("suspension_on_last_observation")
    # staleness: observations after the last price bar, or decision date beyond the last observation
    last_bar_date = bars[-1].trade_date
    trailing = [row for row in usable if row.trade_date > last_bar_date]
    if len(trailing) > w["max_staleness_sessions"]:
        reasons.append(f"stale_last_bar:{len(trailing)}_sessions_without_price")
    decision = _parse_date(cutoff.decision_date, "invalid_cutoff_decision_date")
    if (decision - _parse_date(last_bar_date, "invalid_trade_date")).days > 7:
        reasons.append("stale_last_bar:decision_date_more_than_7_days_after_last_price")
    # long gaps between consecutive price bars inside the position window (suspensions or missing data)
    window_bars = bars[-w["position"] :]
    gap_dates = [_parse_date(b.trade_date, "invalid_trade_date") for b in window_bars]
    worst_gap = max(((b - a).days for a, b in zip(gap_dates, gap_dates[1:])), default=0)
    if worst_gap > w["long_gap_sessions"] * 2:  # calendar days; ~10 sessions
        reasons.append(f"long_gap_in_window:{worst_gap}_calendar_days")
    susp_in_window = sum(1 for row in usable if row.kind == "full_day_suspension" and row.trade_date >= window_bars[0].trade_date)
    if susp_in_window > w["long_gap_sessions"]:
        reasons.append(f"many_suspensions_in_window:{susp_in_window}")
    if security.corporate_action_status == "known":
        first_in_window = window_bars[0].trade_date
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
    lookback = POLICY["windows"]["failed_markup_lookback"]
    features = bar_features(bars, index)
    markup_seen = any(_markup_rule(bar_features(bars, i)) for i in range(max(0, index - lookback), index))
    if _distribution_rule(features):
        return {"label": PHASE_DISTRIBUTION, "rule": "distribution", "reasons": ["high_position_volume_rejection"], "markup_within_lookback": markup_seen}
    if _markup_rule(features):
        return {"label": PHASE_MARKUP, "rule": "markup", "reasons": ["return_expansion_with_volume"], "markup_within_lookback": markup_seen}
    dd = features.get("drawdown_from_lookback_high")
    if markup_seen and dd is not None and dd <= POLICY["phase_rules"]["failed_markup"]["drawdown_from_lookback_high_le"]:
        return {"label": PHASE_FAILED_MARKUP, "rule": "failed_markup", "reasons": ["prior_markup_then_drawdown_at_cutoff"], "markup_within_lookback": True}
    if _accumulation_rule(features):
        return {"label": PHASE_ACCUMULATION, "rule": "accumulation", "reasons": ["range_bound_converged_averages"], "markup_within_lookback": markup_seen}
    return {"label": PHASE_INDETERMINATE, "rule": "no_rule_matched", "reasons": ["no_rule_matched"], "markup_within_lookback": markup_seen}


def label_phase(bars: Sequence[Observation], features: Mapping[str, Any], gate_reasons: Sequence[str]) -> dict[str, Any]:
    """Quality gates first (unknown is never zero), then the rule precedence."""
    if gate_reasons:
        return {"label": PHASE_INDETERMINATE, "rule": "quality_gate", "reasons": list(gate_reasons), "markup_within_lookback": None}
    return rule_phase(bars, len(bars) - 1)


def label_liquidity(features: Mapping[str, Any]) -> dict[str, Any]:
    amount = features.get("amount_20_mean_cny")
    if amount is None:
        return {"band": LIQUIDITY_UNKNOWN, "amount_20_mean_cny": None, "reasons": ["amount_20_unavailable"]}
    for item in POLICY["liquidity_bands_amount_20_cny"]:
        if item["lt"] is None or amount < item["lt"]:
            return {"band": item["band"], "amount_20_mean_cny": amount, "reasons": []}
    return {"band": LIQUIDITY_UNKNOWN, "amount_20_mean_cny": amount, "reasons": ["band_table_exhausted"]}


def label_regime(benchmark_bars: Sequence[Observation], decision_last_bar_date: str | None,
                 universe_coverage: float | None) -> dict[str, Any]:
    r = POLICY["regime_rules"]
    reasons: list[str] = []
    if universe_coverage is not None and universe_coverage < r["universe_coverage_min"]:
        reasons.append(f"market_wide_missingness:{universe_coverage:.3f}")
    if len(benchmark_bars) < r["benchmark_required_sessions"]:
        reasons.append(f"benchmark_insufficient:{len(benchmark_bars)}<{r['benchmark_required_sessions']}")
    if decision_last_bar_date is not None and benchmark_bars and benchmark_bars[-1].trade_date != decision_last_bar_date:
        reasons.append("benchmark_bar_missing_on_decision_bar_date")
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
    """Rule-only distribution / failed-markup phases among the previous lookback bars."""
    lookback = POLICY["windows"]["distribution_veto_lookback"]
    index = len(bars) - 1
    found: set[str] = set()
    for i in range(max(0, index - lookback), index):
        label = rule_phase(bars, i)["label"]
        if label in (PHASE_DISTRIBUTION, PHASE_FAILED_MARKUP):
            found.add(label)
    return sorted(found)


def label_selection(phase: Mapping[str, Any], liquidity: Mapping[str, Any], bars: Sequence[Observation]) -> dict[str, Any]:
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
    thresholds = POLICY["limit_thresholds_pct"]
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
    r = POLICY["trade_rules"]["entry_signal"]
    base = {"tradability": "unverified",
            "execution": {"legal_next_session": "unknown", "basis": "next-session open/limit/suspension state is not observable at the cutoff"}}
    if selection["label"] == SELECTION_INDETERMINATE:
        return {"label": ENTRY_INDETERMINATE, "reasons": ["selection_indeterminate"], **base}
    reasons: list[str] = []
    if selection["label"] != r["requires_selection"]:
        reasons.append("not_a_candidate")
    if features.get("ma20") is None or features["close"] <= features["ma20"]:
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


def label_position_event(position: PositionState | None, symbol: str, cutoff: Cutoff, bars: Sequence[Observation],
                         phase: Mapping[str, Any]) -> dict[str, Any]:
    t = POLICY["trade_rules"]
    if position is None:
        return {"label": EVENT_NO_TRADE, "reasons": ["no_open_position_state"], "reference_price": None, "holding_sessions": None}
    if position.symbol != symbol or position.policy_hash != POLICY_HASH:
        raise LabelInputError("position_state_binding_mismatch", f"{position.symbol}/{position.policy_hash[:12]} vs {symbol}/{POLICY_HASH[:12]}")
    if not (position.entry_decision_date < cutoff.decision_date) or position.reference_date > cutoff.decision_date:
        raise LabelInputError("position_state_not_earlier", f"entry {position.entry_decision_date} ref {position.reference_date} cutoff {cutoff.decision_date}")
    if not _is_number(position.reference_price) or position.reference_price <= 0:
        raise LabelInputError("position_state_invalid_reference_price", repr(position.reference_price))
    if not bars:
        return {"label": EVENT_HOLD, "reasons": ["no_price_bar_at_cutoff"], "reference_price": position.reference_price, "holding_sessions": None}
    close = float(bars[-1].close)
    holding = sum(1 for b in bars if position.reference_date < b.trade_date <= cutoff.decision_date)
    ref = float(position.reference_price)
    if phase["label"] in (PHASE_DISTRIBUTION, PHASE_FAILED_MARKUP):
        label, reasons = EVENT_INVALIDATION, [f"phase_{phase['label']}_at_cutoff"]
    elif close <= ref * (1.0 - t["stop_loss_pct"]):
        label, reasons = EVENT_STOP, [f"close_le_reference_minus_{t['stop_loss_pct']}"]
    elif close >= ref * (1.0 + t["take_profit_pct"]):
        label, reasons = EVENT_EXIT, [f"close_ge_reference_plus_{t['take_profit_pct']}"]
    elif holding >= t["max_holding_sessions"]:
        label, reasons = EVENT_EXIT, [f"holding_sessions_ge_{t['max_holding_sessions']}"]
    else:
        label, reasons = EVENT_HOLD, ["no_event_rule_triggered"]
    return {"label": label, "reasons": reasons, "reference_price": ref, "holding_sessions": holding,
            "close_at_cutoff": close, "evaluation_basis": t["evaluation_basis"]}


# --------------------------------------------------------------------------- #
# Generator                                                                   #
# --------------------------------------------------------------------------- #


def episode_id(symbol: str, decision_date: str, fingerprint: str) -> str:
    return sha256_text(canonical_json({"namespace": NAMESPACE, "policy_hash": POLICY_HASH, "symbol": symbol,
                                       "decision_date": decision_date, "input_fingerprint": fingerprint}))[:32]


def _universe_check(symbol: str, request: LabelRequest) -> dict[str, Any]:
    if request.synthetic:
        return {"in_frozen_universe": False, "counts_toward_case_library": False, "reason": "synthetic_fixture"}
    if request.frozen_universe is None:
        return {"in_frozen_universe": None, "counts_toward_case_library": False, "reason": "universe_not_supplied"}
    inside = symbol in request.frozen_universe
    return {"in_frozen_universe": inside, "counts_toward_case_library": False,
            "reason": "pending_review" if inside else "outside_frozen_universe_separate_decision"}


def generate_labels(request: LabelRequest) -> dict[str, Any]:
    """Produce the full pending-review label record for one symbol at one cutoff."""
    symbol = validate_symbol(request.symbol, request.synthetic)
    rows = validate_observations(request.observations, symbol, request.synthetic)
    usable, availability, diagnostics = select_usable(rows, request.cutoff)
    bars = [row for row in usable if row.kind == "price"]
    fingerprint = input_fingerprint(usable)

    if request.prior_state is not None:
        _check_prior_state(request.prior_state, symbol, rows, request)

    if bars:
        features = bar_features(bars, len(bars) - 1)
    else:
        features = {"bars_available": 0, "close": None, "ma20": None, "volume_ratio_20": None, "pct_change": None,
                    "zero_volume_session": None, "amount_20_mean_cny": None, "scope_exception_on_bar": False}
    gates = _quality_gates(usable, bars, request.cutoff, request.security, features) if bars else ["no_price_bars_before_cutoff"]
    phase = label_phase(bars, features, gates)
    liquidity = label_liquidity(features)
    selection = label_selection(phase, liquidity, bars)
    limit = limit_assessment(symbol, request.security, features.get("pct_change"))
    entry = label_entry(selection, features, limit)
    position_event = label_position_event(request.position_state, symbol, request.cutoff, bars, phase)

    bench_usable: list[Observation] = []
    bench_availability: dict[str, Any] | None = None
    if request.benchmark_observations:
        if request.benchmark_symbol is None:
            raise LabelInputError("benchmark_symbol_required", "benchmark observations without benchmark_symbol")
        bench_rows = validate_observations(request.benchmark_observations, request.benchmark_symbol, request.synthetic)
        bench_usable, bench_availability, bench_diagnostics = select_usable(bench_rows, request.cutoff)
        bench_usable = [row for row in bench_usable if row.kind == "price"]
        diagnostics["benchmark"] = bench_diagnostics
    regime = label_regime(bench_usable, bars[-1].trade_date if bars else None, request.universe_coverage_on_decision_date)

    data_quality = sorted(set(gates + liquidity["reasons"] + regime["reasons"]))
    adjustment_uncertainty = request.security.corporate_action_status != "none_verified"
    if adjustment_uncertainty:
        data_quality.append("adjustment_uncertainty:corporate_action_status=" + request.security.corporate_action_status)
    if not request.security.turnover_available:
        data_quality.append("turnover_unavailable")
    if request.security.float_shares is None:
        data_quality.append("float_shares_unavailable")
    if request.security.listing_date is None:
        data_quality.append("listing_date_unavailable")

    source_refs = sorted({row.source_ref for row in usable} | {row.source_ref for row in bench_usable})
    record = {
        "schema": OUTPUT_SCHEMA,
        "namespace": NAMESPACE,
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "policy_hash": POLICY_HASH,
        "producer_sha256": producer_sha256(),
        "symbol": symbol,
        "synthetic": bool(request.synthetic),
        "universe": _universe_check(symbol, request),
        "cutoff": request.cutoff.record(),
        "input_availability": availability,
        "benchmark_availability": bench_availability,
        "provenance": {"input_fingerprint": fingerprint, "source_refs": source_refs,
                       "benchmark_symbol": request.benchmark_symbol if bench_usable else None},
        "episode_id": episode_id(symbol, request.cutoff.decision_date, fingerprint),
        "security_context": request.security.record(),
        "features": features,
        "labels": {
            "phase": phase,
            "selection": selection,
            "entry": entry,
            "position_event": position_event,
            "liquidity": liquidity,
            "regime": regime,
            "limit": limit,
        },
        "data_quality": data_quality,
        "semantics": {
            "observable_behavioural_proxy": True,
            "hidden_actor_claim": False,
            "trade_recommendation": False,
            "realized_return_claim": False,
            "adjustment_uncertainty": adjustment_uncertainty,
            "strict_pit_eligible": availability["strict_pit_eligible"],
            "training_eligible": False,
        },
        "review": {"status": REVIEW_PENDING, "reviews": [], "reviewer_ids": [], "reviewed_at": None, "approved": False},
        "review_only": True,
        "live_trading_enabled": False,
    }
    record["record_hash"] = sha256_text(canonical_json(record))
    record["request_diagnostics"] = diagnostics  # depends on what was offered, not on what was consumed
    return record


def record_hash(output: Mapping[str, Any]) -> str:
    """Recompute the stable hash of a label record (excludes request_diagnostics and the hash itself)."""
    core = {k: v for k, v in output.items() if k not in ("record_hash", "request_diagnostics")}
    return sha256_text(canonical_json(core))


def _check_prior_state(prior: PriorState, symbol: str, rows: Sequence[Observation], request: LabelRequest) -> None:
    if prior.symbol != symbol or prior.policy_hash != POLICY_HASH:
        raise LabelInputError("prior_state_binding_mismatch", f"{prior.symbol}/{prior.policy_hash[:12]}")
    if not (prior.decision_date < request.cutoff.decision_date):
        raise LabelInputError("prior_state_not_earlier", f"{prior.decision_date} >= {request.cutoff.decision_date}")
    if prior.phase not in PHASES:
        raise LabelInputError("prior_state_unknown_phase", prior.phase)
    earlier = Cutoff(prior.decision_date, prior.as_of, request.cutoff.mode)
    if earlier.as_of_dt() > request.cutoff.as_of_dt():
        raise LabelInputError("prior_state_not_earlier", f"prior as_of {prior.as_of} after cutoff as_of {request.cutoff.as_of}")
    replay = LabelRequest(symbol=symbol, observations=rows, cutoff=earlier, security=request.security, synthetic=request.synthetic)
    recomputed = generate_labels(replay)["labels"]["phase"]["label"]
    if recomputed != prior.phase:
        raise LabelInputError("prior_state_inconsistent", f"offered {prior.phase}, recomputed {recomputed} at {prior.decision_date}")


def label_series(request: LabelRequest, decision_dates: Sequence[str]) -> list[dict[str, Any]]:
    """Evaluate the policy at several cutoffs (each consuming only data <= its own cutoff)."""
    outputs = []
    for d in decision_dates:
        cutoff = Cutoff(d, close_time(d).isoformat(), request.cutoff.mode)
        outputs.append(generate_labels(LabelRequest(
            symbol=request.symbol, observations=request.observations, cutoff=cutoff, security=request.security,
            benchmark_symbol=request.benchmark_symbol, benchmark_observations=request.benchmark_observations,
            universe_coverage_on_decision_date=request.universe_coverage_on_decision_date,
            synthetic=request.synthetic, frozen_universe=request.frozen_universe)))
    return outputs


# --------------------------------------------------------------------------- #
# Episodes, matching, counting                                                #
# --------------------------------------------------------------------------- #


def build_episodes(outputs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Group consecutive same-phase cutoff outputs of one symbol into episodes."""
    min_sessions = POLICY["windows"]["min_episode_sessions"]
    episodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    symbols = {o["symbol"] for o in outputs}
    if len(symbols) > 1:
        raise LabelInputError("mixed_symbols_in_series", ",".join(sorted(symbols)))
    dates = [o["cutoff"]["decision_date"] for o in outputs]
    if any(b <= a for a, b in zip(dates, dates[1:])):
        raise LabelInputError("series_not_chronological", "decision dates must be strictly increasing")
    hashes = {o["policy_hash"] for o in outputs}
    if len(hashes) > 1:
        raise LabelInputError("mixed_policy_hashes_in_series", ",".join(sorted(h[:12] for h in hashes)))
    for out in outputs:
        label = out["labels"]["phase"]["label"]
        d = out["cutoff"]["decision_date"]
        if current is not None and current["phase"] == label:
            current["end"] = d
            current["sessions"] += 1
            current["member_episode_ids"].append(out["episode_id"])
            continue
        if current is not None:
            episodes.append(current)
        current = {"symbol": out["symbol"], "phase": label, "start": d, "end": d, "sessions": 1,
                   "member_episode_ids": [out["episode_id"]], "synthetic": out["synthetic"],
                   "selection_at_end": out["labels"]["selection"]["label"], "policy_hash": out["policy_hash"]}
    if current is not None:
        episodes.append(current)
    for ep in episodes:
        ep["open_at_last_cutoff"] = ep is episodes[-1]
        ep["meets_min_sessions"] = ep["sessions"] >= min_sessions
        ep["episode_key"] = ep["member_episode_ids"][0]
        ep["review"] = {"status": REVIEW_PENDING, "reviews": [], "reviewer_ids": []}
        ep["counts_toward_case_library"] = False
        ep["overlap_rule"] = "episodes of one symbol are disjoint by construction; positives of one symbol within dependence_window are one effective decision group"
    return episodes


def effective_decision_dates(episodes: Sequence[Mapping[str, Any]], phase: str = PHASE_ACCUMULATION,
                             session_index: Mapping[str, int] | None = None, include_synthetic: bool = False) -> dict[str, Any]:
    """Count effective independent decision-date groups per symbol.

    Synthetic episodes are excluded unless ``include_synthetic`` (used only to
    test the counting arithmetic; the result is still marked synthetic)."""
    window = POLICY["windows"]["dependence_window_sessions"]
    real = [e for e in episodes if e["phase"] == phase and not e.get("synthetic")]
    synthetic = [e for e in episodes if e["phase"] == phase and e.get("synthetic")]
    counted = real + (synthetic if include_synthetic else [])
    groups = 0
    by_symbol: dict[str, list[str]] = {}
    for e in sorted(counted, key=lambda x: (x["symbol"], x["start"])):
        by_symbol.setdefault(e["symbol"], []).append(e["start"])
    for starts in by_symbol.values():
        last: str | None = None
        for s in starts:
            if last is None:
                groups += 1
                last = s
                continue
            if session_index is not None and s in session_index and last in session_index:
                apart = session_index[s] - session_index[last] > window
            else:
                apart = (date.fromisoformat(s) - date.fromisoformat(last)).days > window * 7 // 5
            if apart:
                groups += 1
                last = s
    return {"phase": phase, "raw_episodes": len(real), "synthetic_excluded": len(synthetic),
            "synthetic_included_for_arithmetic_only": include_synthetic,
            "effective_decision_dates": 0 if (include_synthetic and not real) else groups,
            "effective_decision_dates_arithmetic": groups,
            "dependence_window_sessions": window,
            "target_min_reviewed_positives": POLICY["case_library"]["targets"]["min_reviewed_positives"],
            "reviewed_positives": 0, "note": "reviewed_positives counts only episodes with independent review; none exist in M3-01"}


_OUTCOME_FIELD = re.compile(r"^(outcome|future|forward|realized|max_return|min_return|close_return)")


def _leak_check(record: Mapping[str, Any]) -> None:
    for key in record:
        if _OUTCOME_FIELD.match(str(key)):
            raise LabelInputError("outcome_leakage", f"field {key!r} is a later-known outcome and cannot enter matching")


def match_controls(positive: Mapping[str, Any], pool: Sequence[Mapping[str, Any]],
                   session_index: Mapping[str, int]) -> dict[str, Any]:
    """Deterministic control matching using cutoff-time information only.

    ``positive`` and pool items are ``generate_labels`` outputs (or the compact
    ``case_summary`` of one).  ``session_index`` maps decision dates to session
    ordinals (calendar-derived, not price-derived).
    """
    m = POLICY["matching"]
    tol = POLICY["windows"]["period_match_tolerance_sessions"]
    p = case_summary(positive)
    _leak_check(p)
    if p["selection"] != SELECTION_CANDIDATE:
        raise LabelInputError("positive_not_candidate", p["selection"])
    if p["decision_date"] not in session_index:
        raise LabelInputError("decision_date_not_in_session_index", p["decision_date"])
    p_idx = session_index[p["decision_date"]]
    candidates = []
    rejected: dict[str, int] = {}
    for item in pool:
        c = case_summary(item)
        _leak_check(c)
        why = None
        if c["symbol"] == p["symbol"]:
            why = "same_symbol"
        elif c["selection"] != m["control_selection_label"]:
            why = "not_non_candidate"
        elif c["liquidity_band"] != p["liquidity_band"] or c["liquidity_band"] == LIQUIDITY_UNKNOWN:
            why = "liquidity_band_mismatch_or_unknown"
        elif c["regime"] != p["regime"] or c["regime"] == REGIME_UNKNOWN:
            why = "regime_mismatch_or_unknown"
        elif c["decision_date"] not in session_index:
            why = "decision_date_not_in_session_index"
        elif abs(session_index[c["decision_date"]] - p_idx) > tol:
            why = "outside_period_tolerance"
        elif c["synthetic"] != p["synthetic"]:
            why = "synthetic_real_mixing"
        if why:
            rejected[why] = rejected.get(why, 0) + 1
            continue
        dist = abs(session_index[c["decision_date"]] - p_idx)
        amt_p, amt_c = p["amount_20_mean_cny"], c["amount_20_mean_cny"]
        amt_dist = abs(math.log(amt_c / amt_p)) if amt_p and amt_c else float("inf")
        candidates.append(((dist, amt_dist, c["symbol"], c["decision_date"]), c))
    candidates.sort(key=lambda x: x[0])
    chosen = [c for _, c in candidates[: m["k_max"]]]
    return {
        "positive_episode_id": p["episode_id"],
        "controls": [{"episode_id": c["episode_id"], "symbol": c["symbol"], "decision_date": c["decision_date"],
                      "role": "matched_non_candidate"} for c in chosen],
        "control_count": len(chosen),
        "unmatched": len(chosen) < m["k_min"],
        "k_min": m["k_min"], "k_max": m["k_max"],
        "rejected_pool_counts": dict(sorted(rejected.items())),
        "matching_inputs": "cutoff-time only: selection, liquidity band, regime, session distance, amount_20",
        "synthetic": p["synthetic"],
        "counts_toward_case_library": False,
    }


def control_reuse_counts(matches: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    unmatched = 0
    for match in matches:
        if match["unmatched"]:
            unmatched += 1
        for c in match["controls"]:
            counts[c["episode_id"]] = counts.get(c["episode_id"], 0) + 1
    return {"positives": len(matches), "unmatched_positives": unmatched,
            "distinct_controls": len(counts), "max_reuse": max(counts.values(), default=0),
            "reused_controls": sum(1 for v in counts.values() if v > 1)}


def case_summary(output: Mapping[str, Any]) -> dict[str, Any]:
    """Compact cutoff-time view used for matching; never carries outcomes."""
    if "labels" not in output:  # already a summary
        return dict(output)
    return {
        "episode_id": output["episode_id"], "symbol": output["symbol"], "decision_date": output["cutoff"]["decision_date"],
        "policy_hash": output["policy_hash"], "selection": output["labels"]["selection"]["label"],
        "phase": output["labels"]["phase"]["label"], "liquidity_band": output["labels"]["liquidity"]["band"],
        "regime": output["labels"]["regime"]["regime"], "amount_20_mean_cny": output["features"].get("amount_20_mean_cny"),
        "synthetic": output["synthetic"],
    }


# --------------------------------------------------------------------------- #
# Reviews (never fabricated by the generator)                                 #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ReviewRecord:
    reviewer_id: str
    reviewer_kind: str  # "agent" | "human"
    reviewed_at: str
    verdict: str  # "positive" | "negative" | "ambiguous" | "failed" | "reject_data"
    evidence_refs: tuple[str, ...]
    notes: str = ""

    def record(self) -> dict[str, Any]:
        if self.reviewer_kind not in ("agent", "human"):
            raise LabelInputError("invalid_reviewer_kind", self.reviewer_kind)
        if self.verdict not in ("positive", "negative", "ambiguous", "failed", "reject_data"):
            raise LabelInputError("invalid_review_verdict", self.verdict)
        _parse_datetime(self.reviewed_at, "invalid_reviewed_at")
        if not self.reviewer_id:
            raise LabelInputError("missing_reviewer_id")
        return {"reviewer_id": self.reviewer_id, "reviewer_kind": self.reviewer_kind, "reviewed_at": self.reviewed_at,
                "verdict": self.verdict, "evidence_refs": list(self.evidence_refs), "notes": self.notes}


def attach_review(case: Mapping[str, Any], review: ReviewRecord) -> dict[str, Any]:
    """Return a new case with the review appended; the input case is not mutated."""
    updated = json.loads(json.dumps(case, ensure_ascii=False))
    block = updated.setdefault("review", {"status": REVIEW_PENDING, "reviews": [], "reviewer_ids": []})
    block["reviews"].append(review.record())
    block["reviewer_ids"] = sorted({r["reviewer_id"] for r in block["reviews"]})
    verdicts = {r["reviewer_id"]: r["verdict"] for r in block["reviews"]}
    distinct = sorted(set(verdicts.values()))
    if len(block["reviewer_ids"]) < 2:
        block["status"] = "single_review_not_independent"
        block["agreement"] = None
    elif len(distinct) == 1:
        block["status"] = "independently_reviewed"
        block["agreement"] = "agree"
        block["consensus_verdict"] = distinct[0]
    else:
        block["status"] = "disputed"
        block["agreement"] = "disagree"
        block["consensus_verdict"] = None
    block["approved"] = False  # approval is a separate, user-level act
    block["reviewed_at"] = max(r["reviewed_at"] for r in block["reviews"])
    updated["counts_toward_case_library"] = (
        block["status"] == "independently_reviewed" and not updated.get("synthetic", False)
    )
    return updated


# --------------------------------------------------------------------------- #
# Later-known outcome annotation (separate from labels)                       #
# --------------------------------------------------------------------------- #


def annotate_outcome(case: Mapping[str, Any], later_observations: Sequence[Observation], later_cutoff: Cutoff,
                     horizon_sessions: int = 20) -> dict[str, Any]:
    """Compute what became known *after* the case cutoff.  Returned separately;
    never merged into the case labels and never usable for matching."""
    symbol = case["symbol"]
    rows = validate_observations(later_observations, symbol, case["synthetic"])
    usable, availability, _diagnostics = select_usable(rows, later_cutoff)
    after = [r for r in usable if r.kind == "price" and r.trade_date > case["cutoff"]["decision_date"]]
    if later_cutoff.decision_date <= case["cutoff"]["decision_date"]:
        raise LabelInputError("outcome_cutoff_not_later", later_cutoff.decision_date)
    window = after[:horizon_sessions]
    if not window:
        return {"annotation_kind": "later_known_outcome", "not_a_label": True, "episode_id": case["episode_id"],
                "status": "pending_future_data", "sessions_observed": 0, "later_cutoff": later_cutoff.record(),
                "input_availability": availability, "realized_return_claim": False}
    ref = float(window[0].open)
    closes = [float(b.close) for b in window]
    return {
        "annotation_kind": "later_known_outcome", "not_a_label": True, "episode_id": case["episode_id"],
        "policy_hash": case["policy_hash"], "status": "observed" if len(window) >= horizon_sessions else "partial",
        "sessions_observed": len(window), "horizon_sessions": horizon_sessions,
        "reference": {"basis": "next_session_open_unadjusted", "date": window[0].trade_date, "price": ref},
        "close_return_unadjusted": closes[-1] / ref - 1.0,
        "max_close_return_unadjusted": max(closes) / ref - 1.0,
        "min_low_return_unadjusted": min(float(b.low) for b in window) / ref - 1.0,
        "adjustment_uncertainty": True,
        "realized_return_claim": False,
        "later_cutoff": later_cutoff.record(),
        "input_availability": availability,
        "note": "unadjusted prices; corporate actions inside the horizon are not resolved; not a training target",
    }


# --------------------------------------------------------------------------- #
# Chronological protection, seed context, universe                            #
# --------------------------------------------------------------------------- #


def split_role(decision_date: str) -> str:
    _parse_date(decision_date, "invalid_decision_date")
    s = POLICY["split_proposal"]
    for role in ("development", "validation", "final_holdout"):
        lo, hi = s[role]
        if lo <= decision_date <= hi:
            return role
    return "outside_research_interval"


def guard_final_holdout(records: Iterable[Mapping[str, Any]], purpose: str) -> dict[str, Any]:
    """Raise when final-holdout records would be used for rule/threshold selection or target counting."""
    forbidden = ("rule_selection", "threshold_selection", "target_count", "parameter_search")
    roles: dict[str, int] = {}
    for rec in records:
        d = rec["cutoff"]["decision_date"] if "cutoff" in rec else rec["decision_date"]
        role = split_role(d)
        roles[role] = roles.get(role, 0) + 1
    if purpose in forbidden and roles.get("final_holdout", 0) > 0:
        raise LabelInputError("final_holdout_consumed", f"purpose={purpose} touched {roles['final_holdout']} holdout records")
    return {"purpose": purpose, "roles": dict(sorted(roles.items())), "holdout_protected": True}


def seed_context() -> list[dict[str, Any]]:
    return [dict(item, case_data_fabricated=False, reviewed=False) for item in POLICY["seed_context"]]


def assert_in_universe(symbol: str, frozen_universe: frozenset[str]) -> None:
    if symbol not in frozen_universe:
        raise LabelInputError("outside_frozen_universe", f"{symbol}: extension is a separate decision")


def policy_document() -> dict[str, Any]:
    """Machine-readable policy with its own hash (for LABEL_POLICY.json)."""
    return {"policy": POLICY, "policy_hash": POLICY_HASH, "hash_rule": "sha256(canonical_json(policy))"}


__all__ = [
    "NAMESPACE", "POLICY_ID", "POLICY_VERSION", "POLICY", "POLICY_HASH", "OUTPUT_SCHEMA",
    "MODE_STRICT", "MODE_RETROSPECTIVE", "PHASES",
    "LabelInputError", "Observation", "Cutoff", "SecurityContext", "PriorState", "PositionState", "LabelRequest",
    "ReviewRecord", "validate_observations", "validate_symbol", "select_usable", "input_fingerprint", "bar_features",
    "rule_phase", "label_phase", "label_selection", "label_entry", "label_position_event", "label_liquidity", "label_regime",
    "limit_assessment", "generate_labels", "label_series", "build_episodes", "effective_decision_dates",
    "match_controls", "control_reuse_counts", "case_summary", "attach_review", "annotate_outcome", "record_hash",
    "split_role", "guard_final_holdout", "seed_context", "assert_in_universe", "policy_document",
    "canonical_json", "sha256_text", "producer_sha256", "close_time", "infer_board", "episode_id",
]
