"""M4-03B replay core: sealed snapshot, reconciliation, B0 features, global-chronology replay over the frozen engines.

Everything here is pure computation over an in-memory ``Snapshot`` (built once from the bounded SQLite read by
run_m4_03b_replay.py, or from synthetic bars by the tests).  No I/O, no SQLite, no clock.  The frozen kernel / ledger /
risk modules and the accepted ``proposal_mapping`` are injected (loaded by file path after hash verification by the
caller).

Chronology per session S (global, all symbols together):
  1. 09:30 open attempts for every live intent whose eligible session is S, exits (sells) before entries (buys), then
     symbol / intent id order, each with its original bound decision context; buys receive the last already-available
     close of every OTHER held symbol as marks (model instants of that earlier session; the engine selects/refuses);
  2. 16:00 decision at S with closes available by then (marks), B0 signals computed on closes <= S, benchmark level.
Nothing from S's close/high/low/volume reaches S's open attempts (``proposal_mapping.OpenAttemptInputs`` has no such
field).  Intents created at the last decision session are censored (never attempted); open positions at the end are
reported with their engine state and a hypothetical last-close valuation.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

DEV_START, DEV_END = "2023-09-04", "2025-03-31"
WARM_START, WARM_END = "2022-08-24", "2023-09-01"
WARM_SESSIONS = 250
BENCHMARK = "SH000300"
SMA_N = 20
LISTING_EXCLUDED_SESSIONS = 5
INITIAL_CASH = "1000000.00"
POLICY_PARAMS = {"policy_id": "HYPOTHETICAL_03B_B0_POLICY", "provenance": "hypothetical_fixture", "max_position_weight": "0.05", "max_gross_exposure": "0.60",
                 "min_cash_reserve": "0", "stop_loss_pct": "0.05", "profit_target_pct": "0.10", "max_holding_sessions": 20, "cooldown_sessions": 5,
                 "max_mark_age_sessions": 0, "max_gap_pct": "0.02", "intent_expiry_sessions": 1, "exit_priority": ("stop_loss", "profit_target", "max_holding"),
                 "entry_phase": "open_auction", "exit_phase": "open_auction"}
BRANCHES = {"assumed_full_fill": ("assumed", "full_fill"), "assumed_fixed_5000": ("assumed", "fixed_5000"), "assumed_capacity_none": ("assumed", "none"), "raw": ("raw", "none")}
FROZEN = {"backend/app/research/m4_execution.py": ("83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7", "9bea83482d545e6f39dd8eb70e89d674dd5d900378b596c243da8e122c273e62"),
          "backend/app/research/m4_portfolio.py": ("2b3eec837e4c3603661371fb94e8d942f45c9bfadbf018fc5d6ebee6fadb5360", "633f78d987141b0e3dccad5d8e711b241a2eaf58b2a8dbe65e57603b5624d6f6"),
          "backend/app/research/m4_risk.py": ("faec444ee98ed6ee8c20da217a6cb29ced53d7de2ceae1e2198b1cbc73b665f2", "013f1580f9b6c08092281202f012a567a8f2c743815345c505afe8ebd220ffdf"),
          "claude methods/_m4_20260912/claude_03a/proposal_mapping.py": ("276cb037575f8d05a313b3266ecad46008e015d17c99ca98786c403d0c3e70de", None)}
STATUS_DEFAULT_ASSUMPTION = "ASSUMPTION:security_status_listed_default_no_status_evidence_declared_pool_only"
BAND_REFERENCE_ASSUMPTION = "ASSUMPTION:band_reference_is_last_available_close_before_attempt_session"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_frozen(project: Path) -> dict:
    """Load the three frozen engines and the accepted mapping by file path after verifying their hashes."""
    mods, hashes = {}, {}
    for rel, (expected, policy) in FROZEN.items():
        path = project / rel
        got = sha256_file(path)
        if got != expected:
            raise RuntimeError(f"frozen module hash mismatch {rel}: {got}")
        hashes[rel] = got
    k = load_module("m4_execution_frozen_03b", project / "backend/app/research/m4_execution.py")
    p = load_module("m4_portfolio_frozen_03b", project / "backend/app/research/m4_portfolio.py")
    r = load_module("m4_risk_frozen_03b", project / "backend/app/research/m4_risk.py")
    pm = load_module("proposal_mapping_accepted_03b", project / "claude methods/_m4_20260912/claude_03a/proposal_mapping.py")
    for mod, rel in ((k, "backend/app/research/m4_execution.py"), (p, "backend/app/research/m4_portfolio.py"), (r, "backend/app/research/m4_risk.py")):
        attr = {"backend/app/research/m4_execution.py": "POLICY_HASH", "backend/app/research/m4_portfolio.py": "LEDGER_POLICY_HASH", "backend/app/research/m4_risk.py": "RISK_POLICY_HASH"}[rel]
        if getattr(mod, attr) != FROZEN[rel][1]:
            raise RuntimeError(f"policy hash mismatch {rel}")
    return {"k": k, "p": p, "r": r, "pm": pm, "hashes": hashes}


def normalize_session(text: str) -> str:
    """YYYYMMDD -> YYYY-MM-DD; YYYY-MM-DD kept; anything else rejected."""
    t = str(text)
    if len(t) == 8 and t.isdigit():
        return f"{t[:4]}-{t[4:6]}-{t[6:8]}"
    if len(t) == 10 and t[4] == "-" and t[7] == "-" and t[:4].isdigit() and t[5:7].isdigit() and t[8:].isdigit():
        return t
    raise ValueError(f"unrecognized session date {text!r}")


def price_text(value: Any) -> str:
    """Exact decimal spelling of a stored price (REAL): shortest round-trip repr, then the 0.01 tick when it is exact."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f"invalid price {value!r}")
    d = Decimal(repr(value)) if isinstance(value, float) else Decimal(str(value))
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(q) if (q - d).copy_abs() < Decimal("1e-9") else str(d)


