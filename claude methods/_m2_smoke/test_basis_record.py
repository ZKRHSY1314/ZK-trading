"""Offline synthetic tests and retained-artifact validation for `basis_record.py`.

The A-numbered cases are the matrix of Appendix A.8 in
`claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md` (revision 6). The R- cases validate the
module against the RETAINED artifacts, read-only.

No network, no SQLite, no adapter replay, no capture, no production write. Negative
fixtures are built by COPYING a retained revision into a temporary directory and mutating
the copy; every retained tree is hashed before and after the suite and must be identical.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import smoke_capture as cap                                       # noqa: E402
import basis_record as br                                        # noqa: E402

# From here on nothing in this suite may reach a remote host, for any reason.
_GUARD = cap.no_remote_connections("the basis-record suite attempted a network connection")
_GUARD.__enter__()

V3 = HERE / "revision_20260908T082833Z_r2abc_v2"
V3_SIBLING = HERE / "revision_20260908T082833Z_r2abc"
V1 = HERE / "revision_20260908T021722Z_d1d2"
V2 = HERE / "revision_20260908T021722Z_d2_literal"
CAPTURE = HERE / "evidence_20260908T082833Z"
GUARDED = tuple(sorted(p for p in HERE.iterdir() if p.is_dir()
                       and p.name.startswith(("evidence_", "revision_", "receipts_",
                                              "frozen_impl_"))))

CASES = []


def case(name):
    def wrap(fn):
        CASES.append((name, fn))
        return fn
    return wrap


def tree(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


def copy_revision(tmp, source=V3, name=None):
    target = Path(tmp) / (name or source.name)
    shutil.copytree(source, target)
    return target


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False),
                          encoding="utf-8")


def write(directory, out_root, **kwargs):
    """Every test write goes to a bounded scratch root inside the OS temp directory."""
    return br.write_evaluation(directory, out_root, allow_scratch_root=True, **kwargs)


def refuse(directory, out_root=None, *, allow_scratch_root=True):
    """Run the writer and require a refusal; return the VerificationError."""
    try:
        br.write_evaluation(directory, out_root,
                            allow_scratch_root=allow_scratch_root)
    except br.VerificationError as exc:
        return exc
    raise AssertionError("the writer accepted an input it must refuse")


def loaded(source=V3):
    verified = br.verify(source)
    return verified["manifest"], verified["checks"], verified


# ============================================================ A-1 .. A-4: derivation
@case("A-1 complete stock inputs derive `none` / `unverified`, and are never eligible")
def _():
    manifest, checks, verified = loaded()
    records = br.derive_records(manifest, checks,
                                upstream_pins=verified["upstream_producer_pins"]["declared"])
    stock = records["sh600011"]
    assert stock["adapter_transform"] == "none", stock["adapter_transform_reasons"]
    assert stock["adapter_transform_reasons"] == []
    assert stock["vendor_basis"] == "unverified"
    verdict = br.evaluate(stock)
    assert verdict["eligible"] is False and "vendor_basis_unverified" in verdict["reasons"]
    # the check-time observation is labelled as such and carries no capture-time claim
    observation = stock["basis_evidence_ref"]["check_time_observations"]
    assert observation["observed_at"] == checks["run_meta"]["checked_at_utc"]
    assert "NOT a capture-time pin" in observation["note"]
    # the absolute, non-ASCII source path is normalized inside the record
    assert not observation["adapter_basis_facts"]["source"].startswith("D:")
    # `adjust` has no structured field; it is only implied by a producer pin
    assert "no structured field exists" in \
        stock["basis_evidence_ref"]["invocation_facts"]["adjust_argument"]


@case("A-2 the index needs no B2, and stays `unknown` for want of a recorded pin")
def _():
    manifest, checks, _v = loaded()
    index = br.derive_records(manifest, checks)["sh000300"]
    assert index["b2_applicable"] is False
    assert index["adapter_transform"] == "unknown"
    assert any("index-adapter pin" in r for r in index["adapter_transform_reasons"])
    # the absence of B2 is NOT itself a failure reason for a benchmark
    assert not any("F-4" in r for r in index["adapter_transform_reasons"])
    # N-1: the unit is unknown by construction, not by failure
    assert index["volume_unit"] == "unknown"
    assert "by construction" in index["volume_unit_note"]


@case("A-3 an unreadable B2 property makes the stock transform unknown")
def _():
    manifest, checks, _v = loaded()
    broken = copy.deepcopy(checks)
    for entry in broken["deterministic"]["checks"]:
        if entry["id"] == "B2":
            entry["status"] = "FAIL"
    stock = br.derive_records(manifest, broken)["sh600011"]
    assert stock["adapter_transform"] == "unknown"
    assert any(r.startswith("F-4") for r in stock["adapter_transform_reasons"])


@case("A-4 producer pins absent from PROVENANCE emit no record at all")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp)
        provenance = read(revision / "PROVENANCE.json")
        del provenance["producer_implementation"]
        write_json(revision / "PROVENANCE.json", provenance)
        exc = refuse(revision, tmp)
        assert exc.code == "producer_pins_absent", exc.code
        assert not list(Path(tmp).glob("basis_eval_*"))


# ============================================================= A-5 .. A-8: evaluator
@case("A-5 stale pins are reported, and the stored record is not rewritten")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp)
        provenance = read(revision / "PROVENANCE.json")
        before = json.dumps(provenance, sort_keys=True)
        provenance["producer_implementation"]["smoke_checks.py"] = "0" * 64
        write_json(revision / "PROVENANCE.json", provenance)
        result = write(revision, tmp)
        record = result["records"]["sh600011"]
        assert record["basis_evidence_ref"]["pins_stale"] is True
        assert "pins_stale" in result["eligibility"]["sh600011"]["reasons"]
        assert result["eligibility"]["sh600011"]["eligible"] is False
        # only the temporary copy was edited; the retained original is untouched
        assert json.dumps(read(V3 / "PROVENANCE.json"), sort_keys=True) == before


@case("A-6 a view mixing producer pins is reported as a mixed view")
def _():
    manifest, checks, verified = loaded()
    pins = verified["upstream_producer_pins"]["declared"]
    one = br.derive_records(manifest, checks, upstream_pins=pins)["sh600011"]
    other = copy.deepcopy(one)
    other["basis_evidence_ref"]["upstream_producer_pins"] = dict(pins,
                                                                **{"smoke_checks.py": "x"})
    view = br.evaluate_view([one, other])
    assert view["eligible"] is False and "mixed_view" in view["reasons"]
    assert "uniformity of ignorance" in view["note"]


@case("A-7 a hand-edited `unadjusted` record is rejected, with no threshold consulted")
def _():
    manifest, checks, _v = loaded()
    forged = copy.deepcopy(br.derive_records(manifest, checks)["sh600011"])
    forged["vendor_basis"] = "unadjusted"
    forged["basis_evidence_ref"] = {}
    verdict = br.evaluate(forged)
    assert verdict["eligible"] is False
    assert "unsupported_vendor_basis_assertion" in verdict["reasons"]


@case("A-8 serialization is deterministic and `meta` is excluded from the digest")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        first = write(copy_revision(tmp, name=V3.name), Path(tmp) / "a")
        second = write(V3, Path(tmp) / "b")
        assert first["records_sha256"] == second["records_sha256"]
        a = (Path(tmp) / "a" / ("basis_eval_" + V3.name) / "basis_records.json")
        b = (Path(tmp) / "b" / ("basis_eval_" + V3.name) / "basis_records.json")
        left, right = read(a), read(b)
        # the volatile block differs in path and may differ in timestamp; it is excluded
        assert left["meta"]["selected_revision_absolute_path"] != \
            right["meta"]["selected_revision_absolute_path"]
        del left["meta"], right["meta"]
        assert left == right
        assert cap.canonical_sha256({k: left[k] for k in
                                     ("records", "eligibility", "view_eligibility")}) \
            == left["records_sha256"]


# ============================================================= A-9 .. A-14: guards
@case("A-9 an existing output directory is never overwritten")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        write(V3, tmp)
        exc = refuse(V3, tmp)
        assert exc.code == "output_path" and "already exists" in exc.detail


@case("A-10 the writer refuses to write inside a protected directory")
def _():
    exc = refuse(V3, HERE / "evidence_20260908T082833Z")
    assert exc.code == "output_path" and "protected directory" in exc.detail
    assert not any(p.name.startswith("basis_eval_") for p in CAPTURE.iterdir())


@case("A-11 a raw body that differs from its recorded hash stops the write")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp)
        body = sorted((revision / "raw").iterdir())[0]
        body.write_bytes(body.read_bytes() + b" ")
        exc = refuse(revision, tmp)
        assert exc.code == "input_hash_mismatch", exc.code
        assert not list(Path(tmp).glob("basis_eval_*"))


@case("A-12 an edited deterministic field without a re-digest fails the first anchor")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp)
        checks = read(revision / "checks.json")
        checks["deterministic"]["verdicts"]["capability"] = "PASS"
        write_json(revision / "checks.json", checks)
        exc = refuse(revision, tmp)
        assert exc.step == "4" and exc.code == "deterministic_digest_mismatch"


@case("A-13 a run_id that disagrees across files fails cross-file identity")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp)
        checks = read(revision / "checks.json")
        # run_meta is OUTSIDE the deterministic block, so the digests still agree:
        # only the cross-file identity step can catch this.
        checks["run_meta"]["run_id"] = "20260908T021722Z"
        write_json(revision / "checks.json", checks)
        exc = refuse(revision, tmp)
        assert exc.step == "6" and exc.code == "run_id_mismatch", (exc.step, exc.code)


@case("A-14 a missing consumed input stops the write")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp)
        (revision / "capture_manifest.json").unlink()
        exc = refuse(revision, tmp)
        assert exc.step == "1" and exc.code == "missing_input"


# ================================================== A-15 .. A-17: versions and labels
@case("A-15 a different module or rules version makes records not comparable")
def _():
    manifest, checks, _v = loaded()
    left = br.derive_records(manifest, checks)["sh600011"]
    right = copy.deepcopy(left)
    assert br.records_comparable(left, right)
    right["record_producer"] = dict(right["record_producer"], module_sha256="f" * 64)
    assert not br.records_comparable(left, right)
    right = copy.deepcopy(left)
    right["record_producer"] = dict(right["record_producer"],
                                    derivation_rules_version="p1.derivation.rev99")
    assert not br.records_comparable(left, right)


@case("A-16 an unrecognized rules version is refused, not evaluated under today's rules")
def _():
    manifest, checks, _v = loaded()
    record = copy.deepcopy(br.derive_records(manifest, checks)["sh600011"])
    record["record_producer"] = dict(record["record_producer"],
                                     evaluator_rules_version="p1.evaluator.rev99")
    verdict = br.evaluate(record)
    assert verdict["eligible"] is False
    assert "unknown_rules_version" in verdict["reasons"]


@case("A-17 genuine references and current pins do not support an `unadjusted` claim")
def _():
    manifest, checks, verified = loaded()
    pins = verified["upstream_producer_pins"]["declared"]
    record = copy.deepcopy(br.derive_records(manifest, checks, upstream_pins=pins)[
        "sh600011"])
    # every reference below is real and every pin is current; only the label is flipped
    assert record["basis_evidence_ref"]["capture_run_id"] == "20260908T082833Z"
    assert record["basis_evidence_ref"]["pins_stale"] is False
    record["vendor_basis"] = "unadjusted"
    verdict = br.evaluate(record)
    assert verdict["eligible"] is False
    assert verdict["reasons"] == ["unsupported_vendor_basis_assertion"], verdict["reasons"]


# ================================================= A-18 .. A-19: URL and replay classes
@case("A-18 a skipped-but-listed request is planned, never evidenced access")
def _():
    manifest = read(V1 / "capture_manifest.json")
    checks = read(V1 / "checks.json")
    records = br.derive_records(manifest, checks)
    planned = sum(len(r["url_evidence"]["planned"]) for r in records.values())
    accessed = sum(len(r["url_evidence"]["evidenced_access"]) for r in records.values())
    skipped = sum(len(r["url_evidence"]["skipped"]) for r in records.values())
    assert (planned, accessed, skipped) == (5, 2, 3), (planned, accessed, skipped)
    assert {s["skip_scope"] for r in records.values()
            for s in r["url_evidence"]["skipped"]} == {"job_local", "run_global"}
    # the job whose history was never issued cannot derive a transform
    assert records["bj920000"]["adapter_transform"] == "unknown"
    assert any("evidenced access" in reason
               for reason in records["bj920000"]["adapter_transform_reasons"])


@case("A-19 a job absent from the replay is `replay_not_evaluated`, not a pass")
def _():
    manifest, checks, _v = loaded()
    partial = copy.deepcopy(checks)
    partial["deterministic"]["checks"] = [c for c in partial["deterministic"]["checks"]
                                          if not (c["id"] == "R1"
                                                  and c["symbol"] == "sh600011")]
    record = br.derive_records(manifest, partial)["sh600011"]
    assert record["adapter_transform"] == "unknown"
    assert any("replay_not_evaluated" in r for r in record["adapter_transform_reasons"])
    assert record["series_coverage"]["replay_evaluated"] is False
    # the replay URL set is still recorded as replay evidence, never as capture evidence
    assert "not a live capture log" in record["url_evidence"]["replay_requested"]["note"]


# ============================================ A-20 .. A-23: binding, anchors, attempts
@case("A-20 a valid revision presented under another revision's name is refused")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        # `..._r2abc` is internally valid: its own digest and anchor agree. Presented
        # under the selected name it must still be refused by the revision binding.
        revision = copy_revision(tmp, source=V3_SIBLING, name=V3.name)
        exc = refuse(revision, tmp)
        assert exc.step == "5b" and exc.code == "revision_binding", (exc.step, exc.code)
        assert exc.observed == V3_SIBLING.name and exc.expected == V3.name
        assert not list(Path(tmp).glob("basis_eval_*"))


@case("A-21 re-digested deterministic content still fails the revision anchor")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp)
        checks = read(revision / "checks.json")
        checks["deterministic"]["verdicts"]["capability"] = "PASS"
        checks["deterministic_sha256"] = cap.canonical_sha256(checks["deterministic"])
        write_json(revision / "checks.json", checks)
        exc = refuse(revision, tmp)
        assert exc.step == "4" and exc.code == "revision_anchor_mismatch", exc.code
        assert exc.expected == read(V3 / "PROVENANCE.json")[
            "revised_offline_result"]["deterministic_sha256"]


@case("A-22 unknown schema, a missing anchor, and no provenance are all refused")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp, name=V3.name + "_a")
        provenance = read(revision / "PROVENANCE.json")
        provenance["schema"] = "m2b.offline_revision.v99"
        write_json(revision / "PROVENANCE.json", provenance)
        exc = refuse(revision, tmp)
        assert exc.step == "5a" and exc.code == "unknown_schema"

        revision = copy_revision(tmp, name=V3.name + "_b")
        provenance = read(revision / "PROVENANCE.json")
        provenance["revision"] = revision.name
        del provenance["revised_offline_result"]
        write_json(revision / "PROVENANCE.json", provenance)
        exc = refuse(revision, tmp)
        assert exc.step == "5a" and exc.code == "missing_anchor"

    # a capture directory has no revision identity at all
    exc = refuse(CAPTURE)
    assert exc.step == "5c" and exc.code == "no_revision_identity"


@case("A-23 an attempt with no response status is attempted, not responded")
def _():
    manifest, checks, _v = loaded()
    mutated = copy.deepcopy(manifest)
    for attempt in mutated["attempts"]:
        attempt["status"] = None
        attempt["error"] = "TimeoutError"
    record = br.derive_records(mutated, checks)["sh600011"]
    history = record["url_evidence"]["evidenced_access"][0]
    assert history["responded"] is False and history["statuses"] == [None]
    assert record["adapter_transform"] == "unknown"
    assert any("response status" in r for r in record["adapter_transform_reasons"])


# =============================== BR-R1: the required input inventory and the ledger
@case("BR-R1a a missing input_hashes field is a refusal, never 'nothing to verify'")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp)
        provenance = read(revision / "PROVENANCE.json")
        del provenance["input_hashes"]
        write_json(revision / "PROVENANCE.json", provenance)
        exc = refuse(revision, tmp)
        assert exc.step == "2" and exc.code == "input_hashes_absent", (exc.step, exc.code)
        assert not list(Path(tmp).glob("basis_eval_*"))


@case("BR-R1b a partial input_hashes inventory is refused")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp)
        provenance = read(revision / "PROVENANCE.json")
        provenance["input_hashes"] = {
            "capture_manifest.json": provenance["input_hashes"]["capture_manifest.json"]}
        write_json(revision / "PROVENANCE.json", provenance)
        exc = refuse(revision, tmp)
        assert exc.step == "2" and exc.code == "input_hashes_incomplete", exc.code
        assert "reference/reference_extract.json" in str(exc.detail)


@case("BR-R1c an edited reference extract is caught even with the declaration untouched")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp)
        extract = revision / "reference" / "reference_extract.json"
        extract.write_text(extract.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        exc = refuse(revision, tmp)
        assert exc.step == "2" and exc.code == "input_hash_mismatch", exc.code
        assert "reference/reference_extract.json" in exc.detail


@case("BR-R1d malformed digests and unsafe input paths are refused")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp, name=V3.name)
        provenance = read(revision / "PROVENANCE.json")
        provenance["input_hashes"]["capture_manifest.json"] = "not-a-digest"
        write_json(revision / "PROVENANCE.json", provenance)
        exc = refuse(revision, tmp)
        assert exc.code == "input_hashes_malformed", exc.code

    with tempfile.TemporaryDirectory() as tmp:
        revision = copy_revision(tmp, name=V3.name)
        provenance = read(revision / "PROVENANCE.json")
        provenance["input_hashes"]["../escape.json"] = "0" * 64
        write_json(revision / "PROVENANCE.json", provenance)
        exc = refuse(revision, tmp)
        assert exc.code == "unsafe_input_path", exc.code


@case("BR-R1e the ledger records every artifact actually read, with unambiguous roles")
def _():
    verified = br.verify(V3)
    ledger = verified["consumed_artifacts"]
    assert sorted(ledger) == [
        "PROVENANCE.json", "capture_manifest.json", "checks.json",
        "raw/01_sh600011_klc_kl.js.bin", "raw/02_sh600011_getAmountBySymbol.bin",
        "raw/03_sh000300_klc_kl.js.bin", "raw/04_bj920000_klc_kl.js.bin",
        "raw/05_bj920000_getAmountBySymbol.bin", "reference/reference_extract.json"]
    extract = ledger["reference/reference_extract.json"]
    assert extract["roles"] == ["reference_extract"] and extract["declared_hash_matched"]
    body = ledger["raw/01_sh600011_klc_kl.js.bin"]
    assert body["declared_hash_matched"] and body["manifest_body_sha256_matched"]
    assert ledger["checks.json"]["roles"] == ["revision_json"]
    with tempfile.TemporaryDirectory() as tmp:
        result = write(V3, tmp)
        provenance = read(result["output_dir"] / "PROVENANCE.json")
        assert sorted(provenance["consumed_artifacts"]) == sorted(ledger)
        assert "never collide" in provenance["consumed_artifacts_note"]
        assert sorted(provenance["required_input_inventory"]) == sorted(
            br.required_input_inventory(read(V3 / "capture_manifest.json")))


# ================================ BR-R2: the approved output root, Windows-safely
@case("BR-R2a a reviewer-owned directory is refused as an output root")
def _():
    reviewer = HERE.parent / "_m2_codex_review"
    exc = refuse(V3, reviewer)
    assert exc.code == "output_path" and "reviewer- or" in exc.detail, exc.detail
    assert not any(p.name.startswith("basis_eval_") for p in reviewer.iterdir())


@case("BR-R2b protected prefixes are compared case-insensitively")
def _():
    for name in ("EVIDENCE_codex_guard_probe_never_created",
                 "Revision_probe_never_created", "FROZEN_IMPL_probe"):
        try:
            br._guard_output_path(HERE / name / "basis_eval_probe",
                                  allow_scratch_root=True)
        except br.VerificationError as exc:
            assert exc.code == "output_path", (name, exc.code)
        else:
            raise AssertionError("a protected prefix was accepted: %s" % name)
        assert not (HERE / name).exists(), "the probe must create nothing"


@case("BR-R2c only the canonical root, or an opted-in temp scratch root, is accepted")
def _():
    # the approved canonical root is accepted by the guard, and nothing is created
    probe = br._guard_output_path(br.CANONICAL_OUTPUT_ROOT / "basis_eval_probe_only")
    assert probe.parent == br.CANONICAL_OUTPUT_ROOT and not probe.exists()
    # an arbitrary root is refused, with or without the scratch opt-in
    for allow in (False, True):
        try:
            br._guard_output_path(HERE.parent / "basis_eval_probe_only",
                                  allow_scratch_root=allow)
        except br.VerificationError as exc:
            assert exc.code == "output_root", exc.code
        else:
            raise AssertionError("an unapproved root was accepted (allow=%s)" % allow)
    # a temp root is refused unless the allowance is explicit
    with tempfile.TemporaryDirectory() as tmp:
        exc = refuse(V3, tmp, allow_scratch_root=False)
        assert exc.code == "output_root", exc.code
        assert write(V3, tmp)["output_dir"].parent == Path(tmp).resolve()
    assert not any(p.name.startswith("basis_eval_probe")
                   for p in br.CANONICAL_OUTPUT_ROOT.iterdir())


# ============== BR-R3: request / attempt / replay associations gate a positive claim
def _mutated_manifest(**edit):
    manifest, checks, _v = loaded()
    mutated = copy.deepcopy(manifest)
    edit_fn = edit["edit"]
    edit_fn(mutated)
    return br.derive_records(mutated, checks)["sh600011"], checks


@case("BR-R3a an out-of-range attempt position refuses the positive transform")
def _():
    def edit(manifest):
        for record in manifest["requests"]:
            if record["job"] == "sh600011" and record["kind"] == "klc":
                record["attempt_positions"] = [99]
    record, _c = _mutated_manifest(edit=edit)
    assert record["adapter_transform"] == "unknown"
    assert any("outside the recorded attempts" in r
               for r in record["adapter_transform_reasons"])
    assert record["url_evidence"]["evidenced_access"] == [] or all(
        e["kind"] != "klc" for e in record["url_evidence"]["evidenced_access"])


@case("BR-R3b an attempt whose URL is not the request's refuses the positive transform")
def _():
    def edit(manifest):
        manifest["attempts"][0]["url"] = "https://example.invalid/other"
    record, _c = _mutated_manifest(edit=edit)
    assert record["adapter_transform"] == "unknown"
    assert any("not this request's URL" in r
               for r in record["adapter_transform_reasons"])


@case("BR-R3c an attempt_count that disagrees with the record refuses the claim")
def _():
    def edit(manifest):
        for record in manifest["requests"]:
            if record["job"] == "sh600011" and record["kind"] == "klc":
                record["attempt_count"] = 3
    record, _c = _mutated_manifest(edit=edit)
    assert record["adapter_transform"] == "unknown"
    assert any("attempt_count disagrees" in r
               for r in record["adapter_transform_reasons"])


@case("BR-R3d absent R1urls evidence refuses the positive transform")
def _():
    manifest, checks, _v = loaded()
    stripped = copy.deepcopy(checks)
    stripped["deterministic"]["checks"] = [c for c in stripped["deterministic"]["checks"]
                                           if c["id"] != "R1urls"]
    record = br.derive_records(manifest, stripped)["sh600011"]
    assert record["adapter_transform"] == "unknown"
    assert any("replay_url_evidence_missing" in r
               for r in record["adapter_transform_reasons"])


@case("BR-R3e a history URL absent from the replay's URLs refuses the claim")
def _():
    manifest, checks, _v = loaded()
    narrowed = copy.deepcopy(checks)
    for entry in narrowed["deterministic"]["checks"]:
        if entry["id"] == "R1urls":
            entry["measured"] = [u for u in entry["measured"] if "sh600011" not in u]
    record = br.derive_records(manifest, narrowed)["sh600011"]
    assert record["adapter_transform"] == "unknown"
    assert any("absent from the replay's requested URLs" in r
               for r in record["adapter_transform_reasons"])
    # the other stock is unaffected
    assert br.derive_records(manifest, narrowed)["bj920000"]["adapter_transform"] == "none"


# ================================= BR-R4: full record-producer comparability in views
@case("BR-R4 a view mixing record-producer identities is reported as incomparable")
def _():
    manifest, checks, _v = loaded()
    base = br.derive_records(manifest, checks)["sh600011"]
    for field, value in (("module_sha256", "f" * 64),
                         ("record_schema_version", "m2b.basis_record.v99"),
                         ("derivation_rules_version", "p1.derivation.rev99"),
                         ("evaluator_rules_version", "p1.evaluator.rev99")):
        other = copy.deepcopy(base)
        other["record_producer"] = dict(other["record_producer"], **{field: value})
        view = br.evaluate_view([base, other])
        assert view["eligible"] is False
        assert "incomparable_record_producers" in view["reasons"], field
        assert view["comparable_record_producers"] is False
        assert view["record_producer_identities"] == 2
    same = br.evaluate_view([base, copy.deepcopy(base)])
    assert same["comparable_record_producers"] is True
    assert "incomparable_record_producers" not in same["reasons"]
    assert same["eligible"] is False


# ================================================== R-: the retained artifacts
@case("R-A the retained v3 revision verifies through steps 1-7; step 8 guards the write")
def _():
    verified = br.verify(V3)
    assert [s["step"] for s in verified["steps"]] == ["1", "2", "3", "4", "5", "6", "7"]
    assert verified["schema"] == "m2b.offline_revision.v3"
    assert verified["deterministic_sha256"] == \
        "099640a21e5927a057f3d2d1468b5765312bf1b68ff0d056051a18317fc81292"
    assert verified["pins_stale"] is False
    assert verified["steps"][1]["declared_inputs_verified"] == 7
    assert verified["steps"][1]["raw_bodies_verified"] == 5
    assert verified["steps"][1]["complete_schema"] is True
    assert verified["steps"][1]["artifacts_hashed"] == 9


@case("R-B the incomplete legacy revisions are refused, not partially trusted")
def _():
    for legacy, schema in ((V1, "m2b.offline_revision.v1"),
                           (V2, "m2b.offline_revision.v2")):
        exc = refuse(legacy)
        assert exc.code == "incomplete_legacy_schema", (legacy.name, exc.code)
        assert schema in exc.detail
        assert "partially trusted" in exc.detail


@case("R-C the retained records are exactly three, none of them eligible")
def _():
    manifest, checks, verified = loaded()
    records = br.derive_records(manifest, checks,
                                upstream_pins=verified["upstream_producer_pins"]["declared"])
    assert sorted(records) == ["bj920000", "sh000300", "sh600011"]
    assert {n: r["adapter_transform"] for n, r in records.items()} == {
        "sh600011": "none", "bj920000": "none", "sh000300": "unknown"}
    assert {r["vendor_basis"] for r in records.values()} == {"unverified"}
    assert all(br.evaluate(r)["eligible"] is False for r in records.values())
    assert br.evaluate_view(list(records.values()))["eligible"] is False
    assert records["sh600011"]["series_coverage"]["rows"] == 978
    assert records["sh000300"]["series_coverage"]["rows"] == 5987


@case("R-D the module exposes no eligible=true path and states its limits")
def _():
    source = (HERE / "basis_record.py").read_text(encoding="utf-8")
    assert '"eligible": True' not in source and "'eligible': True" not in source
    assert source.count('"eligible": False') >= 2
    assert len(br.DETECTION_LIMITS) == 3
    assert any("does NOT detect every same-digest file substitution" in limit
               for limit in br.DETECTION_LIMITS)
    assert any("self-consistent forgery" in limit for limit in br.DETECTION_LIMITS)
    assert any("not that the endpoint was reachable" in limit
               for limit in br.DETECTION_LIMITS)


def main():
    print("P1 basis-record suite (offline; no network, SQLite, replay or capture)")
    before = {p.name: tree(p) for p in GUARDED}
    failures = 0
    for name, fn in CASES:
        try:
            fn()
            print("  [ok] %s" % name)
        except AssertionError as exc:
            failures += 1
            print("  [XX] %s\n       %s" % (name, exc))
        except Exception as exc:                                  # noqa: BLE001
            failures += 1
            print("  [XX] %s\n       unexpected %s: %s"
                  % (name, type(exc).__name__, exc))
    after = {p.name: tree(p) for p in GUARDED}
    changed = sorted(name for name in before if before[name] != after[name])
    print("\n  guarded directories: %d, changed: %s" % (len(GUARDED), changed or "none"))
    if changed:
        failures += 1
    print("\n  %d cases, %d unexpected" % (len(CASES), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
