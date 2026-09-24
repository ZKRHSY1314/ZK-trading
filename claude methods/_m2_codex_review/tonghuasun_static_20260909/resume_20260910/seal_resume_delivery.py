"""Seal this continuation only. Never overwrite either earlier stage's files."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent
ROOT = PRIOR.parents[2]
CAPTURE = HERE / "capture"
OUTPUT = HERE / "resume_delivery_manifest.json"


def digest(path):
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        raise AssertionError("database_access_not_allowed")
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


old_manifest = PRIOR / "probe_delivery_manifest.json"
assert digest(old_manifest) == "759c626d22886aac586972be2e4e73c57fed047a93378116ba4a1951d36214e5"
old_checks = {name: digest(PRIOR / name) == value for name, value in read(old_manifest)["artifacts"].items()}
static_checks = {name: digest(Path(name)) == value for name, value in read(PRIOR / "artifact_manifest.json")["artifacts"].items()}
new_pins = {name: digest(Path(name)) == value for name, value in read(CAPTURE / "producer_and_contract_pins.json").items()}
old_pins = {name: digest(Path(name)) == value for name, value in read(PRIOR / "ths_live_20260910/producer_and_contract_pins.json").items()}
assert all(old_checks.values()) and all(static_checks.values()) and all(new_pins.values()) and all(old_pins.values())

preserved = read(PRIOR / "probe_preservation_after.json")
tracked = {name: digest(ROOT / name) == value for name, value in preserved["tracked_workspace_hashes"].items()}
protected = {name: digest(ROOT / name) == value["expected"] for name, value in preserved["protected"].items()}
g1_dir = ROOT / "claude methods/_m2_smoke/g1_corporate_actions_20260909"
g1 = {name: digest(g1_dir / name) == value["expected"] for name, value in preserved["g1"].items()}
g1_paths_match = set(g1) == {p.relative_to(g1_dir).as_posix() for p in g1_dir.rglob("*") if p.is_file()}
docs = {name: digest(ROOT / "claude methods" / name) == value for name, value in preserved["documents"].items()}
assert all(tracked.values()) and all(protected.values()) and all(g1.values()) and g1_paths_match and all(docs.values())
git = lambda *args: subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
    text=True, encoding="utf-8").stdout.strip()
assert not git("diff", "--cached", "--name-only")
head = git("rev-parse", "HEAD")
assert head == preserved["head"]
tracked_names = {name for name in git("ls-files", "-z").split("\0") if name and (ROOT / name).is_file()
    and Path(name).suffix.lower() not in {".db", ".sqlite", ".sqlite3"}}
assert tracked_names == set(tracked)

summary = read(CAPTURE / "summary.json")
assert {p.name for p in CAPTURE.glob("attempt_?.json")} == {f"attempt_{i}.json" for i in range(2, 6)}
assert {p.name for p in CAPTURE.glob("response_*.bin")} == {f"response_{i}.bin" for i in range(2, 6)}
for number in range(2, 6):
    receipt = read(CAPTURE / f"attempt_{number}_completed.json")
    assert receipt["job"]["id"] == number and receipt["http_status"] == 200
    assert receipt["raw_sha256"] == digest(CAPTURE / f"response_{number}.bin")
assert summary["prior_rest_attempts"] == 1 and summary["new_rest_attempts"] == 4
assert summary["cumulative_rest_attempts"] == 5 and summary["rest_attempts_not_issued"] == 1
assert summary["automatic_resume_allowed"] is False and summary["job_1_reissued"] is False
assert read(HERE / "independent_raw_review.json")["evidence_consistency_passed"] is True

result = {
    "sealed_at_utc": datetime.now(timezone.utc).isoformat(), "head": head, "staged_files": 0,
    "old_42_artifacts_match": old_checks, "older_13_static_artifacts_match": static_checks,
    "new_producer_and_contract_match": new_pins, "old_producer_and_contract_match": old_pins,
    "tracked_files_checked": len(tracked), "all_tracked_match": True,
    "protected_files_checked": len(protected), "all_protected_match": True,
    "g1_files_checked": len(g1), "all_g1_match": True, "g1_paths_match": g1_paths_match,
    "claude_documents_match": docs,
    "prior_attempts": 1, "new_attempts": 4, "cumulative_attempts": 5, "unissued_original_job": 6,
    "stock_long_history_observed": True, "index_usable_history_observed": False,
    "m2_accepted": False, "eligible": False, "automatic_resume_allowed": False,
    "client_restarted_with_user_authorization": True, "configuration_or_token_edits": False,
    "artifacts": {p.relative_to(HERE).as_posix(): digest(p) for p in sorted(HERE.rglob("*")) if p.is_file() and p != OUTPUT},
}
with OUTPUT.open("x", encoding="utf-8", newline="\n") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(json.dumps({key: value for key, value in result.items() if key not in {
    "artifacts", "old_42_artifacts_match", "older_13_static_artifacts_match", "new_producer_and_contract_match",
    "old_producer_and_contract_match", "claude_documents_match"}}, indent=2))