# ---------------------------------------------------------------------------- snapshot
class Snapshot:
    """Sealed, immutable-by-convention in-memory input: calendar slice, bars, halts, listing, boards, provenance."""

    def __init__(self, sessions: list[str], bars: dict[str, dict[str, dict]], halts: dict[str, set], listing: dict[str, str | None], boards: dict[str, str],
                 roles: dict[str, str], listing_refs: dict[str, str], meta: dict | None = None):
        self.sessions = list(sessions)
        self.index = {s: i for i, s in enumerate(self.sessions)}
        self.bars = bars
        self.halts = {s: set(v) for s, v in halts.items()}
        self.listing = listing
        self.boards = boards
        self.roles = roles
        self.listing_refs = listing_refs
        self.meta = meta or {}
        self.stocks = sorted(s for s, role in roles.items() if role == "stock")
        self.input_hash = self.seal()

    def seal(self) -> str:
        body = {"sessions": self.sessions, "listing": self.listing, "boards": self.boards, "roles": self.roles,
                "bars": {s: {d: [b["open"], b["high"], b["low"], b["close"], b["volume"], b["amount"], b["observed_at"], b["raw_sha256"], b["point_index"]] for d, b in sorted(v.items())}
                         for s, v in sorted(self.bars.items())},
                "halts": {s: sorted(v) for s, v in sorted(self.halts.items())}}
        return sha256_text(canonical(body))

    def last_bar_before(self, symbol: str, session: str) -> tuple[str, dict] | None:
        i = self.index[session] - 1
        bars = self.bars.get(symbol, {})
        while i >= 0:
            d = self.sessions[i]
            if d in bars:
                return d, bars[d]
            i -= 1
        return None

    def sessions_since_listing(self, symbol: str, session: str) -> int | None:
        ld = self.listing.get(symbol)
        if ld is None:
            return None
        if ld not in self.index:
            # listing date outside the loaded calendar slice: before the slice -> large age; after -> not listed
            return 10**6 if ld < self.sessions[0] else -1
        return self.index[session] - self.index[ld]


