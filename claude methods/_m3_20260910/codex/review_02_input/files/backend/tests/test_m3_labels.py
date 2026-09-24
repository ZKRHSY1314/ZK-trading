"""Adversarial synthetic tests for ``backend/app/research/m3_labels.py`` (policy 0.2.0-draft).

Run directly with the project interpreter (stdlib unittest, loaded by file path,
no ``app`` package import, no conftest, no SQLite, no network):

    D:/codex-A股交易/backend/.venv/Scripts/python.exe -B -X utf8 backend/tests/test_m3_labels.py -v

Every fixture is visibly synthetic (``SYN######`` symbols, ``synthetic=True``,
``SYNTHETIC_ONLY:`` evidence refs, a declared synthetic calendar) and is
excluded from real case counts by the module itself.  The ``CodexReviewReproductions``
class re-expresses every failing method of Codex's independent review
(``_m3_20260910/codex/test_independent_contract.py``) against the revised API.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import math
import sys
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "research" / "m3_labels.py"


def _load():
    spec = importlib.util.spec_from_file_location("m3_labels_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses need the module registered before exec
    spec.loader.exec_module(module)
    return module


m = _load()

# --------------------------------------------------------------------------- #
# Synthetic fixtures (deterministic; no wall clock, no randomness module)      #
# --------------------------------------------------------------------------- #

SYN_A = "SYN000001"
SYN_B = "SYN000002"
SYN_BENCH = "SYN900300"
EARLY = "2022-12-31T00:00:00+08:00"
SYN_EVIDENCE = ("SYNTHETIC_ONLY:evidence:fixture",)
SYN_EXEC = "SYNTHETIC_ONLY:execution:fixture"


def sessions(start: str, n: int) -> list[str]:
    d = date.fromisoformat(start)
    out: list[str] = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


CAL_DATES = sessions("2023-01-02", 420)
CAL = m.SessionCalendar(tuple(CAL_DATES), "SYNTHETIC_ONLY:weekday-calendar-2023", EARLY, synthetic=True)


def lcg(seed: int):
    x = seed
    while True:
        x = (1103515245 * x + 12345) % 2**31
        yield x / 2**31


def bars_from(symbol: str, dates, closes, volumes, *, avail_hours: float = 3.0, avail_fixed: str | None = None,
              upper_shadow: float = 0.01) -> list:
    rows = []
    prev = None
    for d, c, v in zip(dates, closes, volumes):
        o = prev if prev is not None else c
        hi = max(o, c) * (1.0 + upper_shadow)
        lo = min(o, c) * 0.99
        amt = v * (hi + lo) / 2.0
        available = avail_fixed or (m.close_time(d) + timedelta(hours=avail_hours)).isoformat()
        rows.append(m.Observation(symbol=symbol, trade_date=d, kind="price", available_at=available,
                                  source_ref=f"syn:{symbol}:{d}", open=round(o, 4), high=round(hi, 4), low=round(lo, 4),
                                  close=round(c, 4), volume=float(v), amount=round(amt, 2)))
        prev = c
    return rows


def suspension(symbol: str, d: str):
    return m.Observation(symbol=symbol, trade_date=d, kind="full_day_suspension",
                         available_at=(m.close_time(d) + timedelta(hours=3)).isoformat(), source_ref=f"syn:susp:{symbol}:{d}")


def sequence_positive_then_failed(seed: int = 7) -> tuple[list[str], list[float], list[int]]:
    """300 range-bound sessions, 20 markup sessions (+30%, 1.6x volume), 15 failing sessions (-18%), 25 drift."""
    r = lcg(seed)
    closes: list[float] = []
    vols: list[int] = []
    c = 10.0
    for i in range(300):
        c = 10.4 - 0.0012 * i + (next(r) - 0.5) * 0.7
        closes.append(c)
        vols.append(1_000_000 + int(next(r) * 200_000))
    for _ in range(20):
        c *= 1.0135
        closes.append(c)
        vols.append(1_700_000 + int(next(r) * 200_000))
    for _ in range(15):
        c *= 0.987
        closes.append(c)
        vols.append(1_050_000 + int(next(r) * 100_000))
    for _ in range(25):
        c *= 1.0 + (next(r) - 0.5) * 0.01
        closes.append(c)
        vols.append(1_000_000 + int(next(r) * 100_000))
    return CAL_DATES[: len(closes)], closes, vols


def sequence_distribution(seed: int = 11, n_rise: int = 280) -> tuple[list[str], list[float], list[int]]:
    r = lcg(seed)
    closes: list[float] = []
    vols: list[int] = []
    c = 10.0
    for i in range(n_rise):
        c *= 1.0 + 0.0022 + (next(r) - 0.5) * 0.006
        closes.append(c)
        vols.append(1_000_000 + int(next(r) * 150_000))
    closes.append(c * 0.985)
    vols.append(2_600_000)
    return CAL_DATES[: len(closes)], closes, vols


def cutoff_for(decision_date: str, mode: str = m.MODE_STRICT, hours: float = 4.0):
    return m.Cutoff(decision_date, (m.close_time(decision_date) + timedelta(hours=hours)).isoformat(), mode)


def request_for(symbol: str, rows, decision_date: str, mode: str = m.MODE_STRICT, **kw):
    kw.setdefault("calendar", CAL)
    return m.LabelRequest(symbol=symbol, observations=rows, cutoff=cutoff_for(decision_date, mode), synthetic=True, **kw)


def verified_context(**kw) -> "m.SecurityContext":
    base = dict(corporate_action_status=m.CA_NONE_VERIFIED, evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
    base.update(kw)
    return m.SecurityContext(**base)


def coverage(ratio: float = 1.0, available_at: str = EARLY):
    return m.Coverage(ratio, "SYNTHETIC_ONLY:coverage", available_at)


def bench_for(dates, drift: float = 0.002):
    return bars_from(SYN_BENCH, dates, [3000.0 * (1.0 + drift) ** i for i in range(len(dates))], [10_000_000] * len(dates))


def syn_review(case, reviewer: str, verdict: str, when: str = "2026-09-11T02:00:00+00:00", **kw):
    base = dict(reviewer_id=reviewer, reviewer_kind="agent", reviewed_at=when, verdict=verdict,
                evidence_refs=(f"SYNTHETIC_ONLY:evidence:{reviewer}",), execution_ref=f"SYNTHETIC_ONLY:execution:{reviewer}",
                case_episode_id=case["episode_id"], case_record_hash=case["record_hash"], case_policy_hash=case["policy_hash"],
                synthetic=True)
    base.update(kw)
    return m.ReviewRecord(**base)


def stable(o: dict) -> dict:
    return {k: v for k, v in o.items() if k != "request_diagnostics"}


# Codex-style flat fixture (270 sessions from 2024-01-01, availability exactly at the close)
CODEX_DATES = sessions("2024-01-01", 300)
CODEX_CAL = m.SessionCalendar(tuple(CODEX_DATES), "SYNTHETIC_ONLY:weekday-calendar-2024", EARLY, synthetic=True)


def codex_fixture(symbol: str = SYN_A, count: int = 270, price: float = 10.0) -> list:
    return [m.Observation(symbol=symbol, trade_date=day, kind="price", available_at=m.close_time(day).isoformat(),
                          source_ref=f"SYNTHETIC_ONLY:{symbol}:{i}", open=price, high=price * 1.1, low=price * 0.9,
                          close=price, volume=2_000_000.0, amount=2_000_000.0 * price) for i, day in enumerate(CODEX_DATES[:count])]


def codex_request(**changes):
    rows = codex_fixture()
    values = dict(symbol=SYN_A, observations=rows, cutoff=m.Cutoff(rows[-1].trade_date, rows[-1].available_at),
                  synthetic=True, calendar=CODEX_CAL)
    values.update(changes)
    return m.LabelRequest(**values)


def codex_summary(symbol: str, day: str, selection: str = "non_candidate", record_hash: str | None = None, **kw) -> dict:
    """A compact summary carrying every field the revised matcher requires."""
    base = dict(episode_id="SYNTHETIC_ONLY:" + symbol + ":" + day, record_hash=record_hash or m.sha256_text(symbol + day),
                symbol=symbol, role="stock", decision_date=day, policy_hash=m.POLICY_HASH, policy_version=m.POLICY_VERSION,
                mode="strict", convention="close+0s", selection=selection,
                phase="accumulation" if selection == "candidate" else "markup", liquidity_band="L1_thin", regime="range",
                amount_20_mean_cny=20_000_000.0, synthetic=True, in_frozen_universe=False, universe_sha256=None,
                split_role=m.split_role(day), current_state="observed")
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# Policy identity and integrity (R3 policy export)                            #
# --------------------------------------------------------------------------- #


class PolicyIdentityTests(unittest.TestCase):
    def test_namespace_version_and_hash(self):
        self.assertEqual(m.NAMESPACE, "m3.labels")
        self.assertEqual(m.POLICY_VERSION, "0.2.0-draft")
        self.assertEqual(m.OUTPUT_SCHEMA, "m3.labels.output.v2")
        self.assertEqual(m.POLICY_HASH, m.sha256_text(m.canonical_json(m.POLICY)))
        self.assertEqual(m.SUPERSEDES["module_sha256"], "6a0590cf2dd9b7acbc9421c818e558e24d6c2877175c8a903d47dab375a99065")
        self.assertEqual(m.policy_document()["policy_hash"], m.POLICY_HASH)
        self.assertFalse(m.POLICY["safety"]["live_trading_enabled"])

    def test_module_is_pure_stdlib_and_clock_free(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        allowed = {"copy", "hashlib", "json", "math", "re", "dataclasses", "datetime", "pathlib", "typing", "__future__"}
        self.assertTrue(imported <= allowed, imported - allowed)
        for forbidden in ("date.today", "datetime.now", "utcnow(", "time.time", "sqlite3", "urlopen", "pandas", "random", "subprocess"):
            self.assertNotIn(forbidden, source, forbidden)

    def test_exported_policy_mutation_cannot_change_labels_under_the_same_hash(self):
        before = m.generate_labels(codex_request())
        doc = m.policy_document()
        doc["policy"]["phase_rules"]["accumulation"]["position_250_lt"] = -1  # mutate the export copy
        after = m.generate_labels(codex_request())
        self.assertEqual(stable(before), stable(after))
        self.assertEqual(after["policy_hash"], m.POLICY_HASH)
        # mutating the public POLICY dict is detected fail-closed and cannot run under the old hash
        original = copy.deepcopy(m.POLICY)
        try:
            m.POLICY["phase_rules"]["accumulation"]["position_250_lt"] = -1
            with self.assertRaises(m.LabelInputError) as ctx:
                m.generate_labels(codex_request())
            self.assertEqual(ctx.exception.code, "policy_hash_mismatch")
        finally:
            m.POLICY.clear()
            m.POLICY.update(original)
        # mutating the private live rules is detected too
        rules_backup = copy.deepcopy(m._RULES)
        try:
            m._RULES["phase_rules"]["accumulation"]["position_250_lt"] = -1
            with self.assertRaises(m.LabelInputError):
                m.generate_labels(codex_request())
            with self.assertRaises(m.LabelInputError):
                m.match_controls(before, [])
        finally:
            m._RULES.clear()
            m._RULES.update(rules_backup)
        self.assertEqual(m.assert_policy_integrity(), m.POLICY_HASH)


# --------------------------------------------------------------------------- #
# Input rejection (stock rows, calendar, context, coverage, roles)            #
# --------------------------------------------------------------------------- #


class InputRejectionTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def _expect(self, code: str, rows, symbol=SYN_A, synthetic=True, **kw):
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_observations(rows, symbol, synthetic, **kw)
        self.assertEqual(ctx.exception.code, code)

    def test_wrong_identity_duplicate_unsorted(self):
        self._expect("wrong_security_identity", self.rows, symbol=SYN_B)
        self._expect("duplicate_key", self.rows[:5] + [self.rows[4]])
        self._expect("unsorted_input", [self.rows[1], self.rows[0]])
        self._expect("no_observations", [])

    def test_symbol_patterns_and_roles(self):
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_symbol("SZ002115", synthetic=True)
        self.assertEqual(ctx.exception.code, "synthetic_symbol_pattern")
        with self.assertRaises(m.LabelInputError):
            m.validate_symbol(SYN_A, synthetic=False)
        with self.assertRaises(m.LabelInputError):
            m.validate_symbol("sz002115", synthetic=False)
        self.assertEqual(m.validate_symbol("BJ920006", synthetic=False), "BJ920006")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_symbol("SH000300", synthetic=False)  # a benchmark cannot be labelled as a stock
        self.assertEqual(ctx.exception.code, "instrument_role_mismatch")
        self.assertEqual(m.validate_symbol("SH000300", synthetic=False, role="benchmark"), "SH000300")
        with self.assertRaises(m.LabelInputError):
            m.validate_symbol(SYN_A, synthetic=True, role="benchmark")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_symbol(SYN_A, synthetic="yes")
        self.assertEqual(ctx.exception.code, "invalid_synthetic_flag")

    def test_nonfinite_bool_and_invalid_numbers(self):
        base = self.rows[0]

        def rep(**kw):
            return [m.Observation(**{**base.record(), **kw})]

        self._expect("nonfinite_or_missing_numeric", rep(close=float("nan")))
        self._expect("nonfinite_or_missing_numeric", rep(volume=float("inf")))
        self._expect("nonfinite_or_missing_numeric", rep(amount=True))
        self._expect("nonfinite_or_missing_numeric", rep(open=None))
        self._expect("invalid_price", rep(high=base.low - 0.01))
        self._expect("invalid_price", rep(low=0.0, close=0.0, open=0.0, high=0.0))
        self._expect("invalid_price", rep(close=base.high + 1.0))
        self._expect("invalid_volume_or_amount", rep(volume=-1.0))
        self._expect("invalid_volume_or_amount", rep(volume=0.0, amount=5.0))
        self._expect("vwap_outside_range", rep(amount=base.amount * 3.0))

    def test_availability_units_kinds_and_calendar(self):
        base = self.rows[0]

        def rep(**kw):
            return [m.Observation(**{**base.record(), **kw})]

        self._expect("availability_before_close", rep(available_at=(m.close_time(base.trade_date) - timedelta(minutes=1)).isoformat()))
        self._expect("invalid_available_at", rep(available_at="2023-01-02T18:00:00"))
        self._expect("invalid_available_at", rep(available_at=None))
        self._expect("unsupported_adjustment_mode", rep(adjustment_mode="qfq"))
        self._expect("unsupported_volume_unit", rep(volume_unit="hand"))
        self._expect("unknown_observation_kind", rep(kind="index"))
        self._expect("missing_source_ref", rep(source_ref=""))
        self._expect("invalid_trade_date", rep(trade_date="ERROR"))
        self._expect("suspension_with_prices", [m.Observation(**{**suspension(SYN_A, base.trade_date).record(), "close": 1.0})])
        self._expect("observation_not_a_session", rep(trade_date="2023-01-01"), calendar=CAL)  # a Sunday
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(m.LabelRequest(symbol=SYN_A, observations=self.rows, cutoff=cutoff_for(self.dates[299]), synthetic=True))
        self.assertEqual(ctx.exception.code, "calendar_required")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, "2023-12-31"))
        self.assertEqual(ctx.exception.code, "decision_date_not_a_session")
        bad_cal = m.SessionCalendar(("2023-01-02", "2023-01-02"), "x", EARLY, True)
        with self.assertRaises(m.LabelInputError):
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[299], calendar=bad_cal))
        with self.assertRaises(m.LabelInputError):
            m.SessionCalendar(("2023-01-02",), "x", "2023-01-01T00:00:00", True).validated()  # naive availability

    def test_cutoff_validation(self):
        with self.assertRaises(m.LabelInputError) as ctx:
            m.select_usable(self.rows, m.Cutoff("2023-06-01", "2023-06-01T10:00:00+08:00", "strict"))
        self.assertEqual(ctx.exception.code, "cutoff_before_decision_close")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.select_usable(self.rows, m.Cutoff("2023-06-01", "2023-06-10T15:00:00+08:00", "strict"))
        self.assertEqual(ctx.exception.code, "strict_cutoff_too_late")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.select_usable(self.rows, m.Cutoff("2023-06-01", "2023-06-01T16:00:00+08:00", "hindsight"))
        self.assertEqual(ctx.exception.code, "invalid_cutoff_mode")
        with self.assertRaises(m.LabelInputError):
            m.select_usable(self.rows, m.Cutoff("2023-06-01", "2023-06-01T16:00:00", "strict"))
        self.assertEqual(cutoff_for("2023-06-01").convention(), "close+14400s")

    def test_security_context_validation(self):
        def bad(code, **kw):
            with self.assertRaises(m.LabelInputError) as ctx:
                m.SecurityContext(**kw).validated()
            self.assertEqual(ctx.exception.code, code, kw)

        bad("invalid_security_context", corporate_action_status="KNOWN", known_ex_dates=("2024-09-26",), evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
        bad("invalid_security_context", corporate_action_status="known", evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
        bad("invalid_security_context", st_status="ST", evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
        bad("invalid_security_context", known_ex_dates=("2024-01-01",), evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)  # unknown status with dates
        bad("invalid_security_context", corporate_action_status="none_verified", known_ex_dates=("2024-01-01",), evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
        bad("invalid_security_context", corporate_action_status="partial_known", known_ex_dates=("2024-02-01", "2024-01-01"), evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
        bad("invalid_security_context", corporate_action_status="partial_known", known_ex_dates=("2024-13-01",), evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
        bad("invalid_security_context", float_shares=True, evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
        bad("invalid_security_context", float_shares=-1.0, evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
        bad("invalid_security_context", turnover_available="yes", evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
        bad("invalid_security_context", listing_date="20240101", evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
        bad("security_facts_without_evidence", st_status="not_st")
        bad("security_facts_without_availability", st_status="not_st", evidence_refs=SYN_EVIDENCE)
        bad("invalid_security_context", st_status="not_st", evidence_refs=SYN_EVIDENCE, facts_available_at="2023-01-01T00:00:00")
        bad("invalid_security_context", evidence_refs="not-a-tuple")
        m.SecurityContext().validated()  # all unknown needs no evidence
        verified_context().validated()

    def test_coverage_validation(self):
        for value in (True, False, float("nan"), float("inf"), 1.5, -1, "0.9"):
            with self.subTest(value=value):
                with self.assertRaises(m.LabelInputError) as ctx:
                    m.generate_labels(codex_request(universe_coverage_on_decision_date=value))
                self.assertEqual(ctx.exception.code, "invalid_universe_coverage")
        with self.assertRaises(m.LabelInputError):
            m.Coverage(0.9, "", EARLY).validated()
        with self.assertRaises(m.LabelInputError):
            m.Coverage(0.9, "SYNTHETIC_ONLY:x", "2023-01-01T00:00:00").validated()
        out = m.generate_labels(codex_request(universe_coverage_on_decision_date=None))
        self.assertEqual(out["labels"]["regime"]["regime"], "unknown")
        self.assertIn("universe_coverage_unknown", out["labels"]["regime"]["reasons"])
        self.assertEqual(out["identity"]["decision_inputs"]["coverage"]["status"], "unknown")

    def test_real_requests_need_real_calendar_universe_and_evidenced_coverage(self):
        dates, closes, vols = sequence_positive_then_failed()
        rows = bars_from("SH600011", dates, closes, vols, avail_fixed="2026-09-10T04:17:10+00:00")
        real_cal = m.SessionCalendar(tuple(CAL_DATES), "TEST_PIN:calendar", EARLY, synthetic=False)
        universe = m.FrozenUniverse(frozenset({"SH600011"}), "TEST_PIN:pilot_symbols.csv", "9" * 64)
        cutoff = m.Cutoff(dates[295], "2026-09-10T05:00:00+00:00", m.MODE_RETROSPECTIVE)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(m.LabelRequest(symbol="SH600011", observations=rows, cutoff=cutoff, calendar=CAL, universe=universe))
        self.assertEqual(ctx.exception.code, "synthetic_calendar_for_real_request")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(m.LabelRequest(symbol="SH600011", observations=rows, cutoff=cutoff, calendar=real_cal))
        self.assertEqual(ctx.exception.code, "universe_required")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(m.LabelRequest(symbol="SH600011", observations=rows, cutoff=cutoff, calendar=real_cal, universe=universe,
                                             universe_coverage_on_decision_date=0.95))
        self.assertEqual(ctx.exception.code, "coverage_without_evidence")
        out = m.generate_labels(m.LabelRequest(symbol="SH600011", observations=rows, cutoff=cutoff, calendar=real_cal, universe=universe))
        self.assertTrue(out["universe"]["in_frozen_universe"])
        self.assertFalse(out["pit"]["strict_pit_eligible"])
        self.assertFalse(out["universe"]["counts_toward_case_library"])


# --------------------------------------------------------------------------- #
# Causality, availability and whole-output PIT (R4, R5 series convention)      #
# --------------------------------------------------------------------------- #


class CausalityTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def test_strict_cutoff_excludes_late_availability(self):
        d = self.dates[280]
        late = self.rows[:281]
        late[-1] = m.Observation(**{**late[-1].record(), "available_at": (m.close_time(d) + timedelta(days=2)).isoformat()})
        usable, summary, diag = m.select_usable(late, cutoff_for(d))
        self.assertEqual(usable[-1].trade_date, self.dates[279])
        self.assertEqual(summary["availability_violations_consumed"], 0)
        self.assertEqual(diag["rows_excluded_late_availability"], 1)
        out = m.generate_labels(request_for(SYN_A, late, d))
        self.assertEqual(out["current_state"], "missing")  # the decision bar is not knowable yet
        self.assertEqual(out["labels"]["selection"]["label"], "indeterminate")

    def test_retrospective_capture_never_strict_pit(self):
        capture = "2026-09-10T04:17:10+00:00"
        rows = bars_from(SYN_A, self.dates, self.closes, self.vols, avail_fixed=capture)
        d = self.dates[300]
        strict = m.generate_labels(request_for(SYN_A, rows, d, m.MODE_STRICT))
        self.assertEqual(strict["input_availability"]["rows_consumed"], 0)
        self.assertEqual(strict["labels"]["phase"]["label"], "indeterminate")
        self.assertEqual(strict["request_diagnostics"]["rows_excluded_late_availability"], 301)
        retro = m.generate_labels(m.LabelRequest(symbol=SYN_A, observations=rows, calendar=CAL, synthetic=True,
                                                 cutoff=m.Cutoff(d, "2026-09-10T05:00:00+00:00", m.MODE_RETROSPECTIVE)))
        self.assertEqual(retro["input_availability"]["rows_consumed"], 301)
        self.assertEqual(retro["input_availability"]["availability_violations_consumed"], 0)  # captured before the 2026 as_of ...
        self.assertEqual(retro["input_availability"]["captured_after_decision_window"], 301)  # ... but long after the 2024 decision
        self.assertFalse(retro["pit"]["facts"]["stock_bars"])
        self.assertFalse(retro["pit"]["strict_pit_eligible"])
        self.assertFalse(retro["pit"]["training_eligible"])
        self.assertTrue(retro["pit"]["retrospective"])
        self.assertEqual(retro["pit"]["provenance_kind"], "retrospective_capture_not_point_in_time")
        self.assertNotEqual(retro["labels"]["phase"]["label"], "indeterminate")

    def test_suffix_mutation_and_truncation_invariance_stock(self):
        d = self.dates[290]
        full = m.generate_labels(request_for(SYN_A, self.rows, d))
        truncated = m.generate_labels(request_for(SYN_A, self.rows[:291], d))
        mutated_rows = self.rows[:291] + bars_from(SYN_A, self.dates[291:], [c * 3.0 for c in self.closes[291:]], [v * 5 for v in self.vols[291:]])
        mutated = m.generate_labels(request_for(SYN_A, mutated_rows, d))
        self.assertEqual(stable(full), stable(truncated))
        self.assertEqual(stable(full), stable(mutated))
        self.assertEqual(full["record_hash"], m.record_hash(full))
        self.assertEqual(full["episode_id"], mutated["episode_id"])
        self.assertNotEqual(full["request_diagnostics"], truncated["request_diagnostics"])

    def test_suffix_invariance_benchmark_context_and_state(self):
        d = self.dates[295]
        bench = bench_for(self.dates)
        ctx = verified_context()
        pos = m.PositionState(SYN_A, m.POLICY_HASH, self.dates[280], self.dates[281], float(self.rows[281].open),
                              evidence_ref="SYNTHETIC_ONLY:position", available_at=EARLY)
        base = request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=bench,
                           universe_coverage_on_decision_date=coverage(), security=ctx, position_state=pos)
        full = m.generate_labels(base)
        future_bench = bench[:296] + bars_from(SYN_BENCH, self.dates[296:], [1.0 + i for i in range(len(self.dates) - 296)], [1] * (len(self.dates) - 296))
        later_ctx = replace(ctx, known_ex_dates=(), corporate_action_status=m.CA_NONE_VERIFIED)
        variant = m.generate_labels(replace(base, benchmark_observations=future_bench, observations=self.rows[:296], security=later_ctx))
        self.assertEqual(stable(full), stable(variant))
        # a *later* known ex-date (after the cutoff) does not change the record either; an earlier one does
        after = replace(ctx, corporate_action_status=m.CA_PARTIAL_KNOWN, known_ex_dates=(self.dates[330],))
        before = replace(ctx, corporate_action_status=m.CA_PARTIAL_KNOWN, known_ex_dates=(self.dates[100],))
        out_after = m.generate_labels(replace(base, security=after))
        out_before = m.generate_labels(replace(base, security=before))
        self.assertEqual(out_after["labels"]["phase"]["label"], full["labels"]["phase"]["label"])
        self.assertIn("known_corporate_action_in_window", out_before["labels"]["phase"]["reasons"])
        self.assertNotEqual(out_after["episode_id"], full["episode_id"])  # different declared facts => different identity

    def test_state_isolation_and_repeatability(self):
        policy_before = m.POLICY_HASH
        d = self.dates[320]
        a1 = m.generate_labels(request_for(SYN_A, self.rows, d))
        other = bars_from(SYN_B, *sequence_distribution())
        m.generate_labels(request_for(SYN_B, other, other[-1].trade_date))
        a2 = m.generate_labels(request_for(SYN_A, self.rows, d))
        self.assertEqual(a1, a2)
        self.assertEqual(m.assert_policy_integrity(), policy_before)
        s1 = m.label_series(request_for(SYN_A, self.rows, d), self.dates[300:305])
        s2 = m.label_series(request_for(SYN_A, self.rows, d), self.dates[300:305])
        self.assertEqual(s1, s2)

    def test_series_keeps_the_declared_convention_and_consumes_decision_bars(self):
        req = request_for(SYN_A, self.rows, self.dates[299])  # close+4h; bars available at close+3h
        series = m.label_series(req, self.dates[290:295])
        for out, d in zip(series, self.dates[290:295]):
            self.assertEqual(out["cutoff"]["decision_date"], d)
            self.assertEqual(out["cutoff"]["convention"], "close+14400s")
            self.assertEqual(out["current_state"], "observed")
            self.assertEqual(out["input_availability"]["max_trade_date_consumed"], d)
        tight = m.LabelRequest(symbol=SYN_A, observations=self.rows, calendar=CAL, synthetic=True,
                               cutoff=m.Cutoff(self.dates[299], m.close_time(self.dates[299]).isoformat()))  # close+0s
        strict_series = m.label_series(tight, self.dates[290:292])
        self.assertTrue(all(o["current_state"] == "missing" for o in strict_series))  # honestly reported, not silently shifted

    def test_strict_whole_output_pit_covers_every_consumed_fact(self):
        d = self.dates[295]
        late = (m.close_time(d) + timedelta(days=5)).isoformat()
        base = request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=bench_for(self.dates),
                           universe_coverage_on_decision_date=coverage(), security=verified_context())
        good = m.generate_labels(base)
        self.assertTrue(good["pit"]["strict_pit_eligible"])
        self.assertEqual(good["pit"]["consumed_fact_classes"], ["stock_bars", "benchmark_bars", "security_context", "coverage", "calendar"])
        late_ctx = m.generate_labels(replace(base, security=verified_context(facts_available_at=late)))
        self.assertFalse(late_ctx["pit"]["strict_pit_eligible"])
        self.assertFalse(late_ctx["identity"]["decision_inputs"]["context_usable"])
        self.assertIn("security_facts_not_available_at_cutoff", late_ctx["data_quality"])
        self.assertEqual(late_ctx["labels"]["position_event"]["label"], "no_trade")
        late_cov = m.generate_labels(replace(base, universe_coverage_on_decision_date=coverage(available_at=late)))
        self.assertFalse(late_cov["pit"]["strict_pit_eligible"])
        self.assertEqual(late_cov["labels"]["regime"]["regime"], "unknown")
        self.assertIn("universe_coverage_not_available_at_cutoff", late_cov["labels"]["regime"]["reasons"])
        late_cal = m.generate_labels(replace(base, calendar=replace(CAL, available_at=late)))
        self.assertFalse(late_cal["pit"]["strict_pit_eligible"])
        self.assertFalse(late_cal["pit"]["facts"]["calendar"])
        retro = m.generate_labels(replace(base, cutoff=cutoff_for(d, m.MODE_RETROSPECTIVE), security=verified_context(facts_available_at=late)))
        self.assertFalse(retro["pit"]["strict_pit_eligible"])
        self.assertEqual(retro["context_availability"]["status"], "consumed_with_availability_violation")


# --------------------------------------------------------------------------- #
# Decision identity (R3)                                                      #
# --------------------------------------------------------------------------- #


class IdentityTests(unittest.TestCase):
    def test_identity_binds_benchmark_context_coverage_calendar_and_state(self):
        base = codex_request(benchmark_symbol=SYN_BENCH, benchmark_observations=codex_fixture(SYN_BENCH, 270, 3000.0),
                             universe_coverage_on_decision_date=coverage())
        a = m.generate_labels(base)
        b = list(base.benchmark_observations)
        b[-1] = replace(b[-1], open=3600.0, high=3960.0, low=3300.0, close=3600.0, amount=2_000_000.0 * 3600.0)
        z = m.generate_labels(replace(base, benchmark_observations=b))
        self.assertNotEqual(a["labels"]["regime"], z["labels"]["regime"])
        self.assertNotEqual(a["episode_id"], z["episode_id"])
        self.assertNotEqual(a["record_hash"], z["record_hash"])
        known = verified_context(corporate_action_status=m.CA_PARTIAL_KNOWN, known_ex_dates=(base.cutoff.decision_date,))
        k = m.generate_labels(replace(base, security=known))
        self.assertNotEqual(a["labels"]["phase"]["label"], k["labels"]["phase"]["label"])
        self.assertNotEqual(a["episode_id"], k["episode_id"])
        c = m.generate_labels(replace(base, universe_coverage_on_decision_date=coverage(0.95)))
        self.assertNotEqual(a["episode_id"], c["episode_id"])
        other_cal = m.SessionCalendar(tuple(CODEX_DATES[:295]), "SYNTHETIC_ONLY:other-calendar", EARLY, True)
        cc = m.generate_labels(replace(base, calendar=other_cal))
        self.assertNotEqual(a["episode_id"], cc["episode_id"])
        rows = base.observations
        pos = m.PositionState(SYN_A, m.POLICY_HASH, rows[-6].trade_date, rows[-5].trade_date, float(rows[-5].open),
                              evidence_ref="SYNTHETIC_ONLY:position", available_at=EARLY)
        p = m.generate_labels(replace(base, position_state=pos))
        self.assertNotEqual(a["episode_id"], p["episode_id"])
        self.assertEqual(a["identity"]["decision_inputs"]["stock_rows"], p["identity"]["decision_inputs"]["stock_rows"])

    def test_record_hash_boundaries_and_tamper_detection(self):
        out = m.generate_labels(codex_request())
        self.assertEqual(m.record_hash(out), out["record_hash"])
        self.assertNotIn("review_ledger", {k for k in out if k in m._CORE_EXCLUDED} - {"review_ledger"})
        tampered = copy.deepcopy(out)
        tampered["labels"]["selection"]["label"] = "non_candidate"
        with self.assertRaises(m.LabelInputError) as ctx:
            m.verify_record(tampered)
        self.assertEqual(ctx.exception.code, "record_hash_mismatch")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.verify_record(dict(out, schema="m3.labels.output.v1"))
        self.assertEqual(ctx.exception.code, "unsupported_record")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.verify_record(dict(out, policy_hash="0" * 64))
        self.assertEqual(ctx.exception.code, "policy_hash_mismatch")
        m.verify_record(out)
        # a one-tick change in a consumed bar changes fingerprint, id and hash
        rows = list(codex_fixture())
        rows[100] = replace(rows[100], close=10.01, amount=2_000_000.0 * 10.005)
        other = m.generate_labels(codex_request(observations=rows))
        self.assertNotEqual(other["episode_id"], out["episode_id"])
        self.assertNotEqual(other["identity"]["decision_fingerprint"], out["identity"]["decision_fingerprint"])


# --------------------------------------------------------------------------- #
# Phase sequences                                                             #
# --------------------------------------------------------------------------- #


class PhaseSequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dates, cls.closes, cls.vols = sequence_positive_then_failed()
        cls.rows = bars_from(SYN_A, cls.dates, cls.closes, cls.vols)
        cls.series = m.label_series(request_for(SYN_A, cls.rows, cls.dates[-1]), cls.dates[249:])
        cls.by_date = {o["cutoff"]["decision_date"]: o for o in cls.series}
        cls.episodes = m.build_episodes(cls.series, CAL)

    def test_positive_markup_failed_sequence(self):
        path = [e["phase"] for e in self.episodes]
        self.assertIn("accumulation", path)
        self.assertIn("markup", path)
        self.assertIn("failed_markup", path)
        self.assertLess(path.index("accumulation"), path.index("markup"))
        self.assertLess(path.index("markup"), path.index("failed_markup"))
        failed = next(e for e in self.episodes if e["phase"] == "failed_markup")
        out = self.by_date[failed["start"]]
        self.assertTrue(out["labels"]["phase"]["markup_within_lookback"])
        self.assertEqual(out["labels"]["selection"]["label"], "non_candidate")
        self.assertEqual(failed["kind"], "failed")

    def test_accumulation_is_candidate_and_carries_semantics(self):
        acc = next(e for e in self.episodes if e["phase"] == "accumulation")
        out = self.by_date[acc["end"]]
        self.assertEqual(out["labels"]["selection"]["label"], "candidate")
        self.assertTrue(out["review_only"])
        self.assertFalse(out["live_trading_enabled"])
        self.assertFalse(out["semantics"]["hidden_actor_claim"])
        self.assertFalse(out["semantics"]["trade_recommendation"])
        self.assertEqual(out["labels"]["entry"]["tradability"], "unverified")
        self.assertEqual(out["labels"]["entry"]["execution"]["legal_next_session"], "unknown")
        self.assertEqual(out["labels"]["position_event"]["label"], "no_trade")
        self.assertEqual(out["current_state"], "observed")

    def test_failed_markup_requires_prior_observable_markup(self):
        r = lcg(3)
        closes, vols = [], []
        c = 10.0
        for _ in range(300):
            c = 10.0 + (next(r) - 0.5) * 0.1
            closes.append(c)
            vols.append(1_000_000)
        for _ in range(15):
            c *= 0.987
            closes.append(c)
            vols.append(1_000_000)
        dates = CAL_DATES[: len(closes)]
        rows = bars_from(SYN_B, dates, closes, vols)
        out = m.generate_labels(request_for(SYN_B, rows, dates[-1]))
        self.assertNotEqual(out["labels"]["phase"]["label"], "failed_markup")
        self.assertFalse(out["labels"]["phase"]["markup_within_lookback"])

    def test_accumulation_after_failed_markup_is_not_a_candidate(self):
        failed = next(e for e in self.episodes if e["phase"] == "failed_markup")
        following = [e for e in self.episodes if e["start"] > failed["end"] and e["phase"] == "accumulation"]
        self.assertTrue(following)
        out = self.by_date[following[0]["start"]]
        self.assertEqual(out["labels"]["selection"]["label"], "non_candidate")
        self.assertIn("failed_markup_within_veto_lookback", out["labels"]["selection"]["reasons"])


class DistributionAndAmbiguityTests(unittest.TestCase):
    def test_distribution_negative_case(self):
        dates, closes, vols = sequence_distribution()
        rows = bars_from(SYN_B, dates, closes, vols, upper_shadow=0.04)
        out = m.generate_labels(request_for(SYN_B, rows, dates[-1]))
        f = out["features"]
        self.assertGreater(f["position_250"], 0.78)
        self.assertGreater(f["volume_ratio_20"], 1.45)
        self.assertLess(f["close_to_high"], 0.97)
        self.assertEqual(out["labels"]["phase"]["label"], "distribution")
        self.assertEqual(out["labels"]["selection"]["label"], "non_candidate")

    def test_ambiguous_stays_indeterminate(self):
        dates, closes, vols = sequence_positive_then_failed()
        rows = bars_from(SYN_A, dates, closes, vols)
        outs = m.label_series(request_for(SYN_A, rows, dates[-1]), dates[300:340])
        indeterminate = [o for o in outs if o["labels"]["phase"]["rule"] == "no_rule_matched"]
        self.assertTrue(indeterminate)
        o = indeterminate[0]
        self.assertEqual(o["labels"]["phase"]["label"], "indeterminate")
        self.assertEqual(o["labels"]["selection"]["label"], "indeterminate")
        self.assertEqual(o["labels"]["entry"]["label"], "indeterminate")
        self.assertEqual(o["labels"]["position_event"]["label"], "no_trade")


# --------------------------------------------------------------------------- #
# Calendar and current-data quality (R5), corporate actions (R4), BJ scope    #
# --------------------------------------------------------------------------- #


class DataQualityTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def test_insufficient_warmup(self):
        out = m.generate_labels(request_for(SYN_A, self.rows[:200], self.dates[199]))
        self.assertEqual(out["labels"]["phase"]["label"], "indeterminate")
        self.assertTrue(any(r.startswith("insufficient_warmup:200<250") for r in out["labels"]["phase"]["reasons"]))

    def test_missing_decision_session_cannot_label_current_candidate(self):
        d = self.dates[295]
        out = m.generate_labels(request_for(SYN_A, self.rows[:295], d))  # yesterday's bar exists, today's does not
        self.assertEqual(out["current_state"], "missing")
        self.assertIn("decision_session_evidence_missing", out["labels"]["phase"]["reasons"])
        self.assertEqual(out["labels"]["selection"]["label"], "indeterminate")
        self.assertEqual(out["labels"]["entry"]["label"], "indeterminate")

    def test_suspension_on_decision_session_is_distinct_from_missing(self):
        d = self.dates[295]
        out = m.generate_labels(request_for(SYN_A, self.rows[:295] + [suspension(SYN_A, d)], d))
        self.assertEqual(out["current_state"], "suspended")
        self.assertIn("suspension_on_decision_session", out["labels"]["phase"]["reasons"])
        self.assertEqual(out["labels"]["selection"]["label"], "indeterminate")
        self.assertEqual(out["features"]["trade_date"], self.dates[294])

    def test_interior_gaps_suspension_runs_and_staleness_in_sessions(self):
        gap = self.rows[:280] + self.rows[281:296]  # one interior session without price or suspension
        out = m.generate_labels(request_for(SYN_A, gap, self.dates[295]))
        self.assertIn("interior_missing_sessions:1", out["labels"]["phase"]["reasons"])
        run = self.rows[:270] + [suspension(SYN_A, x) for x in self.dates[270:282]] + self.rows[282:296]
        out = m.generate_labels(request_for(SYN_A, run, self.dates[295]))
        reasons = out["labels"]["phase"]["reasons"]
        self.assertTrue(any(r.startswith("long_no_price_run_in_window:12") for r in reasons))
        self.assertTrue(any(r.startswith("many_suspensions_in_window:12") for r in reasons))
        self.assertEqual(out["session_view"]["suspensions_in_window"], 12)
        stale = m.generate_labels(request_for(SYN_A, self.rows[:290] + [suspension(SYN_A, x) for x in self.dates[290:293]], self.dates[292]))
        self.assertTrue(any(r.startswith("stale_last_price:3_sessions") for r in stale["labels"]["phase"]["reasons"]))
        self.assertEqual(stale["current_state"], "suspended")

    def test_corporate_action_handling(self):
        d = self.dates[295]
        known = verified_context(corporate_action_status=m.CA_PARTIAL_KNOWN, known_ex_dates=(self.dates[280],))
        out = m.generate_labels(request_for(SYN_A, self.rows, d, security=known))
        self.assertIn("known_corporate_action_in_window", out["labels"]["phase"]["reasons"])
        self.assertTrue(out["semantics"]["adjustment_uncertainty"])  # partial: completeness stays unknown
        unknown = m.generate_labels(request_for(SYN_A, self.rows, d))
        self.assertTrue(unknown["semantics"]["adjustment_uncertainty"])
        self.assertIn("adjustment_uncertainty:corporate_action_status=unknown", unknown["data_quality"])
        self.assertIn("turnover_unavailable", unknown["data_quality"])
        self.assertEqual(unknown["labels"]["phase"]["label"], "accumulation")
        verified = m.generate_labels(request_for(SYN_A, self.rows, d, security=verified_context()))
        self.assertFalse(verified["semantics"]["adjustment_uncertainty"])
        complete = m.generate_labels(request_for(SYN_A, self.rows, d, security=verified_context(corporate_action_status=m.CA_COMPLETE_KNOWN, known_ex_dates=(self.dates[10],))))
        self.assertFalse(complete["semantics"]["adjustment_uncertainty"])
        self.assertEqual(complete["labels"]["phase"]["label"], "accumulation")

    def test_bj_scope_exception_only_for_pinned_key(self):
        exc = m.POLICY["scope_exceptions"][0]
        self.assertEqual((exc["symbol"], exc["trade_date"]), ("BJ920006", "2023-12-04"))
        d = "2023-12-04"
        base = bars_from("BJ920006", [d], [12.5], [1_610_724])[0]
        bad = m.Observation(**{**base.record(), "high": 12.75, "low": 12.15, "open": 12.3, "close": 12.5, "volume": 1_610_724.0, "amount": 18_876_856.0})
        m.validate_observations([bad], "BJ920006", synthetic=False)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_observations([m.Observation(**{**bad.record(), "symbol": "BJ920007"})], "BJ920007", synthetic=False)
        self.assertEqual(ctx.exception.code, "vwap_outside_range")
        with self.assertRaises(m.LabelInputError):
            m.validate_observations([m.Observation(**{**bad.record(), "trade_date": "2023-12-05"})], "BJ920006", synthetic=False)
        self.assertIsNone(m._volume_for_ratio(bad))
        real_dates = [x for x in CAL_DATES if x <= d][-290:]
        idx = real_dates.index(d)
        closes = [12.4 + 0.05 * math.sin(i / 7.0) for i in range(len(real_dates))]
        rows = bars_from("BJ920006", real_dates, closes, [1_500_000] * len(real_dates), avail_fixed="2026-09-10T04:17:10+00:00")
        rows[idx] = m.Observation(**{**rows[idx].record(), "amount": 18_876_856.0, "volume": 1_610_724.0, "high": 12.75, "low": 12.15, "open": 12.3, "close": 12.5})
        real_cal = m.SessionCalendar(tuple(CAL_DATES), "TEST_PIN:calendar", EARLY, synthetic=False)
        universe = m.FrozenUniverse(frozenset({"BJ920006"}), "TEST_PIN:pilot_symbols.csv", "9" * 64)
        out = m.generate_labels(m.LabelRequest(symbol="BJ920006", observations=rows, synthetic=False, calendar=real_cal, universe=universe,
                                               cutoff=m.Cutoff(d, "2026-09-10T05:00:00+00:00", m.MODE_RETROSPECTIVE)))
        self.assertIsNone(out["features"]["volume_ratio_20"])
        self.assertIn("scope_exception_on_decision_bar", out["labels"]["phase"]["reasons"])
        self.assertEqual(out["labels"]["phase"]["label"], "indeterminate")


# --------------------------------------------------------------------------- #
# Trade state, position events (R6), prior state                             #
# --------------------------------------------------------------------------- #


class TradeStateTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def _confirmed_day(self, pct: float, vol_mult: float = 2.0, index: int = 295):
        rows = list(self.rows[: index - 1])
        prior_mean = sum(float(b.close) for b in rows[-20:]) / 20.0
        d0, d1 = self.dates[index - 1], self.dates[index]
        prev_open = float(rows[-1].close)
        rows.append(m.Observation(symbol=SYN_A, trade_date=d0, kind="price", source_ref=f"syn:{SYN_A}:{d0}",
                                  available_at=(m.close_time(d0) + timedelta(hours=3)).isoformat(),
                                  open=round(prev_open, 4), high=round(max(prev_open, prior_mean) * 1.003, 4),
                                  low=round(min(prev_open, prior_mean) * 0.997, 4), close=round(prior_mean, 4),
                                  volume=1_000_000.0, amount=round(1_000_000.0 * (prev_open + prior_mean) / 2.0, 2)))
        c = prior_mean * (1.0 + pct)
        vol = float(int(1_000_000 * vol_mult))
        rows.append(m.Observation(symbol=SYN_A, trade_date=d1, kind="price", source_ref=f"syn:{SYN_A}:{d1}",
                                  available_at=(m.close_time(d1) + timedelta(hours=3)).isoformat(),
                                  open=round(prior_mean, 4), high=round(c * 1.002, 4), low=round(prior_mean * 0.995, 4),
                                  close=round(c, 4), volume=vol, amount=round(vol * (prior_mean + c) / 2.0, 2)))
        return rows, d1

    def _position(self, entry_idx: int, ref_idx: int, **kw):
        base = dict(symbol=SYN_A, policy_hash=m.POLICY_HASH, entry_decision_date=self.dates[entry_idx], reference_date=self.dates[ref_idx],
                    reference_price=float(self.rows[ref_idx].open), reference_basis="next_session_open",
                    evidence_ref="SYNTHETIC_ONLY:position", available_at=EARLY)
        base.update(kw)
        return m.PositionState(**base)

    def test_signal_eligible_but_tradability_unverified(self):
        rows, d = self._confirmed_day(0.02)
        out = m.generate_labels(request_for(SYN_A, rows, d, security=verified_context(st_status="not_st")))
        self.assertEqual(out["labels"]["selection"]["label"], "candidate")
        self.assertEqual(out["labels"]["entry"]["label"], "signal_eligible", out["labels"]["entry"])
        self.assertEqual(out["labels"]["entry"]["tradability"], "unverified")
        self.assertEqual(out["labels"]["entry"]["execution"]["legal_next_session"], "unknown")

    def test_limit_unknown_is_conservative(self):
        rows, d = self._confirmed_day(0.05)
        unknown_st = m.generate_labels(request_for(SYN_A, rows, d))
        lim = unknown_st["labels"]["limit"]
        self.assertEqual((lim["board"], lim["threshold_pct"], lim["confidence"]), ("main", 4.8, "board_inferred_st_unknown_lowest_threshold"))
        self.assertTrue(lim["limit_like_possible"])
        self.assertNotEqual(unknown_st["labels"]["entry"]["label"], "signal_eligible")
        declared = m.generate_labels(request_for(SYN_A, rows, d, security=verified_context(st_status="not_st")))
        self.assertEqual(declared["labels"]["limit"]["threshold_pct"], 9.8)
        features = {"close": 10.5, "ma20": 10.0, "volume_ratio_20": 2.0, "zero_volume_session": False, "pct_change": 0.05}
        blocked = m.label_entry({"label": "candidate"}, features, m.limit_assessment(SYN_A, m.SecurityContext(), 0.05))
        self.assertEqual(blocked["reasons"], ["limit_like_possible"])
        allowed = m.label_entry({"label": "candidate"}, features, m.limit_assessment(SYN_A, verified_context(st_status="not_st"), 0.05))
        self.assertEqual(allowed["label"], "signal_eligible")
        self.assertIn("limit_state_unknown", m.label_entry({"label": "candidate"}, features, m.limit_assessment(SYN_A, m.SecurityContext(), None))["reasons"])
        self.assertIn("limit_down_possible", m.label_entry({"label": "candidate"}, dict(features, pct_change=-0.05), m.limit_assessment(SYN_A, m.SecurityContext(), -0.05))["reasons"])
        self.assertEqual(m.limit_assessment("BJ920006", m.SecurityContext(), 0.10)["threshold_pct"], 29.0)
        self.assertEqual(m.limit_assessment("SZ301251", m.SecurityContext(), 0.10)["threshold_pct"], 19.5)
        # late-available ST declaration is not usable under strict: conservative threshold again
        late = m.generate_labels(request_for(SYN_A, rows, d, security=verified_context(st_status="not_st", facts_available_at=(m.close_time(d) + timedelta(days=3)).isoformat())))
        self.assertEqual(late["labels"]["limit"]["threshold_pct"], 4.8)

    def test_volume_ratio_below_min_blocks_entry(self):
        rows, d = self._confirmed_day(0.02, vol_mult=1.0)
        out = m.generate_labels(request_for(SYN_A, rows, d, security=verified_context(st_status="not_st")))
        self.assertIn("volume_ratio_below_min", out["labels"]["entry"]["reasons"])

    def test_position_events_with_verified_basis(self):
        ctx = verified_context()
        pos = self._position(295, 296)
        hold = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=pos, security=ctx))
        self.assertEqual(hold["labels"]["position_event"]["label"], "hold")
        self.assertTrue(hold["labels"]["position_event"]["basis_verified"])
        self.assertEqual(hold["labels"]["position_event"]["holding_sessions"], 2)
        exit_out = m.generate_labels(request_for(SYN_A, self.rows, self.dates[312], position_state=pos, security=ctx))
        self.assertEqual(exit_out["labels"]["position_event"]["label"], "exit_event")
        top = self._position(318, 319)
        stop = m.generate_labels(request_for(SYN_A, self.rows, self.dates[330], position_state=top, security=ctx))
        self.assertIn(stop["labels"]["position_event"]["label"], ("stop_event", "invalidation_event"))
        series = m.label_series(request_for(SYN_A, self.rows, self.dates[-1]), self.dates[320:340])
        failed_dates = [o["cutoff"]["decision_date"] for o in series if o["labels"]["phase"]["label"] == "failed_markup"]
        inv = m.generate_labels(request_for(SYN_A, self.rows, failed_dates[0], position_state=top, security=ctx))
        self.assertEqual(inv["labels"]["position_event"]["label"], "invalidation_event")
        long_pos = self._position(255, 256)
        held = m.generate_labels(request_for(SYN_A, self.rows, self.dates[290], position_state=long_pos, security=ctx))
        self.assertIn(held["labels"]["position_event"]["label"], ("exit_event", "stop_event"))
        self.assertEqual(m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], security=ctx))["labels"]["position_event"]["label"], "no_trade")

    def test_unverified_basis_yields_review_required_not_price_events(self):
        top = self._position(318, 319)
        unknown = m.generate_labels(request_for(SYN_A, self.rows, self.dates[330], position_state=top))  # corporate actions unknown
        ev = unknown["labels"]["position_event"]
        self.assertNotIn(ev["label"], ("stop_event", "exit_event"))
        self.assertIn(ev["label"], ("review_required", "invalidation_event"))
        self.assertFalse(ev["basis_verified"])
        self.assertTrue(ev["price_condition"]["close_le_stop_level"])  # reported, not claimed
        partial = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=self._position(295, 296),
                                                security=verified_context(corporate_action_status=m.CA_PARTIAL_KNOWN, known_ex_dates=(self.dates[10],))))
        self.assertEqual(partial["labels"]["position_event"]["label"], "review_required")
        in_window = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=self._position(295, 296),
                                                  security=verified_context(corporate_action_status=m.CA_COMPLETE_KNOWN, known_ex_dates=(self.dates[297],))))
        self.assertIn("known_corporate_action_in_holding_window", in_window["labels"]["position_event"]["reasons"])
        self.assertNotIn(in_window["labels"]["position_event"]["label"], ("stop_event", "exit_event"))
        missing = m.generate_labels(request_for(SYN_A, self.rows[:298], self.dates[298], position_state=self._position(295, 296), security=verified_context()))
        self.assertEqual(missing["labels"]["position_event"]["label"], "unknown")
        suspended = m.generate_labels(request_for(SYN_A, self.rows[:298] + [suspension(SYN_A, self.dates[298])], self.dates[298],
                                                  position_state=self._position(295, 296), security=verified_context()))
        self.assertEqual(suspended["labels"]["position_event"]["label"], "unknown")

    def test_position_state_rejections(self):
        def expect(code, pos, d=298, **kw):
            with self.assertRaises(m.LabelInputError) as ctx:
                m.generate_labels(request_for(SYN_A, self.rows, self.dates[d], position_state=pos, **kw))
            self.assertEqual(ctx.exception.code, code)

        expect("position_state_binding_mismatch", self._position(295, 296, symbol=SYN_B))
        expect("position_state_binding_mismatch", self._position(295, 296, policy_hash="0" * 64))
        expect("position_reference_before_entry", self._position(295, 285))
        expect("position_reference_before_entry", self._position(295, 295))  # next_session_open needs a later session
        expect("position_state_not_earlier", self._position(298, 299))
        expect("position_state_invalid_reference_price", self._position(295, 296, reference_price=float("nan")))
        expect("position_reference_price_mismatch", self._position(295, 296, reference_price=float(self.rows[296].open) * 1.5))
        expect("position_state_without_evidence", self._position(295, 296, evidence_ref=""))
        expect("position_state_without_availability", self._position(295, 296, available_at=None))
        expect("position_state_not_available_at_cutoff", self._position(295, 296, available_at="2030-01-01T00:00:00+08:00"))
        expect("position_state_invalid_basis", self._position(295, 296, reference_basis="guess"))
        expect("position_state_not_a_session", m.PositionState(SYN_A, m.POLICY_HASH, "2023-12-30", "2023-12-31", 10.0, evidence_ref="x", available_at=EARLY))
        declared = self._position(295, 296, reference_basis="declared", reference_price=9.0)
        out = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=declared, security=verified_context()))
        self.assertIn(out["labels"]["position_event"]["label"], ("hold", "exit_event", "stop_event"))

    def test_prior_state_binding(self):
        earlier = m.generate_labels(request_for(SYN_A, self.rows, self.dates[290]))
        as_of = earlier["cutoff"]["as_of"]
        good = m.PriorState(SYN_A, self.dates[290], as_of, m.POLICY_HASH, earlier["labels"]["phase"]["label"], earlier["episode_id"])
        m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=good))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=replace(good, phase="distribution")))
        self.assertEqual(ctx.exception.code, "prior_state_inconsistent")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=replace(good, episode_id="0" * 32)))
        self.assertEqual(ctx.exception.code, "prior_state_inconsistent")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=replace(good, policy_hash="f" * 64)))
        self.assertEqual(ctx.exception.code, "prior_state_binding_mismatch")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=replace(good, decision_date=self.dates[295])))
        self.assertEqual(ctx.exception.code, "prior_state_not_earlier")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=replace(good, as_of="2030-01-01T00:00:00+08:00")))
        self.assertEqual(ctx.exception.code, "prior_state_not_earlier")


# --------------------------------------------------------------------------- #
# Context: liquidity and regime                                               #
# --------------------------------------------------------------------------- #


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def test_liquidity_bands(self):
        self.assertEqual(m.label_liquidity({"amount_20_mean_cny": 1.0e7})["band"], "L1_thin")
        self.assertEqual(m.label_liquidity({"amount_20_mean_cny": 5.0e7})["band"], "L2_low")
        self.assertEqual(m.label_liquidity({"amount_20_mean_cny": 2.0e8})["band"], "L3_mid")
        self.assertEqual(m.label_liquidity({"amount_20_mean_cny": 9.0e8})["band"], "L4_deep")
        self.assertEqual(m.label_liquidity({"amount_20_mean_cny": None})["band"], "unknown")

    def test_regime_from_benchmark_and_market_wide_missingness(self):
        d = self.dates[295]
        n = 296

        def run(bench, cov=coverage(), **kw):
            return m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=bench,
                                                 universe_coverage_on_decision_date=cov, **kw))["labels"]["regime"]

        self.assertEqual(run(bench_for(self.dates[:n], 0.002))["regime"], "bull")
        self.assertEqual(run(bench_for(self.dates[:n], -0.002))["regime"], "bear")
        self.assertEqual(run(bench_for(self.dates[:n], 0.0))["regime"], "range")
        self.assertEqual(run(bench_for(self.dates[:n], 0.002)[-40:])["regime"], "unknown")
        missing_day = run(bench_for(self.dates[:n], 0.002)[:-1])
        self.assertIn("benchmark_bar_missing_on_decision_session", missing_day["reasons"])
        sparse = run(bench_for(self.dates[:n], 0.002), coverage(0.5))
        self.assertTrue(any(r.startswith("market_wide_missingness") for r in sparse["reasons"]))
        self.assertEqual(run(bench_for(self.dates[:n], 0.002), None)["regime"], "unknown")
        none = m.generate_labels(request_for(SYN_A, self.rows, d, universe_coverage_on_decision_date=coverage()))
        self.assertEqual(none["labels"]["regime"]["regime"], "unknown")
        late = list(bench_for(self.dates[:n], 0.002))
        late[-1] = replace(late[-1], available_at="2026-09-10T00:00:00+08:00")
        self.assertEqual(run(late)["regime"], "unknown")
        with self.assertRaises(m.LabelInputError):
            m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_observations=bench_for(self.dates[:n])))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_B, benchmark_observations=bars_from(SYN_B, self.dates[:n], [1.0] * n, [1] * n)))
        self.assertEqual(ctx.exception.code, "instrument_role_mismatch")


# --------------------------------------------------------------------------- #
# Case library: matching (R1), reviews (R2), episodes (R7), counting (R2/R8)  #
# --------------------------------------------------------------------------- #


class CaseLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dates, cls.closes, cls.vols = sequence_positive_then_failed()
        cls.rows = bars_from(SYN_A, cls.dates, cls.closes, cls.vols)
        cls.bench = bench_for(cls.dates)
        cls.d = cls.dates[295]
        cls.positive = m.generate_labels(request_for(SYN_A, cls.rows, cls.d, benchmark_symbol=SYN_BENCH, benchmark_observations=cls.bench,
                                                     universe_coverage_on_decision_date=coverage()))
        assert cls.positive["labels"]["selection"]["label"] == "candidate", cls.positive["labels"]["selection"]
        cls.pool = []
        for k in range(6):
            sym = f"SYN00001{k}"
            _, pc, pv = sequence_distribution(seed=11 + k, n_rise=295)
            prows = bars_from(sym, cls.dates[:296], [c * (1.0 + 0.03 * k) for c in pc], pv, upper_shadow=0.04)
            cls.pool.append(m.generate_labels(request_for(sym, prows, cls.d, benchmark_symbol=SYN_BENCH, benchmark_observations=cls.bench,
                                                          universe_coverage_on_decision_date=coverage())))
        _, fc, fv = sequence_distribution(seed=31, n_rise=293)
        far = bars_from("SYN000099", cls.dates[:294], fc, fv, upper_shadow=0.04)
        cls.pool.append(m.generate_labels(request_for("SYN000099", far, cls.dates[293], benchmark_symbol=SYN_BENCH, benchmark_observations=cls.bench,
                                                      universe_coverage_on_decision_date=coverage())))
        cls.pool.append(m.generate_labels(request_for(SYN_A, cls.rows, cls.dates[330], benchmark_symbol=SYN_BENCH, benchmark_observations=cls.bench,
                                                      universe_coverage_on_decision_date=coverage())))

    def test_same_date_matching_is_deterministic_and_outcome_free(self):
        match = m.match_controls(self.positive, self.pool)
        again = m.match_controls(self.positive, list(reversed(self.pool)))
        self.assertEqual(match, again)
        self.assertGreaterEqual(match["control_count"], 3)
        self.assertLessEqual(match["control_count"], 5)
        self.assertFalse(match["unmatched"])
        self.assertEqual(len({c["symbol"] for c in match["controls"]}), match["control_count"])
        self.assertTrue(all(c["symbol"] != SYN_A for c in match["controls"]))
        self.assertEqual(match["rejected_pool_counts"].get("same_symbol"), 1)
        self.assertEqual(match["rejected_pool_counts"].get("different_decision_date"), 1)
        self.assertEqual(match["positive_record_hash"], self.positive["record_hash"])
        self.assertTrue(all(len(c["record_hash"]) == 64 for c in match["controls"]))
        leaked = dict(m.case_summary(self.pool[0]), outcome_return_20=0.5)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, [leaked])
        self.assertEqual(ctx.exception.code, "outcome_leakage")
        with self.assertRaises(m.LabelInputError):
            m.match_controls(dict(self.positive, future_max=1.0), self.pool)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.pool[0], self.pool)
        self.assertEqual(ctx.exception.code, "positive_not_candidate")

    def test_duplicates_conflicts_and_identity_do_not_inflate_controls(self):
        one = self.pool[0]
        five_copies = m.match_controls(self.positive, [one] * 5)
        self.assertEqual(five_copies["control_count"], 1)
        self.assertEqual(five_copies["identical_duplicates_collapsed"], 4)
        self.assertTrue(five_copies["unmatched"])
        conflicting = copy.deepcopy(one)
        conflicting["labels"]["liquidity"]["band"] = "L2_low"
        conflicting["record_hash"] = m.record_hash(conflicting)  # a different, internally consistent version of the same control
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, [one, conflicting])
        self.assertEqual(ctx.exception.code, "conflicting_duplicate_control")
        tampered = copy.deepcopy(one)
        tampered["labels"]["selection"]["label"] = "non_candidate"
        tampered["symbol"] = "SYN000077"
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, [tampered])
        self.assertEqual(ctx.exception.code, "record_hash_mismatch")
        other_policy = dict(m.case_summary(one), policy_hash="0" * 64)
        self.assertEqual(m.match_controls(self.positive, [other_policy])["rejected_pool_counts"], {"policy_mismatch": 1})
        other_version = dict(m.case_summary(one), policy_version="0.1.0-draft")
        self.assertEqual(m.match_controls(self.positive, [other_version])["rejected_pool_counts"], {"policy_mismatch": 1})
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, [{"episode_id": "x", "symbol": "SYN000010", "decision_date": self.d}])
        self.assertEqual(ctx.exception.code, "malformed_summary")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, [dict(m.case_summary(one), synthetic="yes")])
        self.assertEqual(ctx.exception.code, "invalid_synthetic_flag")
        mixed_universe = dict(m.case_summary(one), universe_sha256="1" * 64)
        self.assertEqual(m.match_controls(self.positive, [mixed_universe])["rejected_pool_counts"], {"universe_mismatch": 1})
        convention = dict(m.case_summary(one), convention="close+0s")
        self.assertEqual(m.match_controls(self.positive, [convention])["rejected_pool_counts"], {"cutoff_convention_mismatch": 1})
        benchmark_role = dict(m.case_summary(one), role="benchmark", symbol=SYN_BENCH)
        self.assertEqual(m.match_controls(self.positive, [benchmark_role])["rejected_pool_counts"], {"not_a_stock": 1})
        suspended = dict(m.case_summary(one), current_state="suspended")
        self.assertEqual(m.match_controls(self.positive, [suspended])["rejected_pool_counts"], {"control_current_state_not_observed": 1})

    def test_matching_split_admission_and_unknown_context(self):
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, self.pool, purpose="target_counts")
        self.assertEqual(ctx.exception.code, "unknown_purpose")
        holdout_positive = dict(m.case_summary(self.positive), decision_date="2026-02-02", split_role="final_holdout")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(holdout_positive, self.pool)
        self.assertEqual(ctx.exception.code, "final_holdout_consumed")
        validation_positive = dict(m.case_summary(self.positive), decision_date="2025-06-02", split_role="validation")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(validation_positive, self.pool)
        self.assertEqual(ctx.exception.code, "split_role_not_admissible")
        ok = m.match_controls(validation_positive, [], purpose="validation_readonly_check")
        self.assertTrue(ok["unmatched"])
        no_regime = m.generate_labels(request_for(SYN_A, self.rows, self.d))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(no_regime, self.pool)
        self.assertEqual(ctx.exception.code, "positive_context_unknown")
        real_summary = dict(m.case_summary(self.positive), synthetic=False, in_frozen_universe=False)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(real_summary, [])
        self.assertEqual(ctx.exception.code, "outside_frozen_universe")
        reuse = m.control_reuse_counts([m.match_controls(self.positive, self.pool[:1]), m.match_controls(self.positive, self.pool), m.match_controls(self.positive, self.pool)])
        self.assertEqual((reuse["positives"], reuse["unmatched_positives"]), (3, 1))
        self.assertGreaterEqual(reuse["max_reuse"], 2)

    def test_review_provenance_binding(self):
        out = self.positive
        ledger = out["review_ledger"]
        self.assertEqual(ledger["status"], "pending_review")
        self.assertEqual(ledger["entries"], [])
        self.assertFalse(ledger["independence_asserted_by_generator"])
        self.assertEqual(ledger["bound_record_hash"], out["record_hash"])
        one = m.attach_review(out, syn_review(out, "synthetic_reviewer_A", "positive"))
        self.assertEqual(one["record_hash"], out["record_hash"])  # label core untouched
        self.assertNotEqual(one["review_ledger"]["ledger_hash"], out["review_ledger"]["ledger_hash"])
        self.assertEqual(one["review_ledger"]["status"], "single_review_not_independent")
        self.assertEqual(out["review_ledger"]["entries"], [])  # input not mutated
        # rejections
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(out, syn_review(out, "B", "positive", evidence_refs=()))
        self.assertEqual(ctx.exception.code, "review_without_evidence")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(out, syn_review(out, "B", "positive", execution_ref=""))
        self.assertEqual(ctx.exception.code, "review_without_execution_ref")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(out, syn_review(out, "B", "positive", reviewer_kind="rule_engine"))
        self.assertEqual(ctx.exception.code, "invalid_reviewer_kind")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(out, syn_review(out, "B", "positive", when="2026-09-11T02:00:00"))
        self.assertEqual(ctx.exception.code, "invalid_reviewed_at")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(out, syn_review(out, "B", "positive", synthetic=False))
        self.assertEqual(ctx.exception.code, "review_synthetic_flag_mismatch")
        other = self.pool[0]
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(other, syn_review(out, "B", "positive"))  # review of A attached to B
        self.assertEqual(ctx.exception.code, "review_case_binding_mismatch")
        stale_version = m.generate_labels(request_for(SYN_A, self.rows, self.d))  # same symbol/date, different consumed evidence
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(stale_version, syn_review(out, "B", "positive"))
        self.assertEqual(ctx.exception.code, "review_case_binding_mismatch")
        tampered = copy.deepcopy(one)
        tampered["review_ledger"]["entries"][0]["verdict"] = "negative"
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(tampered, syn_review(out, "C", "positive"))
        self.assertEqual(ctx.exception.code, "ledger_hash_mismatch")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(one, syn_review(out, "synthetic_reviewer_A", "positive"))
        self.assertEqual(ctx.exception.code, "duplicate_review")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(one, syn_review(out, "synthetic_reviewer_A", "negative", when="2026-09-11T05:00:00+00:00"))
        self.assertEqual(ctx.exception.code, "conflicting_duplicate_review")

    def test_review_disagreement_supersession_and_independence(self):
        out = self.positive
        one = m.attach_review(out, syn_review(out, "codex_synthetic", "positive"))
        two = m.attach_review(one, syn_review(out, "claude_synthetic", "ambiguous", when="2026-09-11T03:00:00+00:00"))
        self.assertEqual(two["review_ledger"]["status"], "disputed")
        self.assertEqual(two["review_ledger"]["agreement"], "disagree")
        self.assertIsNone(two["review_ledger"]["consensus_verdict"])
        self.assertEqual([e["verdict"] for e in two["review_ledger"]["entries"]], ["positive", "ambiguous"])
        earlier_hash = two["review_ledger"]["entries"][1]["entry_hash"]
        three = m.attach_review(two, syn_review(out, "claude_synthetic", "positive", when="2026-09-11T06:00:00+00:00",
                                                supersedes=earlier_hash, supersede_reason="re-read the volume evidence"))
        self.assertEqual(three["review_ledger"]["status"], "independently_reviewed")
        self.assertEqual(three["review_ledger"]["consensus_verdict"], "positive")
        self.assertEqual(len(three["review_ledger"]["entries"]), 3)  # disagreement history preserved
        self.assertFalse(three["review_ledger"]["approved"])
        with self.assertRaises(m.LabelInputError):
            m.attach_review(two, syn_review(out, "codex_synthetic", "negative", when="2026-09-11T07:00:00+00:00", supersedes=earlier_hash, supersede_reason="x"))  # not own entry
        with self.assertRaises(m.LabelInputError):
            m.attach_review(two, syn_review(out, "claude_synthetic", "positive", when="2026-09-11T07:00:00+00:00", supersedes=earlier_hash))  # no reason
        with self.assertRaises(m.LabelInputError) as ctx:  # the same reviewer repeating a verdict must supersede, not pile up
            m.attach_review(one, syn_review(out, "codex_synthetic", "positive", when="2026-09-11T09:00:00+00:00", evidence_refs=("SYNTHETIC_ONLY:evidence:again",)))
        self.assertEqual(ctx.exception.code, "duplicate_review")
        first_hash = one["review_ledger"]["entries"][0]["entry_hash"]
        same_again = m.attach_review(one, syn_review(out, "codex_synthetic", "positive", when="2026-09-11T09:00:00+00:00",
                                                    evidence_refs=("SYNTHETIC_ONLY:evidence:again",), supersedes=first_hash, supersede_reason="added evidence"))
        self.assertEqual(same_again["review_ledger"]["status"], "single_review_not_independent")  # one reviewer, however many entries
        self.assertEqual(len(same_again["review_ledger"]["entries"]), 2)

    def test_episodes_track_selection_changes_duration_and_continuity(self):
        series = m.label_series(request_for(SYN_A, self.rows, self.dates[-1]), self.dates[249:])
        episodes = m.build_episodes(series, CAL)
        for ep in episodes:
            self.assertEqual(ep["selection_at_end"], ep["selection_path"][-1]["selection"])
            self.assertEqual(ep["selection_at_start"], ep["selection_path"][0]["selection"])
            self.assertFalse(ep["counts_toward_case_library"])
            self.assertEqual(ep["policy_hash"], m.POLICY_HASH)
            if ep["sessions"] >= 3:
                self.assertEqual(ep["min_duration_established_at"], series[[o["cutoff"]["decision_date"] for o in series].index(ep["start"]) + 2]["cutoff"]["decision_date"])
            else:
                self.assertIsNone(ep["min_duration_established_at"])
                self.assertFalse(ep["meets_min_sessions"])
        self.assertTrue(episodes[-1]["open_at_last_cutoff"])
        self.assertEqual(episodes[-1]["status"], "open_censored")
        self.assertTrue(all(e["closed_reason"] in ("phase_change", "series_gap") for e in episodes[:-1]))
        acc = next(e for e in episodes if e["phase"] == "accumulation" and e["eligibility_changes"] > 0) if any(e["phase"] == "accumulation" and e["eligibility_changes"] > 0 for e in episodes) else None
        if acc is not None:
            self.assertGreater(len(acc["selection_path"]), 1)
        # a skipped session closes the episode with series_gap
        gapped = m.build_episodes(series[:5] + series[6:10], CAL)
        self.assertTrue(any(e["closed_reason"] == "series_gap" for e in gapped))
        # rejections
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes([series[0], series[0], series[0]], CAL)
        self.assertEqual(ctx.exception.code, "duplicate_decision_dates")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes([series[1], series[0]], CAL)
        self.assertEqual(ctx.exception.code, "series_not_chronological")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes(series[:2] + [dict(series[2], symbol=SYN_B)], CAL)
        self.assertIn(ctx.exception.code, ("mixed_symbols_in_series", "record_hash_mismatch"))
        tampered = copy.deepcopy(series[2])
        tampered["labels"]["phase"]["label"] = "markup"
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes(series[:2] + [tampered], CAL)
        self.assertEqual(ctx.exception.code, "record_hash_mismatch")
        other_conv = m.label_series(m.LabelRequest(symbol=SYN_A, observations=self.rows, calendar=CAL, synthetic=True,
                                                   cutoff=cutoff_for(self.dates[-1], hours=6)), self.dates[252:254])
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes(series[:3] + other_conv, CAL)
        self.assertEqual(ctx.exception.code, "mixed_conventions_in_series")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes(series[:3], CODEX_CAL)
        self.assertEqual(ctx.exception.code, "calendar_mismatch_in_series")

    def test_dependence_groups_chain_connect(self):
        def ep(symbol, start_idx, end_idx, key):
            return {"symbol": symbol, "phase": "accumulation", "start_session_index": start_idx, "end_session_index": end_idx,
                    "episode_key": key, "synthetic": False}

        chained = [ep("SH600011", 0, 10, "a"), ep("SH600011", 20, 30, "b"), ep("SH600011", 45, 50, "c"), ep("SH600011", 100, 110, "d"), ep("SH600226", 5, 8, "e")]
        groups = m.dependence_groups(chained)
        self.assertEqual(groups["effective_decision_groups"], 3)  # {a,b,c} chain, {d}, {e}
        self.assertEqual([g["members"] for g in groups["groups"]], [["a", "b", "c"], ["d"], ["e"]])
        overlapping = [ep("SH600011", 0, 10, "a"), ep("SH600011", 5, 30, "b")]
        self.assertEqual(m.dependence_groups(overlapping)["effective_decision_groups"], 1)
        synthetic = [dict(ep(SYN_A, 0, 10, "s1"), synthetic=True), dict(ep(SYN_A, 100, 110, "s2"), synthetic=True)]
        self.assertEqual(m.dependence_groups(synthetic)["effective_decision_groups"], 0)
        self.assertEqual(m.dependence_groups(synthetic)["synthetic_excluded"], 2)
        arithmetic = m.dependence_groups(synthetic, include_synthetic=True)
        self.assertEqual((arithmetic["effective_decision_groups"], arithmetic["effective_decision_groups_arithmetic"]), (0, 2))
        with self.assertRaises(m.LabelInputError):
            m.dependence_groups([{"symbol": "SH600011", "phase": "accumulation", "episode_key": "x"}])

    def test_library_counts_are_fail_closed(self):
        match = m.match_controls(self.positive, self.pool)
        reviewed = m.attach_review(m.attach_review(self.positive, syn_review(self.positive, "r1", "positive")),
                                   syn_review(self.positive, "r2", "positive", when="2026-09-11T03:00:00+00:00"))
        counts = m.library_counts([reviewed] + self.pool, [match], CAL)
        self.assertEqual(counts["records_total"], len(self.pool) + 1)
        self.assertEqual(counts["records_synthetic"], len(self.pool) + 1)
        self.assertEqual(counts["independently_reviewed"], 1)
        self.assertEqual(counts["positively_reviewed_episodes"], 0)  # synthetic reviews never count
        self.assertEqual(counts["qualified_positives"], 0)
        self.assertEqual(counts["effective_dependence_groups"], 0)
        self.assertEqual(counts["disqualified"], {"synthetic_review": 1})
        self.assertFalse(counts["target_met"])
        self.assertEqual(counts["target_min_reviewed_positives"], 50)
        pending = m.library_counts([self.positive], [], CAL)
        self.assertEqual(pending["pending_review"], 1)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.library_counts([self.positive], [], CAL, purpose="target_counts")
        self.assertEqual(ctx.exception.code, "unknown_purpose")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.library_counts([self.positive], [match, match], CAL)
        self.assertEqual(ctx.exception.code, "duplicate_match_record")
        admission = m.admit_cases([self.positive], "initial_library_admission")
        self.assertEqual(len(admission["admitted"]), 1)  # 2024 synthetic date sits in the development interval
        with self.assertRaises(m.LabelInputError):
            m.admit_cases([dict(self.positive, symbol="SYN000003")], "initial_library_admission")  # tamper => record_hash mismatch

    def test_outcome_annotation_is_separate(self):
        later = cutoff_for(self.dates[330])
        ann = m.annotate_outcome(self.positive, self.rows, later, CAL, horizon_sessions=20)
        self.assertEqual(ann["annotation_kind"], "later_known_outcome")
        self.assertTrue(ann["not_a_label"])
        self.assertFalse(ann["realized_return_claim"])
        self.assertEqual(ann["record_hash"], self.positive["record_hash"])
        self.assertEqual(ann["reference"]["date"], self.dates[296])
        self.assertNotIn("close_return_unadjusted", json.dumps(self.positive["labels"]))
        with self.assertRaises(m.LabelInputError):
            m.annotate_outcome(self.positive, self.rows, cutoff_for(self.d), CAL)
        self.assertEqual(m.annotate_outcome(self.positive, self.rows[:296], later, CAL)["status"], "pending_future_data")


# --------------------------------------------------------------------------- #
# Chronological protection (R8), seed context, universe, provenance          #
# --------------------------------------------------------------------------- #


class ProtectionTests(unittest.TestCase):
    def test_split_roles_and_purpose_allowlist(self):
        self.assertEqual(m.split_role("2023-09-04"), "development")
        self.assertEqual(m.split_role("2025-03-31"), "development")
        self.assertEqual(m.split_role("2025-04-01"), "validation")
        self.assertEqual(m.split_role("2025-12-31"), "validation")
        self.assertEqual(m.split_role("2026-01-01"), "final_holdout")
        self.assertEqual(m.split_role("2026-09-04"), "final_holdout")
        self.assertEqual(m.split_role("2023-09-01"), "outside_research_interval")
        self.assertEqual(m.POLICY["split_proposal"]["development"], ["2023-09-04", "2025-03-31"])
        self.assertEqual(m.POLICY["split_proposal"]["validation"], ["2025-04-01", "2025-12-31"])
        self.assertEqual(m.POLICY["split_proposal"]["final_holdout"], ["2026-01-01", "2026-09-04"])
        records = [{"decision_date": "2024-05-06"}, {"decision_date": "2026-02-02"}]
        for purpose in ("threshold_selection", "rule_selection", "target_count", "parameter_search", "initial_library_admission", "validation_readonly_check"):
            with self.assertRaises(m.LabelInputError) as ctx:
                m.guard_final_holdout(records, purpose)
            self.assertEqual(ctx.exception.code, "final_holdout_consumed", purpose)
        for bad in ("target_counts", "", "FINAL_REPORT", None):
            with self.assertRaises(m.LabelInputError) as ctx:
                m.guard_final_holdout(records[:1], bad)
            self.assertEqual(ctx.exception.code, "unknown_purpose")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.guard_final_holdout([{"decision_date": "2025-06-02"}], "target_count")
        self.assertEqual(ctx.exception.code, "split_role_not_admissible")
        self.assertEqual(m.guard_final_holdout([{"decision_date": "2025-06-02"}], "validation_readonly_check")["roles"], {"validation": 1})
        self.assertEqual(m.guard_final_holdout(records, "final_report")["roles"], {"development": 1, "final_holdout": 1})

    def test_seed_context_and_frozen_universe(self):
        seeds = m.seed_context()
        self.assertEqual({s["symbol"] for s in seeds}, {"SZ002115", "SZ002081"})
        for s in seeds:
            self.assertEqual((s["status"], s["in_frozen_universe"], s["case_count_contribution"], s["case_data_fabricated"], s["reviewed"]),
                             ("legacy_unverified", False, 0, False, False))
        universe = m.FrozenUniverse(frozenset({"SH600011", "BJ920006", "SZ002656"}), "TEST_PIN:pilot_symbols.csv", "9" * 64)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.assert_in_universe("SZ002115", universe)
        self.assertEqual(ctx.exception.code, "outside_frozen_universe")
        m.assert_in_universe("SH600011", universe)
        with self.assertRaises(m.LabelInputError):
            m.FrozenUniverse(frozenset(), "x", "9" * 64).validated()
        with self.assertRaises(m.LabelInputError):
            m.FrozenUniverse(frozenset({"SH600011"}), "x", "short").validated()
        dates, closes, vols = sequence_positive_then_failed()
        real_cal = m.SessionCalendar(tuple(CAL_DATES), "TEST_PIN:calendar", EARLY, synthetic=False)
        rows = bars_from("SZ002115", dates, closes, vols, avail_fixed="2026-09-10T04:17:10+00:00")
        outside = m.generate_labels(m.LabelRequest(symbol="SZ002115", observations=rows, synthetic=False, universe=universe, calendar=real_cal,
                                                   cutoff=m.Cutoff(dates[295], "2026-09-10T05:00:00+00:00", m.MODE_RETROSPECTIVE)))
        self.assertFalse(outside["universe"]["in_frozen_universe"])
        self.assertEqual(outside["universe"]["reason"], "outside_frozen_universe_separate_decision")
        self.assertEqual(m.POLICY["frozen_universe"]["sha256"], "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe")
        self.assertIn("SH600011 ex-dates 2024-07-11/2025-07-10/2026-07-03", m.POLICY["corporate_actions"]["m2_partial_facts"])

    def test_output_carries_required_provenance(self):
        dates, closes, vols = sequence_positive_then_failed()
        rows = bars_from(SYN_A, dates, closes, vols)
        out = m.generate_labels(request_for(SYN_A, rows, dates[295]))
        for key in ("policy_version", "policy_hash", "producer_sha256", "cutoff", "calendar", "current_state", "input_availability",
                    "context_availability", "pit", "provenance", "identity", "episode_id", "record_hash", "review_ledger", "data_quality", "split_role"):
            self.assertIn(key, out)
        self.assertEqual(out["producer_sha256"], m.producer_sha256())
        self.assertEqual(out["calendar"]["fingerprint"], CAL.fingerprint())
        self.assertTrue(out["calendar"]["synthetic"])
        self.assertTrue(all(ref.startswith("syn:") for ref in out["provenance"]["source_refs"]))
        self.assertTrue(out["synthetic"])
        json.dumps(out, allow_nan=False)


# --------------------------------------------------------------------------- #
# One-for-one reproductions of the Codex review's failing methods (new API)   #
# --------------------------------------------------------------------------- #


class CodexReviewReproductions(unittest.TestCase):
    """Each method mirrors a method of _m3_20260910/codex/test_independent_contract.py.
    Fixture adaptations to the revised API: a declared synthetic calendar, a SYN9##### benchmark
    symbol, evidenced SecurityContext/Coverage/PositionState, and full-field summaries."""

    def test_matching_duplicate_record_does_not_meet_three_control_minimum(self):
        p = codex_summary(SYN_A, "2024-09-02", "candidate")
        c = codex_summary(SYN_B, p["decision_date"])
        result = m.match_controls(p, [c] * 5)
        self.assertTrue(result["unmatched"])
        self.assertLessEqual(result["control_count"], 1)
        self.assertEqual(result["identical_duplicates_collapsed"], 4)

    def test_matching_same_control_symbol_on_five_dates_is_not_five_controls(self):
        p = codex_summary(SYN_A, "2024-09-06", "candidate")
        days = [f"2024-09-0{i}" for i in range(2, 7)]
        result = m.match_controls(p, [codex_summary(SYN_B, d) for d in days])
        self.assertTrue(result["unmatched"])
        self.assertLessEqual(result["control_count"], 1)
        self.assertEqual(result["rejected_pool_counts"].get("different_decision_date"), 4)

    def test_matching_mixed_policy_not_selected(self):
        p = codex_summary(SYN_A, "2024-09-02", "candidate")
        c = codex_summary(SYN_B, p["decision_date"], policy_hash="different-policy")
        result = m.match_controls(p, [c])
        self.assertEqual(result["control_count"], 0)
        self.assertEqual(result["rejected_pool_counts"], {"policy_mismatch": 1})

    def test_matching_later_decision_not_available_to_positive_cutoff(self):
        p = codex_summary(SYN_A, "2024-09-02", "candidate")
        c = codex_summary(SYN_B, "2024-09-03")
        result = m.match_controls(p, [c])
        self.assertEqual(result["control_count"], 0)
        self.assertEqual(result["rejected_pool_counts"], {"different_decision_date": 1})

    def test_episode_identity_binds_benchmark_that_changes_regime(self):
        base = codex_request(benchmark_symbol=SYN_BENCH, benchmark_observations=codex_fixture(SYN_BENCH, 270, 3000.0),
                             universe_coverage_on_decision_date=coverage())
        b = list(base.benchmark_observations)
        b[-1] = replace(b[-1], open=3600.0, high=3960.0, low=3300.0, close=3600.0, amount=2_000_000.0 * 3600.0)
        a = m.generate_labels(base)
        z = m.generate_labels(replace(base, benchmark_observations=b))
        self.assertNotEqual(a["labels"]["regime"], z["labels"]["regime"])
        self.assertNotEqual(a["episode_id"], z["episode_id"])

    def test_episode_identity_binds_security_context_that_changes_phase(self):
        base = codex_request()
        known = verified_context(corporate_action_status=m.CA_PARTIAL_KNOWN, known_ex_dates=(base.cutoff.decision_date,))
        a, b = m.generate_labels(base), m.generate_labels(replace(base, security=known))
        self.assertNotEqual(a["labels"]["phase"], b["labels"]["phase"])
        self.assertNotEqual(a["episode_id"], b["episode_id"])

    def test_late_benchmark_stays_unknown_at_decision_cutoff(self):
        b = codex_fixture(SYN_BENCH, 270, 3000.0)
        b[-1] = replace(b[-1], available_at="2026-09-10T00:00:00+08:00")
        out = m.generate_labels(codex_request(benchmark_symbol=SYN_BENCH, benchmark_observations=b, universe_coverage_on_decision_date=coverage()))
        self.assertEqual(out["labels"]["regime"]["regime"], "unknown")

    def test_invalid_context_enum_cannot_remove_adjustment_gate(self):
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(codex_request(security=m.SecurityContext(corporate_action_status="KNOWN", known_ex_dates=("2024-09-26",),
                                                                       evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)))
        self.assertEqual(ctx.exception.code, "invalid_security_context")

    def test_invalid_coverage_is_rejected_not_known_market_regime(self):
        for value in [True, float("nan"), 1.5, -1]:
            with self.subTest(value=value):
                with self.assertRaises(m.LabelInputError):
                    m.generate_labels(codex_request(benchmark_symbol=SYN_BENCH, benchmark_observations=codex_fixture(SYN_BENCH, 270, 3000.0),
                                                    universe_coverage_on_decision_date=value))

    def test_missing_decision_bar_cannot_label_current_candidate(self):
        rows = codex_fixture()
        out = m.generate_labels(codex_request(observations=rows[:-1]))
        self.assertEqual(out["current_state"], "missing")
        self.assertEqual(out["labels"]["selection"]["label"], "indeterminate")

    def test_duplicate_cutoffs_do_not_create_three_session_episode(self):
        out = m.generate_labels(codex_request())
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes([out, out, out], CODEX_CAL)
        self.assertEqual(ctx.exception.code, "duplicate_decision_dates")

    def test_episode_end_selection_is_current_end_not_first_member(self):
        rows = codex_fixture(count=272)
        req = codex_request(observations=rows, cutoff=m.Cutoff(rows[-1].trade_date, rows[-1].available_at))
        series = m.label_series(req, [rows[-3].trade_date, rows[-2].trade_date, rows[-1].trade_date])
        end = copy.deepcopy(series[-1])
        end["labels"]["selection"]["label"] = "non_candidate"
        end["record_hash"] = m.record_hash(end)  # a genuine, internally consistent later record with a changed selection
        episodes = m.build_episodes(series[:-1] + [end], CODEX_CAL)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["selection_at_start"], "candidate")
        self.assertEqual(episodes[0]["selection_at_end"], "non_candidate")
        self.assertEqual(episodes[0]["eligibility_changes"], 1)
        self.assertEqual(episodes[0]["min_duration_established_at"], rows[-1].trade_date)

    def test_review_without_any_evidence_cannot_be_independently_reviewed(self):
        out = m.generate_labels(codex_request())
        for who in ["synthetic_reviewer_A", "synthetic_reviewer_B"]:
            with self.assertRaises(m.LabelInputError) as ctx:
                out = m.attach_review(out, syn_review(out, who, "positive", evidence_refs=()))
            self.assertEqual(ctx.exception.code, "review_without_evidence")
        self.assertEqual(out["review_ledger"]["status"], "pending_review")

    def test_review_is_bound_to_specific_case_and_evidence_version(self):
        a = m.generate_labels(codex_request())
        rows = codex_fixture(count=269)
        b = m.generate_labels(codex_request(observations=rows, cutoff=m.Cutoff(rows[-1].trade_date, rows[-1].available_at)))
        review = syn_review(a, "synthetic_reviewer_A", "positive")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(b, review)
        self.assertEqual(ctx.exception.code, "review_case_binding_mismatch")

    def test_holdout_unknown_purpose_cannot_claim_protected(self):
        with self.assertRaises(m.LabelInputError) as ctx:
            m.guard_final_holdout([{"decision_date": "2026-03-01"}], "target_counts")
        self.assertEqual(ctx.exception.code, "unknown_purpose")

    def test_mutable_policy_export_cannot_change_labels_under_same_hash(self):
        before = m.generate_labels(codex_request())
        doc = m.policy_document()
        doc["policy"]["phase_rules"]["accumulation"]["position_250_lt"] = -1
        after = m.generate_labels(codex_request())
        self.assertEqual(after["labels"], before["labels"])
        self.assertEqual(after["policy_hash"], before["policy_hash"])

    def test_known_action_does_not_emit_unadjusted_price_stop(self):
        base = codex_request()
        rows = base.observations
        pos = m.PositionState(base.symbol, m.POLICY_HASH, rows[-4].trade_date, rows[-3].trade_date, 12.0, reference_basis="declared",
                              evidence_ref="SYNTHETIC_ONLY:position", available_at=EARLY)
        out = m.generate_labels(replace(base, position_state=pos,
                                        security=verified_context(corporate_action_status=m.CA_COMPLETE_KNOWN, known_ex_dates=(rows[-2].trade_date,))))
        self.assertEqual(out["labels"]["phase"]["label"], "indeterminate")
        self.assertNotIn(out["labels"]["position_event"]["label"], ["stop_event", "exit_event"])
        self.assertEqual(out["labels"]["position_event"]["label"], "review_required")
        self.assertIn("known_corporate_action_in_holding_window", out["labels"]["position_event"]["reasons"])
        self.assertTrue(out["labels"]["position_event"]["price_condition"]["close_le_stop_level"])

    def test_position_reference_before_entry_is_rejected(self):
        base = codex_request()
        rows = base.observations
        pos = m.PositionState(base.symbol, m.POLICY_HASH, rows[-4].trade_date, rows[-10].trade_date, 10.0,
                              evidence_ref="SYNTHETIC_ONLY:position", available_at=EARLY)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(replace(base, position_state=pos))
        self.assertEqual(ctx.exception.code, "position_reference_before_entry")


if __name__ == "__main__":
    unittest.main(verbosity=2)
