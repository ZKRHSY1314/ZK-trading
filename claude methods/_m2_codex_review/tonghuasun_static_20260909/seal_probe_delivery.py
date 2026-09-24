"""Read-only integrity checks; write one new audit manifest, never old receipts."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LIVE = HERE / "ths_live_20260910"
DESTINATION = HERE / "probe_delivery_manifest.json"


def digest(path):
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        raise AssertionError("Database access is outside this check")
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


old = read(HERE / "artifact_manifest.json")["artifacts"]
old_matches = {name: digest(Path(name)) == value for name, value in old.items()}
assert all(old_matches.values()), "Old static-stage artifacts changed"
capture_pins = read(LIVE / "producer_and_contract_pins.json")
capture_matches = {name: digest(Path(name)) == value for name, value in capture_pins.items()}
assert all(capture_matches.values()), "Captured producer or contract changed"

preserved = read(HERE / "probe_preservation_after.json")
tracked_matches = {name: digest(ROOT / name) == value
                   for name, value in preserved["tracked_workspace_hashes"].items()}
protected_matches = {name: digest(ROOT / name) == value["expected"]
                     for name, value in preserved["protected"].items()}
g1_dir = ROOT / "claude methods/_m2_smoke/g1_corporate_actions_20260909"
g1_matches = {name: digest(g1_dir / name) == value["expected"]
              for name, value in preserved["g1"].items()}
g1_paths_match = set(g1_matches) == {p.relative_to(g1_dir).as_posix() for p in g1_dir.rglob("*") if p.is_file()}
documents_match = {name: digest(ROOT / "claude methods" / name) == value
                   for name, value in preserved["documents"].items()}
assert all(tracked_matches.values()) and all(protected_matches.values())
assert all(g1_matches.values()) and g1_paths_match and all(documents_match.values())
git = lambda *args: subprocess.run(["git", *args], cwd=ROOT, check=True,
    capture_output=True, text=True, encoding="utf-8").stdout.strip()
assert not git("diff", "--cached", "--name-only")
head = git("rev-parse", "HEAD")
assert head == preserved["head"]
tracked_names = {name for name in git("ls-files", "-z").split("\0")
                 if name and (ROOT / name).is_file() and Path(name).suffix.lower() not in {".db", ".sqlite", ".sqlite3"}}
assert tracked_names == set(tracked_matches)

summary = read(LIVE / "summary.json")
receipt = read(LIVE / "attempt_1_completed.json")
assert len(list(LIVE.glob("attempt_?.json"))) == 1
assert len(list(LIVE.glob("response_*.bin"))) == 1
assert receipt["http_status"] == 401 and digest(LIVE / "response_1.bin") == receipt["raw_sha256"]
assert summary["rest_attempts_consumed"] == 1 and summary["rest_attempts_not_issued"] == 5
assert summary["automatic_resume_allowed"] is False

result = {
    "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
    "head": head, "staged_files": 0,
    "old_static_artifacts_match": old_matches,
    "captured_producer_and_contract_match": capture_matches,
    "tracked_files_checked": len(tracked_matches), "all_tracked_match": True,
    "protected_files_checked": len(protected_matches), "all_protected_match": True,
    "g1_files_checked": len(g1_matches), "all_g1_match": True, "g1_paths_match": g1_paths_match,
    "claude_documents_match": documents_match,
    "rest_attempts_consumed": 1, "rest_attempts_unissued": 5, "http_status": 401,
    "long_history_observed": False, "m2_accepted": False, "eligible": False,
    "client_restart_performed": False, "new_retry_authorized": False,
    "artifacts": {p.relative_to(HERE).as_posix(): digest(p)
                  for p in sorted(HERE.rglob("*")) if p.is_file() and p != DESTINATION},
}
with DESTINATION.open("x", encoding="utf-8", newline="\n") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(json.dumps({k: v for k, v in result.items() if k not in {
    "artifacts", "old_static_artifacts_match", "captured_producer_and_contract_match", "claude_documents_match"}}, indent=2))
print(json.dumps({"old_static_artifacts_matched": len(old_matches),
    "captured_producer_and_contract_matched": len(capture_matches), "sealed_artifacts": len(result["artifacts"])}))