def snapshot_from_rows(rows: dict, qualification: dict, index_doc: dict, calendar_sessions: list[str], pilot: list[dict]) -> tuple[Snapshot, dict]:
    """Reconcile the Q1-Q9 rows exactly as the frozen reader does and build the sealed snapshot (development + warmup)."""
    scopes = {s["symbol"]: s for s in qualification["scopes"]}
    expected_dates = {s: set(v["expected_price_dates"]) for s, v in scopes.items()}
    suspended_dates = {s: set(v["suspended_dates"]) for s, v in scopes.items()}
    ledger = {(g["symbol"], g["date"]): g for g in qualification["suspension_ledger"]}
    instruments = {i["symbol"]: i for i in index_doc["instruments"]}
    problems, exclusions = [], []
    counts = {name: len(v) for name, v in rows.items()}
    expected = {"Q1_trading_prices": 27900, "Q2_history_prices": 27900, "Q3_row_evidence": 27900, "Q4_coverage_trading": 28100, "Q4_coverage_history": 28100,
                "Q5_suspensions_trading": 200, "Q5_suspensions_history": 200, "Q6_qualification_records": 52, "Q7_instruments": 52, "Q8_contract_trading": 1, "Q8_contract_history": 1, "Q9_ingest_runs": 1}
    for name, n in expected.items():
        if counts.get(name) != n:
            problems.append(f"row_count:{name}:{counts.get(name)}!={n}")
    contract_t, contract_h = rows["Q8_contract_trading"], rows["Q8_contract_history"]
    if contract_t != contract_h:
        problems.append("dataset_contract_mismatch_between_stores")
    if rows["Q9_ingest_runs"] and rows["Q9_ingest_runs"][0][1] != "ths_v2_20260910_041710_97ef9c09":
        problems.append("ingest_run_identity")
    qual_hash = {}
    for symbol, sha, rec_json in rows["Q6_qualification_records"]:
        scope = scopes.get(symbol)
        if scope is None or sha != sha256_text(canonical(scope)) or rec_json != canonical(scope):
            problems.append(f"qualification_record_mismatch:{symbol}")
        qual_hash[symbol] = sha
    if set(qual_hash) != set(scopes) or {s[0] for s in rows["Q7_instruments"]} != set(scopes):
        problems.append("instruments_or_qualifications_differ_from_frozen_scopes")
    if rows["Q4_coverage_trading"] != rows["Q4_coverage_history"] or rows["Q5_suspensions_trading"] != rows["Q5_suspensions_history"]:
        problems.append("coverage_or_suspension_store_mismatch")
    if problems:
        return None, {"passed": False, "problems": problems, "counts": counts}
    h_map = {(x[0], x[1]): x for x in rows["Q2_history_prices"]}
    ev_map = {(x[0], x[1]): x for x in rows["Q3_row_evidence"]}
    cov = {(x[0], x[1]): x[2] for x in rows["Q4_coverage_trading"]}
    sus = {(x[0], x[1]): x for x in rows["Q5_suspensions_trading"]}
    bars: dict[str, dict[str, dict]] = {}
    accepted = set()
    numeric_digest = hashlib.sha256()
    for row in rows["Q1_trading_prices"]:
        symbol, date, o, hi, lo, c, v, a, source, quality, adjustment, volume_unit = row
        key = (symbol, date)
        scope = scopes.get(symbol)
        if scope is None:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "symbol_not_in_frozen_scopes"}); continue
        h = h_map.get(key)
        if h is None:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "missing_in_history"}); continue
        nums = [o, hi, lo, c, v, a]
        if any(x is None or isinstance(x, bool) or not isinstance(x, (int, float)) or x != x for x in nums):
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "nonfinite_or_null_numeric"}); continue
        if tuple(nums) != tuple(h[3:9]):
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "numeric_mismatch_between_stores"}); continue
        if adjustment != "none" or h[2] != "none":
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "adjustment_mode_not_none"}); continue
        if quality != "qualified_candidate":
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "quality_status_not_qualified"}); continue
        if source != "tonghuashun" or h[9] != "tonghuashun":
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "source_provider_mismatch"}); continue
        if volume_unit != scope["volume_unit"]:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "volume_unit_mismatch_with_scope"}); continue
        ev = ev_map.get(key)
        if ev is None:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "row_evidence_missing"}); continue
        raw, request, producer, parser, receipt, manifest, observed_at, point_index, qual_sha = ev[2:11]
        if not all(isinstance(x, str) and len(x) == 64 for x in (raw, request, producer, parser, receipt, manifest)):
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "row_evidence_lineage_malformed"}); continue
        capture = next((cp for cp in scope["captures"] if cp["raw_sha256"] == raw and cp["request_sha256"] == request and cp["producer_sha256"] == producer
                        and cp["parser_sha256"] == parser and cp["capture_receipt_sha256"] == receipt and cp["capture_producer_manifest_sha256"] == manifest), None)
        if capture is None:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "row_evidence_lineage_not_in_frozen_capture"}); continue
        if not isinstance(point_index, int) or point_index < 0 or point_index >= capture["rows"]:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "point_index_out_of_capture_range"}); continue
        if observed_at != h[10] or observed_at != capture["observed_at"]:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "observed_at_fetched_at_mismatch"}); continue
        if qual_sha != qual_hash[symbol]:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "qualification_sha_mismatch"}); continue
        if date not in expected_dates[symbol]:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "price_key_not_expected_by_scope"}); continue
        if key in sus:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "price_and_suspension_conflict"}); continue
        if cov.get(key) != "price":
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "coverage_classification_not_price"}); continue
        if not (0 < lo <= min(o, c) <= max(o, c) <= hi) or v < 0 or a < 0:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "ohlc_order_or_negative_aggregate"}); continue
        accepted.add(key)
        bars.setdefault(symbol, {})[date] = {"open": price_text(o), "high": price_text(hi), "low": price_text(lo), "close": price_text(c), "volume": int(v) if float(v).is_integer() else v,
                                             "amount": price_text(a), "observed_at": observed_at, "raw_sha256": raw, "point_index": point_index, "ingest_run_id": h[11]}
        numeric_digest.update((canonical([symbol, date, o, hi, lo, c, v, a]) + "\n").encode())
    t_keys = {(x[0], x[1]) for x in rows["Q1_trading_prices"]}
    for key in h_map:
        if key not in t_keys:
            exclusions.append({"symbol": key[0], "trade_date": key[1], "reason": "missing_in_trading"})
    halts: dict[str, set] = {}
    for key, (symbol, date, evidence_sha, record_json) in sus.items():
        gap = ledger.get(key)
        if gap is None or evidence_sha != sha256_text(canonical(gap)) or record_json != canonical(gap):
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "suspension_not_in_frozen_ledger_or_hash_mismatch"}); continue
        if cov.get(key) != "full_day_suspension" or key in accepted or date not in suspended_dates[symbol]:
            exclusions.append({"symbol": symbol, "trade_date": date, "reason": "suspension_coverage_or_scope_conflict"}); continue
        halts.setdefault(symbol, set()).add(date)
    excluded_keys = {(e["symbol"], e["trade_date"]) for e in exclusions}
    for symbol, scope in scopes.items():
        for date in scope["expected_price_dates"]:
            if date <= DEV_END and (symbol, date) not in accepted and (symbol, date) not in excluded_keys:
                exclusions.append({"symbol": symbol, "trade_date": date, "reason": "expected_price_key_missing_from_store"})
        for date in scope["suspended_dates"]:
            if date <= DEV_END and date not in halts.get(symbol, set()):
                exclusions.append({"symbol": symbol, "trade_date": date, "reason": "expected_suspension_missing_from_store"})
    stray = [k for k in cov if k not in accepted and k not in sus]
    for symbol, date in stray:
        exclusions.append({"symbol": symbol, "trade_date": date, "reason": "coverage_key_without_price_or_suspension"})
    # calendar slice: warmup start .. the next legal session after DEV_END (its prices are never read)
    sessions = [normalize_session(s) for s in calendar_sessions]
    if sessions != sorted(set(sessions)):
        return None, {"passed": False, "problems": ["calendar_not_sorted_unique"], "counts": counts}
    i0, i1 = sessions.index(WARM_START), sessions.index(DEV_END)
    if sessions[i1 - 377] != DEV_START or sessions[sessions.index(DEV_START) - WARM_SESSIONS] != WARM_START or sessions[i0 + WARM_SESSIONS - 1] != WARM_END:
        return None, {"passed": False, "problems": ["calendar_window_mismatch"], "counts": counts}
    slice_sessions = sessions[i0:i1 + 2]        # includes the next legal session (2025-04-01) for expiry / T+1 derivation only
    pilot_rows = {r["symbol"]: r for r in pilot}
    listing = {s: instruments[s]["listing_date"] for s in scopes}
    roles = {s: instruments[s]["instrument_class"] for s in scopes}
    refs = {}
    for s in scopes:
        le = instruments[s]["listing_evidence"]
        refs[s] = f"metadata_index_01/index.json:instruments[{s}].listing_evidence:" + (le.get("identity_kind") or le.get("status") or "unknown") + ":" + (le.get("document_sha256") or le.get("sha256") or "none")
    boards = {}
    counts_dev = Counter()
    for s in scopes:
        boards[s] = "index" if roles[s] == "benchmark" else None
    snap_bars = {s: {d: b for d, b in v.items() if WARM_START <= d <= DEV_END} for s, v in bars.items()}
    snap_halts = {s: {d for d in v if WARM_START <= d <= DEV_END} for s, v in halts.items()}
    for s, v in snap_bars.items():
        for d in v:
            counts_dev[(roles[s], "development" if d >= DEV_START else "warmup")] += 1
    dropped_before_warm = sum(1 for s, v in bars.items() for d in v if d < WARM_START)
    report = {"passed": not problems, "problems": problems, "counts": counts, "accepted_price_keys": len(accepted), "accepted_halt_keys": sum(len(v) for v in halts.values()),
              "numeric_rows_sha256": numeric_digest.hexdigest(), "exclusions": exclusions, "exclusion_count": len(exclusions),
              "bars_by_role_and_segment": {f"{k[0]}:{k[1]}": v for k, v in sorted(counts_dev.items())},
              "rows_before_warmup_start_reconciled_not_consumed": dropped_before_warm,
              "calendar": {"slice_first": slice_sessions[0], "slice_last": slice_sessions[-1], "slice_sessions": len(slice_sessions), "development_sessions": i1 - sessions.index(DEV_START) + 1,
                           "warmup_sessions": WARM_SESSIONS, "next_legal_session_after_end": slice_sessions[-1], "normalization": "YYYYMMDD -> YYYY-MM-DD before comparison"},
              "pilot_symbols": len(pilot_rows), "scopes": len(scopes)}
    snap = Snapshot(slice_sessions, snap_bars, snap_halts, listing, boards, roles, refs,
                    meta={"numeric_rows_sha256": report["numeric_rows_sha256"], "accepted_price_keys": len(accepted), "accepted_halt_keys": report["accepted_halt_keys"]})
    return snap, report


