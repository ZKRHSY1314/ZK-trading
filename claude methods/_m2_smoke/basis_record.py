"""P1 basis records - the offline, evidence-side derivation and eligibility evaluator.

Implements the reviewed specification in Appendix A of
`claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md` (revision 6), under the user's adoption
of U-1 - U-5 and U-7. **U-6 remains deferred**, so this module has **no `eligible=true`
path at all**.

What it does
------------
Reads ONE selected offline revision directory, verifies it (A.5.2), derives one record per
job (A.3/A.4), evaluates basis-dependent eligibility (A.6) and writes the result to a NEW
`basis_eval_<revision>/` directory (A.5.3).

What it never does
------------------
No HTTP, no plugin call, no SQLite open, no adapter replay, no service action, no gate
wiring, no production write, no capture. It reads JSON and hashes bytes. It writes only a
fresh directory directly under ONE approved canonical root, and refuses - with
case-insensitive, Windows-safe path comparisons - to write under `evidence_*`,
`revision_*`, `receipts_*`, `frozen_impl_*` or any reviewer- or producer-owned directory.
A scratch root is an explicit, bounded test allowance confined to the OS temp directory.

Two version namespaces (A.5.1)
------------------------------
`upstream_producer_pins` describes the code that produced the consumed `checks.json`;
`record_producer` describes THIS module, its record schema and its rule-set versions. A
change to this module's rules is therefore visible even when every upstream pin is
identical, and records whose rule versions differ are not comparable.

Stated detection limits - none of these is claimed to be solved
---------------------------------------------------------------
1. A fully self-consistent forgery - every consumed file altered together with every
   recorded hash - is not detectable by these steps.
2. **Revision binding does NOT detect every same-digest file substitution.** It compares
   `PROVENANCE.revision` with the selected directory's name. Two revisions of one capture
   can carry the same deterministic block and digest - `revision_20260908T021722Z_d1d2`
   and `..._d2_literal` both record `784ffa66...` - so a substituted file whose content
   hashes identically under the legitimate provenance is not distinguished.
3. A recorded attempt proves only that an attempt was initiated and recorded: not that the
   endpoint was reachable, and not that any HTTP response arrived. Receipt is evidenced
   only by a non-null `status`.

CLI
---
    python -B -X utf8 basis_record.py <revision_directory> [--suffix LABEL]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import smoke_capture as cap                                        # noqa: E402

# ------------------------------------------------------------------ module identity
RECORD_SCHEMA_VERSION = "m2b.basis_record.v1"
DERIVATION_RULES_VERSION = "p1.derivation.rev6"
EVALUATOR_RULES_VERSION = "p1.evaluator.rev6"
KNOWN_DERIVATION_RULES = frozenset({DERIVATION_RULES_VERSION})
KNOWN_EVALUATOR_RULES = frozenset({EVALUATOR_RULES_VERSION})

#: The five upstream producers, whose pins describe the code that made `checks.json`.
UPSTREAM_PRODUCERS = ("smoke_capture.py", "smoke_checks.py", "smoke_outcomes.py",
                      "sina_klc_decoder.py", "test_m2_smoke.py")

#: Directories this module must never write into. Compared case-insensitively, because
#: NTFS is case-insensitive and `EVIDENCE_...` is the same directory as `evidence_...`.
PROTECTED_PREFIXES = ("evidence_", "revision_", "receipts_", "frozen_impl_")
#: Reviewer-owned directories are never a write target either.
PROTECTED_NAMES = ("_m2_codex_review", "_m1_closure", "_m2_pilot")
OUTPUT_PREFIX = "basis_eval_"
#: BR-R2: the ONE approved canonical output root. A scratch root is allowed only under an
#: explicit, bounded opt-in and only inside the operating system's temporary directory.
CANONICAL_OUTPUT_ROOT = HERE
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

#: A.5.2a - the supported revision schemas and where each keeps its result anchor.
SUPPORTED_SCHEMAS = {
    "m2b.offline_revision.v1": {
        "anchor": ("revised_deterministic_sha256",),
        "parent_key": "original_evidence",
        "producer_pins_key": None,
        "has_input_hashes": False,
        "complete": False,
    },
    "m2b.offline_revision.v2": {
        "anchor": ("revised_deterministic_sha256",),
        "parent_key": "parent_evidence",
        "producer_pins_key": "producer_implementation",
        "has_input_hashes": False,
        "complete": False,
    },
    "m2b.offline_revision.v3": {
        "anchor": ("revised_offline_result", "deterministic_sha256"),
        "parent_key": "parent_evidence",
        "producer_pins_key": "producer_implementation",
        "has_input_hashes": True,
        "complete": True,
    },
}

DETECTION_LIMITS = (
    "A fully self-consistent forgery - every consumed file altered together with every "
    "recorded hash - is not detectable by these verification steps.",
    "Revision binding compares PROVENANCE.revision with the selected directory name. It "
    "does NOT detect every same-digest file substitution: two revisions of one capture "
    "can share a deterministic block and digest (revision_20260908T021722Z_d1d2 and "
    "revision_20260908T021722Z_d2_literal both record 784ffa66...), so substituted "
    "content that hashes identically under the legitimate provenance is not "
    "distinguished.",
    "A recorded attempt proves an attempt was initiated and recorded - not that the "
    "endpoint was reachable, and not that an HTTP response was received. Receipt is "
    "evidenced only by a non-null status; a 200 still says nothing about payload "
    "usability.",
)


class VerificationError(Exception):
    """A pre-write verification step failed. No trusted record may be produced."""

    def __init__(self, step, code, detail, observed=None, expected=None):
        super().__init__("step %s (%s): %s" % (step, code, detail))
        self.step = step
        self.code = code
        self.detail = detail
        self.observed = observed
        self.expected = expected

    def as_dict(self):
        return {"failed_step": self.step, "code": self.code, "detail": self.detail,
                "observed": self.observed, "expected": self.expected}


# ------------------------------------------------------------------------- helpers
def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_json(path, step, code):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VerificationError(step, code, "%s is not readable JSON: %s"
                                % (Path(path).name, exc))


def repo_relative(path):
    """A stable, repo-relative form for the hashed block; absolute paths stay in `meta`."""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return "<outside-repo>/" + Path(path).name


def normcase(path):
    return os.path.normcase(str(Path(path)))


def within(child, parent):
    """Case- and separator-insensitive containment, resolved. Windows-safe."""
    try:
        c = normcase(Path(child).resolve())
        p = normcase(Path(parent).resolve())
    except OSError:
        return False
    return c == p or c.startswith(p + os.sep)


def _unsafe_relative(relative):
    """True when a declared input path could escape the revision directory."""
    if not isinstance(relative, str) or not relative:
        return True
    if "\\" in relative or relative.startswith("/"):
        return True
    candidate = Path(relative)
    if candidate.is_absolute() or candidate.drive:
        return True
    return any(part in ("..", "") for part in candidate.parts)


def required_input_inventory(manifest):
    """BR-R1: what a COMPLETE schema must declare, derived from the manifest itself."""
    required = {"capture_manifest.json", "reference/reference_extract.json"}
    for record in (manifest or {}).get("requests", []):
        if record.get("raw_file"):
            required.add("raw/" + record["raw_file"])
    return required


def _dig(obj, path):
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


def module_identity():
    return {
        "module": "basis_record.py",
        "module_sha256": sha256_file(Path(__file__).resolve()),
        "record_schema_version": RECORD_SCHEMA_VERSION,
        "derivation_rules_version": DERIVATION_RULES_VERSION,
        "evaluator_rules_version": EVALUATOR_RULES_VERSION,
    }


def records_comparable(left, right):
    """Records from different module or rule versions are NOT comparable (A-15)."""
    keys = ("module_sha256", "record_schema_version", "derivation_rules_version",
            "evaluator_rules_version")
    a = (left or {}).get("record_producer") or {}
    b = (right or {}).get("record_producer") or {}
    return all(a.get(k) == b.get(k) for k in keys)


# =========================================================== A.5.2 - verification
def schema_descriptor(provenance):
    """A.5.2(5a). Unknown schema or a missing anchor is rejected - never a fallback."""
    schema = (provenance or {}).get("schema")
    descriptor = SUPPORTED_SCHEMAS.get(schema)
    if descriptor is None:
        raise VerificationError("5a", "unknown_schema",
                                "PROVENANCE.schema %r is not a supported revision schema; "
                                "there is no fallback to capture-run identity" % (schema,),
                                schema, sorted(SUPPORTED_SCHEMAS))
    anchor = _dig(provenance, descriptor["anchor"])
    if not isinstance(anchor, str) or not anchor:
        raise VerificationError("5a", "missing_anchor",
                                "schema %s declares its result anchor at %s, which is "
                                "absent or not a string"
                                % (schema, ".".join(descriptor["anchor"])),
                                anchor, ".".join(descriptor["anchor"]))
    return schema, descriptor, anchor


def select_revision(directory):
    """A.5.2(5c). Only a revision directory carrying a PROVENANCE.json may be selected."""
    path = Path(directory).resolve()
    if not path.is_dir():
        raise VerificationError("1", "missing_input",
                                "%s is not a directory" % path)
    if not (path / "PROVENANCE.json").exists():
        raise VerificationError("5c", "no_revision_identity",
                                "%s carries no PROVENANCE.json, so it has no revision "
                                "identity and cannot be selected. A capture directory is "
                                "not a revision, and a missing anchor is never read as "
                                "'not applicable'" % path.name)
    return path


def verify(directory):
    """Run every A.5.2 step in order. Raises `VerificationError` on the first failure.

    5(a) is evaluated as a precondition of step 4, because step 4 needs the schema's
    result anchor in order to compare against it at all.
    """
    revision = select_revision(directory)
    steps = []

    # ---- 1. presence ---------------------------------------------------------------
    required_files = ("PROVENANCE.json", "checks.json", "capture_manifest.json")
    missing = [name for name in required_files if not (revision / name).is_file()]
    if missing:
        raise VerificationError("1", "missing_input",
                                "the selected revision is missing %s" % missing)
    provenance = _load_json(revision / "PROVENANCE.json", "1", "unreadable_input")
    checks = _load_json(revision / "checks.json", "1", "unreadable_input")
    manifest = _load_json(revision / "capture_manifest.json", "1", "unreadable_input")
    steps.append({"step": "1", "name": "presence", "result": "ok",
                  "files": sorted(required_files)})

    # ---- 2. input hashes, over the REQUIRED inventory (BR-R1) ----------------------
    descriptor_early = SUPPORTED_SCHEMAS.get(provenance.get("schema"))
    complete_schema = bool(descriptor_early and descriptor_early.get("complete"))
    declared = provenance.get("input_hashes")
    required = required_input_inventory(manifest)
    verified_inputs = {}
    ledger = {}

    def record_artifact(relative, path, role, declared_hash=None, manifest_hash=None):
        entry = ledger.setdefault(relative, {"sha256": sha256_file(path), "roles": []})
        if role not in entry["roles"]:
            entry["roles"].append(role)
        if declared_hash is not None:
            entry["declared_hash_matched"] = declared_hash == entry["sha256"]
        if manifest_hash is not None:
            entry["manifest_body_sha256_matched"] = manifest_hash == entry["sha256"]
        return entry["sha256"]

    for name in required_files:
        record_artifact(name, revision / name, "revision_json")

    if complete_schema:
        if not isinstance(declared, dict) or not declared:
            raise VerificationError(
                "2", "input_hashes_absent",
                "schema %s must declare input_hashes; the field is absent or empty, and "
                "a missing field is never read as 'nothing to verify'"
                % provenance.get("schema"))
        for relative, expected in sorted(declared.items()):
            if _unsafe_relative(relative):
                raise VerificationError("2", "unsafe_input_path",
                                        "declared input path %r may escape the revision "
                                        "directory" % (relative,))
            if not isinstance(expected, str) or not _HEX64.match(expected):
                raise VerificationError("2", "input_hashes_malformed",
                                        "declared input %s does not carry a sha256 hex "
                                        "digest" % relative, expected, "64 hex chars")
        missing = sorted(required - set(declared))
        if missing:
            raise VerificationError("2", "input_hashes_incomplete",
                                    "the declared input inventory omits %s" % missing,
                                    sorted(declared), sorted(required))

    for relative, expected in sorted((declared or {}).items()):
        if _unsafe_relative(relative):
            raise VerificationError("2", "unsafe_input_path",
                                    "declared input path %r may escape the revision "
                                    "directory" % (relative,))
        target = revision / relative
        if not target.is_file():
            raise VerificationError("2", "missing_input",
                                    "declared input %s is absent" % relative)
        role = ("reference_extract" if relative.startswith("reference/")
                else "raw_body" if relative.startswith("raw/") else "declared_input")
        actual = record_artifact(relative, target, role, declared_hash=expected)
        if actual != expected:
            raise VerificationError("2", "input_hash_mismatch",
                                    "declared input %s does not hash as recorded"
                                    % relative, actual, expected)
        verified_inputs[relative] = actual

    bodies = {}
    for record in manifest.get("requests", []):
        raw_file, body_sha = record.get("raw_file"), record.get("body_sha256")
        if not raw_file or not body_sha:
            continue
        relative = "raw/" + raw_file
        target = revision / relative
        if not target.is_file():
            raise VerificationError("2", "missing_input",
                                    "the manifest references %s, which is absent"
                                    % relative)
        actual = record_artifact(relative, target, "raw_body", manifest_hash=body_sha)
        if actual != body_sha:
            raise VerificationError("2", "input_hash_mismatch",
                                    "%s does not hash as the manifest records" % relative,
                                    actual, body_sha)
        bodies[relative] = actual
    steps.append({"step": "2", "name": "input hashes", "result": "ok",
                  "complete_schema": complete_schema,
                  "required_inventory": sorted(required),
                  "declared_inputs_verified": len(verified_inputs),
                  "raw_bodies_verified": len(bodies),
                  "artifacts_hashed": len(ledger)})

    # ---- 3. structure --------------------------------------------------------------
    problems = []
    if not str(manifest.get("schema", "")).startswith("m2b.capture_manifest."):
        problems.append("capture_manifest.schema %r" % manifest.get("schema"))
    if not isinstance(checks.get("deterministic"), dict):
        problems.append("checks.deterministic is not an object")
    if not isinstance(checks.get("deterministic_sha256"), str):
        problems.append("checks.deterministic_sha256 is not a string")
    if not isinstance(provenance.get("schema"), str):
        problems.append("PROVENANCE.schema is not a string")
    if not isinstance(provenance.get("revision"), str):
        problems.append("PROVENANCE.revision is not a string")
    if problems:
        raise VerificationError("3", "structure", "; ".join(problems))
    steps.append({"step": "3", "name": "structure", "result": "ok"})

    # ---- 5a (precondition of 4) + 4. two digest anchors ----------------------------
    schema, descriptor, anchor = schema_descriptor(provenance)
    recomputed = cap.canonical_sha256(checks["deterministic"])
    if recomputed != checks["deterministic_sha256"]:
        raise VerificationError("4", "deterministic_digest_mismatch",
                                "the recomputed deterministic digest differs from "
                                "checks.deterministic_sha256",
                                recomputed, checks["deterministic_sha256"])
    if recomputed != anchor:
        raise VerificationError("4", "revision_anchor_mismatch",
                                "the recomputed deterministic digest differs from the "
                                "selected revision's %s anchor"
                                % ".".join(descriptor["anchor"]), recomputed, anchor)
    steps.append({"step": "4", "name": "two digest anchors", "result": "ok",
                  "schema": schema, "anchor_path": ".".join(descriptor["anchor"]),
                  "digest": recomputed})

    # ---- 5. revision binding -------------------------------------------------------
    if provenance["revision"] != revision.name:
        raise VerificationError("5b", "revision_binding",
                                "PROVENANCE.revision does not name the selected "
                                "directory", provenance["revision"], revision.name)
    if not descriptor["has_input_hashes"] or descriptor["producer_pins_key"] is None:
        raise VerificationError(
            "5a", "incomplete_legacy_schema",
            "schema %s records %s, so this revision cannot be fully verified and no "
            "trusted record is produced from it - a partially verified input never "
            "yields a partially trusted record"
            % (schema, "no input_hashes and no producer pins"
               if descriptor["producer_pins_key"] is None else "no input_hashes"))
    steps.append({"step": "5", "name": "revision binding", "result": "ok",
                  "revision": revision.name, "schema": schema})

    # ---- 6. cross-file identity (a supplement, never a substitute) ------------------
    run_id = manifest.get("run_id")
    meta_run_id = _dig(checks, ("run_meta", "run_id"))
    if not run_id or meta_run_id != run_id:
        raise VerificationError("6", "run_id_mismatch",
                                "checks.run_meta.run_id does not equal "
                                "capture_manifest.run_id", meta_run_id, run_id)
    parent_reference = provenance.get(descriptor["parent_key"])
    if not isinstance(parent_reference, str) or run_id not in parent_reference:
        raise VerificationError("6", "parent_reference_mismatch",
                                "PROVENANCE.%s does not reference the capture run_id"
                                % descriptor["parent_key"], parent_reference, run_id)
    if run_id not in revision.name:
        raise VerificationError("6", "revision_name_mismatch",
                                "the revision directory name does not carry the capture "
                                "run_id", revision.name, run_id)
    parent_dir = (REPO_ROOT / parent_reference).resolve()
    if not parent_dir.is_dir():
        raise VerificationError("6", "parent_evidence_absent",
                                "the referenced parent evidence directory is absent",
                                str(parent_dir), parent_reference)
    for relative, expected in sorted(verified_inputs.items()):
        target = parent_dir / relative
        if not target.is_file():
            raise VerificationError("6", "parent_input_absent",
                                    "the parent evidence has no %s" % relative)
        actual = sha256_file(target)
        if actual != expected:
            raise VerificationError("6", "parent_input_mismatch",
                                    "%s differs between the revision and its parent "
                                    "evidence" % relative, actual, expected)
    known_jobs = {job["job"] for job in cap.JOBS}
    manifest_jobs = {record.get("job") for record in manifest.get("requests", [])}
    if not manifest_jobs or not manifest_jobs <= known_jobs:
        raise VerificationError("6", "unknown_job",
                                "the manifest references jobs outside cap.JOBS",
                                sorted(j for j in manifest_jobs if j not in known_jobs),
                                sorted(known_jobs))
    steps.append({"step": "6", "name": "cross-file identity", "result": "ok",
                  "run_id": run_id, "parent_evidence": parent_reference,
                  "parent_inputs_verified": len(verified_inputs)})

    # ---- 7. upstream pins ----------------------------------------------------------
    declared_pins = provenance.get(descriptor["producer_pins_key"]) or {}
    if not declared_pins:
        # A.4: an unattributable record is worse than none.
        raise VerificationError("7", "producer_pins_absent",
                                "PROVENANCE.%s is absent or empty, so the record could "
                                "not be attributed to the code that produced it"
                                % descriptor["producer_pins_key"])
    installed = {name: sha256_file(HERE / name) for name in UPSTREAM_PRODUCERS
                 if (HERE / name).is_file()}
    drifted = sorted(name for name, value in declared_pins.items()
                     if installed.get(name) != value)
    pins_stale = bool(drifted) or sorted(declared_pins) != sorted(UPSTREAM_PRODUCERS)
    steps.append({"step": "7", "name": "upstream pins",
                  "result": "stale" if pins_stale else "ok",
                  "drifted": drifted,
                  "note": "a mismatch does not erase history; it forbids any "
                          "authoritative claim" if pins_stale else None})

    return {
        "revision_dir": revision,
        "revision": revision.name,
        "schema": schema,
        "descriptor": descriptor,
        "provenance": provenance,
        "checks": checks,
        "manifest": manifest,
        "consumed_artifacts": ledger,
        "verified_inputs": verified_inputs,
        "deterministic_sha256": recomputed,
        "upstream_producer_pins": {"declared": declared_pins, "installed": installed,
                                   "matched": not pins_stale, "drifted": drifted},
        "pins_stale": pins_stale,
        "steps": steps,
    }


# ============================================================ A.3/A.4 - derivation
def _checks_index(checks):
    index = {}
    for entry in checks["deterministic"].get("checks", []):
        index.setdefault((entry.get("id"), entry.get("symbol")), []).append(entry)
    return index


def _status(index, cid, symbol):
    entries = index.get((cid, symbol))
    return entries[0]["status"] if entries else None


def _measured(index, cid, symbol):
    entries = index.get((cid, symbol))
    return entries[0].get("measured") if entries else None


def _url_evidence(manifest, job):
    """A.3.1 - three URL classes, never merged.

    BR-R3: the association between a request record and the attempts it claims is
    VALIDATED, not assumed. `attempt_positions` must be integers that index the recorded
    attempts and select exactly the attempts carrying this request's index; the counts
    must agree; and every selected attempt's URL must be the request's own. A request with
    any association error is not counted as evidenced access, and the error is reported.
    """
    records = [r for r in manifest.get("requests", []) if r.get("job") == job]
    attempts = manifest.get("attempts", []) or []
    planned, accessed, skipped, errors = [], [], [], []
    for record in records:
        url = record.get("requested_url")
        number = record.get("index")
        planned.append({"url": url, "kind": record.get("kind"),
                        "outcome": record.get("outcome")})
        if record.get("outcome") == "skipped":
            skipped.append({"url": url, "kind": record.get("kind"),
                            "skip_scope": record.get("skip_scope"),
                            "note": "planned, not accessed"})
            continue

        local = []
        expected_positions = [i for i, a in enumerate(attempts)
                              if a.get("request_index") == number]
        positions = record.get("attempt_positions")
        count = record.get("attempt_count")
        if not isinstance(positions, list) or not all(
                isinstance(p, int) and not isinstance(p, bool) for p in positions):
            local.append("request %s: attempt_positions is not a list of integers"
                         % number)
        elif any(p < 0 or p >= len(attempts) for p in positions):
            local.append("request %s: an attempt position lies outside the recorded "
                         "attempts" % number)
        elif sorted(positions) != expected_positions:
            local.append("request %s: attempt_positions do not select exactly the "
                         "attempts recorded for this request" % number)
        if not isinstance(count, int) or isinstance(count, bool) \
                or count != len(expected_positions) \
                or (isinstance(positions, list) and count != len(positions)):
            local.append("request %s: attempt_count disagrees with the recorded attempts"
                         % number)
        selected = [attempts[p] for p in (positions or [])
                    if isinstance(p, int) and not isinstance(p, bool)
                    and 0 <= p < len(attempts)]
        for attempt in selected:
            if attempt.get("request_index") != number:
                local.append("request %s: a selected attempt belongs to request %r"
                             % (number, attempt.get("request_index")))
            if attempt.get("url") != url:
                local.append("request %s: a selected attempt's URL is not this request's "
                             "URL" % number)
        served = record.get("served_url")
        if served and served != url:
            local.append("request %s: served_url differs from requested_url" % number)

        if local:
            errors.extend(local)
            continue
        if not expected_positions:
            continue                     # planned, never accessed - not an error itself
        own = [attempts[p] for p in expected_positions]
        statuses = [a.get("status") for a in own]
        accessed.append({
            "url": url, "kind": record.get("kind"),
            "request_index": number,
            "attempts": len(own),
            "attempt_positions": sorted(positions),
            "statuses": statuses,
            "responded": any(s is not None for s in statuses),
            "served_url": served,
            "note": "an attempt proves it was initiated and recorded; receipt of an "
                    "HTTP response is evidenced only by a non-null status",
        })
    return {"planned": planned, "skipped": skipped, "evidenced_access": accessed,
            "association_errors": errors}


def _history_evidence(url_evidence, kind="klc"):
    for entry in url_evidence["evidenced_access"]:
        if entry["kind"] == kind:
            return entry
    return None


def derive_records(manifest, checks, *, upstream_pins=None, pins_stale=False):
    """One record per job (A.4). Never per row; never inferred where evidence is absent."""
    index = _checks_index(checks)
    replay_urls = _measured(index, "R1urls", "run")
    decoded = checks["deterministic"].get("decoded_summary") or {}
    basis_facts = checks["deterministic"].get("adapter_basis_facts") or {}
    checked_at = _dig(checks, ("run_meta", "checked_at_utc"))
    identity = module_identity()

    records = {}
    for job in cap.JOBS:
        name, klass = job["job"], job["instrument_class"]
        if not any(r.get("job") == name for r in manifest.get("requests", [])):
            continue
        urls = _url_evidence(manifest, name)
        history = _history_evidence(urls)
        r1 = index.get(("R1", name))
        reasons, transform = [], "unknown"

        s1_ok = _status(index, "S1", name) == "PASS"
        if not s1_ok:
            reasons.append("F-1: the planned URL set does not match the adapter constants")
        for problem in urls["association_errors"]:
            reasons.append("association_error: " + problem)
        if history is None:
            reasons.append("F-1: the history request shows no evidenced access")
        elif not history["responded"]:
            reasons.append("no attempt on the history request recorded a response status")
        if r1 is None:
            reasons.append("replay_not_evaluated: no R1 result for this job")
        elif r1[0]["status"] != "PASS":
            reasons.append("the adapter replay did not pass for this job")
        # BR-R3: replay URL evidence must actually cover this job before a positive claim.
        r1urls = index.get(("R1urls", "run"))
        if r1urls is None or r1urls[0].get("status") != "PASS":
            reasons.append("replay_url_evidence_missing: R1urls is absent or not PASS, so "
                           "the replay's requested URLs are not established")
        elif history is not None and history["url"] not in set(replay_urls or []):
            reasons.append("replay_url_evidence_missing: this job's history URL is absent "
                           "from the replay's requested URLs")

        if klass == "stock":
            if _status(index, "B1", "run") != "PASS":
                reasons.append("F-2: a factor endpoint was requested in this run")
            if _status(index, "B2", "run") != "PASS":
                reasons.append("F-4: the adapter code properties are not established")
            b2_applicable = True
            index_pin = None
        else:
            # D-1b: B2 and the adjust argument are NOT APPLICABLE to the index, and their
            # absence is not a failure (N-1 pattern). The index adapter's source hash is
            # recorded nowhere in the retained artifacts, so the pin leg cannot be met.
            b2_applicable = False
            index_pin = basis_facts.get("index_source_sha256")
            if not index_pin:
                reasons.append("no recorded index-adapter pin: D-1b's pin leg has no "
                               "input in these artifacts and cannot be supplied "
                               "retrospectively")
        if not reasons:
            transform = "none"

        history_index = None
        for record in manifest.get("requests", []):
            if record.get("job") == name and record.get("kind") == "klc":
                history_index = record.get("index")
        summary = decoded.get(str(history_index)) or {}
        r1_measured = (r1[0].get("measured") if r1 else None) or {}
        unit = "unknown"
        if klass == "stock" and _status(index, "U2", name) == "PASS":
            unit = (_measured(index, "U2", name) or {}).get("windowed", "unknown")

        records[name] = {
            "job": name,
            "instrument_class": klass,
            "adapter_transform": transform,
            "adapter_transform_reasons": reasons,
            "vendor_basis": "unverified",
            "vendor_basis_reason": (
                "U-6 defines no sufficiency rule; no retained evidence establishes the "
                "vendor's price basis. D-2 forbids any automatic upgrade"),
            "volume_unit": unit if klass == "stock" else "unknown",
            "volume_unit_note": (
                "a benchmark carries no amount series, so the unit is unknown by "
                "construction (N-1) and this is not a failure"
                if klass != "stock" else None),
            "b2_applicable": b2_applicable,
            "url_evidence": dict(urls, replay_requested={
                "urls": replay_urls,
                "note": "offline replay, not a live capture log; R1urls PASS only "
                        "excludes uncaptured URLs and asserts no completeness",
            }),
            "series_coverage": {
                "rows": r1_measured.get("rows"),
                "first_date": r1_measured.get("first_date"),
                "last_date": r1_measured.get("last_date"),
                "dates_returned": r1_measured.get("dates_returned"),
                "js_variable": summary.get("js_variable"),
                "branch": summary.get("branch"),
                "decoded_row_count": summary.get("row_count"),
                "replay_evaluated": r1 is not None,
            },
            "basis_evidence_ref": {
                "capture_run_id": manifest.get("run_id"),
                "capture_pins": manifest.get("environment", {}),
                "check_time_observations": {
                    "adapter_basis_facts": dict(
                        basis_facts, source=repo_relative(basis_facts["source"]))
                    if basis_facts.get("source") else basis_facts,
                    "observed_at": checked_at,
                    "note": "a check-time observation of the installed file, NOT a "
                            "capture-time pin; it is never back-dated",
                },
                "invocation_facts": {
                    "adjust_argument": "no structured field exists; implied by the "
                                       "producer pin smoke_checks.py "
                                       + str((upstream_pins or {}).get("smoke_checks.py")),
                },
                "upstream_producer_pins": upstream_pins or {},
                "pins_stale": pins_stale,
            },
            "record_producer": identity,
            "limits": list(DETECTION_LIMITS),
        }
    return records


# ================================================================ A.6 - the evaluator
KNOWN_VENDOR_BASIS = frozenset({"unverified", "unadjusted", "adjusted", "inconsistent"})


def evaluate(record):
    """Basis-dependent eligibility ONLY. There is no `eligible=True` branch.

    The evaluator is separately callable, so it must not trust the labels in its input:
    constraining the producer is not a substitute for validating the record.
    """
    reasons = []
    producer = (record or {}).get("record_producer") or {}
    if producer.get("derivation_rules_version") not in KNOWN_DERIVATION_RULES \
            or producer.get("evaluator_rules_version") not in KNOWN_EVALUATOR_RULES:
        reasons.append("unknown_rules_version")
    basis = (record or {}).get("vendor_basis")
    if basis not in KNOWN_VENDOR_BASIS:
        reasons.append("unsupported_vendor_basis_assertion")
    elif basis == "unverified":
        reasons.append("vendor_basis_unverified")
    else:
        # A record asserting a decided vendor basis is refused even when its evidence
        # references are genuine and its pins current: no adopted rule (U-6) can validate
        # such a claim, and a real reference does not make an assertion supported.
        reasons.append("unsupported_vendor_basis_assertion")
    if ((record or {}).get("basis_evidence_ref") or {}).get("pins_stale"):
        reasons.append("pins_stale")
    if (record or {}).get("verification_failed"):
        reasons.append("evidence_mismatch")
    return {
        "eligible": False,
        "reasons": sorted(set(reasons)),
        "note": "U-6 is deferred, so this module exposes no eligible=true path. A future "
                "positive path requires an adopted sufficiency rule AND a separately "
                "reviewed evidence-validation rule; none is pre-wired here.",
        "evaluator_rules_version": EVALUATOR_RULES_VERSION,
    }


def _producer_identity(record):
    keys = ("module_sha256", "record_schema_version", "derivation_rules_version",
            "evaluator_rules_version")
    producer = (record or {}).get("record_producer") or {}
    return json.dumps({k: producer.get(k) for k in keys}, sort_keys=True)


def evaluate_view(records):
    """A view is eligible only if every record is - which cannot happen in this version.

    BR-R4: comparability is enforced across the FULL record-producer identity - module
    hash, record schema and both rule-set versions - as well as upstream pins and vendor
    basis. Records from different producers describe different things and are never
    silently pooled.
    """
    records = list(records)
    values = {r.get("vendor_basis") for r in records}
    pins = {json.dumps((r.get("basis_evidence_ref") or {}).get("upstream_producer_pins"),
                       sort_keys=True) for r in records}
    identities = {_producer_identity(r) for r in records}
    reasons = sorted({reason for r in records for reason in evaluate(r)["reasons"]})
    if len(values) > 1:
        reasons.append("mixed_view")
    if len(pins) > 1:
        reasons.append("mixed_view")
    comparable = all(records_comparable(records[0], other) for other in records[1:]) \
        if records else True
    if len(identities) > 1 or not comparable:
        reasons.append("incomparable_record_producers")
    return {"eligible": False, "reasons": sorted(set(reasons)),
            "records": len(records),
            "comparable_record_producers": comparable and len(identities) <= 1,
            "record_producer_identities": len(identities),
            "note": "uniform `unverified` is uniformity of ignorance, not of convention"}


# ============================================================== A.5.3 - the output
def _serialize(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _guard_output_path(target, *, allow_scratch_root=False):
    """BR-R2. Normal output goes to ONE approved canonical root, compared Windows-safely.

    A scratch root is an explicit, bounded allowance for tests: it must be opted into and
    must lie inside the operating system's temporary directory. Reviewer-owned,
    evidence, revision, receipt and frozen locations are refused case-insensitively,
    because `EVIDENCE_x` and `evidence_x` are the same directory on NTFS.
    """
    target = Path(target).resolve()
    if not target.name.startswith(OUTPUT_PREFIX):
        raise VerificationError("8", "output_path",
                                "the output directory name must start with %r"
                                % OUTPUT_PREFIX, target.name, OUTPUT_PREFIX)
    lowered_prefixes = tuple(os.path.normcase(p) for p in PROTECTED_PREFIXES)
    lowered_names = tuple(os.path.normcase(n) for n in PROTECTED_NAMES)
    for part in target.parts:
        low = os.path.normcase(part)
        if low.startswith(lowered_prefixes):
            raise VerificationError("8", "output_path",
                                    "refusing to write inside a protected directory: %s"
                                    % part)
        if low in lowered_names:
            raise VerificationError("8", "output_path",
                                    "refusing to write inside a reviewer- or "
                                    "producer-owned directory: %s" % part)
    parent = target.parent
    if normcase(parent) != normcase(CANONICAL_OUTPUT_ROOT):
        allowed = allow_scratch_root and within(parent, tempfile.gettempdir())
        if not allowed:
            raise VerificationError(
                "8", "output_root",
                "output must be a fresh directory directly under the approved root; a "
                "scratch root is permitted only with allow_scratch_root=True and only "
                "inside the operating system's temporary directory",
                str(parent), str(CANONICAL_OUTPUT_ROOT))
    if target.exists():
        raise VerificationError("8", "output_path",
                                "the output directory already exists; a re-derivation "
                                "creates a NEW directory and never edits an old one",
                                str(target), "absent")
    return target


def write_evaluation(directory, out_root=None, *, suffix=None,
                     allow_scratch_root=False):
    """Verify -> derive -> evaluate -> write. Any verification failure writes no record."""
    verified = verify(directory)
    revision = verified["revision_dir"]
    name = OUTPUT_PREFIX + verified["revision"] + (("__" + suffix) if suffix else "")
    target = _guard_output_path(Path(out_root or CANONICAL_OUTPUT_ROOT) / name,
                                allow_scratch_root=allow_scratch_root)

    pins = verified["upstream_producer_pins"]["declared"]
    records = derive_records(verified["manifest"], verified["checks"],
                             upstream_pins=pins, pins_stale=verified["pins_stale"])
    eligibility = {name: evaluate(record) for name, record in records.items()}
    view = evaluate_view(list(records.values()))

    hashed = {"records": records, "eligibility": eligibility, "view_eligibility": view}
    digest = cap.canonical_sha256(hashed)

    consumed = verified["consumed_artifacts"]
    provenance = {
        "schema": "m2b.basis_eval.v1",
        "what_this_is": (
            "An offline, evidence-side derivation of P1 basis records from ONE retained "
            "revision, plus a basis-dependent eligibility evaluation. It is not a "
            "capture, not a label with authority, and it wires no gate. It replaces "
            "neither the capability verdict nor any per-job verdict, EV6, basis_gate or "
            "--pricing-basis."),
        "selected_revision": verified["revision"],
        "selected_revision_path": repo_relative(revision),
        "revision_schema": verified["schema"],
        "source_identity": {
            "capture_run_id": verified["manifest"].get("run_id"),
            "revision_name": verified["revision"],
            "parent_evidence": verified["provenance"].get(
                verified["descriptor"]["parent_key"]),
            "consumed_deterministic_sha256": verified["deterministic_sha256"],
        },
        "upstream_producer_pins": {
            "declared": verified["upstream_producer_pins"]["declared"],
            "recomputed_from_installed_files":
                verified["upstream_producer_pins"]["installed"],
            "matched": verified["upstream_producer_pins"]["matched"],
            "drifted": verified["upstream_producer_pins"]["drifted"],
        },
        "record_producer": module_identity(),
        "consumed_artifacts": consumed,
        "consumed_artifacts_note": (
            "Every artifact this run actually read, keyed by its path RELATIVE TO THE "
            "SELECTED REVISION, with the recomputed sha256 and the role(s) it played. "
            "These keys are revision-relative data paths and never collide with "
            "`upstream_producer_pins`, which is keyed by the file name of an INSTALLED "
            "module under _m2_smoke/ and describes code, not consumed evidence."),
        "required_input_inventory": sorted(
            required_input_inventory(verified["manifest"])),
        "verification_steps": verified["steps"],
        "records_sha256": digest,
        "eligibility_summary": {
            "any_eligible": False,
            "note": "this module has no eligible=true path while U-6 is deferred",
        },
        "detection_limits": list(DETECTION_LIMITS),
        "authority": (
            "This output grants no operational authority. It does not close P1 and does "
            "not establish source-capability acceptance."),
    }

    target.mkdir(parents=True)
    body = dict(hashed)
    body["records_sha256"] = digest
    body["meta"] = {
        "generated_at_utc": _dt.datetime.now(_dt.timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "selected_revision_absolute_path": str(revision),
        "adapter_basis_facts_absolute_source": (
            (verified["checks"]["deterministic"].get("adapter_basis_facts") or {})
            .get("source")),
        "note": "volatile; excluded from records_sha256",
    }
    (target / "basis_records.json").write_text(_serialize(body), encoding="utf-8")
    (target / "PROVENANCE.json").write_text(_serialize(provenance), encoding="utf-8")
    return {"output_dir": target, "records_sha256": digest, "records": records,
            "eligibility": eligibility, "view_eligibility": view,
            "verification": verified["steps"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("revision", help="the ONE revision directory to evaluate")
    parser.add_argument("--suffix", default=None,
                        help="label appended to the fresh basis_eval_* directory name")
    args = parser.parse_args(argv)
    try:
        result = write_evaluation(args.revision, None, suffix=args.suffix)
    except VerificationError as exc:
        print(json.dumps({"result": "REFUSED", "record_written": False,
                          **exc.as_dict()}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({
        "result": "written",
        "output_dir": repo_relative(result["output_dir"]),
        "records_sha256": result["records_sha256"],
        "records": {name: {"adapter_transform": r["adapter_transform"],
                           "vendor_basis": r["vendor_basis"],
                           "eligible": result["eligibility"][name]["eligible"],
                           "reasons": result["eligibility"][name]["reasons"]}
                    for name, r in result["records"].items()},
        "view_eligibility": result["view_eligibility"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
