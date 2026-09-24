"""M2a R3 - machine-checkable acceptance over the accepted M1 gate.

The M1 gate is imported and used unchanged; nothing in `_m1_closure/` is modified. What
this module adds is a decision procedure that a person cannot fudge:

* Every gate line is parsed, not just the exit code. `exit 1` on its own is NOT an
  acceptable Run B result - the rule is about WHICH gate failed.
* The parse is cross-checked against the gate's own verdict line. If the two disagree,
  acceptance is UNKNOWN, never PASS.
* The per-security warm-up shortfall is recomputed here from the unchanged manifest and
  pinned calendar. The gate's own detail line prints only a three-row sample, which is a
  summary, not evidence; the full set is derived independently and compared against the
  pinned expectation including each security's eligible count.

Research acceptance : every required gate PASS/NOT_APPLICABLE.
Warm-up acceptance  : integrity gates (W1_pricing, W1_history, W2) PASS, and no other
                      required FAIL/UNKNOWN except the explicitly expected V3b depth
                      shortfall, whose membership must match the pinned set exactly.

Warm-up acceptance is a statement about COLLECTED DATA INTEGRITY. It is not feature
readiness and is never reported as such.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
M1 = HERE.parent / "_m1_closure"
sys.path.insert(0, str(M1))

from coverage_gap_generator import sessions_between  # noqa: E402
from staging_gate import entry_eligibility, load_manifest  # noqa: E402

RESEARCH_START, RESEARCH_END = "2023-09-04", "2026-09-04"
WARMUP_DEPTH = 250

STATUSES = ("PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE")
SUCCESSFUL = frozenset({"PASS", "NOT_APPLICABLE"})
INTEGRITY_GATES = ("W1_pricing", "W1_history", "W2")
DEPTH_GATE = "V3b"

#: The gate inventory is OWNED HERE, not supplied by the caller. The previous version
#: took an optional `expected_ids=()`, so a run reporting only `P4=PASS` - every other
#: mandatory gate simply absent - was accepted. An acceptance boundary that depends on
#: the caller remembering to pass a list is not a boundary.
RESEARCH_REQUIRED = (
    "C0",                                    # pinned calendar matches the baseline
    "A_trading", "A_history",                # both archives unchanged
    "P1", "P2", "P3", "P4", "P5", "P6",      # pricing view, incl. units (P4) and basis (P6)
    "M1", "M2", "M3",                        # per-key membership, both views
    "H1", "H2", "H3", "H4", "H5",            # history view, incl. basis (H5)
    "X1", "X2",                              # declared transformation + reconciliation
    "B0",                                    # frozen baseline unmodified
)
WARMUP_REQUIRED = RESEARCH_REQUIRED + ("V3a",) + INTEGRITY_GATES + (DEPTH_GATE,)

#: The approved population, so a reduced manifest cannot be accepted merely because it
#: still contains the same 14 short securities.
EXPECTED_STOCKS = 50
EXPECTED_BENCHMARKS = 2

GATE_LINE = re.compile(
    r"^ {2}(?P<id>\S+)\s+(?P<desc>.+?)\s+(?P<status>%s)\s*(?P<flag>\(advisory\))?\s*$"
    % "|".join(STATUSES))
VERDICT_OK = re.compile(r"^\s*RESULT: SUCCEEDED")
VERDICT_BAD = re.compile(r"^\s*RESULT: FAILED - \d+ required gate\(s\) not satisfied: (.+)$")

#: Pinned in the authorization request BEFORE any collection, so it cannot be widened
#: afterwards to absorb a real failure. symbol -> eligible warm-up sessions.
PINNED_SHORTFALL = {
    "BJ920002": 0, "BJ920003": 0, "BJ920005": 0, "BJ920007": 0, "BJ920519": 0,
    "BJ920627": 0, "SH603075": 0, "SH688549": 0, "SH688702": 0, "SZ301251": 0,
    "SZ301507": 0, "SZ301529": 0,
    "BJ920001": 167, "BJ920006": 75,
}


class AcceptanceError(Exception):
    """The gate output could not be interpreted; fail closed."""


@dataclass
class GateResult:
    id: str
    description: str
    status: str
    required: bool


@dataclass
class Verdict:
    accepted: bool
    reason: str
    gates: list = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def failing_required(self):
        return [g for g in self.gates if g.required and g.status not in SUCCESSFUL]


def parse_gate_output(text, exit_code, expected_ids=()):
    """Strictly parse per-gate results and cross-check them against the verdict line.

    `expected_ids` is a MINIMUM, applied on top of the internal inventory that the
    public entry points enforce; it can add requirements, never remove them.
    """
    gates, verdicts = [], []
    for line in text.splitlines():
        match = GATE_LINE.match(line)
        if match:
            gates.append(GateResult(id=match.group("id"),
                                    description=match.group("desc").strip(),
                                    status=match.group("status"),
                                    required=match.group("flag") is None))
            continue
        if VERDICT_OK.match(line):
            verdicts.append([])
        else:
            bad = VERDICT_BAD.match(line)
            if bad:
                verdicts.append([i.strip() for i in bad.group(1).split(",") if i.strip()])

    if not gates:
        raise AcceptanceError("no gate lines parsed; refusing to interpret the run")
    if not verdicts:
        raise AcceptanceError("no RESULT verdict line found; refusing to interpret the run")
    if len(verdicts) > 1:
        # Taking the LAST verdict let a "FAILED ... P4" line be overridden by a later
        # "SUCCEEDED". More than one verdict means the report is not one run.
        raise AcceptanceError(
            "%d RESULT verdict lines found (%s); a report carrying conflicting verdicts "
            "is not a single interpretable run"
            % (len(verdicts), ["FAILED:%s" % v if v else "SUCCEEDED" for v in verdicts]))
    verdict_ids = verdicts[0]

    seen = {}
    for gate in gates:
        if gate.id in seen:
            raise AcceptanceError(
                "gate %s appears more than once (%s then %s); refusing an ambiguous run"
                % (gate.id, seen[gate.id].status, gate.status))
        seen[gate.id] = gate
    missing = [i for i in expected_ids if i not in seen]
    if missing:
        raise AcceptanceError("expected gates absent from the output: %s" % missing)

    derived = sorted(g.id for g in gates if g.required and g.status not in SUCCESSFUL)
    if derived != sorted(verdict_ids):
        raise AcceptanceError(
            "parse disagrees with the gate's own verdict (parsed failing=%s, "
            "verdict=%s); refusing to accept on an ambiguous reading"
            % (derived, sorted(verdict_ids)))
    expected_exit = 1 if derived else 0
    if exit_code != expected_exit:
        raise AcceptanceError("exit code %d contradicts the parsed gate set %s"
                              % (exit_code, derived))
    return gates


# ------------------------------------------------------- independent shortfall check

def warmup_interval(sessions=None):
    sessions = sessions or sessions_between("1990-12-19", "2026-12-31")
    before = [s for s in sessions if s < RESEARCH_START]
    return before[-WARMUP_DEPTH:]


def compute_full_shortfall(manifest_path, staging_trading, depth=WARMUP_DEPTH):
    """The COMPLETE per-security shortfall, recomputed from manifest + calendar + data.

    Independent of the gate's own three-row sample.
    """
    warm = warmup_interval()
    stocks, _ = load_manifest(Path(manifest_path))
    conn = sqlite3.connect("file:%s?mode=ro" % staging_trading, uri=True)
    conn.execute("PRAGMA query_only=1")
    shortfall, ready = {}, []
    for entry in stocks:
        eligible, _ = entry_eligibility(entry, warm)
        if eligible:
            seen = {r[0] for r in conn.execute(
                "SELECT DISTINCT trade_date FROM daily_bar_cache WHERE symbol = ? "
                "AND trade_date BETWEEN ? AND ?",
                (entry["symbol"], warm[0], warm[-1]))}
            observed = len(set(eligible) & seen)
        else:
            observed = 0
        (ready.append(entry["symbol"]) if observed >= depth
         else shortfall.__setitem__(entry["symbol"], observed))
    conn.close()
    return shortfall, ready


def check_pinned_shortfall(shortfall, pinned=None):
    """The shortfall must be exactly the pinned set, security by security."""
    pinned = PINNED_SHORTFALL if pinned is None else pinned
    unexpected = sorted(set(shortfall) - set(pinned))
    absent = sorted(set(pinned) - set(shortfall))
    mismatched = sorted(
        (s, shortfall[s], pinned[s]) for s in set(shortfall) & set(pinned)
        if shortfall[s] != pinned[s])
    ok = not (unexpected or absent or mismatched)
    return ok, {"unexpected_shortfall": unexpected, "expected_but_absent": absent,
                "count_mismatch": mismatched, "observed_count": len(shortfall),
                "pinned_count": len(pinned)}


# ------------------------------------------------------------- inventory + binding

def enforce_inventory(gates, inventory):
    """Every gate in the inventory must be present AND required. Fail closed."""
    by_id = {g.id: g for g in gates}
    missing = [gid for gid in inventory if gid not in by_id]
    if missing:
        raise AcceptanceError(
            "mandatory gates absent from the run: %s. An acceptance decision cannot be "
            "made from a partial gate set." % missing)
    weakened = [gid for gid in inventory if not by_id[gid].required]
    if weakened:
        raise AcceptanceError(
            "mandatory gates ran as advisory: %s. Requiredness is owned by this "
            "acceptance boundary, not by the caller's flags." % weakened)
    return by_id


def bind_inputs(manifest_path, expected_manifest_sha, calendar_path,
                expected_calendar_sha, candidate_fingerprint):
    """Acceptance is about ONE run's inputs and ONE candidate. All bindings mandatory.

    Every argument here was previously optional, so the public default accepted any
    manifest with the right shape - swapping SH688001 for SH600998 kept 50+2 and passed.
    Comparison is now full-hash equality, not a prefix.
    """
    for name, value in (("expected_manifest_sha", expected_manifest_sha),
                        ("calendar_path", calendar_path),
                        ("expected_calendar_sha", expected_calendar_sha),
                        ("candidate_fingerprint", candidate_fingerprint)):
        if not value:
            raise AcceptanceError(
                "%s is mandatory: acceptance must be bound to the frozen inputs and the "
                "exact candidate views" % name)

    detail = {"candidate_fingerprint": candidate_fingerprint}
    actual = hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()
    detail["manifest_sha256"] = actual
    if actual != expected_manifest_sha:
        raise AcceptanceError("manifest %s does not match the pinned %s"
                              % (actual, expected_manifest_sha))
    cal = hashlib.sha256(Path(calendar_path).read_bytes()).hexdigest()
    detail["calendar_sha256"] = cal
    if cal != expected_calendar_sha:
        raise AcceptanceError("calendar %s does not match the pinned %s"
                              % (cal, expected_calendar_sha))

    stocks, marks = load_manifest(Path(manifest_path))
    detail["stocks"] = len(stocks)
    detail["benchmarks"] = len(marks)
    if (len(stocks), len(marks)) != (EXPECTED_STOCKS, EXPECTED_BENCHMARKS):
        raise AcceptanceError(
            "manifest declares %d stocks + %d benchmarks, not the approved %d + %d. A "
            "reduced population is not acceptable even if it still contains the pinned "
            "short securities." % (len(stocks), len(marks), EXPECTED_STOCKS,
                                   EXPECTED_BENCHMARKS))
    return detail


# --------------------------------------------------------------------- the decisions

def accept_research(text, exit_code, *, manifest_path, expected_manifest_sha,
                    calendar_path, expected_calendar_sha, candidate_fingerprint,
                    expected_ids=()):
    """The public research boundary. There is no bypass switch.

    `enforce=False` previously let a report containing only `P4=PASS` be accepted; the
    report claimed callers could not remove the internal inventory while the public flag
    did exactly that. Low-level fixtures now use the private helpers instead.
    """
    gates = parse_gate_output(text, exit_code, expected_ids)
    enforce_inventory(gates, RESEARCH_REQUIRED)
    details = bind_inputs(manifest_path, expected_manifest_sha, calendar_path,
                          expected_calendar_sha, candidate_fingerprint)
    failing = [g for g in gates if g.required and g.status not in SUCCESSFUL]
    if failing:
        return Verdict(False, "research acceptance requires every required gate to "
                              "succeed; failing: %s"
                       % ", ".join("%s=%s" % (g.id, g.status) for g in failing),
                       gates, details)
    return Verdict(True, "all %d required gates PASS/NOT_APPLICABLE" %
                   sum(1 for g in gates if g.required), gates, details)


def accept_warmup_collection(text, exit_code, manifest_path, staging_trading, *,
                             expected_manifest_sha, calendar_path,
                             expected_calendar_sha, candidate_fingerprint,
                             expected_ids=(), pinned=None):
    """Integrity must PASS; only the pinned depth shortfall may fail. No bypass switch."""
    gates = parse_gate_output(text, exit_code, expected_ids)
    enforce_inventory(gates, WARMUP_REQUIRED)
    bound = bind_inputs(manifest_path, expected_manifest_sha, calendar_path,
                        expected_calendar_sha, candidate_fingerprint)
    return _warmup_decision(gates, manifest_path, staging_trading, pinned, bound)


def _warmup_decision(gates, manifest_path, staging_trading, pinned, bound):
    """The decision body. PRIVATE: reduced fixtures exercise this, never the public
    boundary, so a test's convenience can never widen what production accepts."""
    by_id = {g.id: g for g in gates}

    depth = by_id.get(DEPTH_GATE)
    if depth is None:
        return Verdict(False, "%s is absent; the expected depth shortfall cannot be "
                              "confirmed" % DEPTH_GATE, gates, bound)
    if not depth.required:
        return Verdict(False, "%s ran as advisory; the depth result must be a required "
                              "gate" % DEPTH_GATE, gates, bound)
    if depth.status != "FAIL":
        return Verdict(False,
                       "%s is %s. The pinned plan expects exactly FAIL: UNKNOWN is "
                       "missing evidence, not a known IPO depth limitation, and "
                       "PASS contradicts the pinned shortfall."
                       % (DEPTH_GATE, depth.status), gates, bound)

    for gate_id in INTEGRITY_GATES:
        gate = by_id.get(gate_id)
        if gate is None:
            return Verdict(False, "integrity gate %s absent from the run" % gate_id, gates)
        if gate.status != "PASS":
            return Verdict(False, "integrity gate %s is %s; warm-up data is not accepted"
                           % (gate_id, gate.status), gates)
        if not gate.required:
            return Verdict(False,
                           "integrity gate %s ran as advisory; warm-up integrity must be "
                           "blocking (use --warmup-required)" % gate_id, gates)

    failing = [g for g in gates if g.required and g.status not in SUCCESSFUL]
    others = [g for g in failing if g.id != DEPTH_GATE]
    if others:
        return Verdict(False, "required gate(s) other than the expected depth shortfall "
                              "failed: %s"
                       % ", ".join("%s=%s" % (g.id, g.status) for g in others), gates)

    shortfall, ready = compute_full_shortfall(manifest_path, staging_trading)
    ok, detail = check_pinned_shortfall(shortfall, pinned)
    detail.update({"ready_count": len(ready), "shortfall": shortfall})
    detail.update(bound)
    if not ok:
        return Verdict(False, "the warm-up shortfall does not match the pinned set "
                              "exactly: %s" % detail, gates, detail)

    depth_gate = by_id.get(DEPTH_GATE)
    if depth_gate is not None and depth_gate.status in SUCCESSFUL and shortfall:
        return Verdict(False, "%s reports success while %d securities are short; "
                              "refusing an inconsistent reading"
                       % (DEPTH_GATE, len(shortfall)), gates, detail)

    return Verdict(True,
                   "warm-up COLLECTION accepted: integrity gates PASS and the only "
                   "required failure is the pinned %d-security depth shortfall. This is "
                   "data integrity, NOT feature readiness." % len(shortfall),
                   gates, detail)