def warmup_depths(snapshot: Snapshot, start: str = WARM_START, end: str = WARM_END) -> dict[str, dict]:
    """Actual usable bars per symbol inside the fixed feature warmup window [start, end] (calendar sessions), plus halts there."""
    out = {}
    window = [s for s in snapshot.sessions if start <= s <= end]
    for symbol in sorted(snapshot.roles):
        bars = snapshot.bars.get(symbol, {})
        have = [s for s in window if s in bars]
        out[symbol] = {"window_sessions": len(window), "bars_in_window": len(have), "halt_keys_in_window": sum(1 for s in window if s in snapshot.halts.get(symbol, set())),
                       "first_bar_in_window": have[0] if have else None, "last_bar_in_window": have[-1] if have else None,
                       "consecutive_bars_ending_at_window_end": next((n for n in range(len(window), -1, -1) if all(window[len(window) - n + j] in bars for j in range(n))), 0)}
    return out


# ---------------------------------------------------------------------------- features (B0)
def sma_window(snapshot: Snapshot, symbol: str, session: str, n: int) -> list[Decimal] | None:
    """Closes on the n consecutive calendar sessions ending at ``session``; None when any of them lacks a price bar."""
    i = snapshot.index[session]
    if i - n + 1 < 0:
        return None
    bars = snapshot.bars.get(symbol, {})
    out = []
    for j in range(i - n + 1, i + 1):
        b = bars.get(snapshot.sessions[j])
        if b is None:
            return None
        out.append(Decimal(b["close"]))
    return out


def b0_signal(snapshot: Snapshot, symbol: str, session: str) -> dict:
    """B0: close(S) > SMA20(S) and close(S-1) <= SMA20(S-1); needs 21 consecutive price-bar sessions ending at S."""
    w = sma_window(snapshot, symbol, session, SMA_N + 1)
    if w is None:
        i = snapshot.index[session]
        have = 0
        bars = snapshot.bars.get(symbol, {})
        for j in range(i, -1, -1):
            if snapshot.sessions[j] in bars:
                have += 1
            else:
                break
        return {"signal": False, "reason": "insufficient_history", "consecutive_bars_ending_at_session": have}
    prev, cur = w[:SMA_N], w[1:]
    sma_prev, sma_cur = sum(prev) / SMA_N, sum(cur) / SMA_N
    sig = cur[-1] > sma_cur and prev[-1] <= sma_prev
    return {"signal": bool(sig), "reason": "signal" if sig else "no_signal", "sma20": str(sma_cur), "sma20_prev": str(sma_prev), "close": str(cur[-1]), "close_prev": str(prev[-1])}


