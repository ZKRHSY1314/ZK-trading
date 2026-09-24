"""Adversarial synthetic tests for ``backend/app/research/m3_labels.py``.

Run directly with the project interpreter (stdlib unittest, loaded by file path,
no ``app`` package import, no conftest, no SQLite, no network):

    D:/codex-A股交易/backend/.venv/Scripts/python.exe -B -X utf8 backend/tests/test_m3_labels.py -v

Every fixture is visibly synthetic (``SYN######`` symbols, ``synthetic=True``)
and is excluded from real case counts by the module itself.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import math
import sys
import unittest
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


def sessions(start: str, n: int) -> list[str]:
    d = date.fromisoformat(start)
    out: list[str] = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


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
        # gently drifting, noisy range: the tail sits in the lower part of its 250-session range
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
    return sessions("2023-01-02", len(closes)), closes, vols


def sequence_distribution(seed: int = 11, n_rise: int = 280) -> tuple[list[str], list[float], list[int]]:
    """Slow rise to the top of its range, then a volume spike with intraday rejection on the last session."""
    r = lcg(seed)
    closes: list[float] = []
    vols: list[int] = []
    c = 10.0
    for i in range(n_rise):
        c *= 1.0 + 0.0022 + (next(r) - 0.5) * 0.006
        closes.append(c)
        vols.append(1_000_000 + int(next(r) * 150_000))
    closes.append(c * 0.985)  # close well below the day's high (upper shadow added by bars_from)
    vols.append(2_600_000)
    return sessions("2023-01-02", len(closes)), closes, vols


def request_for(symbol: str, rows, decision_date: str, mode: str = m.MODE_STRICT, **kw):
    cutoff = m.Cutoff(decision_date, (m.close_time(decision_date) + timedelta(hours=4)).isoformat(), mode)
    return m.LabelRequest(symbol=symbol, observations=rows, cutoff=cutoff, synthetic=True, **kw)


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


class PolicyIdentityTests(unittest.TestCase):
    def test_namespace_version_and_hash(self):
        self.assertEqual(m.NAMESPACE, "m3.labels")
        self.assertIn("draft", m.POLICY_VERSION)
        self.assertEqual(m.POLICY_HASH, m.sha256_text(m.canonical_json(m.POLICY)))
        legacy = {"observable_structure_v1", "main_force_phase_replays", "agent_learning_outcomes"}
        self.assertFalse({m.NAMESPACE, m.POLICY_ID} & legacy)
        doc = m.policy_document()
        self.assertEqual(doc["policy_hash"], m.POLICY_HASH)
        self.assertFalse(m.POLICY["safety"]["live_trading_enabled"])
        self.assertTrue(m.POLICY["safety"]["review_only"])

    def test_module_is_pure_stdlib_and_clock_free(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        allowed = {"hashlib", "json", "math", "re", "dataclasses", "datetime", "pathlib", "typing", "__future__"}
        self.assertTrue(imported <= allowed, imported - allowed)
        for forbidden in ("date.today", "datetime.now", "utcnow(", "time.time", "sqlite3", "urlopen", "requests", "pandas", "random"):
            self.assertNotIn(forbidden, source, forbidden)


class InputRejectionTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def _expect(self, code: str, rows, symbol=SYN_A, synthetic=True):
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_observations(rows, symbol, synthetic)
        self.assertEqual(ctx.exception.code, code)

    def test_wrong_identity_duplicate_unsorted(self):
        self._expect("wrong_security_identity", self.rows, symbol=SYN_B)
        self._expect("duplicate_key", self.rows[:5] + [self.rows[4]])
        self._expect("unsorted_input", [self.rows[1], self.rows[0]])
        self._expect("no_observations", [])

    def test_symbol_patterns(self):
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_symbol("SZ002115", synthetic=True)
        self.assertEqual(ctx.exception.code, "synthetic_symbol_pattern")
        with self.assertRaises(m.LabelInputError):
            m.validate_symbol(SYN_A, synthetic=False)
        with self.assertRaises(m.LabelInputError):
            m.validate_symbol("sz002115", synthetic=False)
        self.assertEqual(m.validate_symbol("BJ920006", synthetic=False), "BJ920006")

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

    def test_availability_units_and_kinds(self):
        base = self.rows[0]

        def rep(**kw):
            return [m.Observation(**{**base.record(), **kw})]

        self._expect("availability_before_close", rep(available_at=(m.close_time(base.trade_date) - timedelta(minutes=1)).isoformat()))
        self._expect("invalid_available_at", rep(available_at="2023-01-02T18:00:00"))  # naive datetime
        self._expect("invalid_available_at", rep(available_at=None))
        self._expect("unsupported_adjustment_mode", rep(adjustment_mode="qfq"))
        self._expect("unsupported_volume_unit", rep(volume_unit="hand"))
        self._expect("unknown_observation_kind", rep(kind="index"))
        self._expect("missing_source_ref", rep(source_ref=""))
        self._expect("invalid_trade_date", rep(trade_date="ERROR"))
        self._expect("suspension_with_prices", [m.Observation(**{**suspension(SYN_A, base.trade_date).record(), "close": 1.0})])

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


class CausalityTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def test_strict_cutoff_excludes_late_availability(self):
        d = self.dates[280]
        late = self.rows[:281]
        # the decision-day bar is declared available only two days later
        late[-1] = m.Observation(**{**late[-1].record(), "available_at": (m.close_time(d) + timedelta(days=2)).isoformat()})
        usable, summary, diag = m.select_usable(late, m.Cutoff(d, (m.close_time(d) + timedelta(hours=4)).isoformat(), "strict"))
        self.assertEqual(usable[-1].trade_date, self.dates[279])
        self.assertEqual(summary["availability_violations_consumed"], 0)
        self.assertEqual(diag["rows_excluded_late_availability"], 1)
        self.assertEqual(diag["rows_excluded_after_cutoff"], 0)
        self.assertTrue(summary["strict_pit_eligible"])
        self.assertFalse(summary["training_eligible"])
        # the same row is consumed once it is declared available in time
        usable2, summary2, diag2 = m.select_usable(self.rows[:281], m.Cutoff(d, (m.close_time(d) + timedelta(hours=4)).isoformat(), "strict"))
        self.assertEqual(usable2[-1].trade_date, d)
        self.assertEqual(diag2["rows_excluded_late_availability"], 0)

    def test_retrospective_capture_never_strict_pit(self):
        capture = "2026-09-10T04:17:10+00:00"  # M2-style: every row captured on one day
        rows = bars_from(SYN_A, self.dates, self.closes, self.vols, avail_fixed=capture)
        d = self.dates[300]
        strict = m.generate_labels(request_for(SYN_A, rows, d, m.MODE_STRICT))
        self.assertEqual(strict["input_availability"]["rows_consumed"], 0)
        self.assertEqual(strict["labels"]["phase"]["label"], "indeterminate")
        self.assertIn("no_price_bars_before_cutoff", strict["labels"]["phase"]["reasons"])
        retro = m.generate_labels(request_for(SYN_A, rows, d, m.MODE_RETROSPECTIVE))
        ia = retro["input_availability"]
        self.assertEqual(ia["rows_consumed"], 301)
        self.assertEqual(ia["availability_violations_consumed"], 301)
        self.assertEqual(strict["request_diagnostics"]["rows_excluded_late_availability"], 301)
        self.assertFalse(ia["strict_pit_eligible"])
        self.assertFalse(ia["training_eligible"])
        self.assertTrue(ia["retrospective"])
        self.assertEqual(ia["provenance_kind"], "retrospective_capture_not_point_in_time")
        self.assertFalse(retro["semantics"]["strict_pit_eligible"])
        self.assertFalse(retro["semantics"]["training_eligible"])
        self.assertNotEqual(retro["labels"]["phase"]["label"], "indeterminate")

    def test_suffix_mutation_and_truncation_invariance(self):
        d = self.dates[290]  # inside the accumulation regime, before the markup exists
        full = m.generate_labels(request_for(SYN_A, self.rows, d))
        truncated = m.generate_labels(request_for(SYN_A, self.rows[:291], d))
        mutated_rows = self.rows[:291] + bars_from(SYN_A, self.dates[291:], [c * 3.0 for c in self.closes[291:]],
                                                    [v * 5 for v in self.vols[291:]])
        mutated = m.generate_labels(request_for(SYN_A, mutated_rows, d))

        def stable(o):
            return {k: v for k, v in o.items() if k != "request_diagnostics"}

        self.assertEqual(stable(full), stable(truncated))
        self.assertEqual(stable(full), stable(mutated))
        self.assertEqual(full["record_hash"], mutated["record_hash"])
        self.assertEqual(full["record_hash"], m.record_hash(full))
        self.assertEqual(full["episode_id"], mutated["episode_id"])
        self.assertEqual(full["input_availability"]["rows_consumed"], 291)
        self.assertEqual(full["request_diagnostics"]["rows_excluded_after_cutoff"], len(self.rows) - 291)
        self.assertEqual(truncated["request_diagnostics"]["rows_excluded_after_cutoff"], 0)
        self.assertNotEqual(full["request_diagnostics"], truncated["request_diagnostics"])

    def test_past_accumulation_not_relabelled_by_future_markup(self):
        d = self.dates[295]
        before = m.generate_labels(request_for(SYN_A, self.rows[:296], d))
        after = m.generate_labels(request_for(SYN_A, self.rows, d))
        self.assertEqual(before["labels"], after["labels"])
        self.assertEqual(before["labels"]["phase"]["label"], "accumulation")

    def test_state_isolation_and_repeatability(self):
        policy_before = m.POLICY_HASH
        d = self.dates[320]
        a1 = m.generate_labels(request_for(SYN_A, self.rows, d))
        other = bars_from(SYN_B, *sequence_distribution())
        m.generate_labels(request_for(SYN_B, other, other[-1].trade_date))
        a2 = m.generate_labels(request_for(SYN_A, self.rows, d))
        self.assertEqual(a1, a2)
        self.assertEqual(m.POLICY_HASH, policy_before)
        self.assertEqual(m.sha256_text(m.canonical_json(m.POLICY)), policy_before)
        series1 = m.label_series(request_for(SYN_A, self.rows, d), self.dates[300:305])
        series2 = m.label_series(request_for(SYN_A, self.rows, d), self.dates[300:305])
        self.assertEqual(series1, series2)


class PhaseSequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dates, cls.closes, cls.vols = sequence_positive_then_failed()
        cls.rows = bars_from(SYN_A, cls.dates, cls.closes, cls.vols)
        cls.series = m.label_series(request_for(SYN_A, cls.rows, cls.dates[-1]), cls.dates[249:])
        cls.by_date = {o["cutoff"]["decision_date"]: o for o in cls.series}
        cls.episodes = m.build_episodes(cls.series)

    def test_positive_markup_failed_sequence(self):
        path = [e["phase"] for e in self.episodes]
        self.assertIn("accumulation", path)
        self.assertIn("markup", path)
        self.assertIn("failed_markup", path)
        self.assertLess(path.index("accumulation"), path.index("markup"))
        self.assertLess(path.index("markup"), path.index("failed_markup"))
        first_markup = next(e for e in self.episodes if e["phase"] == "markup")
        self.assertGreaterEqual(first_markup["start"], self.dates[300])
        failed = next(e for e in self.episodes if e["phase"] == "failed_markup")
        self.assertGreaterEqual(failed["start"], self.dates[320])
        out = self.by_date[failed["start"]]
        self.assertTrue(out["labels"]["phase"]["markup_within_lookback"])
        self.assertEqual(out["labels"]["selection"]["label"], "non_candidate")
        self.assertEqual(out["labels"]["entry"]["label"], "signal_not_eligible")

    def test_accumulation_is_candidate_and_carries_semantics(self):
        acc = next(e for e in self.episodes if e["phase"] == "accumulation")
        out = self.by_date[acc["end"]]
        self.assertEqual(out["labels"]["selection"]["label"], "candidate")
        self.assertTrue(out["review_only"])
        self.assertFalse(out["live_trading_enabled"])
        self.assertFalse(out["semantics"]["hidden_actor_claim"])
        self.assertFalse(out["semantics"]["trade_recommendation"])
        self.assertTrue(out["semantics"]["observable_behavioural_proxy"])
        self.assertEqual(out["labels"]["entry"]["tradability"], "unverified")
        self.assertEqual(out["labels"]["entry"]["execution"]["legal_next_session"], "unknown")
        self.assertEqual(out["labels"]["position_event"]["label"], "no_trade")

    def test_failed_markup_requires_prior_observable_markup(self):
        # Same drawdown shape without any prior markup: a fresh decline from a flat range.
        r = lcg(3)
        closes, vols = [], []
        c = 10.0
        for i in range(300):
            c = 10.0 + (next(r) - 0.5) * 0.1
            closes.append(c)
            vols.append(1_000_000)
        for _ in range(15):
            c *= 0.987
            closes.append(c)
            vols.append(1_000_000)
        dates = sessions("2023-01-02", len(closes))
        rows = bars_from(SYN_B, dates, closes, vols)
        out = m.generate_labels(request_for(SYN_B, rows, dates[-1]))
        self.assertNotEqual(out["labels"]["phase"]["label"], "failed_markup")
        self.assertFalse(out["labels"]["phase"]["markup_within_lookback"])

    def test_accumulation_after_failed_markup_is_not_a_candidate(self):
        failed = next(e for e in self.episodes if e["phase"] == "failed_markup")
        following = [e for e in self.episodes if e["start"] > failed["end"] and e["phase"] == "accumulation"]
        if following:
            out = self.by_date[following[0]["start"]]
            self.assertEqual(out["labels"]["selection"]["label"], "non_candidate")
            self.assertIn("failed_markup_within_veto_lookback", out["labels"]["selection"]["reasons"])

    def test_episode_contract(self):
        for e in self.episodes:
            self.assertFalse(e["counts_toward_case_library"])
            self.assertTrue(e["synthetic"])
            self.assertEqual(e["review"]["status"], "pending_review")
            self.assertEqual(e["policy_hash"], m.POLICY_HASH)
        self.assertTrue(self.episodes[-1]["open_at_last_cutoff"])
        self.assertTrue(all(not e["open_at_last_cutoff"] for e in self.episodes[:-1]))
        with self.assertRaises(m.LabelInputError):
            m.build_episodes(self.series[:2] + [dict(self.series[2], symbol=SYN_B)])
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes([self.series[1], self.series[0]])
        self.assertEqual(ctx.exception.code, "series_not_chronological")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.build_episodes(self.series[:2] + [dict(self.series[2], policy_hash="0" * 64)])
        self.assertEqual(ctx.exception.code, "mixed_policy_hashes_in_series")


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
        self.assertEqual(out["labels"]["entry"]["label"], "signal_not_eligible")

    def test_ambiguous_stays_indeterminate(self):
        dates, closes, vols = sequence_positive_then_failed()
        rows = bars_from(SYN_A, dates, closes, vols)
        # index 310: mid-markup return but the volume ratio decays -> often no rule matches
        outs = m.label_series(request_for(SYN_A, rows, dates[-1]), dates[300:340])
        indeterminate = [o for o in outs if o["labels"]["phase"]["rule"] == "no_rule_matched"]
        self.assertTrue(indeterminate, "expected at least one ambiguous cutoff in the transition window")
        o = indeterminate[0]
        self.assertEqual(o["labels"]["phase"]["label"], "indeterminate")
        self.assertEqual(o["labels"]["selection"]["label"], "indeterminate")
        self.assertEqual(o["labels"]["entry"]["label"], "indeterminate")
        self.assertEqual(o["labels"]["position_event"]["label"], "no_trade")


class DataQualityTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def test_insufficient_warmup(self):
        out = m.generate_labels(request_for(SYN_A, self.rows[:200], self.dates[199]))
        self.assertEqual(out["labels"]["phase"]["label"], "indeterminate")
        self.assertTrue(any(r.startswith("insufficient_warmup:200<250") for r in out["labels"]["phase"]["reasons"]))
        self.assertEqual(out["labels"]["selection"]["label"], "indeterminate")

    def test_suspension_on_last_observation_and_many_suspensions(self):
        d = self.dates[290]
        rows = self.rows[:290] + [suspension(SYN_A, d)]
        out = m.generate_labels(request_for(SYN_A, rows, d))
        self.assertIn("suspension_on_last_observation", out["labels"]["phase"]["reasons"])
        self.assertEqual(out["labels"]["phase"]["label"], "indeterminate")
        # a suspension row never becomes a price and is never zero
        self.assertEqual(out["features"]["trade_date"], self.dates[289])
        # twelve suspensions inside the window
        rows = self.rows[:270] + [suspension(SYN_A, x) for x in self.dates[270:282]] + self.rows[282:296]
        out = m.generate_labels(request_for(SYN_A, rows, self.dates[295]))
        self.assertTrue(any(r.startswith("many_suspensions_in_window") for r in out["labels"]["phase"]["reasons"]))

    def test_long_gap_and_staleness(self):
        rows = self.rows[:280] + self.rows[296:]
        out = m.generate_labels(request_for(SYN_A, rows, self.dates[300]))
        self.assertTrue(any(r.startswith("long_gap_in_window") for r in out["labels"]["phase"]["reasons"]))
        stale = m.generate_labels(m.LabelRequest(symbol=SYN_A, observations=self.rows[:290], synthetic=True,
                                                 cutoff=m.Cutoff("2024-03-01", "2024-03-01T16:00:00+08:00", m.MODE_RETROSPECTIVE)))
        self.assertTrue(any(r.startswith("stale_last_bar") for r in stale["labels"]["phase"]["reasons"]))

    def test_corporate_action_handling(self):
        d = self.dates[295]
        known = m.SecurityContext(corporate_action_status="known", known_ex_dates=(self.dates[280],))
        out = m.generate_labels(request_for(SYN_A, self.rows, d, security=known))
        self.assertIn("known_corporate_action_in_window", out["labels"]["phase"]["reasons"])
        self.assertEqual(out["labels"]["phase"]["label"], "indeterminate")
        unknown = m.generate_labels(request_for(SYN_A, self.rows, d))
        self.assertTrue(unknown["semantics"]["adjustment_uncertainty"])
        self.assertFalse(unknown["semantics"]["realized_return_claim"])
        self.assertIn("adjustment_uncertainty:corporate_action_status=unknown", unknown["data_quality"])
        self.assertIn("turnover_unavailable", unknown["data_quality"])
        self.assertIn("float_shares_unavailable", unknown["data_quality"])
        self.assertEqual(unknown["labels"]["phase"]["label"], "accumulation")  # still labelled, uncertainty carried
        verified = m.generate_labels(request_for(SYN_A, self.rows, d, security=m.SecurityContext(corporate_action_status="none_verified")))
        self.assertFalse(verified["semantics"]["adjustment_uncertainty"])

    def test_bj_scope_exception_only_for_pinned_key(self):
        exc = m.POLICY["scope_exceptions"][0]
        self.assertEqual((exc["symbol"], exc["trade_date"]), ("BJ920006", "2023-12-04"))
        d = "2023-12-04"
        base = bars_from("BJ920006", [d], [12.5], [1_610_724])[0]
        bad = m.Observation(**{**base.record(), "high": 12.75, "low": 12.15, "open": 12.3, "close": 12.5,
                               "volume": 1_610_724.0, "amount": 18_876_856.0})  # whole-day vwap 11.7195 < low
        m.validate_observations([bad], "BJ920006", synthetic=False)  # accepted because pinned
        other = m.Observation(**{**bad.record(), "symbol": "BJ920007"})
        with self.assertRaises(m.LabelInputError) as ctx:
            m.validate_observations([other], "BJ920007", synthetic=False)
        self.assertEqual(ctx.exception.code, "vwap_outside_range")
        other_day = m.Observation(**{**bad.record(), "trade_date": "2023-12-05"})
        with self.assertRaises(m.LabelInputError):
            m.validate_observations([other_day], "BJ920006", synthetic=False)
        # the pinned bar's volume/amount never enters ratio means and blocks the decision bar
        self.assertIsNone(m._volume_for_ratio(bad))
        real_dates = sessions("2022-11-01", 300)
        real_dates = [x for x in real_dates if x != d][:280] + [d]
        real_dates.sort()
        idx = real_dates.index(d)
        closes = [12.4 + 0.05 * math.sin(i / 7.0) for i in range(len(real_dates))]
        rows = bars_from("BJ920006", real_dates, closes, [1_500_000] * len(real_dates), avail_fixed="2026-09-10T04:17:10+00:00")
        rows[idx] = m.Observation(**{**rows[idx].record(), "amount": 18_876_856.0, "volume": 1_610_724.0,
                                     "high": 12.75, "low": 12.15, "open": 12.3, "close": 12.5})
        out = m.generate_labels(m.LabelRequest(symbol="BJ920006", observations=rows, synthetic=False,
                                               cutoff=m.Cutoff(d, "2026-09-10T05:00:00+00:00", m.MODE_RETROSPECTIVE)))
        self.assertIsNone(out["features"]["volume_ratio_20"])
        self.assertIn("scope_exception_on_decision_bar", out["labels"]["phase"]["reasons"])
        self.assertEqual(out["labels"]["phase"]["label"], "indeterminate")
        self.assertFalse(out["universe"]["counts_toward_case_library"])


class TradeStateTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def _confirmed_day(self, pct: float, vol_mult: float = 2.0, index: int = 295):
        """Rebuild bars[index-1] at the prior 20-session mean and bars[index] as a +pct day with vol_mult volume."""
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

    def test_signal_eligible_but_tradability_unverified(self):
        rows, d = self._confirmed_day(0.02)
        out = m.generate_labels(request_for(SYN_A, rows, d, security=m.SecurityContext(st_status="not_st")))
        self.assertEqual(out["labels"]["selection"]["label"], "candidate")
        self.assertEqual(out["labels"]["entry"]["label"], "signal_eligible", out["labels"]["entry"])
        self.assertEqual(out["labels"]["entry"]["tradability"], "unverified")
        self.assertEqual(out["labels"]["entry"]["execution"]["legal_next_session"], "unknown")
        self.assertFalse(out["semantics"]["trade_recommendation"])

    def test_limit_unknown_is_conservative(self):
        rows, d = self._confirmed_day(0.05)
        unknown_st = m.generate_labels(request_for(SYN_A, rows, d))
        lim = unknown_st["labels"]["limit"]
        self.assertEqual(lim["board"], "main")
        self.assertEqual(lim["threshold_pct"], 4.8)
        self.assertEqual(lim["confidence"], "board_inferred_st_unknown_lowest_threshold")
        self.assertTrue(lim["limit_like_possible"])
        self.assertNotEqual(unknown_st["labels"]["entry"]["label"], "signal_eligible")
        declared = m.generate_labels(request_for(SYN_A, rows, d, security=m.SecurityContext(st_status="not_st")))
        self.assertEqual(declared["labels"]["limit"]["threshold_pct"], 9.8)
        self.assertFalse(declared["labels"]["limit"]["limit_like_possible"])
        # entry rule in isolation: a possible limit-like day blocks the signal even for a confirmed candidate
        features = {"close": 10.5, "ma20": 10.0, "volume_ratio_20": 2.0, "zero_volume_session": False, "pct_change": 0.05}
        blocked = m.label_entry({"label": "candidate"}, features, m.limit_assessment("SYN000001", m.SecurityContext(), 0.05))
        self.assertEqual(blocked["label"], "signal_not_eligible")
        self.assertEqual(blocked["reasons"], ["limit_like_possible"])
        allowed = m.label_entry({"label": "candidate"}, features, m.limit_assessment("SYN000001", m.SecurityContext(st_status="not_st"), 0.05))
        self.assertEqual(allowed["label"], "signal_eligible")
        unknown_move = m.label_entry({"label": "candidate"}, features, m.limit_assessment("SYN000001", m.SecurityContext(), None))
        self.assertIn("limit_state_unknown", unknown_move["reasons"])
        down = m.label_entry({"label": "candidate"}, dict(features, pct_change=-0.05), m.limit_assessment("SYN000001", m.SecurityContext(), -0.05))
        self.assertIn("limit_down_possible", down["reasons"])
        self.assertEqual(m.limit_assessment("BJ920006", m.SecurityContext(), 0.10)["threshold_pct"], 29.0)
        self.assertEqual(m.limit_assessment("SZ301251", m.SecurityContext(), 0.10)["threshold_pct"], 19.5)
        self.assertEqual(m.limit_assessment("SH688549", m.SecurityContext(), 0.10)["threshold_pct"], 19.5)
        down = m.limit_assessment("SH600000", m.SecurityContext(), -0.05)
        self.assertTrue(down["limit_down_possible"])
        self.assertIsNone(m.limit_assessment("SH600000", m.SecurityContext(), None)["limit_like_possible"])

    def test_volume_ratio_below_min_blocks_entry(self):
        rows, d = self._confirmed_day(0.02, vol_mult=1.0)
        out = m.generate_labels(request_for(SYN_A, rows, d, security=m.SecurityContext(st_status="not_st")))
        self.assertEqual(out["labels"]["entry"]["label"], "signal_not_eligible")
        self.assertIn("volume_ratio_below_min", out["labels"]["entry"]["reasons"])

    def test_position_events(self):
        entry_date = self.dates[295]
        ref_price = float(self.rows[296].open)
        pos = m.PositionState(SYN_A, m.POLICY_HASH, entry_date, self.dates[296], ref_price)
        hold = m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=pos))
        self.assertEqual(hold["labels"]["position_event"]["label"], "hold")
        self.assertEqual(hold["labels"]["position_event"]["holding_sessions"], 2)
        exit_out = m.generate_labels(request_for(SYN_A, self.rows, self.dates[312], position_state=pos))
        self.assertEqual(exit_out["labels"]["position_event"]["label"], "exit_event")
        self.assertIn("close_ge_reference_plus_0.08", exit_out["labels"]["position_event"]["reasons"])
        # stop: reference set at the markup top, evaluated after the failure
        top_pos = m.PositionState(SYN_A, m.POLICY_HASH, self.dates[318], self.dates[319], float(self.rows[319].open))
        stop = m.generate_labels(request_for(SYN_A, self.rows, self.dates[330], position_state=top_pos))
        self.assertIn(stop["labels"]["position_event"]["label"], ("stop_event", "invalidation_event"))
        # invalidation precedes stop when the phase is failed_markup/distribution
        series = m.label_series(request_for(SYN_A, self.rows, self.dates[-1]), self.dates[320:340])
        failed_dates = [o["cutoff"]["decision_date"] for o in series if o["labels"]["phase"]["label"] == "failed_markup"]
        self.assertTrue(failed_dates)
        inv = m.generate_labels(request_for(SYN_A, self.rows, failed_dates[0], position_state=top_pos))
        self.assertEqual(inv["labels"]["position_event"]["label"], "invalidation_event")
        # max holding exit
        long_pos = m.PositionState(SYN_A, m.POLICY_HASH, self.dates[255], self.dates[256], float(self.rows[256].open))
        held = m.generate_labels(request_for(SYN_A, self.rows, self.dates[290], position_state=long_pos))
        self.assertIn(held["labels"]["position_event"]["label"], ("exit_event", "stop_event"))

    def test_position_binding_rejections(self):
        pos = m.PositionState(SYN_B, m.POLICY_HASH, self.dates[295], self.dates[296], 10.0)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=pos))
        self.assertEqual(ctx.exception.code, "position_state_binding_mismatch")
        pos = m.PositionState(SYN_A, "0" * 64, self.dates[295], self.dates[296], 10.0)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=pos))
        self.assertEqual(ctx.exception.code, "position_state_binding_mismatch")
        pos = m.PositionState(SYN_A, m.POLICY_HASH, self.dates[298], self.dates[299], 10.0)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=pos))
        self.assertEqual(ctx.exception.code, "position_state_not_earlier")
        pos = m.PositionState(SYN_A, m.POLICY_HASH, self.dates[295], self.dates[296], float("nan"))
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[298], position_state=pos))
        self.assertEqual(ctx.exception.code, "position_state_invalid_reference_price")

    def test_prior_state_binding(self):
        earlier = m.generate_labels(request_for(SYN_A, self.rows, self.dates[290]))
        as_of = earlier["cutoff"]["as_of"]
        good = m.PriorState(SYN_A, self.dates[290], as_of, m.POLICY_HASH, earlier["labels"]["phase"]["label"])
        m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=good))
        wrong_phase = m.PriorState(SYN_A, self.dates[290], as_of, m.POLICY_HASH, "distribution")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=wrong_phase))
        self.assertEqual(ctx.exception.code, "prior_state_inconsistent")
        # the same phase name computed from different (mutated) history is inconsistent too
        altered = list(self.rows)
        altered[285] = m.Observation(**{**altered[285].record(), "close": round(float(altered[285].close) * 1.5, 4),
                                        "high": round(float(altered[285].close) * 1.6, 4), "amount": altered[285].amount * 1.55})
        altered_out = m.generate_labels(request_for(SYN_A, altered, self.dates[290]))
        if altered_out["labels"]["phase"]["label"] != earlier["labels"]["phase"]["label"]:
            with self.assertRaises(m.LabelInputError):
                m.generate_labels(request_for(SYN_A, altered, self.dates[295], prior_state=good))
        wrong_policy = m.PriorState(SYN_A, self.dates[290], as_of, "f" * 64, "accumulation")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=wrong_policy))
        self.assertEqual(ctx.exception.code, "prior_state_binding_mismatch")
        not_earlier = m.PriorState(SYN_A, self.dates[295], as_of, m.POLICY_HASH, "accumulation")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=not_earlier))
        self.assertEqual(ctx.exception.code, "prior_state_not_earlier")
        late_as_of = m.PriorState(SYN_A, self.dates[290], "2030-01-01T00:00:00+08:00", m.POLICY_HASH, "accumulation")
        with self.assertRaises(m.LabelInputError) as ctx:
            m.generate_labels(request_for(SYN_A, self.rows, self.dates[295], prior_state=late_as_of))
        self.assertEqual(ctx.exception.code, "prior_state_not_earlier")


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.dates, self.closes, self.vols = sequence_positive_then_failed()
        self.rows = bars_from(SYN_A, self.dates, self.closes, self.vols)

    def _bench(self, drift: float, n: int = 296):
        closes = [3000.0 * (1.0 + drift) ** i for i in range(n)]
        return bars_from(SYN_BENCH, self.dates[:n], closes, [10_000_000] * n)

    def test_liquidity_bands(self):
        self.assertEqual(m.label_liquidity({"amount_20_mean_cny": 1.0e7})["band"], "L1_thin")
        self.assertEqual(m.label_liquidity({"amount_20_mean_cny": 5.0e7})["band"], "L2_low")
        self.assertEqual(m.label_liquidity({"amount_20_mean_cny": 2.0e8})["band"], "L3_mid")
        self.assertEqual(m.label_liquidity({"amount_20_mean_cny": 9.0e8})["band"], "L4_deep")
        self.assertEqual(m.label_liquidity({"amount_20_mean_cny": None})["band"], "unknown")

    def test_regime_from_benchmark_and_market_wide_missingness(self):
        d = self.dates[295]
        bull = m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=self._bench(0.002)))
        self.assertEqual(bull["labels"]["regime"]["regime"], "bull")
        bear = m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=self._bench(-0.002)))
        self.assertEqual(bear["labels"]["regime"]["regime"], "bear")
        flat = m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=self._bench(0.0)))
        self.assertEqual(flat["labels"]["regime"]["regime"], "range")
        none = m.generate_labels(request_for(SYN_A, self.rows, d))
        self.assertEqual(none["labels"]["regime"]["regime"], "unknown")
        short = m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=self._bench(0.002)[-40:]))
        self.assertEqual(short["labels"]["regime"]["regime"], "unknown")
        missing_day = m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=self._bench(0.002)[:-1]))
        self.assertEqual(missing_day["labels"]["regime"]["regime"], "unknown")
        self.assertIn("benchmark_bar_missing_on_decision_bar_date", missing_day["labels"]["regime"]["reasons"])
        sparse = m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=self._bench(0.002),
                                               universe_coverage_on_decision_date=0.5))
        self.assertEqual(sparse["labels"]["regime"]["regime"], "unknown")
        self.assertTrue(any(r.startswith("market_wide_missingness") for r in sparse["labels"]["regime"]["reasons"]))
        with self.assertRaises(m.LabelInputError):
            m.generate_labels(request_for(SYN_A, self.rows, d, benchmark_observations=self._bench(0.002)))


class CaseLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dates, cls.closes, cls.vols = sequence_positive_then_failed()
        cls.rows = bars_from(SYN_A, cls.dates, cls.closes, cls.vols)
        cls.session_index = {d: i for i, d in enumerate(cls.dates)}
        cls.bench = bars_from(SYN_BENCH, cls.dates, [3000.0 * 1.002 ** i for i in range(len(cls.dates))], [10_000_000] * len(cls.dates))
        d = cls.dates[295]
        cls.positive = m.generate_labels(request_for(SYN_A, cls.rows, d, benchmark_symbol=SYN_BENCH, benchmark_observations=cls.bench))
        assert cls.positive["labels"]["selection"]["label"] == "candidate"
        # pool: distribution-shaped controls whose spike lands 0/2/4 sessions before the positive's cutoff,
        # several symbols, same liquidity band and regime; plus far-away and same-symbol decoys
        cls.pool = []
        for k in range(6):
            sym = f"SYN00001{k}"
            offset = (k % 3) * 2
            n = 296 - offset
            _, dcloses, dvols = sequence_distribution(seed=11 + k, n_rise=n - 1)
            drows = bars_from(sym, cls.dates[:n], [c * (1.0 + 0.03 * k) for c in dcloses], dvols, upper_shadow=0.04)
            out = m.generate_labels(request_for(sym, drows, cls.dates[n - 1], benchmark_symbol=SYN_BENCH, benchmark_observations=cls.bench))
            cls.pool.append(out)
        _, fcloses, fvols = sequence_distribution(seed=31, n_rise=259)
        far = bars_from("SYN000099", cls.dates[:260], fcloses, fvols, upper_shadow=0.04)
        cls.pool.append(m.generate_labels(request_for("SYN000099", far, cls.dates[259], benchmark_symbol=SYN_BENCH, benchmark_observations=cls.bench)))
        # same symbol as positive at another cutoff must be excluded
        cls.pool.append(m.generate_labels(request_for(SYN_A, cls.rows, cls.dates[330], benchmark_symbol=SYN_BENCH, benchmark_observations=cls.bench)))

    def test_matching_is_deterministic_and_outcome_free(self):
        pos_band = self.positive["labels"]["liquidity"]["band"]
        eligible = [p for p in self.pool if p["labels"]["selection"]["label"] == "non_candidate"
                    and p["labels"]["liquidity"]["band"] == pos_band and p["symbol"] != SYN_A]
        self.assertGreaterEqual(len(eligible), 3, [(p["symbol"], p["labels"]["selection"]["label"], p["labels"]["liquidity"]["band"]) for p in self.pool])
        match = m.match_controls(self.positive, self.pool, self.session_index)
        again = m.match_controls(self.positive, list(reversed(self.pool)), self.session_index)
        self.assertEqual(match, again)
        self.assertGreaterEqual(match["control_count"], 3)
        self.assertLessEqual(match["control_count"], 5)
        self.assertFalse(match["unmatched"])
        self.assertTrue(all(c["symbol"] != SYN_A for c in match["controls"]))
        self.assertTrue(all(c["role"] == "matched_non_candidate" for c in match["controls"]))
        self.assertGreaterEqual(match["rejected_pool_counts"].get("same_symbol", 0), 1)
        self.assertGreaterEqual(match["rejected_pool_counts"].get("outside_period_tolerance", 0), 1)
        self.assertTrue(all(c["symbol"] != "SYN000099" for c in match["controls"]))
        # nearest cutoffs first, ties by symbol
        distances = [abs(self.session_index[c["decision_date"]] - self.session_index[d]) for c in match["controls"] for d in [self.positive["cutoff"]["decision_date"]]]
        self.assertEqual(distances, sorted(distances))
        self.assertFalse(match["counts_toward_case_library"])
        leaked = dict(m.case_summary(self.pool[0]), outcome_return_20=0.5)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.positive, [leaked], self.session_index)
        self.assertEqual(ctx.exception.code, "outcome_leakage")
        with self.assertRaises(m.LabelInputError):
            m.match_controls(dict(m.case_summary(self.positive), future_max=1.0), self.pool, self.session_index)
        with self.assertRaises(m.LabelInputError) as ctx:
            m.match_controls(self.pool[0], self.pool, self.session_index)
        self.assertEqual(ctx.exception.code, "positive_not_candidate")

    def test_unmatched_and_reuse_counts(self):
        thin = m.match_controls(self.positive, self.pool[:1], self.session_index)
        self.assertTrue(thin["unmatched"])
        full = m.match_controls(self.positive, self.pool, self.session_index)
        reuse = m.control_reuse_counts([thin, full, full])
        self.assertEqual(reuse["positives"], 3)
        self.assertEqual(reuse["unmatched_positives"], 1)
        self.assertGreaterEqual(reuse["max_reuse"], 2)

    def test_stable_episode_ids(self):
        out = self.positive
        expected = m.sha256_text(m.canonical_json({"namespace": m.NAMESPACE, "policy_hash": m.POLICY_HASH, "symbol": SYN_A,
                                                    "decision_date": out["cutoff"]["decision_date"],
                                                    "input_fingerprint": out["provenance"]["input_fingerprint"]}))[:32]
        self.assertEqual(out["episode_id"], expected)
        self.assertNotEqual(out["episode_id"], m.episode_id(SYN_B, out["cutoff"]["decision_date"], out["provenance"]["input_fingerprint"]))
        self.assertNotEqual(out["episode_id"], m.episode_id(SYN_A, self.dates[294], out["provenance"]["input_fingerprint"]))
        self.assertNotEqual(out["episode_id"], m.episode_id(SYN_A, out["cutoff"]["decision_date"], "0" * 64))
        # a one-cent change in a consumed bar changes the fingerprint and the id
        altered = list(self.rows)
        altered[100] = m.Observation(**{**altered[100].record(), "close": round(float(altered[100].close) + 0.01, 4)})
        other = m.generate_labels(request_for(SYN_A, altered, out["cutoff"]["decision_date"]))
        self.assertNotEqual(other["episode_id"], out["episode_id"])

    def test_no_fabricated_reviews_and_disagreement_preserved(self):
        out = self.positive
        self.assertEqual(out["review"], {"status": "pending_review", "reviews": [], "reviewer_ids": [], "reviewed_at": None, "approved": False})
        self.assertNotIn("reviewer", json.dumps(out["labels"]))
        r1 = m.ReviewRecord("codex", "agent", "2026-09-11T02:00:00+00:00", "positive", ("evidence:a",))
        r2 = m.ReviewRecord("claude", "agent", "2026-09-11T03:00:00+00:00", "ambiguous", ("evidence:b",), "range too short")
        one = m.attach_review(out, r1)
        self.assertEqual(out["review"]["reviews"], [])  # input not mutated
        self.assertEqual(one["review"]["status"], "single_review_not_independent")
        self.assertFalse(one["counts_toward_case_library"])
        same_agent_twice = m.attach_review(one, m.ReviewRecord("codex", "agent", "2026-09-11T04:00:00+00:00", "positive", ()))
        self.assertEqual(same_agent_twice["review"]["status"], "single_review_not_independent")
        two = m.attach_review(one, r2)
        self.assertEqual(two["review"]["status"], "disputed")
        self.assertEqual(two["review"]["agreement"], "disagree")
        self.assertIsNone(two["review"]["consensus_verdict"])
        self.assertEqual([r["verdict"] for r in two["review"]["reviews"]], ["positive", "ambiguous"])
        self.assertFalse(two["review"]["approved"])
        agree = m.attach_review(one, m.ReviewRecord("claude", "agent", "2026-09-11T03:00:00+00:00", "positive", ()))
        self.assertEqual(agree["review"]["status"], "independently_reviewed")
        self.assertFalse(agree["counts_toward_case_library"])  # synthetic never counts
        with self.assertRaises(m.LabelInputError):
            m.attach_review(out, m.ReviewRecord("x", "rule_engine", "2026-09-11T03:00:00+00:00", "positive", ()))
        with self.assertRaises(m.LabelInputError):
            m.attach_review(out, m.ReviewRecord("x", "agent", "2026-09-11T03:00:00", "positive", ()))
        with self.assertRaises(m.LabelInputError):
            m.attach_review(out, m.ReviewRecord("", "agent", "2026-09-11T03:00:00+00:00", "positive", ()))

    def test_synthetic_excluded_from_effective_counts(self):
        series = m.label_series(request_for(SYN_A, self.rows, self.dates[-1]), self.dates[249:])
        episodes = m.build_episodes(series)
        counts = m.effective_decision_dates(episodes, session_index=self.session_index)
        self.assertEqual(counts["effective_decision_dates"], 0)
        self.assertGreaterEqual(counts["synthetic_excluded"], 1)
        self.assertEqual(counts["reviewed_positives"], 0)
        self.assertEqual(counts["target_min_reviewed_positives"], 50)
        arithmetic = m.effective_decision_dates(episodes, session_index=self.session_index, include_synthetic=True)
        self.assertEqual(arithmetic["effective_decision_dates"], 0)
        self.assertGreaterEqual(arithmetic["effective_decision_dates_arithmetic"], 1)
        self.assertTrue(arithmetic["synthetic_included_for_arithmetic_only"])

    def test_outcome_annotation_is_separate(self):
        later = m.Cutoff(self.dates[330], (m.close_time(self.dates[330]) + timedelta(hours=4)).isoformat(), m.MODE_STRICT)
        ann = m.annotate_outcome(self.positive, self.rows, later, horizon_sessions=20)
        self.assertEqual(ann["annotation_kind"], "later_known_outcome")
        self.assertTrue(ann["not_a_label"])
        self.assertFalse(ann["realized_return_claim"])
        self.assertTrue(ann["adjustment_uncertainty"])
        self.assertEqual(ann["reference"]["date"], self.dates[296])
        self.assertEqual(ann["sessions_observed"], 20)
        self.assertNotIn("close_return_unadjusted", self.positive)
        self.assertNotIn("close_return_unadjusted", json.dumps(self.positive["labels"]))
        with self.assertRaises(m.LabelInputError):
            m.annotate_outcome(self.positive, self.rows, m.Cutoff(self.dates[295], (m.close_time(self.dates[295]) + timedelta(hours=4)).isoformat()))
        pending = m.annotate_outcome(self.positive, self.rows[:296], later)
        self.assertEqual(pending["status"], "pending_future_data")


class ProtectionTests(unittest.TestCase):
    def test_split_roles_and_holdout_guard(self):
        self.assertEqual(m.split_role("2023-09-04"), "development")
        self.assertEqual(m.split_role("2025-03-31"), "development")
        self.assertEqual(m.split_role("2025-04-01"), "validation")
        self.assertEqual(m.split_role("2025-12-31"), "validation")
        self.assertEqual(m.split_role("2026-01-01"), "final_holdout")
        self.assertEqual(m.split_role("2026-09-04"), "final_holdout")
        self.assertEqual(m.split_role("2023-09-01"), "outside_research_interval")
        self.assertEqual(m.POLICY["split_proposal"]["status"], "proposal_requires_codex_review")
        records = [{"decision_date": "2024-05-06"}, {"decision_date": "2026-02-02"}]
        for purpose in ("threshold_selection", "rule_selection", "target_count", "parameter_search"):
            with self.assertRaises(m.LabelInputError) as ctx:
                m.guard_final_holdout(records, purpose)
            self.assertEqual(ctx.exception.code, "final_holdout_consumed")
        ok = m.guard_final_holdout(records[:1], "threshold_selection")
        self.assertEqual(ok["roles"], {"development": 1})
        report = m.guard_final_holdout(records, "final_report")
        self.assertEqual(report["roles"], {"development": 1, "final_holdout": 1})

    def test_seed_context_and_frozen_universe(self):
        seeds = m.seed_context()
        self.assertEqual({s["symbol"] for s in seeds}, {"SZ002115", "SZ002081"})
        for s in seeds:
            self.assertEqual(s["status"], "legacy_unverified")
            self.assertFalse(s["in_frozen_universe"])
            self.assertEqual(s["case_count_contribution"], 0)
            self.assertFalse(s["case_data_fabricated"])
            self.assertFalse(s["reviewed"])
        universe = frozenset({"SH600011", "BJ920006", "SZ002656"})
        with self.assertRaises(m.LabelInputError) as ctx:
            m.assert_in_universe("SZ002115", universe)
        self.assertEqual(ctx.exception.code, "outside_frozen_universe")
        m.assert_in_universe("SH600011", universe)
        dates, closes, vols = sequence_positive_then_failed()
        rows = bars_from("SH600011", dates, closes, vols, avail_fixed="2026-09-10T04:17:10+00:00")
        out = m.generate_labels(m.LabelRequest(symbol="SH600011", observations=rows, synthetic=False, frozen_universe=universe,
                                               cutoff=m.Cutoff(dates[295], "2026-09-10T05:00:00+00:00", m.MODE_RETROSPECTIVE)))
        self.assertTrue(out["universe"]["in_frozen_universe"])
        self.assertFalse(out["universe"]["counts_toward_case_library"])
        outside = m.generate_labels(m.LabelRequest(symbol="SZ002115", observations=bars_from("SZ002115", dates, closes, vols, avail_fixed="2026-09-10T04:17:10+00:00"),
                                                   synthetic=False, frozen_universe=universe,
                                                   cutoff=m.Cutoff(dates[295], "2026-09-10T05:00:00+00:00", m.MODE_RETROSPECTIVE)))
        self.assertFalse(outside["universe"]["in_frozen_universe"])
        self.assertEqual(outside["universe"]["reason"], "outside_frozen_universe_separate_decision")
        self.assertEqual(m.POLICY["frozen_universe"]["sha256"], "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe")

    def test_output_carries_required_provenance(self):
        dates, closes, vols = sequence_positive_then_failed()
        rows = bars_from(SYN_A, dates, closes, vols)
        out = m.generate_labels(request_for(SYN_A, rows, dates[295]))
        for key in ("policy_version", "policy_hash", "producer_sha256", "cutoff", "input_availability", "provenance", "data_quality", "review"):
            self.assertIn(key, out)
        self.assertEqual(out["policy_hash"], m.POLICY_HASH)
        self.assertEqual(out["producer_sha256"], m.producer_sha256())
        self.assertEqual(out["input_availability"]["max_trade_date_consumed"], dates[295])
        self.assertTrue(out["provenance"]["source_refs"])
        self.assertTrue(all(ref.startswith("syn:") for ref in out["provenance"]["source_refs"]))
        self.assertTrue(out["synthetic"])
        json.dumps(out, allow_nan=False)  # serialisable, no NaN


if __name__ == "__main__":
    unittest.main(verbosity=2)
