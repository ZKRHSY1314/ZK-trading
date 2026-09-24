"""Static file preservation receipt; no project imports, network or database opens."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
METHODS = ROOT / "claude methods"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def compare(mapping, base):
    return {name: {"expected": expected, "actual": sha(base / name),
                   "match": sha(base / name) == expected}
            for name, expected in mapping.items()}


documents = ["M2_BOUNDARY2_EVIDENCE_REQUIREMENTS_DRAFT.md",
             "M2_REMAINING_DEPENDENCY_DECISIONS.md"]
document_hashes = {name: sha(METHODS / name) for name in documents}
pins = []
for name in documents:
    body = (METHODS / name).read_text(encoding="utf-8-sig")
    for path, digest in re.findall(r"\| `([^`]+)` \| `([0-9a-f]{64})` \|", body):
        resolved = METHODS / path
        actual = sha(resolved)
        pins.append({"document": name, "path": path, "expected": digest,
                     "actual": actual, "match": digest == actual})

baseline = json.loads((METHODS / "_m2_codex_review/g3_ratio_codex_review_r2b_results.json").read_text(encoding="utf-8-sig"))["protected_before"]
protected = compare(baseline, ROOT)
g1_snapshot = METHODS / "_m2_codex_review/g1_review_20260909_r3_doc1/reviewed_delivery"
g1_live = METHODS / "_m2_smoke/g1_corporate_actions_20260909"
g1_pins = {p.relative_to(g1_snapshot).as_posix(): sha(p) for p in g1_snapshot.rglob("*") if p.is_file()}
g1 = compare(g1_pins, g1_live)
g1_paths_match = set(g1_pins) == {p.relative_to(g1_live).as_posix() for p in g1_live.rglob("*") if p.is_file()}

git = lambda *args: subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
tracked = git("ls-files", "-z").split("\0")
workspace_pins = {name: sha(ROOT / name) for name in tracked if name and (ROOT / name).is_file() and not name.lower().endswith((".db", ".sqlite", ".sqlite3"))}
receipt = {
    "at_utc": datetime.now(timezone.utc).isoformat(),
    "method": "Only static file reads/hashes, non-secret document snapshots and read-only Git metadata; no project imports, datasets or databases opened, no network or services.",
    "head": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
    "git_status": git("status", "--short"), "staged": git("diff", "--cached", "--name-only"),
    "documents": document_hashes, "pins": pins,
    "pin_occurrences": len(pins), "unique_pin_paths": len({p["path"] for p in pins}),
    "all_pins_match": all(p["match"] for p in pins),
    "protected": protected, "protected_count": len(protected),
    "all_protected_match": all(p["match"] for p in protected.values()),
    "g1": g1, "g1_count": len(g1), "g1_paths_match": g1_paths_match,
    "all_g1_match": all(p["match"] for p in g1.values()),
    "tracked_workspace_hashes": workspace_pins,
}
for name in documents:
    original = (METHODS / name).read_bytes()
    frozen = OUT / ("received_" + name)
    if frozen.exists():
        assert frozen.read_bytes() == original, "Received delivery changed; preserve existing snapshot"
    else:
        frozen.write_bytes(original)
baseline_out = OUT / "takeover_baseline.json"
if baseline_out.exists():
    earlier = json.loads(baseline_out.read_text(encoding="utf-8"))
    receipt["tracked_unchanged_since_baseline"] = earlier["tracked_workspace_hashes"] == workspace_pins
    receipt["documents_unchanged_since_baseline"] = earlier["documents"] == document_hashes
    destination = OUT / "takeover_final_verification.json"
else:
    destination = baseline_out
destination.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
summary = {k: v for k, v in receipt.items() if k not in {"pins", "protected", "g1", "tracked_workspace_hashes", "git_status", "method"}}
print(json.dumps(summary, ensure_ascii=False, indent=2))
assert receipt["all_pins_match"] and receipt["all_protected_match"] and receipt["all_g1_match"] and g1_paths_match
assert not receipt["staged"]
assert receipt.get("tracked_unchanged_since_baseline", True)
assert receipt.get("documents_unchanged_since_baseline", True)