# ---------------------------------------------------------------------------- replay
class Replay:
    def __init__(self, mods: dict, snapshot: Snapshot, branch: str, initial_cash: str = INITIAL_CASH, synthetic: bool = False, engine_id: str | None = None,
                 decision_sessions: tuple[str, str] = (DEV_START, DEV_END), benchmark_symbol: str = BENCHMARK):
        self.k, self.p, self.r, self.pm = mods["k"], mods["p"], mods["r"], mods["pm"]
        self.snap = snapshot
        self.branch = branch
        self.variant, self.cap_variant = BRANCHES[branch]
        self.synthetic = synthetic
        self.first, self.last = decision_sessions
        self.initial_cash = str(initial_cash)                        # the instance's own initial cash: performance denominator (review 01 P2-1)
        self.benchmark = benchmark_symbol                            # SH000300 for the historical run; synthetic index for tests
        self.dev_sessions = [s for s in snapshot.sessions if self.first <= s <= self.last]
        self.captured_ref = snapshot.meta.get("captured_ref", "row_evidence.observed_at")
        self.fees = self.pm.fee_schedule(self.k)
        self.asm = self.pm.execution_assumptions(self.k, declare_unknown_states=(self.variant == "assumed"))
        self.cal = self.pm.calendar(self.k, tuple(snapshot.sessions), self._capture_of_calendar(), self.variant, synthetic, "akshare_calendar_f1f1ce33_normalized" if not synthetic else "syn:calendar")
        self.policy = self.r.RiskPolicy(**POLICY_PARAMS)
        universe = tuple(self.r.UniverseMember(s, "stock", snapshot.boards.get(s) or self.pm.board_by_code_prefix(s), snapshot.listing_refs.get(s, "syn:listing")) for s in snapshot.stocks)
        self.ledger = self.p.PortfolioLedger(self.k, ledger_id=f"M4-03B-{branch}", account_ref="HYPOTHETICAL_03B_ACCOUNT", initial_cash=initial_cash)
        self.engine = self.r.PolicyEngine(kernel=self.k, ledger_module=self.p, ledger=self.ledger, policy=self.policy, universe=universe, benchmark_symbol=self.benchmark,
                                          engine_id=engine_id or f"M4-03B-{branch}")
        self.records: list[dict] = []
        self.funnel = Counter()
        self.entry_outcomes = Counter()
        self.attempt_outcomes = Counter()
        self.exit_intents = Counter()
        self.decision_refusals = Counter()
        self.per_symbol: dict[str, Counter] = {s: Counter() for s in snapshot.stocks}
        self.censored: dict = {}
        self.seq = 0
        self.intent_ctx: dict[str, Any] = {}
        self.diagnostics: list[dict] = []

    def _capture_of_calendar(self) -> str:
        # the calendar file has no capture instant of its own; the raw variant uses the earliest bar capture instant as the
        # only honest "available" instant on file (2026), the assumed variant its declared assumption
        caps = [b["observed_at"] for v in self.snap.bars.values() for b in v.values()]
        return min(caps) if caps else "2026-09-09T17:12:13.572989+00:00"

    # ---- wrappers ------------------------------------------------------------------------------------------------
    def _wrap(self, kind: str, session: str, engine_record: dict, provenance: list[dict], model_time: dict, assumption_ids: list[str], extra: dict | None = None) -> dict:
        self.seq += 1
        rec = {"seq": self.seq, "branch": self.branch, "variant": self.variant, "grade": "assumed" if self.variant == "assumed" else "raw",
               "kind": kind, "session": session, "model_time": model_time, "assumption_ids": sorted(set(assumption_ids)), "raw_provenance": provenance,
               "adjustment_uncertainty": True, "engine_record": engine_record}
        if extra:
            rec.update(extra)
        self.records.append(rec)
        return rec

    def _prov(self, symbol: str, date: str) -> dict:
        b = self.snap.bars[symbol][date]
        return {"symbol": symbol, "trade_date": date, "raw_sha256": b["raw_sha256"], "point_index": b["point_index"], "captured_at": b["observed_at"], "field_source": "daily_bar_cache"}

    # ---- session loop ----------------------------------------------------------------------------------------------
    def run(self) -> dict:
        for S in self.dev_sessions:
            self._open_attempts(S)
            self._decision(S)
        return self._finish()

    def _live_intents_due(self, S: str) -> list[dict]:
        live = [i for i in self.engine.intents().values() if i["status"] in ("pending", "partially_filled", "unfilled_live") and i["eligible_session"] == S]
        live.sort(key=lambda i: (0 if i["side"] == "sell" else 1, i["symbol"], i["intent_id"]))
        return live

    def _other_marks(self, S: str, symbol: str) -> tuple[list, list[dict], list[str]]:
        """Last already-available close of every OTHER held symbol before S (model instants of that earlier session)."""
        marks, prov, ids = [], [], []
        for held in sorted(self.ledger.positions()):
            if held == symbol:
                continue
            lb = self.snap.last_bar_before(held, S)
            if lb is None:
                continue
            d, b = lb
            marks.append(self.pm.mark(self.r, held, d, b["close"], b["observed_at"], self.variant, self.synthetic))
            prov.append({**self._prov(held, d), "role": "other_held_mark", "age_sessions_from_attempt": self.snap.index[S] - self.snap.index[d]})
            if self.variant == "assumed":
                ids.append(self.pm.ASSUMPTIONS["close_availability"])
        return marks, prov, ids

    def _open_attempts(self, S: str) -> None:
        for intent in self._live_intents_due(S):
            symbol, iid = intent["symbol"], intent["intent_id"]
            ctx = self.intent_ctx[iid]
            bar = self.snap.bars.get(symbol, {}).get(S)
            halt = S in self.snap.halts.get(symbol, set())
            lb = self.snap.last_bar_before(symbol, S)
            if bar is None and not halt:
                self.attempt_outcomes["not_attempted_missing_unconfirmed_row"] += 1
                self.per_symbol[symbol]["not_attempted_missing_unconfirmed_row"] += 1
                self.diagnostics.append({"session": S, "symbol": symbol, "intent_id": iid, "event": "not_attempted_missing_unconfirmed_row", "note": "no price row and no confirmed halt key; left to the decision sweep"})
                continue
            if lb is None:
                self.attempt_outcomes["not_attempted_no_previous_close"] += 1
                continue
            prev_date, prev_bar = lb
            age = self.snap.sessions_since_listing(symbol, S)
            inputs = self.pm.OpenAttemptInputs(symbol, S, None if halt else bar["open"], prev_bar["close"], halt, (bar or prev_bar)["observed_at"],
                                               self.snap.boards.get(symbol) or self.pm.board_by_code_prefix(symbol), age)
            qty = intent["remaining"]
            ev = self.pm.attempt_evidence(self.k, self.r, inputs, f"A-{S}-{symbol}", self.variant, self.cap_variant, qty, self.synthetic)
            marks, mprov, mids = self._other_marks(S, symbol) if intent["side"] == "buy" else ([], [], [])
            x = self.engine.execute(iid, ctx, ev, marks=tuple(marks))
            ids = mids + ([self.pm.ASSUMPTIONS["open_print"], self.pm.ASSUMPTIONS["tradable"], self.pm.ASSUMPTIONS["band"], self.pm.ASSUMPTIONS["limit_state"], self.pm.ASSUMPTIONS["st"],
                           self.pm.ASSUMPTIONS["listing"], BAND_REFERENCE_ASSUMPTION] if self.variant == "assumed" else [])
            if halt and self.variant == "assumed":
                ids.append(self.pm.ASSUMPTIONS["halt_placeholder"])
            if ev.capacity is not None:
                ids.append(ev.capacity.assumption_ref)
            prov = ([{**self._prov(symbol, S), "role": "open_print"}] if bar else []) + [{**self._prov(symbol, prev_date), "role": "band_reference_previous_close"}] + mprov
            model_time = {"executed_at": ev.executed_at, "price_observed_at": ev.price.observed_at, "price_available_at": ev.price.available_at,
                          "tradability_observed_at": ev.tradability.observed_at, "capacity_observed_at": ev.capacity.observed_at if ev.capacity else None}
            status = x["status"]
            outcome = x.get("outcome") or {}
            key = status
            if status == "refused":
                key = f"refused:{x.get('reason')}"
            elif status in ("expired", "unfilled_live", "partially_filled"):
                kreasons = ((x.get("ledger_record") or {}).get("kernel") or {}).get("reasons") or outcome.get("reasons") or []
                if kreasons:
                    key = f"{status}:" + "+".join(sorted(q["code"] for q in kreasons))
            elif status == "cancelled":
                key = f"cancelled:{x.get('reason')}"
            side = intent["side"]
            self.attempt_outcomes[f"{side}:{key}"] += 1
            self.per_symbol[symbol][f"attempt_{side}:{key}"] += 1
            post_hoc = None
            if bar and outcome.get("filled_quantity"):
                vol = Decimal(str(bar["volume"]))
                post_hoc = {"order_quantity_over_full_day_volume": str((Decimal(outcome["filled_quantity"]) / vol).quantize(Decimal("0.000001"))) if vol else None,
                            "note": "POST_HOC diagnostic from the same session's full-day volume; never used by the attempt"}
            self._wrap("attempt", S, x, prov, model_time, ids, {"intent_id": iid, "side": side, "capacity_id": ev.capacity.capacity_id if ev.capacity else None,
                                                                 "post_hoc_diagnostics": post_hoc, "halt_placeholder_used": halt})

    def _decision(self, S: str) -> None:
        ctx = self.pm.decision_context(self.r, S, self.cal, self.fees, self.asm)
        held = set(self.ledger.positions())
        marks, prov, signals = [], [], []
        stage = Counter()
        for symbol in self.snap.stocks:
            age = self.snap.sessions_since_listing(symbol, S)
            bar = self.snap.bars.get(symbol, {}).get(S)
            halt = S in self.snap.halts.get(symbol, set())
            if age is not None and age < 0:
                stage["not_listed"] += 1; self.per_symbol[symbol]["not_listed"] += 1; continue
            if halt:
                stage["halt_key"] += 1; self.per_symbol[symbol]["halt_key"] += 1; continue
            if bar is None:
                stage["missing_unconfirmed_row"] += 1; self.per_symbol[symbol]["missing_unconfirmed_row"] += 1; continue
            stage["price_row"] += 1
            marks.append(self.pm.mark(self.r, symbol, S, bar["close"], bar["observed_at"], self.variant, self.synthetic))
            prov.append({**self._prov(symbol, S), "role": "decision_mark"})
            # entry funnel (mutually exclusive stages after price_row)
            next_i = self.snap.index[S] + 1
            next_session = self.snap.sessions[next_i] if next_i < len(self.snap.sessions) else None
            if next_session is None:
                stage["no_next_session_in_calendar"] += 1; continue
            age_next = self.snap.sessions_since_listing(symbol, next_session)
            if age_next is not None and age_next < LISTING_EXCLUDED_SESSIONS:
                stage["new_listing_exclusion"] += 1; self.per_symbol[symbol]["new_listing_exclusion"] += 1; continue
            f = b0_signal(self.snap, symbol, S)
            if f["reason"] == "insufficient_history":
                stage["insufficient_history"] += 1; self.per_symbol[symbol]["insufficient_history"] += 1; continue
            if not f["signal"]:
                stage["no_signal"] += 1; continue
            stage["signal"] += 1; self.per_symbol[symbol]["signal"] += 1
            signals.append(self.pm.signal(self.r, f"B0-{S}-{symbol}", symbol, S, bar["observed_at"], self.variant, self.synthetic))
            if S == self.last:
                stage["signal_on_last_session_beyond_window"] += 1
        bench_bar = self.snap.bars.get(self.benchmark, {}).get(S)
        bench = (self.pm.benchmark_level(self.r, self.benchmark, S, bench_bar["close"], bench_bar["observed_at"], self.variant, self.synthetic),) if bench_bar else ()
        if bench_bar:
            prov.append({**self._prov(self.benchmark, S), "role": "benchmark_level"})
        d = self.engine.decide(f"D-{S}", ctx, marks=tuple(marks), signals=tuple(signals), benchmark=bench)
        for k_, v in stage.items():
            self.funnel[k_] += v
        if d["status"] == "refused":
            for ref in d["refusals"]:
                self.decision_refusals[ref["code"]] += 1
        else:
            for ref in d.get("refusals", []):
                self.decision_refusals[f"item:{ref['code']}:{ref.get('what')}"] += 1
            for e in d.get("entries", []):
                key = e["decision"] if e["decision"] != "refused" else f"refused:{e['reason']}"
                self.entry_outcomes[key] += 1
                self.per_symbol[e["symbol"]][f"entry:{key}"] += 1
                if e["decision"] == "buy":
                    self.intent_ctx[e["intent_id"]] = ctx
            for x in d.get("exits", []):
                if x["decision"] == "exit":
                    self.exit_intents[x["reason"]] += 1
                    self.per_symbol[x["symbol"]][f"exit_intent:{x['reason']}"] += 1
                    self.intent_ctx[x["intent_id"]] = ctx
                else:
                    self.exit_intents[f"held:{x['decision']}"] += 1
            for iid in d.get("expired_intents", []):
                self.attempt_outcomes["swept_expired_at_decision"] += 1
        ids = [self.pm.ASSUMPTIONS["close_availability"], self.pm.ASSUMPTIONS["calendar"], STATUS_DEFAULT_ASSUMPTION] if self.variant == "assumed" else []
        self._wrap("decision", S, d, prov, {"decided_at": ctx.decided_at, "mark_observed_at": f"{S}T15:00:00+08:00" if self.variant == "assumed" else "raw_capture", "mark_available_at": ctx.decided_at if self.variant == "assumed" else "raw_capture"},
                   ids, {"stage_counts": dict(stage), "signals": [s.signal_id for s in signals]})

    def _finish(self) -> dict:
        S = self.last
        ctx = self.pm.decision_context(self.r, S, self.cal, self.fees, self.asm)
        held = sorted(self.ledger.positions())
        marks = [self.pm.mark(self.r, s, S, self.snap.bars[s][S]["close"], self.snap.bars[s][S]["observed_at"], self.variant, self.synthetic) for s in held if S in self.snap.bars.get(s, {})]
        bench, bench_prov, bench_model_time = [], [], {}
        for role, d in (("benchmark_start_level", self.first), ("benchmark_end_level", S)):
            b = self.snap.bars.get(self.benchmark, {}).get(d)
            if b:
                lvl = self.pm.benchmark_level(self.r, self.benchmark, d, b["close"], b["observed_at"], self.variant, self.synthetic)
                bench.append(lvl)
                bench_prov.append({**self._prov(self.benchmark, d), "role": role})
                bench_model_time[role] = {"session": d, "observed_at": lvl.observed_at, "available_at": lvl.available_at, "raw_captured_at": b["observed_at"]}
            else:
                bench_model_time[role] = {"session": d, "observed_at": None, "available_at": None, "raw_captured_at": None, "missing": True}
        perf = self.engine.performance(ctx, marks=tuple(marks), benchmark=tuple(bench), start_session=self.first, initial_cash=self.initial_cash)
        intents = self.engine.intents()
        live = {iid: {"symbol": i["symbol"], "side": i["side"], "status": i["status"], "remaining": i["remaining"], "eligible_session": i["eligible_session"], "expires_at": i["expires_at"]}
                for iid, i in intents.items() if i["status"] in ("pending", "partially_filled", "unfilled_live")}
        snap = self.ledger.snapshot()
        self.censored = {"as_of": ctx.decided_at, "open_positions": {s: {"quantity": q, "has_mark_at_end": s in {m.symbol for m in marks}} for s, q in snap["positions"].items()},
                         "live_intents_beyond_window": live, "note": "positions and intents are reported with their actual engine states; no forced liquidation, no fabricated expiry, no 2025-04-01 price"}
        bench_endpoints = {"symbol": self.benchmark, "start_session": self.first, "end_session": S, "model_time": bench_model_time,
                           "engine_benchmark_status": (perf.get("benchmark") or {}).get("status"), "engine_benchmark_refusals": (perf.get("benchmark") or {}).get("refusals", []),
                           "note": "benchmark levels are the SH000300 closes of the two endpoint sessions consumed by the frozen risk layer's benchmark_return; raw variant keeps the 2026 capture instants and the engine's refusal reasons"}
        self._wrap("performance", S, perf, [{**self._prov(s, S), "role": "last_close_hypothetical_valuation"} for s in held if S in self.snap.bars.get(s, {})] + bench_prov,
                   {"as_of": ctx.decided_at, "mark_observed_at": f"{S}T15:00:00+08:00" if self.variant == "assumed" else "raw_capture", "mark_available_at": ctx.decided_at if self.variant == "assumed" else "raw_capture"},
                   [self.pm.ASSUMPTIONS["close_availability"], STATUS_DEFAULT_ASSUMPTION] if self.variant == "assumed" else [],
                   {"censored": self.censored, "benchmark_endpoints": bench_endpoints, "initial_cash_used": self.initial_cash})
        intents_by_status = Counter(i["status"] for i in intents.values())
        return {"branch": self.branch, "variant": self.variant, "capacity_variant": self.cap_variant, "records": self.records, "ledger_records": list(self.ledger.records),
                "ledger_snapshot": snap, "ledger_reconcile": self.ledger.reconcile(), "engine_chain_hash": self.engine.chain_hash, "ledger_state_hash": self.ledger.state_hash,
                "funnel": {"decision_stage": dict(self.funnel), "entry_outcomes": dict(self.entry_outcomes), "attempt_outcomes": dict(self.attempt_outcomes),
                           "exit_intents": dict(self.exit_intents), "decision_refusals": dict(self.decision_refusals), "intents_by_status": dict(intents_by_status)},
                "per_symbol": {s: dict(c) for s, c in self.per_symbol.items()}, "performance": perf, "censored": self.censored, "diagnostics": self.diagnostics,
                "reservations_final": self.engine.reservations()}


