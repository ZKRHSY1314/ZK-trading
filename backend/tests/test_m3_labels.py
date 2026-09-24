"""Adversarial synthetic tests for ``backend/app/research/m3_labels.py`` (policy 0.3.0-draft).

Run directly with the project interpreter (stdlib unittest, loaded by file path,
no ``app`` package import, no conftest, no SQLite, no network):

    D:/codex-A股交易/backend/.venv/Scripts/python.exe -B -X utf8 backend/tests/test_m3_labels.py -v

Every fixture is visibly synthetic (``SYN######`` symbols, ``synthetic=True``,
``SYNTHETIC_ONLY:``/``syn:fixture-only`` refs, a declared synthetic calendar).  A few
counting tests build *fixture-only* records in real code format (``synthetic=False``
with ``syn:fixture-only`` evidence) purely to exercise the real-format admission branch
in memory; nothing is saved as a case and no review work is claimed.  The classes
``CodexReviewReproductions`` (R1), ``CodexR2ConsumerReproductions`` (R2) and
``CodexFeatureOracleReproductions`` re-express every method of Codex's independent
files against the revised API.
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
from types import SimpleNamespace

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


BENCH_UNITS = dict(volume_unit="not_applicable", amount_unit="not_applicable")  # retained M2 benchmark units


def bars_from(symbol: str, dates, closes, volumes, *, avail_hours: float = 3.0, avail_fixed: str | None = None,
              upper_shadow: float = 0.01, benchmark: bool = False) -> list:
    rows = []
    prev = None
    units = BENCH_UNITS if benchmark else {}
    for d, c, v in zip(dates, closes, volumes):
        o = prev if prev is not None else c
        hi = max(o, c) * (1.0 + upper_shadow)
        lo = min(o, c) * 0.99
        amt = v * (hi + lo) / 2.0
        available = avail_fixed or (m.close_time(d) + timedelta(hours=avail_hours)).isoformat()
        rows.append(m.Observation(symbol=symbol, trade_date=d, kind="price", available_at=available,
                                  source_ref=f"syn:{symbol}:{d}", open=round(o, 4), high=round(hi, 4), low=round(lo, 4),
                                  close=round(c, 4), volume=float(v), amount=round(amt, 2), **units))
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
    return bars_from(SYN_BENCH, dates, [3000.0 * (1.0 + drift) ** i for i in range(len(dates))], [10_000_000] * len(dates), benchmark=True)


def syn_review(case, reviewer: str, verdict: str, when: str = "2026-09-11T02:00:00+00:00", **kw):
    base = dict(reviewer_id=reviewer, reviewer_kind="agent", reviewed_at=when, verdict=verdict,
                evidence_refs=(f"SYNTHETIC_ONLY:evidence:{reviewer}",), execution_ref=f"SYNTHETIC_ONLY:execution:{reviewer}",
                case_episode_id=case["episode_id"], case_record_hash=case["record_hash"], case_policy_hash=case["policy_hash"],
                synthetic=case["synthetic"])
    base.update(kw)
    return m.ReviewRecord(**base)


def stable(o: dict) -> dict:
    return {k: v for k, v in o.items() if k != "request_diagnostics"}


# Codex-style flat fixture (sessions from 2024-01-01, availability exactly at the close)
CODEX_DATES = sessions("2024-01-01", 300)
CODEX_CAL = m.SessionCalendar(tuple(CODEX_DATES), "SYNTHETIC_ONLY:weekday-calendar-2024", EARLY, synthetic=True)


def codex_fixture(symbol: str = SYN_A, count: int = 270, price: float = 10.0) -> list:
    units = BENCH_UNITS if (symbol.startswith("SYN9") or symbol.startswith(("SH000", "SZ399"))) else {}
    return [m.Observation(symbol=symbol, trade_date=day, kind="price", available_at=m.close_time(day).isoformat(),
                          source_ref=f"SYNTHETIC_ONLY:{symbol}:{i}", open=price, high=price * 1.1, low=price * 0.9,
                          close=price, volume=2_000_000.0, amount=2_000_000.0 * price, **units) for i, day in enumerate(CODEX_DATES[:count])]


def codex_request(**changes):
    rows = codex_fixture()
    values = dict(symbol=SYN_A, observations=rows, cutoff=m.Cutoff(rows[-1].trade_date, rows[-1].available_at),
                  synthetic=True, calendar=CODEX_CAL)
    values.update(changes)
    return m.LabelRequest(**values)


def flat_record(symbol: str, end: int = 269, distribution_spike: bool = False, **changes):
    """A genuine record from the Codex-style flat fixture: candidate by rule, or a rule-level
    distribution control when the last bar spikes (high 13.5, close 13, 1.5x volume)."""
    rows = codex_fixture(symbol, end + 1)
    if distribution_spike:
        rows[-1] = replace(rows[-1], high=13.5, close=13.0, volume=3_000_000.0, amount=39_000_000.0)
    values = dict(symbol=symbol, observations=rows, cutoff=m.Cutoff(rows[-1].trade_date, rows[-1].available_at), synthetic=True,
                  calendar=CODEX_CAL, benchmark_symbol=SYN_BENCH, benchmark_observations=codex_fixture(SYN_BENCH, end + 1, 3000.0),
                  universe_coverage_on_decision_date=coverage())
    values.update(changes)
    return m.generate_labels(m.LabelRequest(**values))


REAL_FORMAT_CAL = replace(CODEX_CAL, source_ref="syn:fixture-only-real-format-calendar", synthetic=False)
REAL_FORMAT_SYMBOLS = ("SH600011", "SH600110", "SH600129", "SH600162")
REAL_FORMAT_UNIVERSE = m.FrozenUniverse(frozenset(REAL_FORMAT_SYMBOLS), "syn:fixture-only-universe", "1" * 64)


def real_format_record(symbol: str, end: int = 269, distribution_spike: bool = False, source_tag: str = "syn:fixture-only"):
    """Fixture-only record in real code format (synthetic=False) to exercise the real admission branch.
    NOT a real observation, NOT a real case; every ref says syn:fixture-only."""
    rows = codex_fixture(symbol, end + 1)
    rows = [replace(r, source_ref=f"{source_tag}:{symbol}:{i}") for i, r in enumerate(rows)]
    if distribution_spike:
        rows[-1] = replace(rows[-1], high=13.5, close=13.0, volume=3_000_000.0, amount=39_000_000.0)
    bench = [replace(b, symbol="SH000300", source_ref="syn:fixture-only-benchmark") for b in codex_fixture("SH000300", end + 1, 3000.0)]
    return m.generate_labels(m.LabelRequest(symbol=symbol, observations=rows, cutoff=m.Cutoff(rows[-1].trade_date, rows[-1].available_at),
                                            synthetic=False, calendar=REAL_FORMAT_CAL, universe=REAL_FORMAT_UNIVERSE,
                                            benchmark_symbol="SH000300", benchmark_observations=bench,
                                            universe_coverage_on_decision_date=m.Coverage(1.0, "syn:fixture-only-coverage", EARLY)))


def fixture_review(case, who: str, verdict: str = "positive", when: str = "2026-09-10T07:00:00+00:00", **kw):
    base = dict(reviewer_id=who, reviewer_kind="agent", reviewed_at=when, verdict=verdict,
                evidence_refs=("syn:fixture-only-case-evidence",), execution_ref="syn:fixture-only-execution:" + who,
                case_episode_id=case["episode_id"], case_record_hash=case["record_hash"], case_policy_hash=case["policy_hash"],
                synthetic=case["synthetic"])
    base.update(kw)
    return m.ReviewRecord(**base)


def admissible_library_fixture(changed_source: bool = False, bind_prefix: bool = True):
    """A genuinely admissible, fully bound episode + controls in fixture-only real format.

    Three consecutive candidate decisions of SH600011 (sessions 267..269) establish the
    three-session prefix; the representative (269) carries two non-synthetic fixture-only
    reviews explicitly bound to the prefix proof (case_prefix_hash); three distribution-spike
    controls on 269 give a revalidated 3-control match.  ``changed_source`` regenerates the two
    earlier members from another invented source (valid cores, different evidence)."""
    members = [real_format_record("SH600011", end) for end in (267, 268, 269)]
    if changed_source:
        members[:2] = [real_format_record("SH600011", end, source_tag="syn:fixture-only-changed-source") for end in (267, 268)]
    controls = [real_format_record(sym, 269, distribution_spike=True) for sym in REAL_FORMAT_SYMBOLS[1:]]
    representative = members[-1]
    proof = m.prefix_proof_for(members, REAL_FORMAT_CAL, representative)
    assert proof is not None and proof["established_at"] == representative["cutoff"]["decision_date"], proof
    for who in ("syn:fixture-only-reviewer-a", "syn:fixture-only-reviewer-b"):
        representative = m.attach_review(representative, fixture_review(representative, who, case_prefix_hash=proof["prefix_hash"] if bind_prefix else None))
    match = m.match_controls(representative, controls)
    assert not match["unmatched"] and match["control_count"] == 3, match
    return members[:-1] + [representative], controls, match


# --------------------------------------------------------------------------- #
# Policy identity and integrity                                               #
# --------------------------------------------------------------------------- #


class PolicyIdentityTests(unittest.TestCase):
    def test_namespace_version_and_hash(self):
        self.assertEqual(m.NAMESPACE, "m3.labels")
        self.assertEqual(m.POLICY_VERSION, "0.3.0-draft")
        self.assertEqual(m.OUTPUT_SCHEMA, "m3.labels.output.v3")
        self.assertEqual(m.POLICY_HASH, m.sha256_text(m.canonical_json(m.POLICY)))
        self.assertEqual(m.SUPERSEDES["0.2.0-draft"]["module_sha256"], "fe6046476f492aca4487492e47477166f47d1cfe052167adf021c0bf238d17e7")
        self.assertEqual(m.SUPERSEDES["0.1.0-draft"]["module_sha256"], "6a0590cf2dd9b7acbc9421c818e558e24d6c2877175c8a903d47dab375a99065")
        self.assertEqual(m.policy_document()["policy_hash"], m.POLICY_HASH)
        self.assertFalse(m.POLICY["safety"]["live_trading_enabled"])
        self.assertEqual(m.POLICY["case_library"]["targets"]["min_reviewed_positives"], 50)

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
        doc["policy"]["phase_rules"]["accumulation"]["position_250_lt"] = -1
        after = m.generate_labels(codex_request())
        self.assertEqual(stable(before), stable(after))
        original = copy.deepcopy(m.POLICY)
        try:
            m.POLICY["phase_rules"]["accumulation"]["position_250_lt"] = -1
            with self.assertRaises(m.LabelInputError) as ctx:
                m.generate_labels(codex_request())
            self.assertEqual(ctx.exception.code, "policy_hash_mismatch")
        finally:
            m.POLICY.clear()
            m.POLICY.update(original)
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
            m.validate_symbol("SH000300", synthetic=False)
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
        self._expect("observation_not_a_session", rep(trade_date="2023-01-01"), calendar=CAL)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(m.LabelRequest(symbol=SYN_A, observations=self.rows, cutoff=cutoff_for(self.dates[299]), synthetic=True))
        self.assertEqual(ctx.exception.code, "calendar_required")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, "2023-12-31"))
        self.assertEqual(ctx.exception.code, "decision_date_not_a_session")
        with self.assertRaises(m.LabelInputError):
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[299], calendar=m.SessionCalendar(("2023-01-02", "2023-01-02"), "x", EARLY, True)))
        with self.assertRaises(m.LabelInputError):
            m.SessionCalendar(("2023-01-02",), "x", "2023-01-01T00:00:00", True).validated()

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
        bad("invalid_security_context", known_ex_dates=("2024-01-01",), evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)
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
        m.SecurityContext().validated()
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
# Causality, availability, whole-output PIT, consumed identity (R2-E)          #
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
        self.assertEqual(diag["rows_excluded_late_availability"], 1)
        out = m.generate_labels(request_for(SYN_A, late, d))
        self.assertEqual(out["current_state"], "missing")
        self.assertEqual(out["labels"]["selection"]["label"], "indeterminate")

    def test_retrospective_capture_never_strict_pit(self):
        capture = "2026-09-10T04:17:10+00:00"
        rows = bars_from(SYN_A, self.dates, self.closes, self.vols, avail_fixed=capture)
        d = self.dates[300]
        strict = m.generate_labels(request_for(SYN_A, rows, d, m.MODE_STRICT))
        self.assertEqual(strict["input_availability"]["rows_consumed"], 0)
        self.assertEqual(strict["request_diagnostics"]["rows_excluded_late_availability"], 301)
        retro = m.generate_labels(m.LabelRequest(symbol=SYN_A, observations=rows, calendar=CAL, synthetic=True,
                                                 cutoff=m.Cutoff(d, "2026-09-10T05:00:00+00:00", m.MODE_RETROSPECTIVE)))
        self.assertEqual(retro["input_availability"]["rows_consumed"], 301)
        self.assertEqual(retro["input_availability"]["captured_after_decision_window"], 301)
        self.assertFalse(retro["pit"]["facts"]["stock_bars"])
        self.assertFalse(retro["pit"]["strict_pit_eligible"])
        self.assertFalse(retro["pit"]["training_eligible"])
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

    def test_suffix_invariance_benchmark_context_and_state(self):
        d = self.dates[295]
        bench = bench_for(self.dates)
        ctx = verified_context()
        pos = m.PositionState(SYN_A, m.POLICY_HASH, self.dates[280], self.dates[281], float(self.rows[281].open),
                              evidence_ref="SYNTHETIC_ONLY:position", available_at=(m.open_time(self.dates[281]) + timedelta(minutes=5)).isoformat())
        base = request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=bench,
                           universe_coverage_on_decision_date=coverage(), security=ctx, position_state=pos)
        full = m.generate_labels(base)
        future_bench = bench[:296] + bars_from(SYN_BENCH, self.dates[296:], [1.0 + i for i in range(len(self.dates) - 296)], [1] * (len(self.dates) - 296), benchmark=True)
        variant = m.generate_labels(replace(base, benchmark_observations=future_bench, observations=self.rows[:296]))
        self.assertEqual(stable(full), stable(variant))
        after = replace(ctx, corporate_action_status=m.CA_PARTIAL_KNOWN, known_ex_dates=(self.dates[330],))
        before = replace(ctx, corporate_action_status=m.CA_PARTIAL_KNOWN, known_ex_dates=(self.dates[100],))
        self.assertEqual(m.generate_labels(replace(base, security=after))["labels"]["phase"]["label"], full["labels"]["phase"]["label"])
        self.assertIn("known_corporate_action_in_window", m.generate_labels(replace(base, security=before))["labels"]["phase"]["reasons"])

    def test_offered_only_unavailable_facts_do_not_change_identity(self):
        d = self.dates[295]
        late = (m.close_time(d) + timedelta(days=5)).isoformat()
        base = request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=bench_for(self.dates),
                           universe_coverage_on_decision_date=coverage())
        plain = m.generate_labels(base)
        late_a = m.generate_labels(replace(base, security=m.SecurityContext(st_status="st", evidence_refs=("syn:late-a",), facts_available_at=late)))
        late_b = m.generate_labels(replace(base, security=m.SecurityContext(st_status="not_st", evidence_refs=("syn:late-b",), facts_available_at=late)))
        self.assertFalse(late_a["context_availability"]["usable"])
        self.assertEqual(late_a["labels"], late_b["labels"])
        self.assertEqual(late_a["episode_id"], late_b["episode_id"])
        self.assertEqual(late_a["record_hash"], late_b["record_hash"])
        self.assertEqual(late_a["security_context"], {"effective": "unknown", "status": "not_available_at_cutoff", "usable": False})
        self.assertEqual(late_a["request_diagnostics"]["offered_context_not_consumed"]["st_status"], "st")
        self.assertEqual(late_b["request_diagnostics"]["offered_context_not_consumed"]["evidence_refs"], ["syn:late-b"])
        self.assertNotEqual(late_a["episode_id"], plain["episode_id"])  # an offered-but-unavailable fact still leaves a deterministic mark
        self.assertFalse(late_a["pit"]["strict_pit_eligible"])
        self.assertEqual(late_a["provenance"]["context_evidence_refs"], [])
        # the same boundary for coverage: late coverage evidence is diagnostics, not identity
        cov_a = m.generate_labels(replace(base, universe_coverage_on_decision_date=coverage(0.99, late)))
        cov_b = m.generate_labels(replace(base, universe_coverage_on_decision_date=m.Coverage(0.5, "syn:other", late)))
        self.assertEqual(cov_a["episode_id"], cov_b["episode_id"])
        self.assertEqual(cov_a["labels"]["regime"]["regime"], "unknown")
        self.assertEqual(cov_a["request_diagnostics"]["offered_coverage_not_consumed"]["ratio"], 0.99)
        self.assertIsNone(cov_a["provenance"]["coverage_evidence_ref"])
        # consumed facts DO bind: two different available declarations differ
        used_a = m.generate_labels(replace(base, security=verified_context(st_status="st")))
        used_b = m.generate_labels(replace(base, security=verified_context(st_status="not_st")))
        self.assertNotEqual(used_a["episode_id"], used_b["episode_id"])
        self.assertEqual(used_a["provenance"]["context_evidence_refs"], list(SYN_EVIDENCE))

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
        req = request_for(SYN_A, self.rows, self.dates[299])
        series = m.label_series(req, self.dates[290:295])
        for out, d in zip(series, self.dates[290:295]):
            self.assertEqual((out["cutoff"]["decision_date"], out["cutoff"]["convention"], out["current_state"]), (d, "close+14400s", "observed"))
            self.assertEqual(out["input_availability"]["max_trade_date_consumed"], d)
        tight = m.LabelRequest(symbol=SYN_A, observations=self.rows, calendar=CAL, synthetic=True,
                               cutoff=m.Cutoff(self.dates[299], m.close_time(self.dates[299]).isoformat()))
        self.assertTrue(all(o["current_state"] == "missing" for o in m.label_series(tight, self.dates[290:292])))

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
        self.assertIn("security_facts_not_available_at_cutoff", late_ctx["data_quality"])
        late_cov = m.generate_labels(replace(base, universe_coverage_on_decision_date=coverage(available_at=late)))
        self.assertFalse(late_cov["pit"]["strict_pit_eligible"])
        self.assertIn("universe_coverage_not_available_at_cutoff", late_cov["labels"]["regime"]["reasons"])
        late_cal = m.generate_labels(replace(base, calendar=replace(CAL, available_at=late)))
        self.assertFalse(late_cal["pit"]["facts"]["calendar"])
        retro = m.generate_labels(replace(base, cutoff=cutoff_for(d, m.MODE_RETROSPECTIVE), security=verified_context(facts_available_at=late)))
        self.assertFalse(retro["pit"]["strict_pit_eligible"])
        self.assertEqual(retro["context_availability"]["status"], "consumed_with_availability_violation")


# --------------------------------------------------------------------------- #
# Decision identity and record verification                                   #
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
        known = verified_context(corporate_action_status=m.CA_PARTIAL_KNOWN, known_ex_dates=(base.cutoff.decision_date,))
        k = m.generate_labels(replace(base, security=known))
        self.assertNotEqual(a["labels"]["phase"]["label"], k["labels"]["phase"]["label"])
        self.assertNotEqual(a["episode_id"], k["episode_id"])
        self.assertNotEqual(a["episode_id"], m.generate_labels(replace(base, universe_coverage_on_decision_date=coverage(0.95)))["episode_id"])
        other_cal = m.SessionCalendar(tuple(CODEX_DATES[:295]), "SYNTHETIC_ONLY:other-calendar", EARLY, True)
        self.assertNotEqual(a["episode_id"], m.generate_labels(replace(base, calendar=other_cal))["episode_id"])
        rows = base.observations
        pos = m.PositionState(SYN_A, m.POLICY_HASH, rows[-6].trade_date, rows[-5].trade_date, float(rows[-5].open),
                              evidence_ref="SYNTHETIC_ONLY:position", available_at=(m.open_time(rows[-5].trade_date) + timedelta(minutes=1)).isoformat())
        p = m.generate_labels(replace(base, position_state=pos))
        self.assertNotEqual(a["episode_id"], p["episode_id"])

    def test_record_verification_and_tamper_detection(self):
        out = m.generate_labels(codex_request())
        self.assertEqual(m.record_hash(out), out["record_hash"])
        m.verify_record(out)

        def expect(code, **changes):
            tampered = copy.deepcopy(out)
            for k, v in changes.items():
                tampered[k] = v
            with self.assertRaises(m.LabelInputError) as ctx:
                m.verify_record(tampered)
            self.assertEqual(ctx.exception.code, code, changes)

        tampered = copy.deepcopy(out)
        tampered["labels"]["selection"]["label"] = "non_candidate"
        with self.assertRaises(m.LabelInputError) as ctx:
            m.verify_record(tampered)
        self.assertEqual(ctx.exception.code, "record_hash_mismatch")
        expect("unsupported_record", schema="m3.labels.output.v2")
        expect("policy_hash_mismatch", policy_hash="0" * 64)
        expect("policy_hash_mismatch", policy_version="0.2.0-draft")
        # derived fields must agree with their inputs even when the hash is recomputed by an attacker
        for key, value, code in (("split_role", "validation", "malformed_record"), ("role", "benchmark", "malformed_record"),
                                 ("current_state", "closed", "malformed_record"), ("episode_id", "0" * 32, "malformed_record")):
            forged = copy.deepcopy(out)
            forged[key] = value
            forged["record_hash"] = m.record_hash(forged)
            with self.assertRaises(m.LabelInputError) as ctx:
                m.verify_record(forged)
            self.assertEqual(ctx.exception.code, code, key)
        forged = copy.deepcopy(out)
        forged["cutoff"]["convention"] = "close+999s"
        forged["record_hash"] = m.record_hash(forged)
        with self.assertRaises(m.LabelInputError):
            m.verify_record(forged)
        forged = copy.deepcopy(out)
        forged["pit"]["training_eligible"] = True
        forged["record_hash"] = m.record_hash(forged)
        with self.assertRaises(m.LabelInputError):
            m.verify_record(forged)
        rows = list(codex_fixture())
        rows[100] = replace(rows[100], close=10.01, amount=2_000_000.0 * 10.005)
        other = m.generate_labels(codex_request(observations=rows))
        self.assertNotEqual(other["episode_id"], out["episode_id"])


# --------------------------------------------------------------------------- #
# Phase sequences, distribution, ambiguity                                    #
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
        self.assertEqual(out["labels"]["entry"]["tradability"], "unverified")
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
        out = m.generate_labels(request_for(SYN_B, bars_from(SYN_B, dates, closes, vols), dates[-1]))
        self.assertNotEqual(out["labels"]["phase"]["label"], "failed_markup")
        self.assertFalse(out["labels"]["phase"]["markup_within_lookback"])

    def test_accumulation_after_failed_markup_is_not_a_candidate(self):
        failed = next(e for e in self.episodes if e["phase"] == "failed_markup")
        following = [e for e in self.episodes if e["start"] > failed["end"] and e["phase"] == "accumulation"]
        out = self.by_date[following[0]["start"]]
        self.assertEqual(out["labels"]["selection"]["label"], "non_candidate")
        self.assertIn("failed_markup_within_veto_lookback", out["labels"]["selection"]["reasons"])


class DistributionAndAmbiguityTests(unittest.TestCase):
    def test_distribution_negative_case(self):
        dates, closes, vols = sequence_distribution()
        out = m.generate_labels(request_for(SYN_B, bars_from(SYN_B, dates, closes, vols, upper_shadow=0.04), dates[-1]))
        f = out["features"]
        self.assertGreater(f["position_250"], 0.78)
        self.assertGreater(f["volume_ratio_20"], 1.45)
        self.assertLess(f["close_to_high"], 0.97)
        self.assertEqual(out["labels"]["phase"]["label"], "distribution")
        self.assertEqual(out["labels"]["selection"]["label"], "non_candidate")

    def test_ambiguous_stays_indeterminate(self):
        dates, closes, vols = sequence_positive_then_failed()
        outs = m.label_series(request_for(SYN_A, bars_from(SYN_A, dates, closes, vols), dates[-1]), dates[300:340])
        o = next(o for o in outs if o["labels"]["phase"]["rule"] == "no_rule_matched")
        self.assertEqual((o["labels"]["phase"]["label"], o["labels"]["selection"]["label"], o["labels"]["entry"]["label"], o["labels"]["position_event"]["label"]),
                         ("indeterminate", "indeterminate", "indeterminate", "no_trade"))


# --------------------------------------------------------------------------- #
# Calendar and current-data quality, corporate actions, BJ scope              #
# --------------------------------------------------------------------------- #


class DataQualityTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def test_insufficient_warmup(self):
        out = m.generate_labels(request_for(SYN_A, self.rows[:200], self.dates[199]))
        self.assertTrue(any(r.startswith("insufficient_warmup:200<250") for r in out["labels"]["phase"]["reasons"]))

    def test_missing_decision_session_cannot_label_current_candidate(self):
        out = m.generate_labels(request_for(SYN_A, self.rows[:295], self.dates[295]))
        self.assertEqual(out["current_state"], "missing")
        self.assertIn("decision_session_evidence_missing", out["labels"]["phase"]["reasons"])
        self.assertEqual(out["labels"]["selection"]["label"], "indeterminate")
        self.assertEqual(out["session_view"]["interior_missing_sessions"], 0)

    def test_suspension_on_decision_session_is_distinct_from_missing(self):
        d = self.dates[295]
        out = m.generate_labels(request_for(SYN_A, self.rows[:295] + [suspension(SYN_A, d)], d))
        self.assertEqual(out["current_state"], "suspended")
        self.assertIn("suspension_on_decision_session", out["labels"]["phase"]["reasons"])
        self.assertEqual(out["features"]["trade_date"], self.dates[294])

    def test_interior_gaps_suspension_runs_and_staleness_in_sessions(self):
        out = m.generate_labels(request_for(SYN_A, self.rows[:280] + self.rows[281:296], self.dates[295]))
        self.assertIn("interior_missing_sessions:1", out["labels"]["phase"]["reasons"])
        run = self.rows[:270] + [suspension(SYN_A, x) for x in self.dates[270:282]] + self.rows[282:296]
        out = m.generate_labels(request_for(SYN_A, run, self.dates[295]))
        reasons = out["labels"]["phase"]["reasons"]
        self.assertTrue(any(r.startswith("long_no_price_run_in_window:12") for r in reasons))
        self.assertTrue(any(r.startswith("many_suspensions_in_window:12") for r in reasons))
        stale = m.generate_labels(request_for(SYN_A, self.rows[:290] + [suspension(SYN_A, x) for x in self.dates[290:293]], self.dates[292]))
        self.assertTrue(any(r.startswith("stale_last_price:3_sessions") for r in stale["labels"]["phase"]["reasons"]))

    def test_corporate_action_handling(self):
        d = self.dates[295]
        known = verified_context(corporate_action_status=m.CA_PARTIAL_KNOWN, known_ex_dates=(self.dates[280],))
        out = m.generate_labels(request_for(SYN_A, self.rows, d, security=known))
        self.assertIn("known_corporate_action_in_window", out["labels"]["phase"]["reasons"])
        self.assertTrue(out["semantics"]["adjustment_uncertainty"])
        unknown = m.generate_labels(request_for(SYN_A, self.rows, d))
        self.assertIn("adjustment_uncertainty:corporate_action_status=unknown", unknown["data_quality"])
        self.assertEqual(unknown["labels"]["phase"]["label"], "accumulation")
        self.assertFalse(m.generate_labels(request_for(SYN_A, self.rows, d, security=verified_context()))["semantics"]["adjustment_uncertainty"])
        complete = m.generate_labels(request_for(SYN_A, self.rows, d, security=verified_context(corporate_action_status=m.CA_COMPLETE_KNOWN, known_ex_dates=(self.dates[10],))))
        self.assertFalse(complete["semantics"]["adjustment_uncertainty"])

    def test_bj_scope_exception_only_for_pinned_key(self):
        d = "2023-12-04"
        base = bars_from("BJ920006", [d], [12.5], [1_610_724])[0]
        bad = m.Observation(**{**base.record(), "high": 12.75, "low": 12.15, "open": 12.3, "close": 12.5, "volume": 1_610_724.0, "amount": 18_876_856.0})
        m.validate_observations([bad], "BJ920006", synthetic=False)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_observations([m.Observation(**{**bad.record(), "symbol": "BJ920007"})], "BJ920007", synthetic=False)
        self.assertEqual(ctx.exception.code, "vwap_outside_range")
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


# --------------------------------------------------------------------------- #
# Trade state, position events with basis chronology (R2-F), prior state      #
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

    def _position(self, entry_idx: int, ref_idx: int | None = None, **kw):
        ref_idx = entry_idx + 1 if ref_idx is None else ref_idx
        basis = kw.get("reference_basis", "next_session_open")
        earliest = m.open_time(self.dates[ref_idx]) if basis == "next_session_open" else m.close_time(self.dates[ref_idx])
        price = float(self.rows[ref_idx].open) if basis == "next_session_open" else float(self.rows[ref_idx].close)
        base = dict(symbol=SYN_A, policy_hash=m.POLICY_HASH, entry_decision_date=self.dates[entry_idx], reference_date=self.dates[ref_idx],
                    reference_price=price, reference_basis=basis, evidence_ref="SYNTHETIC_ONLY:position",
                    available_at=(earliest + timedelta(minutes=5)).isoformat())
        base.update(kw)
        return m.PositionState(**base)

    def test_signal_eligible_but_tradability_unverified(self):
        rows, d = self._confirmed_day(0.02)
        out = m.generate_labels(request_for(SYN_A, rows, d, security=verified_context(st_status="not_st")))
        self.assertEqual(out["labels"]["selection"]["label"], "candidate")
        self.assertEqual(out["labels"]["entry"]["label"], "signal_eligible", out["labels"]["entry"])
        self.assertEqual(out["labels"]["entry"]["tradability"], "unverified")

    def test_limit_unknown_is_conservative(self):
        rows, d = self._confirmed_day(0.05)
        unknown_st = m.generate_labels(request_for(SYN_A, rows, d))
        lim = unknown_st["labels"]["limit"]
        self.assertEqual((lim["board"], lim["threshold_pct"]), ("main", 4.8))
        self.assertTrue(lim["limit_like_possible"])
        self.assertNotEqual(unknown_st["labels"]["entry"]["label"], "signal_eligible")
        declared = m.generate_labels(request_for(SYN_A, rows, d, security=verified_context(st_status="not_st")))
        self.assertEqual(declared["labels"]["limit"]["threshold_pct"], 9.8)
        features = {"close": 10.5, "ma20": 10.0, "volume_ratio_20": 2.0, "zero_volume_session": False, "pct_change": 0.05}
        self.assertEqual(m.label_entry({"label": "candidate"}, features, m.limit_assessment(SYN_A, m.SecurityContext(), 0.05))["reasons"], ["limit_like_possible"])
        self.assertEqual(m.label_entry({"label": "candidate"}, features, m.limit_assessment(SYN_A, verified_context(st_status="not_st"), 0.05))["label"], "signal_eligible")
        self.assertEqual(m.limit_assessment("BJ920006", m.SecurityContext(), 0.10)["threshold_pct"], 29.0)
        late = m.generate_labels(request_for(SYN_A, rows, d, security=verified_context(st_status="not_st", facts_available_at=(m.close_time(d) + timedelta(days=3)).isoformat())))
        self.assertEqual(late["labels"]["limit"]["threshold_pct"], 4.8)

    def test_volume_ratio_below_min_blocks_entry(self):
        rows, d = self._confirmed_day(0.02, vol_mult=1.0)
        out = m.generate_labels(request_for(SYN_A, rows, d, security=verified_context(st_status="not_st")))
        self.assertIn("volume_ratio_below_min", out["labels"]["entry"]["reasons"])

    def test_position_events_with_verified_basis(self):
        ctx = verified_context()
        pos = self._position(295)
        hold = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=pos, security=ctx))
        self.assertEqual((hold["labels"]["position_event"]["label"], hold["labels"]["position_event"]["basis_verified"], hold["labels"]["position_event"]["holding_sessions"]), ("hold", True, 2))
        self.assertEqual(m.generate_labels(request_for(SYN_A, self.rows, self.dates[312], position_state=pos, security=ctx))["labels"]["position_event"]["label"], "exit_event")
        top = self._position(318)
        stop = m.generate_labels(request_for(SYN_A, self.rows, self.dates[330], position_state=top, security=ctx))
        self.assertIn(stop["labels"]["position_event"]["label"], ("stop_event", "invalidation_event"))
        series = m.label_series(request_for(SYN_A, self.rows, self.dates[-1]), self.dates[320:340])
        failed_dates = [o["cutoff"]["decision_date"] for o in series if o["labels"]["phase"]["label"] == "failed_markup"]
        inv = m.generate_labels(request_for(SYN_A, self.rows, failed_dates[0], position_state=top, security=ctx))
        self.assertEqual(inv["labels"]["position_event"]["label"], "invalidation_event")
        long_pos = self._position(255)
        self.assertIn(m.generate_labels(request_for(SYN_A, self.rows, self.dates[290], position_state=long_pos, security=ctx))["labels"]["position_event"]["label"], ("exit_event", "stop_event"))
        close_basis = self._position(295, 295, reference_basis="session_close")
        out = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=close_basis, security=ctx))
        self.assertTrue(out["labels"]["position_event"]["basis_verified"])
        self.assertIn(out["labels"]["position_event"]["label"], ("hold", "exit_event", "stop_event"))
        self.assertEqual(m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], security=ctx))["labels"]["position_event"]["label"], "no_trade")

    def test_unverified_basis_yields_review_required_not_price_events(self):
        top = self._position(318)
        unknown = m.generate_labels(request_for(SYN_A, self.rows, self.dates[330], position_state=top))
        ev = unknown["labels"]["position_event"]
        self.assertNotIn(ev["label"], ("stop_event", "exit_event"))
        self.assertFalse(ev["basis_verified"])
        self.assertTrue(ev["price_condition"]["close_le_stop_level"])
        partial = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=self._position(295),
                                                security=verified_context(corporate_action_status=m.CA_PARTIAL_KNOWN, known_ex_dates=(self.dates[10],))))
        self.assertEqual(partial["labels"]["position_event"]["label"], "review_required")
        in_window = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=self._position(295),
                                                  security=verified_context(corporate_action_status=m.CA_COMPLETE_KNOWN, known_ex_dates=(self.dates[297],))))
        self.assertIn("known_corporate_action_in_holding_window", in_window["labels"]["position_event"]["reasons"])
        self.assertNotIn(in_window["labels"]["position_event"]["label"], ("stop_event", "exit_event"))
        self.assertEqual(m.generate_labels(request_for(SYN_A, self.rows[:298], self.dates[298], position_state=self._position(295), security=verified_context()))["labels"]["position_event"]["label"], "unknown")
        self.assertEqual(m.generate_labels(request_for(SYN_A, self.rows[:298] + [suspension(SYN_A, self.dates[298])], self.dates[298],
                                                       position_state=self._position(295), security=verified_context()))["labels"]["position_event"]["label"], "unknown")
        declared = self._position(295, reference_basis="declared", reference_price=9.0)
        out = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=declared, security=verified_context()))
        self.assertEqual(out["labels"]["position_event"]["label"], "review_required")
        self.assertIn("reference_basis_declared_unverified", out["labels"]["position_event"]["reasons"])
        self.assertFalse(out["labels"]["position_event"]["basis_verified"])

    def test_reference_chronology_by_basis(self):
        def expect(code, pos, d=298, **kw):
            with self.assertRaises(m.LabelInputError) as ctx:
                m.generate_labels(request_for(SYN_A, self.rows, self.dates[d], position_state=pos, security=verified_context(), **kw))
            self.assertEqual(ctx.exception.code, code)

        # next_session_open: reference must be the very next session and observable only from its open
        expect("position_reference_not_next_session", self._position(295, 297))
        expect("position_reference_available_before_observable", self._position(295, available_at=(m.open_time(self.dates[296]) - timedelta(minutes=1)).isoformat()))
        expect("position_reference_available_before_observable", self._position(295, available_at=EARLY))
        ok = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=self._position(295, available_at=m.open_time(self.dates[296]).isoformat()), security=verified_context()))
        self.assertTrue(ok["labels"]["position_event"]["basis_verified"])
        # session_close: available_at cannot precede that session's close
        expect("position_reference_available_before_observable", self._position(295, 296, reference_basis="session_close", available_at=(m.close_time(self.dates[296]) - timedelta(minutes=1)).isoformat()))
        expect("position_reference_available_before_observable", self._position(295, 296, reference_basis="session_close", available_at=EARLY))
        exact = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=self._position(295, 296, reference_basis="session_close", available_at=m.close_time(self.dates[296]).isoformat()), security=verified_context()))
        self.assertTrue(exact["labels"]["position_event"]["basis_verified"])
        # a session_close reference on the entry session itself is allowed (ref >= entry)
        same_day = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=self._position(295, 295, reference_basis="session_close"), security=verified_context()))
        self.assertTrue(same_day["labels"]["position_event"]["basis_verified"])
        # declared basis is never verified, whatever the evidence string or timestamp says
        declared = self._position(295, reference_basis="declared", reference_price=9.0, available_at=EARLY)
        out = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=declared, security=verified_context()))
        self.assertFalse(out["labels"]["position_event"]["basis_verified"])
        self.assertEqual(out["labels"]["position_event"]["label"], "review_required")

    def test_position_state_rejections(self):
        def expect(code, pos, d=298, **kw):
            with self.assertRaises(m.LabelInputError) as ctx:
                m.generate_labels(request_for(SYN_A, self.rows, self.dates[d], position_state=pos, **kw))
            self.assertEqual(ctx.exception.code, code)

        expect("position_state_binding_mismatch", self._position(295, symbol=SYN_B))
        expect("position_state_binding_mismatch", self._position(295, policy_hash="0" * 64))
        expect("position_reference_before_entry", self._position(295, 285))
        expect("position_reference_before_entry", self._position(295, 295))
        expect("position_state_not_earlier", self._position(298, 299))
        expect("position_state_invalid_reference_price", self._position(295, reference_price=float("nan")))
        expect("position_reference_price_mismatch", self._position(295, reference_price=float(self.rows[296].open) * 1.5))
        expect("position_state_without_evidence", self._position(295, evidence_ref=""))
        expect("position_state_without_availability", self._position(295, available_at=None))
        expect("position_state_not_available_at_cutoff", self._position(295, available_at="2030-01-01T00:00:00+08:00"))
        expect("position_state_invalid_basis", self._position(295, reference_basis="guess"))
        expect("position_state_not_a_session", m.PositionState(SYN_A, m.POLICY_HASH, "2023-12-30", "2023-12-31", 10.0, evidence_ref="x", available_at=EARLY))

    def test_prior_state_binding(self):
        earlier = m.generate_labels(request_for(SYN_A, self.rows, self.dates[290]))
        as_of = earlier["cutoff"]["as_of"]
        good = m.PriorState(SYN_A, self.dates[290], as_of, m.POLICY_HASH, earlier["labels"]["phase"]["label"], earlier["episode_id"])
        m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=good))
        for change, code in ((dict(phase="distribution"), "prior_state_inconsistent"), (dict(episode_id="0" * 32), "prior_state_inconsistent"),
                             (dict(policy_hash="f" * 64), "prior_state_binding_mismatch"), (dict(decision_date=self.dates[295]), "prior_state_not_earlier"),
                             (dict(as_of="2030-01-01T00:00:00+08:00"), "prior_state_not_earlier")):
            with self.assertRaises(m.LabelInputError) as ctx:
                m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=replace(good, **change)))
            self.assertEqual(ctx.exception.code, code, change)


# --------------------------------------------------------------------------- #
# Benchmark integration (R3 supplement): role-aware units, price-only regime   #
# --------------------------------------------------------------------------- #


class BenchmarkIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)
        self.d = self.dates[295]
        self.n = 296

    def _run(self, bench, **kw):
        return m.generate_labels(request_for(SYN_A, self.rows, self.d, benchmark_symbol=SYN_BENCH, benchmark_observations=bench,
                                             universe_coverage_on_decision_date=coverage(), **kw))

    def test_preserved_m2_benchmark_units_produce_a_price_only_regime(self):
        bench = bench_for(self.dates[: self.n], 0.002)
        self.assertTrue(all(b.volume_unit == "not_applicable" and b.amount_unit == "not_applicable" for b in bench))
        out = self._run(bench)
        regime = out["labels"]["regime"]
        self.assertEqual(regime["regime"], "bull")
        self.assertTrue(regime["price_only"])
        self.assertEqual(regime["benchmark_units"], "not_applicable")
        self.assertFalse(regime["benchmark_volume_amount_consumed"])
        self.assertEqual(self._run(bench_for(self.dates[: self.n], 0.0))["labels"]["regime"]["regime"], "range")
        self.assertEqual(self._run(bench_for(self.dates[: self.n], -0.002))["labels"]["regime"]["regime"], "bear")
        # index levels far from stock prices, with aggregates that would fail a stock vwap check, are accepted
        levels = [replace(b, open=3000.0, high=3100.0, low=2900.0, close=3000.0, volume=1.0e10, amount=5.0e11) for b in bench]
        self.assertEqual(self._run(levels)["labels"]["regime"]["regime"], "range")
        none_aggregates = [replace(b, volume=None, amount=None) for b in bench]
        self.assertEqual(self._run(none_aggregates)["labels"]["regime"]["regime"], "bull")

    def test_unused_benchmark_aggregates_never_change_regime_or_identity(self):
        bench = bench_for(self.dates[: self.n], 0.002)
        base = self._run(bench)
        changed = self._run([replace(b, volume=float(b.volume) * 37.0, amount=float(b.amount) * 0.01) for b in bench])
        self.assertEqual(changed["labels"]["regime"], base["labels"]["regime"])
        self.assertEqual(changed["episode_id"], base["episode_id"])
        self.assertEqual(changed["record_hash"], base["record_hash"])
        self.assertEqual(changed["identity"]["decision_inputs"]["benchmark_rows"], m.benchmark_price_fingerprint(bench))
        # but a changed index level does change both
        level = self._run([replace(b, close=float(b.close) * 1.2, high=float(b.high) * 1.2) for b in bench])
        self.assertNotEqual(level["episode_id"], base["episode_id"])

    def test_invalid_benchmark_rows_still_reject(self):
        bench = bench_for(self.dates[: self.n], 0.002)

        def expect(code, rows, **kw):
            with self.assertRaises(m.LabelInputError) as ctx:
                self._run(rows, **kw)
            self.assertEqual(ctx.exception.code, code)

        expect("invalid_price", bench[:-1] + [replace(bench[-1], high=float(bench[-1].low) - 1.0)])
        expect("invalid_price", bench[:-1] + [replace(bench[-1], low=0.0, open=0.0, close=0.0, high=0.0)])
        expect("nonfinite_or_missing_numeric", bench[:-1] + [replace(bench[-1], close=float("nan"))])
        expect("nonfinite_or_missing_numeric", bench[:-1] + [replace(bench[-1], open=None)])
        expect("invalid_benchmark_aggregate", bench[:-1] + [replace(bench[-1], volume=float("nan"))])
        expect("invalid_benchmark_aggregate", bench[:-1] + [replace(bench[-1], amount=-1.0)])
        expect("invalid_benchmark_aggregate", bench[:-1] + [replace(bench[-1], volume=True)])
        expect("availability_before_close", bench[:-1] + [replace(bench[-1], available_at=(m.close_time(bench[-1].trade_date) - timedelta(minutes=1)).isoformat())])
        expect("wrong_security_identity", bench[:-1] + [replace(bench[-1], symbol="SYN900301")])
        expect("observation_not_a_session", bench[:-1] + [replace(bench[-1], trade_date="2024-02-25")])
        expect("unsupported_adjustment_mode", bench[:-1] + [replace(bench[-1], adjustment_mode="qfq")])
        expect("duplicate_key", bench + [bench[-1]])
        # a benchmark claiming share/CNY units is not honest and is rejected; a stock cannot claim benchmark units
        expect("benchmark_units_must_be_not_applicable", bench[:-1] + [replace(bench[-1], volume_unit="share", amount_unit="CNY")])
        expect("benchmark_units_must_be_not_applicable", bench[:-1] + [replace(bench[-1], amount_unit="CNY")])
        stock_claiming_index_units = self.rows[:295] + [replace(self.rows[295], **BENCH_UNITS)]
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, stock_claiming_index_units, self.d))
        self.assertEqual(ctx.exception.code, "unsupported_volume_unit")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows[:295] + [replace(self.rows[295], amount_unit="not_applicable")], self.d))
        self.assertEqual(ctx.exception.code, "unsupported_amount_unit")
        # stock vwap and unit checks are unchanged
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows[:295] + [replace(self.rows[295], amount=float(self.rows[295].amount) * 3.0)], self.d))
        self.assertEqual(ctx.exception.code, "vwap_outside_range")
        # late benchmark availability stays unknown; benchmark symbols can neither be labelled nor become controls
        late = bench[:-1] + [replace(bench[-1], available_at="2026-09-10T00:00:00+08:00")]
        self.assertEqual(self._run(late)["labels"]["regime"]["regime"], "unknown")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_BENCH, bench, self.d))
        self.assertEqual(ctx.exception.code, "instrument_role_mismatch")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_observations(bench, SYN_BENCH, True, role="stock")
        self.assertEqual(ctx.exception.code, "instrument_role_mismatch")


# --------------------------------------------------------------------------- #
# Context: liquidity and regime                                               #
# --------------------------------------------------------------------------- #


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def test_liquidity_bands(self):
        for amount, band in ((1.0e7, "L1_thin"), (5.0e7, "L2_low"), (2.0e8, "L3_mid"), (9.0e8, "L4_deep"), (None, "unknown")):
            self.assertEqual(m.label_liquidity({"amount_20_mean_cny": amount})["band"], band)

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
        self.assertIn("benchmark_bar_missing_on_decision_session", run(bench_for(self.dates[:n], 0.002)[:-1])["reasons"])
        self.assertTrue(any(r.startswith("market_wide_missingness") for r in run(bench_for(self.dates[:n], 0.002), coverage(0.5))["reasons"]))
        self.assertEqual(run(bench_for(self.dates[:n], 0.002), None)["regime"], "unknown")
        late = list(bench_for(self.dates[:n], 0.002))
        late[-1] = replace(late[-1], available_at="2026-09-10T00:00:00+08:00")
        self.assertEqual(run(late)["regime"], "unknown")
        with self.assertRaises(m.LabelInputError):
            m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_observations=bench_for(self.dates[:n])))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_B, benchmark_observations=bars_from(SYN_B, self.dates[:n], [1.0] * n, [1] * n)))
        self.assertEqual(ctx.exception.code, "instrument_role_mismatch")


# --------------------------------------------------------------------------- #
# Case library: registry/summaries (R2-B), matching (R1/R2-C), ledger (R2-A)  #
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
        cls.registry = m.RecordRegistry([cls.positive] + cls.pool)

    def test_same_date_matching_is_deterministic_and_outcome_free(self):
        match = m.match_controls(self.positive, self.pool)
        again = m.match_controls(self.positive, list(reversed(self.pool)))
        self.assertEqual(match, again)
        self.assertGreaterEqual(match["control_count"], 3)
        self.assertLessEqual(match["control_count"], 5)
        self.assertFalse(match["unmatched"])
        self.assertEqual(len({c["symbol"] for c in match["controls"]}), match["control_count"])
        self.assertEqual(match["rejected_pool_counts"].get("same_symbol"), 1)
        self.assertEqual(match["rejected_pool_counts"].get("different_decision_date"), 1)
        self.assertEqual((match["schema"], match["policy_hash"], match["k_min"], match["k_max"]), ("m3.labels.match.v3", m.POLICY_HASH, 3, 5))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, [dict(self.pool[0], outcome_return_20=0.5)])
        self.assertEqual(ctx.exception.code, "outcome_leakage")
        with self.assertRaises(m.LabelInputError):
            m.match_controls(dict(self.positive, future_max=1.0), self.pool)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.pool[0], self.pool)
        self.assertEqual(ctx.exception.code, "positive_not_candidate")
        # matching through summaries resolved by a registry gives the identical result
        via_summaries = m.match_controls(m.case_summary(self.positive), [m.case_summary(p) for p in self.pool], registry=self.registry)
        self.assertEqual(via_summaries, match)
        revalidated = m.revalidate_match(match, self.registry)
        self.assertEqual({k: revalidated[k] for k in ("controls", "control_count", "unmatched", "positive_episode_id", "positive_record_hash", "decision_date")},
                         {k: match[k] for k in ("controls", "control_count", "unmatched", "positive_episode_id", "positive_record_hash", "decision_date")})

    def test_summaries_are_bound_to_verified_cores(self):
        one = self.pool[0]
        summary = m.case_summary(one)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.case_summary(summary)  # a bare summary is never evidence
        self.assertEqual(ctx.exception.code, "unresolved_record_reference")
        self.assertEqual(m.case_summary(summary, self.registry), summary)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.case_summary(dict(summary, record_hash="z" * 64), self.registry)
        self.assertEqual(ctx.exception.code, "malformed_summary")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.case_summary(dict(summary, record_hash="0" * 64), self.registry)
        self.assertEqual(ctx.exception.code, "stale_record_reference")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.case_summary(dict(summary, episode_id="0" * 32), self.registry)
        self.assertEqual(ctx.exception.code, "unresolved_record_reference")
        for field, value in (("selection", "candidate"), ("liquidity_band", "L2_low"), ("regime", "bear"), ("symbol", "SYN000077"),
                             ("decision_date", self.dates[294]), ("convention", "close+0s"), ("mode", "retrospective"),
                             ("universe_sha256", "1" * 64), ("current_state", "suspended"), ("policy_version", "0.2.0-draft"), ("in_frozen_universe", True)):
            forged = dict(summary, **{field: value})
            if field == "decision_date":
                forged["split_role"] = m.split_role(value)
            with self.assertRaises(m.LabelInputError) as ctx:
                m.case_summary(forged, self.registry)
            self.assertEqual(ctx.exception.code, "summary_conflicts_with_core", field)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_summary_format(dict(summary, split_role="validation"))
        self.assertEqual(ctx.exception.code, "malformed_summary")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_summary_format(dict(summary, amount_20_mean_cny=float("nan")))
        self.assertEqual(ctx.exception.code, "malformed_summary")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_summary_format(dict(summary, synthetic="yes"))
        self.assertEqual(ctx.exception.code, "invalid_synthetic_flag")
        # relabelled candidate summaries cannot become controls
        relabelled = [dict(m.case_summary(self.positive), selection="non_candidate", symbol=f"SYN00002{i}") for i in range(3)]
        with self.assertRaises(m.LabelInputError):
            m.match_controls(self.positive, relabelled, registry=self.registry)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, relabelled)
        self.assertEqual(ctx.exception.code, "unresolved_record_reference")

    def test_duplicates_conflicts_and_identity_do_not_inflate_controls(self):
        one = self.pool[0]
        five_copies = m.match_controls(self.positive, [one] * 5)
        self.assertEqual((five_copies["control_count"], five_copies["identical_duplicates_collapsed"], five_copies["unmatched"]), (1, 4, True))
        conflicting = copy.deepcopy(one)
        conflicting["labels"]["liquidity"]["band"] = "L2_low"
        conflicting["record_hash"] = m.record_hash(conflicting)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, [one, conflicting])
        self.assertIn(ctx.exception.code, ("conflicting_duplicate_control", "malformed_record"))
        tampered = copy.deepcopy(one)
        tampered["labels"]["selection"]["label"] = "non_candidate"
        tampered["symbol"] = "SYN000077"
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, [tampered])
        self.assertEqual(ctx.exception.code, "record_hash_mismatch")
        other_policy = dict(one, policy_hash="0" * 64)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, [other_policy])
        self.assertEqual(ctx.exception.code, "policy_hash_mismatch")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, [{"episode_id": "x", "symbol": "SYN000010", "decision_date": self.d}])
        self.assertEqual(ctx.exception.code, "malformed_summary")
        # genuine records with a different convention / universe / suspended state are rejected by the matcher
        other_conv = m.generate_labels(m.LabelRequest(symbol="SYN000010", observations=bars_from("SYN000010", self.dates[:296], *[[c * 1.0 for c in sequence_distribution(seed=11, n_rise=295)[1]], sequence_distribution(seed=11, n_rise=295)[2]], upper_shadow=0.04),
                                                      cutoff=cutoff_for(self.d, hours=6), calendar=CAL, synthetic=True, benchmark_symbol=SYN_BENCH,
                                                      benchmark_observations=self.bench, universe_coverage_on_decision_date=coverage()))
        self.assertEqual(m.match_controls(self.positive, [other_conv])["rejected_pool_counts"], {"cutoff_convention_mismatch": 1})
        universe = m.FrozenUniverse(frozenset({"SH600011"}), "TEST_PIN:u", "9" * 64)
        other_universe = m.generate_labels(replace(request_for("SYN000010", other_conv and bars_from("SYN000010", self.dates[:296], sequence_distribution(seed=11, n_rise=295)[1], sequence_distribution(seed=11, n_rise=295)[2], upper_shadow=0.04), self.d,
                                                               benchmark_symbol=SYN_BENCH, benchmark_observations=self.bench, universe_coverage_on_decision_date=coverage()), universe=universe))
        self.assertEqual(m.match_controls(self.positive, [other_universe])["rejected_pool_counts"], {"universe_mismatch": 1})
        suspended_rows = bars_from("SYN000010", self.dates[:295], sequence_distribution(seed=11, n_rise=295)[1][:295], sequence_distribution(seed=11, n_rise=295)[2][:295], upper_shadow=0.04) + [suspension("SYN000010", self.d)]
        suspended = m.generate_labels(request_for("SYN000010", suspended_rows, self.d, benchmark_symbol=SYN_BENCH, benchmark_observations=self.bench, universe_coverage_on_decision_date=coverage()))
        self.assertEqual(m.match_controls(self.positive, [suspended])["rejected_pool_counts"], {"control_current_state_not_observed": 1})

    def test_matching_split_admission_and_unknown_context(self):
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, self.pool, purpose="target_counts")
        self.assertEqual(ctx.exception.code, "unknown_purpose")
        no_regime = m.generate_labels(request_for(SYN_A, self.rows, self.d))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(no_regime, self.pool)
        self.assertEqual(ctx.exception.code, "positive_context_unknown")
        missing_day = m.generate_labels(request_for(SYN_A, self.rows[:295], self.d, benchmark_symbol=SYN_BENCH, benchmark_observations=self.bench, universe_coverage_on_decision_date=coverage()))
        with self.assertRaises(m.LabelInputError):
            m.match_controls(missing_day, self.pool)
        reuse = m.control_reuse_counts([m.match_controls(self.positive, self.pool[:1]), m.match_controls(self.positive, self.pool), m.match_controls(self.positive, self.pool)])
        self.assertEqual((reuse["positives"], reuse["unmatched_positives"]), (3, 1))

    def test_revalidate_match_rejects_forged_serializations(self):
        match = m.match_controls(self.positive, self.pool)
        registry = self.registry
        self.assertEqual(m.revalidate_match(match, registry)["controls"], match["controls"])
        for change, code in ((dict(k_min=0), "match_record_mismatch"), (dict(k_max=9), "match_record_mismatch"),
                             (dict(controls=[], control_count=3, distinct_control_symbols=3, unmatched=False), "match_record_mismatch"),
                             (dict(control_count=1), "match_record_mismatch"), (dict(unmatched=True), "match_record_mismatch"),
                             (dict(positive_record_hash="0" * 64), "stale_record_reference"), (dict(positive_episode_id="0" * 32), "unresolved_record_reference"),
                             (dict(policy_hash="0" * 64), "policy_hash_mismatch"), (dict(schema="m3.labels.match.v2"), "policy_hash_mismatch"),
                             (dict(purpose="final_report"), "match_record_mismatch"), (dict(decision_date=self.dates[294]), "match_record_mismatch")):
            forged = copy.deepcopy(match)
            forged.update(change)
            with self.assertRaises(m.LabelInputError) as ctx:
                m.revalidate_match(forged, registry, "initial_library_admission")
            self.assertEqual(ctx.exception.code, code, change)
        forged = copy.deepcopy(match)
        forged["controls"][0]["symbol"] = "SYN000077"
        forged["controls"][0]["record_hash"] = "0" * 64
        with self.assertRaises(m.LabelInputError) as ctx:
            m.revalidate_match(forged, registry)
        self.assertEqual(ctx.exception.code, "stale_record_reference")
        forged = copy.deepcopy(match)
        forged["controls"] = forged["controls"][:2] + [{"episode_id": self.positive["episode_id"], "record_hash": self.positive["record_hash"], "symbol": SYN_A, "role": "matched_non_candidate"}]
        forged["control_count"] = 3
        with self.assertRaises(m.LabelInputError) as ctx:
            m.revalidate_match(forged, registry)
        self.assertEqual(ctx.exception.code, "match_record_mismatch")
        del forged["controls"]
        with self.assertRaises(m.LabelInputError) as ctx:
            m.revalidate_match(forged, registry)
        self.assertEqual(ctx.exception.code, "malformed_match")

    def test_ledger_validation_is_authoritative(self):
        out = self.positive
        self.assertEqual(m.review_status(out)["status"], "pending_review")
        one = m.attach_review(out, syn_review(out, "synthetic_reviewer_A", "positive"))
        self.assertEqual(one["record_hash"], out["record_hash"])
        self.assertEqual(one["review_ledger"]["status"], "single_review_not_independent")
        self.assertEqual(out["review_ledger"]["entries"], [])
        # transplanted valid ledger onto another valid core
        other = copy.deepcopy(self.pool[0])
        other["review_ledger"] = copy.deepcopy(one["review_ledger"])
        self.assertEqual(m.record_hash(other), other["record_hash"])
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(other, syn_review(other, "C", "positive"))
        self.assertEqual(ctx.exception.code, "ledger_binding_mismatch")
        with self.assertRaises(m.LabelInputError):
            m.review_status(other)
        with self.assertRaises(m.LabelInputError):
            m.RecordRegistry([other])
        # tampered entry content without re-hashing
        tampered = copy.deepcopy(one)
        tampered["review_ledger"]["entries"][0]["execution_ref"] = ""
        with self.assertRaises(m.LabelInputError) as ctx:
            m.review_status(tampered)
        self.assertEqual(ctx.exception.code, "ledger_hash_mismatch")  # the ledger hash covers every entry
        rehashed = copy.deepcopy(one)
        rehashed["review_ledger"]["entries"][0]["verdict"] = "negative"
        rehashed["review_ledger"]["ledger_hash"] = m._ledger_hash(rehashed["review_ledger"])  # attacker re-hashes the ledger but not the entry
        with self.assertRaises(m.LabelInputError) as ctx:
            m.library_counts([rehashed], [], CAL)
        self.assertEqual(ctx.exception.code, "review_entry_hash_mismatch")
        rehashed_entry = copy.deepcopy(one)
        entry = rehashed_entry["review_ledger"]["entries"][0]
        entry["verdict"] = "negative"
        entry["entry_hash"] = m._entry_content_hash(entry)
        rehashed_entry["review_ledger"]["ledger_hash"] = m._ledger_hash(rehashed_entry["review_ledger"])
        with self.assertRaises(m.LabelInputError) as ctx:
            m.review_status(rehashed_entry)  # both hashes re-computed: the cached status no longer matches the entries
        self.assertEqual(ctx.exception.code, "ledger_status_mismatch")
        # cached status strings are not trusted
        cached = copy.deepcopy(one)
        cached["review_ledger"]["status"] = "independently_reviewed"
        cached["review_ledger"]["ledger_hash"] = m._ledger_hash(cached["review_ledger"])
        with self.assertRaises(m.LabelInputError) as ctx:
            m.review_status(cached)
        self.assertEqual(ctx.exception.code, "ledger_status_mismatch")
        # ledger hash mismatch and missing ledger
        broken = copy.deepcopy(one)
        broken["review_ledger"]["ledger_hash"] = "0" * 64
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(broken, syn_review(out, "C", "positive"))
        self.assertEqual(ctx.exception.code, "ledger_hash_mismatch")
        missing = copy.deepcopy(one)
        del missing["review_ledger"]
        with self.assertRaises(m.LabelInputError) as ctx:
            m.review_status(missing)
        self.assertEqual(ctx.exception.code, "ledger_missing")
        # entry-level rejections through the same validator
        for kw, code in ((dict(evidence_refs=()), "review_without_evidence"), (dict(execution_ref=""), "review_without_execution_ref"),
                         (dict(reviewer_kind="rule_engine"), "invalid_reviewer_kind"), (dict(when="2026-09-11T02:00:00"), "invalid_reviewed_at"),
                         (dict(synthetic=False), "review_synthetic_flag_mismatch"), (dict(case_record_hash="0" * 64), "review_case_binding_mismatch"),
                         (dict(case_episode_id="zz"), "review_without_case_binding")):
            with self.assertRaises(m.LabelInputError) as ctx:
                m.attach_review(out, syn_review(out, "B", "positive", **kw))
            self.assertEqual(ctx.exception.code, code, kw)
        stale_version = m.generate_labels(request_for(SYN_A, self.rows, self.d))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(stale_version, syn_review(out, "B", "positive"))
        self.assertEqual(ctx.exception.code, "review_case_binding_mismatch")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(one, syn_review(out, "synthetic_reviewer_A", "positive"))
        self.assertEqual(ctx.exception.code, "duplicate_review")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(one, syn_review(out, "synthetic_reviewer_A", "negative", when="2026-09-11T05:00:00+00:00"))
        self.assertEqual(ctx.exception.code, "conflicting_duplicate_review")

    def test_supersession_chain_rules(self):
        out = self.positive
        one = m.attach_review(out, syn_review(out, "codex_synthetic", "positive"))
        two = m.attach_review(one, syn_review(out, "claude_synthetic", "ambiguous", when="2026-09-11T03:00:00+00:00"))
        self.assertEqual((two["review_ledger"]["status"], two["review_ledger"]["agreement"], two["review_ledger"]["consensus_verdict"]), ("disputed", "disagree", None))
        first = two["review_ledger"]["entries"][1]["entry_hash"]
        three = m.attach_review(two, syn_review(out, "claude_synthetic", "positive", when="2026-09-11T06:00:00+00:00", supersedes=first, supersede_reason="re-read the volume evidence"))
        self.assertEqual((three["review_ledger"]["status"], three["review_ledger"]["consensus_verdict"], len(three["review_ledger"]["entries"])), ("independently_reviewed", "positive", 3))
        self.assertEqual(m.review_status(three)["current_verdicts"], {"claude_synthetic": "positive", "codex_synthetic": "positive"})
        # superseding an already superseded entry cannot fork the current verdict
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(three, syn_review(out, "claude_synthetic", "negative", when="2026-09-11T07:00:00+00:00", supersedes=first, supersede_reason="stale base"))
        self.assertEqual(ctx.exception.code, "invalid_supersede")
        # must be strictly later than the superseded entry
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(two, syn_review(out, "claude_synthetic", "positive", when="2026-09-11T03:00:00+00:00", supersedes=first, supersede_reason="same instant"))
        self.assertEqual(ctx.exception.code, "invalid_supersede")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(two, syn_review(out, "claude_synthetic", "positive", when="2026-09-10T03:00:00+00:00", supersedes=first, supersede_reason="earlier"))
        self.assertEqual(ctx.exception.code, "invalid_supersede")
        # only own entries; reason required; unknown target; malformed target
        with self.assertRaises(m.LabelInputError):
            m.attach_review(two, syn_review(out, "codex_synthetic", "negative", when="2026-09-11T07:00:00+00:00", supersedes=first, supersede_reason="x"))
        with self.assertRaises(m.LabelInputError):
            m.attach_review(two, syn_review(out, "claude_synthetic", "positive", when="2026-09-11T07:00:00+00:00", supersedes=first))
        with self.assertRaises(m.LabelInputError):
            m.attach_review(two, syn_review(out, "claude_synthetic", "positive", when="2026-09-11T07:00:00+00:00", supersedes="0" * 64, supersede_reason="x"))
        with self.assertRaises(m.LabelInputError):
            m.attach_review(two, syn_review(out, "claude_synthetic", "positive", when="2026-09-11T07:00:00+00:00", supersedes="not-hex", supersede_reason="x"))
        # a forged chain (target after the superseding entry) is rejected on load
        forged = copy.deepcopy(three)
        entries = forged["review_ledger"]["entries"]
        entries[1], entries[2] = entries[2], entries[1]
        forged["review_ledger"]["ledger_hash"] = m._ledger_hash(forged["review_ledger"])
        with self.assertRaises(m.LabelInputError) as ctx:
            m.review_status(forged)
        self.assertEqual(ctx.exception.code, "invalid_supersede")
        same_reviewer_again = m.attach_review(one, syn_review(out, "codex_synthetic", "positive", when="2026-09-11T09:00:00+00:00",
                                                             evidence_refs=("SYNTHETIC_ONLY:evidence:again",), supersedes=one["review_ledger"]["entries"][0]["entry_hash"], supersede_reason="added evidence"))
        self.assertEqual(same_reviewer_again["review_ledger"]["status"], "single_review_not_independent")

    def test_outcome_annotation_is_separate(self):
        later = cutoff_for(self.dates[330])
        ann = m.annotate_outcome(self.positive, self.rows, later, CAL, horizon_sessions=20)
        self.assertEqual((ann["annotation_kind"], ann["not_a_label"], ann["realized_return_claim"]), ("later_known_outcome", True, False))
        self.assertEqual(ann["record_hash"], self.positive["record_hash"])
        self.assertNotIn("close_return_unadjusted", json.dumps(self.positive["labels"]))
        with self.assertRaises(m.LabelInputError):
            m.annotate_outcome(self.positive, self.rows, cutoff_for(self.d), CAL)


# --------------------------------------------------------------------------- #
# Episodes (R2-D), dependence groups and fail-closed counting with a positive control
# --------------------------------------------------------------------------- #


class EpisodeAndCountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dates, cls.closes, cls.vols = sequence_positive_then_failed()
        cls.rows = bars_from(SYN_A, cls.dates, cls.closes, cls.vols)
        cls.series = m.label_series(request_for(SYN_A, cls.rows, cls.dates[-1]), cls.dates[249:])
        cls.episodes = m.build_episodes(cls.series, CAL)
        cls.members, cls.controls, cls.match = admissible_library_fixture()

    def test_episodes_track_selection_changes_duration_and_continuity(self):
        for ep in self.episodes:
            self.assertEqual(ep["selection_at_end"], ep["selection_path"][-1]["selection"])
            self.assertFalse(ep["counts_toward_case_library"])
            if ep["sessions"] >= 3:
                idx = [o["cutoff"]["decision_date"] for o in self.series].index(ep["start"]) + 2
                self.assertEqual(ep["min_duration_established_at"], self.series[idx]["cutoff"]["decision_date"])
                proof = m.episode_prefix_proof(ep)
                self.assertEqual(proof["representative_episode_id"], ep["member_episode_ids"][2])
                self.assertEqual(len(proof["member_record_hashes"]), 3)
                self.assertNotIn("end", proof)
                self.assertEqual(proof["prefix_hash"], m.episode_prefix_proof(ep)["prefix_hash"])
            else:
                self.assertIsNone(ep["min_duration_established_at"])
                self.assertIsNone(m.episode_prefix_proof(ep))
        self.assertTrue(self.episodes[-1]["open_at_last_cutoff"])
        gapped = m.build_episodes(self.series[:5] + self.series[6:10], CAL)
        self.assertTrue(any(e["closed_reason"] == "series_gap" for e in gapped))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes([self.series[0], self.series[0], self.series[0]], CAL)
        self.assertEqual(ctx.exception.code, "duplicate_decision_dates")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes([self.series[1], self.series[0]], CAL)
        self.assertEqual(ctx.exception.code, "series_not_chronological")
        tampered = copy.deepcopy(self.series[2])
        tampered["labels"]["phase"]["label"] = "markup"
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes(self.series[:2] + [tampered], CAL)
        self.assertEqual(ctx.exception.code, "record_hash_mismatch")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes(self.series[:3], CODEX_CAL)
        self.assertEqual(ctx.exception.code, "calendar_mismatch_in_series")
        acc = next(e for e in self.episodes if e["phase"] == "accumulation" and e["eligibility_changes"] > 0)
        self.assertEqual((acc["selection_at_start"], acc["selection_at_end"]), ("non_candidate", "candidate"))

    def test_dependence_groups_chain_connect(self):
        def ep(symbol, start_idx, end_idx, key, synthetic=False):
            return {"symbol": symbol, "phase": "accumulation", "start_session_index": start_idx, "end_session_index": end_idx, "episode_key": key, "synthetic": synthetic}

        chained = [ep("SH600011", 0, 10, "a"), ep("SH600011", 20, 30, "b"), ep("SH600011", 45, 50, "c"), ep("SH600011", 100, 110, "d"), ep("SH600226", 5, 8, "e")]
        groups = m.dependence_groups(chained)
        self.assertEqual(groups["effective_decision_groups"], 3)
        self.assertEqual([g["members"] for g in groups["groups"]], [["a", "b", "c"], ["d"], ["e"]])
        self.assertEqual(m.dependence_groups([ep("SH600011", 0, 10, "a"), ep("SH600011", 5, 30, "b")])["effective_decision_groups"], 1)
        synthetic = [ep(SYN_A, 0, 10, "s1", True), ep(SYN_A, 100, 110, "s2", True)]
        self.assertEqual(m.dependence_groups(synthetic)["effective_decision_groups"], 0)
        self.assertEqual(m.dependence_groups(synthetic, include_synthetic=True)["effective_decision_groups_arithmetic"], 2)
        with self.assertRaises(m.LabelInputError):
            m.dependence_groups([{"symbol": "SH600011", "phase": "accumulation", "episode_key": "x"}])

    def test_admissible_positive_control_counts_exactly_once(self):
        cases = self.members + self.controls
        counts = m.library_counts(cases, [self.match], REAL_FORMAT_CAL)
        self.assertEqual(counts["raw_input_records"], 6)
        self.assertEqual(counts["unique_records"], 6)
        self.assertEqual(counts["records_real"], 6)
        self.assertEqual(counts["independently_reviewed"], 1)
        self.assertEqual(counts["positively_reviewed_records"], 1)
        self.assertEqual(counts["episodes_duration_established"], 1)
        self.assertEqual(counts["qualified_reviewed_positive_episodes"], 1)
        self.assertEqual(counts["qualified_positives"], 1)
        self.assertEqual((counts["unique_controls"], counts["control_uses"]), (3, 3))
        self.assertEqual(counts["effective_dependence_groups"], 1)
        self.assertFalse(counts["target_met"])
        self.assertEqual(counts["target"]["min_reviewed_positive_episodes"], 50)
        q = counts["qualified_episodes"][0]
        self.assertEqual((q["symbol"], q["established_at"], q["representative_record_hash"]), ("SH600011", self.members[-1]["cutoff"]["decision_date"], self.members[-1]["record_hash"]))
        self.assertEqual(sorted(c["review_status"] for c in q["controls"]), ["pending_review"] * 3)
        self.assertEqual(q["review"]["reviewer_ids"], ["syn:fixture-only-reviewer-a", "syn:fixture-only-reviewer-b"])
        # the same fixture duplicated collapses instead of double counting; conflicting duplicates fail
        dup = m.library_counts(cases + [copy.deepcopy(self.members[-1])], [self.match], REAL_FORMAT_CAL)
        self.assertEqual((dup["raw_input_records"], dup["unique_records"], dup["duplicates_collapsed"], dup["qualified_reviewed_positive_episodes"]), (7, 6, 1, 1))
        conflicting = m.attach_review(self.members[-1], fixture_review(self.members[-1], "syn:fixture-only-reviewer-c", "negative"))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.library_counts(cases + [conflicting], [self.match], REAL_FORMAT_CAL)
        self.assertEqual(ctx.exception.code, "conflicting_duplicate_ledger")

    def test_review_must_bind_the_recomputed_episode_prefix(self):
        cases = self.members + self.controls
        first = m.library_counts(cases, [self.match], REAL_FORMAT_CAL)
        self.assertEqual(first["qualified_reviewed_positive_episodes"], 1)
        proof = m.prefix_proof_for(cases, REAL_FORMAT_CAL, self.members[-1])
        self.assertEqual(first["qualified_episodes"][0]["prefix_hash"], proof["prefix_hash"])
        self.assertEqual(sorted(m.validate_ledger(self.members[-1])["current_prefix_bindings"].values()), [proof["prefix_hash"]] * 2)
        # the unchanged representative (core, evidence, ledger, match) with two earlier members regenerated from
        # another invented source: valid cores, different prefix proof => the old reviews are orphaned, count 0
        changed_members, _, _ = admissible_library_fixture(changed_source=True)
        self.assertNotEqual(changed_members[0]["record_hash"], self.members[0]["record_hash"])
        rebound = m.library_counts(changed_members[:2] + [self.members[-1]] + self.controls, [self.match], REAL_FORMAT_CAL)
        self.assertEqual(rebound["qualified_reviewed_positive_episodes"], 0)
        self.assertEqual(rebound["disqualified_episodes"], {"review_prefix_binding_mismatch": 1})
        self.assertEqual(rebound["episodes_duration_established"], 1)
        self.assertNotEqual(m.prefix_proof_for(changed_members[:2] + [self.members[-1]], REAL_FORMAT_CAL, self.members[-1])["prefix_hash"], proof["prefix_hash"])
        # daily-only reviews (no case_prefix_hash) never qualify an episode
        daily_members, daily_controls, daily_match = admissible_library_fixture(bind_prefix=False)
        daily = m.library_counts(daily_members + daily_controls, [daily_match], REAL_FORMAT_CAL)
        self.assertEqual((daily["independently_reviewed"], daily["qualified_reviewed_positive_episodes"]), (1, 0))
        self.assertEqual(daily["disqualified_episodes"], {"review_not_bound_to_prefix": 1})
        # a wrong or malformed prefix hash is rejected / orphaned
        wrong = m.attach_review(m.attach_review(real_format_record("SH600011", 269), fixture_review(real_format_record("SH600011", 269), "syn:fixture-only-reviewer-a", case_prefix_hash="0" * 64)),
                                fixture_review(real_format_record("SH600011", 269), "syn:fixture-only-reviewer-b", case_prefix_hash="0" * 64))
        wrong_match = m.match_controls(wrong, self.controls)
        wrong_counts = m.library_counts(self.members[:2] + [wrong] + self.controls, [wrong_match], REAL_FORMAT_CAL)
        self.assertEqual(wrong_counts["disqualified_episodes"], {"review_prefix_binding_mismatch": 1})
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(self.members[0], fixture_review(self.members[0], "x", case_prefix_hash="not-hex"))
        self.assertEqual(ctx.exception.code, "malformed_review_entry")
        # the proof never contains the end / later eligibility and is None for a non-representative member
        self.assertIsNone(m.prefix_proof_for(cases, REAL_FORMAT_CAL, self.members[0]))
        self.assertNotIn("end", proof)
        self.assertEqual(proof["member_episode_ids"], [r["episode_id"] for r in self.members])

    def test_declared_decision_inputs_must_recompute_the_fingerprint(self):
        record = m.generate_labels(codex_request())
        forged = copy.deepcopy(record)
        forged["identity"]["decision_inputs"]["stock_rows"] = "0" * 64
        forged["record_hash"] = m.record_hash(forged)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.verify_record(forged)
        self.assertEqual(ctx.exception.code, "decision_fingerprint_mismatch")
        # re-deriving fingerprint and id after altering an input still fails the declared-duplicate checks
        forged["identity"]["decision_fingerprint"] = m.sha256_text(m.canonical_json(forged["identity"]["decision_inputs"]))
        forged["episode_id"] = m.episode_id(forged["symbol"], forged["cutoff"]["decision_date"], forged["identity"]["decision_fingerprint"])
        forged["record_hash"] = m.record_hash(forged)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.verify_record(forged)
        self.assertEqual(ctx.exception.code, "decision_inputs_mismatch")
        for key, value in (("cutoff", dict(record["cutoff"], as_of="2030-01-01T00:00:00+08:00")), ("synthetic", False), ("calendar", "0" * 64),
                           ("security_context", {"effective": "unknown", "status": "all_unknown", "usable": True}), ("context_usable", True)):
            forged = copy.deepcopy(record)
            forged["identity"]["decision_inputs"][key] = value
            forged["identity"]["decision_fingerprint"] = m.sha256_text(m.canonical_json(forged["identity"]["decision_inputs"]))
            forged["episode_id"] = m.episode_id(forged["symbol"], forged["cutoff"]["decision_date"], forged["identity"]["decision_fingerprint"])
            forged["record_hash"] = m.record_hash(forged)
            with self.assertRaises(m.LabelInputError) as ctx:
                m.verify_record(forged)
            self.assertEqual(ctx.exception.code, "decision_inputs_mismatch", key)
        m.verify_record(record)

    def test_counting_rejections_through_the_same_path(self):
        cases = self.members + self.controls
        rep = self.members[-1]

        def run(cases_, matches_, purpose="target_count"):
            return m.library_counts(cases_, matches_, REAL_FORMAT_CAL, purpose)

        # single reviewed day: duration not established => nothing qualifies, no groups
        one = run([rep] + self.controls, [self.match])
        self.assertEqual((one["episodes_duration_established"], one["qualified_reviewed_positive_episodes"], one["effective_dependence_groups"]), (0, 0, 0))
        self.assertEqual(one["independently_reviewed"], 1)
        # a missing intermediate day breaks continuity even though the reviewed representative is present
        gapped = run([self.members[0], rep] + self.controls, [self.match])
        self.assertEqual(gapped["qualified_reviewed_positive_episodes"], 0)
        self.assertEqual(gapped["episodes_duration_not_established"], 2)
        # reviews on the wrong member (not the representative at established_at)
        wrong_member = m.attach_review(m.attach_review(self.members[0], fixture_review(self.members[0], "syn:fixture-only-reviewer-a")),
                                       fixture_review(self.members[0], "syn:fixture-only-reviewer-b"))
        mismatch = run([wrong_member, self.members[1], real_format_record("SH600011", 269)] + self.controls, [])
        self.assertEqual(mismatch["qualified_reviewed_positive_episodes"], 0)
        self.assertEqual(mismatch["disqualified_episodes"], {"review_pending_review": 1})
        # no match record / controls not supplied / forged match
        self.assertEqual(run(cases, [])["disqualified_episodes"], {"no_revalidated_match_for_representative": 1})
        with self.assertRaises(m.LabelInputError) as ctx:
            run(self.members, [self.match])
        self.assertEqual(ctx.exception.code, "unresolved_record_reference")
        forged = copy.deepcopy(self.match)
        forged.update(controls=[], k_min=0, control_count=3, distinct_control_symbols=3, unmatched=False)
        with self.assertRaises(m.LabelInputError) as ctx:
            run(cases, [forged])
        self.assertEqual(ctx.exception.code, "match_record_mismatch")
        forged = copy.deepcopy(self.match)
        for i, c in enumerate(forged["controls"]):
            c["symbol"] = f"SH99999{i}"
            c["record_hash"] = "0" * 64
        with self.assertRaises(m.LabelInputError) as ctx:
            run(cases, [forged])
        self.assertEqual(ctx.exception.code, "stale_record_reference")
        with self.assertRaises(m.LabelInputError) as ctx:
            run(cases, [self.match, copy.deepcopy(self.match)])
        self.assertEqual(ctx.exception.code, "duplicate_match_record")
        # disputed / single / synthetic-review / non-candidate / outside-universe / holdout representatives never qualify
        disputed = m.attach_review(m.attach_review(real_format_record("SH600011", 269), fixture_review(real_format_record("SH600011", 269), "syn:fixture-only-reviewer-a")),
                                   fixture_review(real_format_record("SH600011", 269), "syn:fixture-only-reviewer-b", "ambiguous"))
        d_counts = run(self.members[:-1] + [disputed] + self.controls, [])
        self.assertEqual((d_counts["disputed"], d_counts["qualified_reviewed_positive_episodes"]), (1, 0))
        self.assertEqual(d_counts["disqualified_episodes"], {"review_disputed": 1})
        single = m.attach_review(real_format_record("SH600011", 269), fixture_review(real_format_record("SH600011", 269), "syn:fixture-only-reviewer-a"))
        self.assertEqual(run(self.members[:-1] + [single] + self.controls, [])["disqualified_episodes"], {"review_single_review_not_independent": 1})
        with self.assertRaises(m.LabelInputError) as ctx:
            run(cases, [self.match], purpose="target_counts")
        self.assertEqual(ctx.exception.code, "unknown_purpose")
        # synthetic fixtures through the identical path: reviews and episodes exist but nothing qualifies
        syn_members = [flat_record(SYN_A, end) for end in (267, 268, 269)]
        syn_controls = [flat_record(f"SYN00001{i}", 269, distribution_spike=True) for i in range(3)]
        syn_proof = m.prefix_proof_for(syn_members, CODEX_CAL, syn_members[-1])
        syn_rep = m.attach_review(m.attach_review(syn_members[-1], syn_review(syn_members[-1], "syn_a", "positive", case_prefix_hash=syn_proof["prefix_hash"])),
                                  syn_review(syn_members[-1], "syn_b", "positive", case_prefix_hash=syn_proof["prefix_hash"]))
        syn_match = m.match_controls(syn_rep, syn_controls)
        self.assertEqual(syn_match["control_count"], 3)
        syn_counts = run(syn_members[:-1] + [syn_rep] + syn_controls, [syn_match])
        self.assertEqual((syn_counts["independently_reviewed"], syn_counts["episodes_duration_established"], syn_counts["qualified_reviewed_positive_episodes"], syn_counts["effective_dependence_groups"]), (1, 1, 0, 0))
        self.assertEqual(syn_counts["disqualified_episodes"], {"synthetic_case": 1})
        self.assertEqual(syn_counts["positively_reviewed_records"], 0)

    def test_split_admission_in_counting(self):
        # holdout-dated real-format records are excluded from admission and can never be counted for target purposes
        holdout_dates = sessions("2025-01-01", 300)  # 270 sessions later lands inside the final holdout
        holdout_cal = m.SessionCalendar(tuple(holdout_dates), "syn:fixture-only-holdout-calendar", EARLY, synthetic=False)
        rows = [replace(r, trade_date=d, available_at=m.close_time(d).isoformat()) for r, d in zip(codex_fixture("SH600011", 270), holdout_dates)]
        rows = [replace(r, source_ref=f"syn:fixture-only:h:{i}") for i, r in enumerate(rows)]
        rec = m.generate_labels(m.LabelRequest(symbol="SH600011", observations=rows, cutoff=m.Cutoff(rows[-1].trade_date, rows[-1].available_at), synthetic=False,
                                               calendar=holdout_cal, universe=REAL_FORMAT_UNIVERSE))
        self.assertEqual(rec["split_role"], "final_holdout")
        counts = m.library_counts([rec], [], holdout_cal)
        self.assertEqual(counts["excluded_by_split_role"], {"final_holdout": 1})
        self.assertEqual(counts["records_admitted"], 0)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(rec, [])
        self.assertIn(ctx.exception.code, ("final_holdout_consumed", "positive_context_unknown"))
        self.assertEqual(m.library_counts([rec], [], holdout_cal, purpose="final_report")["records_admitted"], 1)


# --------------------------------------------------------------------------- #
# Chronological protection, seed context, universe, provenance                #
# --------------------------------------------------------------------------- #


class ProtectionTests(unittest.TestCase):
    def test_split_roles_and_purpose_allowlist(self):
        for d, role in (("2023-09-04", "development"), ("2025-03-31", "development"), ("2025-04-01", "validation"), ("2025-12-31", "validation"),
                        ("2026-01-01", "final_holdout"), ("2026-09-04", "final_holdout"), ("2023-09-01", "outside_research_interval")):
            self.assertEqual(m.split_role(d), role)
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
        self.assertEqual(m.guard_final_holdout(records, "final_report")["roles"], {"development": 1, "final_holdout": 1})

    def test_seed_context_and_frozen_universe(self):
        seeds = m.seed_context()
        self.assertEqual({s["symbol"] for s in seeds}, {"SZ002115", "SZ002081"})
        for s in seeds:
            self.assertEqual((s["status"], s["in_frozen_universe"], s["case_count_contribution"], s["reviewed"]), ("legacy_unverified", False, 0, False))
        universe = m.FrozenUniverse(frozenset({"SH600011", "BJ920006", "SZ002656"}), "TEST_PIN:pilot_symbols.csv", "9" * 64)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.assert_in_universe("SZ002115", universe)
        self.assertEqual(ctx.exception.code, "outside_frozen_universe")
        m.assert_in_universe("SH600011", universe)
        dates, closes, vols = sequence_positive_then_failed()
        real_cal = m.SessionCalendar(tuple(CAL_DATES), "TEST_PIN:calendar", EARLY, synthetic=False)
        outside = m.generate_labels(m.LabelRequest(symbol="SZ002115", observations=bars_from("SZ002115", dates, closes, vols, avail_fixed="2026-09-10T04:17:10+00:00"),
                                                   synthetic=False, universe=universe, calendar=real_cal,
                                                   cutoff=m.Cutoff(dates[295], "2026-09-10T05:00:00+00:00", m.MODE_RETROSPECTIVE)))
        self.assertFalse(outside["universe"]["in_frozen_universe"])
        self.assertEqual(m.POLICY["frozen_universe"]["sha256"], "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe")
        self.assertIn("SH600011 ex-dates 2024-07-11/2025-07-10/2026-07-03", m.POLICY["corporate_actions"]["m2_partial_facts"])

    def test_output_carries_required_provenance(self):
        dates, closes, vols = sequence_positive_then_failed()
        out = m.generate_labels(request_for(SYN_A, bars_from(SYN_A, dates, closes, vols), dates[295]))
        for key in ("policy_version", "policy_hash", "producer_sha256", "cutoff", "calendar", "current_state", "input_availability",
                    "context_availability", "pit", "provenance", "identity", "episode_id", "record_hash", "review_ledger", "data_quality", "split_role"):
            self.assertIn(key, out)
        self.assertEqual(out["producer_sha256"], m.producer_sha256())
        self.assertEqual(out["calendar"]["fingerprint"], CAL.fingerprint())
        self.assertTrue(out["synthetic"])
        json.dumps(out, allow_nan=False)


# --------------------------------------------------------------------------- #
# One-for-one reproductions of Codex's R1 review methods (registry API)       #
# --------------------------------------------------------------------------- #


class CodexReviewReproductions(unittest.TestCase):
    """Mirrors _m3_20260910/codex/test_independent_contract.py on the revised API: genuine flat
    records replace bare summaries (a bare summary is no longer evidence)."""

    def test_matching_duplicate_record_does_not_meet_three_control_minimum(self):
        p = flat_record(SYN_A)
        c = flat_record(SYN_B, distribution_spike=True)
        result = m.match_controls(p, [c] * 5)
        self.assertTrue(result["unmatched"])
        self.assertEqual((result["control_count"], result["identical_duplicates_collapsed"]), (1, 4))

    def test_matching_same_control_symbol_on_five_dates_is_not_five_controls(self):
        p = flat_record(SYN_A)
        result = m.match_controls(p, [flat_record(SYN_B, end, distribution_spike=True) for end in (265, 266, 267, 268, 269)])
        self.assertTrue(result["unmatched"])
        self.assertLessEqual(result["control_count"], 1)
        self.assertEqual(result["rejected_pool_counts"].get("different_decision_date"), 4)

    def test_matching_mixed_policy_not_selected(self):
        p = flat_record(SYN_A)
        c = dict(flat_record(SYN_B, distribution_spike=True), policy_hash="different-policy")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(p, [c])
        self.assertEqual(ctx.exception.code, "policy_hash_mismatch")

    def test_matching_later_decision_not_available_to_positive_cutoff(self):
        p = flat_record(SYN_A, 268)
        result = m.match_controls(p, [flat_record(SYN_B, 269, distribution_spike=True)])
        self.assertEqual((result["control_count"], result["rejected_pool_counts"]), (0, {"different_decision_date": 1}))

    def test_episode_identity_binds_benchmark_that_changes_regime(self):
        base = codex_request(benchmark_symbol=SYN_BENCH, benchmark_observations=codex_fixture(SYN_BENCH, 270, 3000.0), universe_coverage_on_decision_date=coverage())
        b = list(base.benchmark_observations)
        b[-1] = replace(b[-1], open=3600.0, high=3960.0, low=3300.0, close=3600.0, amount=2_000_000.0 * 3600.0)
        a, z = m.generate_labels(base), m.generate_labels(replace(base, benchmark_observations=b))
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
            m.generate_labels(codex_request(security=m.SecurityContext(corporate_action_status="KNOWN", known_ex_dates=("2024-09-26",), evidence_refs=SYN_EVIDENCE, facts_available_at=EARLY)))
        self.assertEqual(ctx.exception.code, "invalid_security_context")

    def test_invalid_coverage_is_rejected_not_known_market_regime(self):
        for value in [True, float("nan"), 1.5, -1]:
            with self.subTest(value=value):
                with self.assertRaises(m.LabelInputError):
                    m.generate_labels(codex_request(benchmark_symbol=SYN_BENCH, benchmark_observations=codex_fixture(SYN_BENCH, 270, 3000.0), universe_coverage_on_decision_date=value))

    def test_missing_decision_bar_cannot_label_current_candidate(self):
        out = m.generate_labels(codex_request(observations=codex_fixture()[:-1]))
        self.assertEqual((out["current_state"], out["labels"]["selection"]["label"]), ("missing", "indeterminate"))

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
        end["record_hash"] = m.record_hash(end)
        end["review_ledger"] = m._empty_ledger(end)
        episodes = m.build_episodes(series[:-1] + [end], CODEX_CAL)
        self.assertEqual((episodes[0]["selection_at_start"], episodes[0]["selection_at_end"], episodes[0]["eligibility_changes"]), ("candidate", "non_candidate", 1))
        self.assertEqual(episodes[0]["min_duration_established_at"], rows[-1].trade_date)

    def test_review_without_any_evidence_cannot_be_independently_reviewed(self):
        out = m.generate_labels(codex_request())
        for who in ["synthetic_reviewer_A", "synthetic_reviewer_B"]:
            with self.assertRaises(m.LabelInputError) as ctx:
                m.attach_review(out, syn_review(out, who, "positive", evidence_refs=()))
            self.assertEqual(ctx.exception.code, "review_without_evidence")
        self.assertEqual(m.review_status(out)["status"], "pending_review")

    def test_review_is_bound_to_specific_case_and_evidence_version(self):
        a = m.generate_labels(codex_request())
        rows = codex_fixture(count=269)
        b = m.generate_labels(codex_request(observations=rows, cutoff=m.Cutoff(rows[-1].trade_date, rows[-1].available_at)))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(b, syn_review(a, "synthetic_reviewer_A", "positive"))
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
        self.assertEqual((after["labels"], after["policy_hash"]), (before["labels"], before["policy_hash"]))

    def test_known_action_does_not_emit_unadjusted_price_stop(self):
        base = codex_request()
        rows = base.observations
        pos = m.PositionState(base.symbol, m.POLICY_HASH, rows[-4].trade_date, rows[-3].trade_date, 12.0, reference_basis="declared",
                              evidence_ref="SYNTHETIC_ONLY:position", available_at=EARLY)
        out = m.generate_labels(replace(base, position_state=pos, security=verified_context(corporate_action_status=m.CA_COMPLETE_KNOWN, known_ex_dates=(rows[-2].trade_date,))))
        self.assertEqual(out["labels"]["phase"]["label"], "indeterminate")
        self.assertEqual(out["labels"]["position_event"]["label"], "review_required")
        self.assertIn("known_corporate_action_in_holding_window", out["labels"]["position_event"]["reasons"])

    def test_position_reference_before_entry_is_rejected(self):
        base = codex_request()
        rows = base.observations
        pos = m.PositionState(base.symbol, m.POLICY_HASH, rows[-4].trade_date, rows[-10].trade_date, 10.0, evidence_ref="SYNTHETIC_ONLY:position", available_at=EARLY)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(replace(base, position_state=pos))
        self.assertEqual(ctx.exception.code, "position_reference_before_entry")


# --------------------------------------------------------------------------- #
# One-for-one reproductions of Codex's R2 consumer methods                    #
# --------------------------------------------------------------------------- #

R2_DAYS = sessions("2023-01-02", 300)
R2_CAL = m.SessionCalendar(tuple(R2_DAYS), "syn:independent-calendar", "2022-12-01T00:00:00+08:00", True)


def r2_request(symbol="SYN001001", end=269, **overrides):
    def observations(code):
        units = BENCH_UNITS if code.startswith("SYN9") else {}  # API adaptation: retained benchmark units are mandatory in R3
        return tuple(m.Observation(code, d, "price", d + "T15:00:00+08:00", f"syn:independent:{code}:{d}", 10.0, 11.0, 9.0, 10.0,
                                   2_000_000.0, 20_000_000.0, **units) for d in R2_DAYS[: end + 1])
    args = dict(symbol=symbol, observations=observations(symbol), cutoff=m.Cutoff(R2_DAYS[end], R2_DAYS[end] + "T16:00:00+08:00"),
                calendar=R2_CAL, synthetic=True, benchmark_symbol="SYN900001", benchmark_observations=observations("SYN900001"),
                universe_coverage_on_decision_date=m.Coverage(1.0, "syn:coverage", "2022-12-01T00:00:00+08:00"))
    args.update(overrides)
    return m.LabelRequest(**args)


def r2_review(record, who, verdict="positive", **overrides):
    args = dict(reviewer_id=who, reviewer_kind="agent", reviewed_at="2026-09-10T07:00:00+00:00", verdict=verdict,
                evidence_refs=("syn:fixture-only-case-evidence",), execution_ref="syn:fixture-only-execution:" + who,
                case_episode_id=record["episode_id"], case_record_hash=record["record_hash"], case_policy_hash=record["policy_hash"], synthetic=True)
    args.update(overrides)
    return m.ReviewRecord(**args)


def r2_two_reviews(record):
    for who in ("syn-reviewer-a", "syn-reviewer-b"):
        record = m.attach_review(record, r2_review(record, who))
    return record


def r2_real_format_fixture():
    symbols = ("SH600011", "SH600110", "SH600129", "SH600162")
    universe = m.FrozenUniverse(frozenset(symbols), "syn:fixture-only-universe", "1" * 64)
    cal = replace(R2_CAL, source_ref="syn:fixture-only-real-format-calendar", synthetic=False)
    records = []
    for i, symbol in enumerate(symbols):
        req = r2_request(symbol)
        bench = tuple(replace(b, symbol="SH000300", source_ref="syn:fixture-only-benchmark", **BENCH_UNITS) for b in req.benchmark_observations)
        obs = list(req.observations)
        if i:
            obs[-1] = replace(obs[-1], high=13.5, close=13.0, volume=3_000_000.0, amount=39_000_000.0)
        records.append(m.generate_labels(replace(req, observations=tuple(obs), benchmark_symbol="SH000300", benchmark_observations=bench,
                                                 synthetic=False, calendar=cal, universe=universe)))
    positive = records[0]
    for who in ("syn:fixture-only-reviewer-a", "syn:fixture-only-reviewer-b"):
        positive = m.attach_review(positive, r2_review(positive, who, synthetic=False))
    match = m.match_controls(positive, records[1:])
    assert not match["unmatched"] and match["control_count"] == 3
    return positive, records[1:], match, cal


class CodexR2ConsumerReproductions(unittest.TestCase):
    """Mirrors _m3_20260910/codex/test_independent_r2.py.  Only the counting methods are adapted:
    library_counts now requires every referenced control record to be supplied (fail closed)."""

    def test_fixture_is_candidate_and_every_case_is_synthetic(self):
        rec = m.generate_labels(r2_request())
        self.assertEqual(rec["labels"]["selection"]["label"], "candidate")
        self.assertTrue(rec["synthetic"])
        self.assertFalse(rec["pit"]["training_eligible"])
        self.assertFalse(m.library_counts([rec], [], R2_CAL)["target_met"])

    def test_unmodified_review_append_preserves_core(self):
        rec = m.generate_labels(r2_request())
        reviewed = r2_two_reviews(rec)
        self.assertEqual(reviewed["record_hash"], rec["record_hash"])
        self.assertEqual((len(reviewed["review_ledger"]["entries"]), len(rec["review_ledger"]["entries"])), (2, 0))
        self.assertEqual(m.library_counts([reviewed], [], R2_CAL)["qualified_positives"], 0)

    def test_transplanted_valid_ledger_cannot_accept_a_new_case_review(self):
        first = r2_two_reviews(m.generate_labels(r2_request()))
        other = m.generate_labels(r2_request("SYN001002"))
        other["review_ledger"] = copy.deepcopy(first["review_ledger"])
        self.assertEqual(m.record_hash(other), other["record_hash"])
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(other, r2_review(other, "syn-reviewer-c"))
        self.assertEqual(ctx.exception.code, "ledger_binding_mismatch")

    def test_library_count_rejects_tampered_ledger(self):
        rec = r2_two_reviews(m.generate_labels(r2_request()))
        rec["review_ledger"]["entries"][0]["execution_ref"] = ""
        with self.assertRaises(m.LabelInputError):
            m.library_counts([rec], [], R2_CAL)

    def test_library_count_rejects_duplicate_case_records(self):
        rec = r2_two_reviews(m.generate_labels(r2_request()))
        count = m.library_counts([rec, copy.deepcopy(rec)], [], R2_CAL)
        self.assertEqual((count["raw_input_records"], count["unique_records"], count["independently_reviewed"]), (2, 1, 1))

    def test_compact_summary_cannot_relabel_candidate_controls(self):
        positive = m.generate_labels(r2_request())
        records = [m.generate_labels(r2_request("SYN00100" + str(i + 2))) for i in range(3)]
        forged = []
        for rec in records:
            self.assertEqual(rec["labels"]["selection"]["label"], "candidate")
            forged.append(dict(m.case_summary(rec), selection="non_candidate"))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(positive, forged)
        self.assertEqual(ctx.exception.code, "unresolved_record_reference")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(positive, forged, registry=m.RecordRegistry([positive] + records))
        self.assertEqual(ctx.exception.code, "summary_conflicts_with_core")

    def test_compact_summary_cannot_invent_record_hash(self):
        rec = m.generate_labels(r2_request())
        summary = m.case_summary(rec)
        summary["record_hash"] = "z" * 64
        with self.assertRaises(m.LabelInputError) as ctx:
            m.case_summary(summary)
        self.assertEqual(ctx.exception.code, "malformed_summary")

    def test_superseding_an_already_superseded_review_cannot_fork_current_verdict(self):
        rec = m.generate_labels(r2_request())
        rec = m.attach_review(rec, r2_review(rec, "syn-reviewer-a"))
        initial = rec["review_ledger"]["entries"][0]["entry_hash"]
        rec = m.attach_review(rec, r2_review(rec, "syn-reviewer-a", "ambiguous", supersedes=initial, supersede_reason="syn:corrected-reading", reviewed_at="2026-09-10T07:01:00+00:00"))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(rec, r2_review(rec, "syn-reviewer-a", "negative", supersedes=initial, supersede_reason="syn:stale-base", reviewed_at="2026-09-10T07:02:00+00:00"))
        self.assertEqual(ctx.exception.code, "invalid_supersede")

    def test_superseding_review_must_be_later_than_original(self):
        rec = m.generate_labels(r2_request())
        rec = m.attach_review(rec, r2_review(rec, "syn-reviewer-a"))
        initial = rec["review_ledger"]["entries"][0]["entry_hash"]
        with self.assertRaises(m.LabelInputError) as ctx:
            m.attach_review(rec, r2_review(rec, "syn-reviewer-a", "ambiguous", supersedes=initial, supersede_reason="syn:impossible-time", reviewed_at="2026-09-09T07:00:00+00:00"))
        self.assertEqual(ctx.exception.code, "invalid_supersede")

    def test_session_close_reference_cannot_be_available_before_reference_date(self):
        sec = m.SecurityContext(corporate_action_status=m.CA_NONE_VERIFIED, evidence_refs=("syn:no-actions",), facts_available_at="2022-12-01T00:00:00+08:00")
        pos = m.PositionState("SYN001001", m.POLICY_HASH, R2_DAYS[260], R2_DAYS[261], 10.0, reference_basis="session_close",
                              evidence_ref="syn:reference-close", available_at="2022-12-01T00:00:00+08:00")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(r2_request(security=sec, position_state=pos))
        self.assertEqual(ctx.exception.code, "position_reference_available_before_observable")

    def test_non_consumed_context_does_not_change_decision_identity(self):
        late_a = m.SecurityContext(st_status="st", evidence_refs=("syn:late-a",), facts_available_at="2026-09-10T00:00:00+00:00")
        late_b = replace(late_a, st_status="not_st", evidence_refs=("syn:late-b",))
        first, second = m.generate_labels(r2_request(security=late_a)), m.generate_labels(r2_request(security=late_b))
        self.assertFalse(first["context_availability"]["usable"])
        self.assertEqual(first["labels"], second["labels"])
        self.assertEqual(first["episode_id"], second["episode_id"])

    def test_future_stock_suffix_remains_invariant(self):
        original = r2_request()
        extended = replace(r2_request(end=280), cutoff=original.cutoff)
        first, second = m.generate_labels(original), m.generate_labels(extended)
        self.assertEqual((first["record_hash"], first["episode_id"]), (second["record_hash"], second["episode_id"]))

    def test_counting_cannot_trust_caller_lowered_control_minimum(self):
        rec, controls, match, cal = r2_real_format_fixture()
        match.update(controls=[], k_min=0, control_count=3, distinct_control_symbols=3, unmatched=False)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.library_counts([rec] + controls, [match], cal)
        self.assertEqual(ctx.exception.code, "match_record_mismatch")

    def test_counting_cannot_trust_changed_control_identity(self):
        rec, controls, match, cal = r2_real_format_fixture()
        for index, control in enumerate(match["controls"]):
            control["symbol"] = "SH99999" + str(index)
            control["record_hash"] = "0" * 64
        with self.assertRaises(m.LabelInputError) as ctx:
            m.library_counts([rec] + controls, [match], cal)
        self.assertEqual(ctx.exception.code, "stale_record_reference")

    def test_single_decision_cannot_establish_minimum_episode_duration(self):
        rec, controls, match, cal = r2_real_format_fixture()
        episodes = m.build_episodes([rec], cal)
        self.assertFalse(episodes[0]["meets_min_sessions"])
        count = m.library_counts([rec] + controls, [match], cal)  # controls supplied: the declared in-memory requirement
        self.assertEqual((count["effective_dependence_groups"], count["qualified_reviewed_positive_episodes"], count["independently_reviewed"]), (0, 0, 1))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.library_counts([rec], [match], cal)  # the literal Codex call: referenced controls absent => fail closed
        self.assertEqual(ctx.exception.code, "unresolved_record_reference")


# --------------------------------------------------------------------------- #
# Reproductions of Codex's hand-calculated feature oracle                     #
# --------------------------------------------------------------------------- #


def oracle_bars():
    dates = sessions("2023-01-02", 301)
    rows = [SimpleNamespace(symbol="SYN910001", trade_date=d, open=10.0, high=12.0, low=8.0, close=10.0, volume=1_000_000.0, amount=10_000_000.0, kind="price") for d in dates]
    rows[-1].close = 11.0
    rows[-1].volume = 2_000_000.0
    rows[-1].amount = 22_000_000.0
    return rows


class CodexFeatureOracleReproductions(unittest.TestCase):
    """Mirrors _m3_20260910/codex/test_feature_oracle.py (the feature kernel is unchanged in R3)."""

    def test_hand_calculated_terminal_bar(self):
        f = m.bar_features(oracle_bars(), 300)
        expected = {"close": 11.0, "prev_close": 10.0, "pct_change": 0.1, "return_20": 0.1, "return_60": 0.1, "return_120": 0.1,
                    "ma20": 201 / 20, "ma60": 601 / 60, "ma_spread_20_60": 2 / 601, "position_250": 3 / 4, "high_250": 12.0,
                    "close_to_high": 11 / 12, "drawdown_from_lookback_high": -1 / 12, "volume_ratio_20": 2.0, "amount_20_mean_cny": 10_600_000.0}
        for key, value in expected.items():
            with self.subTest(feature=key):
                self.assertAlmostEqual(f[key], value, places=10)

    def test_position_window_excludes_251st_bar(self):
        rows = oracle_bars()
        rows[50].low, rows[50].high = 1.0, 20.0
        self.assertAlmostEqual(m.bar_features(rows, 300)["position_250"], 3 / 4)
        rows[51].low, rows[51].high = 1.0, 20.0
        self.assertAlmostEqual(m.bar_features(rows, 300)["position_250"], 10 / 19)

    def test_volume_mean_uses_exactly_twenty_prior_bars(self):
        rows = oracle_bars()
        rows[279].volume = 100_000_000.0
        self.assertEqual(m.bar_features(rows, 300)["volume_ratio_20"], 2.0)
        rows[280].volume = 41_000_000.0
        self.assertAlmostEqual(m.bar_features(rows, 300)["volume_ratio_20"], 2 / 3)

    def test_amount_mean_includes_today_but_not_21st_bar(self):
        rows = oracle_bars()
        rows[280].amount = 900_000_000.0
        self.assertEqual(m.bar_features(rows, 300)["amount_20_mean_cny"], 10_600_000.0)
        rows[281].amount = 30_000_000.0
        self.assertEqual(m.bar_features(rows, 300)["amount_20_mean_cny"], 11_600_000.0)

    def test_return_endpoints_use_k_price_intervals(self):
        for distance, key in [(20, "return_20"), (60, "return_60"), (120, "return_120")]:
            with self.subTest(distance=distance):
                rows = oracle_bars()
                rows[300 - distance - 1].close = 4.0
                rows[300 - distance].close = 5.0
                self.assertAlmostEqual(m.bar_features(rows, 300)[key], 1.2)

    def test_kernel_ignores_offered_future_price_suffix(self):
        rows = oracle_bars()
        before = m.bar_features(rows, 300)
        rows.append(SimpleNamespace(symbol="SYN910001", trade_date="2099-01-05", open=700.0, high=900.0, low=500.0, close=800.0, volume=1e12, amount=8e14, kind="price"))
        self.assertEqual(m.bar_features(rows, 300), before)

    def test_undefined_position_and_volume_denominator_remain_unknown(self):
        rows = oracle_bars()
        for row in rows:
            row.low = row.high = row.open = row.close = 10.0
            row.volume = row.amount = 0.0
        f = m.bar_features(rows, 300)
        self.assertIsNone(f["position_250"])
        self.assertIsNone(f["volume_ratio_20"])
        self.assertEqual(f["amount_20_mean_cny"], 0.0)
        self.assertTrue(f["zero_volume_session"])

    def test_return_needs_one_more_price_than_interval_length(self):
        rows = oracle_bars()
        for distance, key in [(20, "return_20"), (60, "return_60"), (120, "return_120")]:
            with self.subTest(distance=distance):
                self.assertIsNone(m.bar_features(rows, distance - 1)[key])
                self.assertEqual(m.bar_features(rows, distance)[key], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
