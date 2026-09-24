"""Explicitly account for the two authorized ignore entries; retain V1 FAIL."""
import hashlib
import json
from pathlib import Path
import sys
import verify_phase_preservation as previous


def review():
    result = previous.review()
    raw = (previous.ROOT / ".gitignore").read_bytes()
    suffix = (b"/claude methods/_m2_codex_implementation_20260910/warmup3_capture/\n"
              b"/claude methods/_m2_codex_implementation_20260910/contract_v2_runs/\n")
    expected = json.loads((previous.HERE / "baseline/tracked_full_names_sha256.json").read_bytes())[".gitignore"]
    exact = raw.endswith(suffix) and hashlib.sha256(raw[:-len(suffix)]).hexdigest() == expected
    other_ok = (all(v["passed"] for v in result["production_files"].values()) and
                all(v["passed"] for v in result["old_delivery_manifests"].values()) and
                result["qualification_producers"]["passed"] and
                result["tracked_files"]["test_has_only_expected_two_assertion_changes"] and
                result["tracked_files"]["unexpected"] == [".gitignore"])
    return dict(schema="m2.preservation.v2", original_checker=result, original_checker_verdict_preserved=True,
        ignore_delta=dict(exact_append_verified=exact, before_sha256=expected, after_sha256=previous.sha(previous.ROOT / ".gitignore"),
            purpose="Keep new captured data and execution receipts out of Git", appended_lines=suffix.decode().splitlines()),
        passed=bool(exact and other_ok), producer_sha256=previous.sha(__file__),
        network_requests=0, production_sqlite_connections=0, live_trading=False)


if __name__ == "__main__":
    path = Path(sys.argv[1]).resolve()
    if path.parent != previous.HERE or path.exists():
        raise SystemExit("new phase output required")
    result = review()
    with path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"passed": result["passed"], "ignore_delta": result["ignore_delta"]}))
    raise SystemExit(0 if result["passed"] else 1)