def output_hash(result: dict) -> str:
    """Hash of everything deterministic (records, ledger records, funnel, performance, censoring); no runtime timestamps exist inside."""
    body = {"records": result["records"], "ledger_records": result["ledger_records"], "funnel": result["funnel"], "performance": result["performance"], "censored": result["censored"],
            "ledger_state_hash": result["ledger_state_hash"], "engine_chain_hash": result["engine_chain_hash"]}
    return sha256_text(canonical(body))


def model_hash(mods: dict) -> str:
    return sha256_text(canonical({"policy": POLICY_PARAMS, "initial_cash": INITIAL_CASH, "sma": SMA_N, "listing_excluded_sessions": LISTING_EXCLUDED_SESSIONS, "branches": BRANCHES,
                                  "frozen": mods["hashes"], "kernel_policy": mods["k"].POLICY_HASH, "ledger_policy": mods["p"].LEDGER_POLICY_HASH, "risk_policy": mods["r"].RISK_POLICY_HASH,
                                  "assumptions": mods["pm"].ASSUMPTIONS, "status_default": STATUS_DEFAULT_ASSUMPTION, "band_reference": BAND_REFERENCE_ASSUMPTION}))


def write_jsonl_gz(path: Path, records: list[dict]) -> dict:
    h = hashlib.sha256()
    with gzip.open(path, "wb") as fh:
        for rec in records:
            line = (canonical(rec) + "\n").encode("utf-8")
            h.update(line)
            fh.write(line)
    return {"path": path.name, "records": len(records), "content_sha256": h.hexdigest(), "file_sha256": sha256_file(path)}


