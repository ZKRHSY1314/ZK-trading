"""R01 - verify every artifact and transitive pin in v2_delivery_manifest.json against disk.

Read-only. Hashes files only. Writes r01_manifest_pins.json next to itself.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASE = HERE.parent / "_m2_codex_implementation_20260910"
MANIFEST = PHASE / "v2_delivery_manifest.json"
EXPECTED_MANIFEST_SHA = "eca6bea3c47ef0d37573f4b20d10d6ffe7956738a98118b7298e703142f7154e"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    actual = sha256(MANIFEST)
    out = {"manifest": str(MANIFEST), "manifest_sha256": actual,
           "manifest_sha256_expected": EXPECTED_MANIFEST_SHA,
           "manifest_matches": actual == EXPECTED_MANIFEST_SHA,
           "artifacts": [], "transitive_pins": []}
    m = json.load(open(MANIFEST, encoding="utf-8"))
    for path, rec in m["artifacts"].items():
        p = Path(path)
        row = {"path": path, "exists": p.is_file()}
        if p.is_file():
            row["sha256"] = sha256(p)
            row["bytes"] = p.stat().st_size
            row["sha256_match"] = row["sha256"] == rec.get("sha256")
            row["bytes_match"] = row["bytes"] == rec.get("bytes")
        out["artifacts"].append(row)
    for path, expected in m["transitive_evidence_pins"].items():
        p = Path(path)
        row = {"path": path, "exists": p.is_file(), "expected": expected}
        if p.is_file():
            row["sha256"] = sha256(p)
            row["match"] = row["sha256"] == expected
        out["transitive_pins"].append(row)
    a_ok = sum(1 for r in out["artifacts"] if r.get("sha256_match") and r.get("bytes_match"))
    t_ok = sum(1 for r in out["transitive_pins"] if r.get("match"))
    out["summary"] = {"artifacts_total": len(out["artifacts"]), "artifacts_ok": a_ok,
                      "transitive_total": len(out["transitive_pins"]), "transitive_ok": t_ok,
                      "run_id": m["run_id"], "row_count": m["row_count"],
                      "row_records_sha256": m["row_records_sha256"],
                      "state": m["state"], "M2_complete": m["M2_complete"]}
    json.dump(out, open(HERE / "r01_manifest_pins.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    print(json.dumps(out["summary"], indent=2))
    bad = [r for r in out["artifacts"] if not (r.get("sha256_match") and r.get("bytes_match"))]
    bad += [r for r in out["transitive_pins"] if not r.get("match")]
    for r in bad:
        print("MISMATCH:", r)
    print("manifest_matches:", out["manifest_matches"])
    return 0 if not bad and out["manifest_matches"] else 1


if __name__ == "__main__":
    sys.exit(main())