def synthetic_snapshot(sessions: list[str], bars: dict[str, dict[str, tuple]], halts: dict[str, set] | None = None, listing: dict[str, str | None] | None = None,
                       roles: dict[str, str] | None = None, captured_at: str = "2026-09-09T17:12:13.572989+00:00") -> Snapshot:
    """Synthetic snapshot for tests: bars[symbol][date] = (open, high, low, close, volume)."""
    roles = roles or {s: ("benchmark" if s.startswith("SYN9") else "stock") for s in bars}
    built = {}
    for s, v in bars.items():
        built[s] = {d: {"open": o, "high": h, "low": l, "close": c, "volume": vol, "amount": "0", "observed_at": captured_at, "raw_sha256": sha256_text(f"{s}:{d}"), "point_index": i, "ingest_run_id": 0}
                    for i, (d, (o, h, l, c, vol)) in enumerate(sorted(v.items()))}
    listing = listing or {s: None for s in bars}
    return Snapshot(list(sessions), built, halts or {}, listing, {s: ("index" if roles[s] == "benchmark" else "main") for s in bars}, roles, {s: "syn:listing" for s in bars},
                    meta={"synthetic": True, "captured_ref": "synthetic_capture"})


__all__ = ["DEV_START", "DEV_END", "WARM_START", "WARM_END", "BENCHMARK", "POLICY_PARAMS", "BRANCHES", "FROZEN", "Snapshot", "Replay", "load_frozen", "normalize_session", "price_text", "warmup_depths",
           "snapshot_from_rows", "b0_signal", "sma_window", "output_hash", "model_hash", "write_jsonl_gz", "synthetic_snapshot", "canonical", "sha256_text", "sha256_file"]
