"""Independent final K1 empty-domain acceptance; disposable fixtures only."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import k1k2_progress_review as review


def main():
    buf = io.StringIO()
    with redirect_stdout(buf):
        review.main()
    rows = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    cases = {r["case"]: r for r in rows if "case" in r}
    assert len(cases) == 11
    for key, row in cases.items():
        expected = 0 if key in {
            "actual_50_plus_2_clean_36193", "warmup_both_clean",
            "warmup_missing_history_not_consumed", "warmup_divergent_history_not_consumed"
        } else 1
        assert row["exit_code"] == expected, row
    for prefix in ("listed_after_research", "delisted_before_research"):
        clean = "\n".join(cases[prefix + "_correctly_empty"]["details"])
        dirty = "\n".join(cases[prefix + "_one_ineligible_row_in_both_views"]["details"])
        assert "MANIFEST REJECTED" in clean and "absent_symbols=0" in clean
        assert "correctly_empty=1" in clean
        assert "ineligible_records" in dirty and "2025-06-10" in dirty
    assert rows[-1]["production_unchanged"]
    print(json.dumps({"independent_research_and_K2_cases": 11, "passed": 11}))

    f = review.fixture
    before = review.metadata()
    with tempfile.TemporaryDirectory(prefix="codex_empty_domain_acceptance_") as directory:
        tmp = Path(directory).resolve()
        at, ah, st, sh, baseline = [tmp / name for name in
                                  ("at.db", "ah.db", "st.db", "sh.db", "baseline.json")]
        manifest = tmp / "diagnostic_ipo.csv"
        manifest.write_text(
            "symbol,stratum,list_date,delist_date\n"
            "BJ920002,ordinary_control,2024-05-30,\n"
            "SH000300,benchmark,,\nSH000001,benchmark,,\n", encoding="utf-8")
        # Expected records derived directly from the declared dates, not gate helpers.
        plan = {"BJ920002": [d for d in f.WINDOW if d >= "2024-05-30"],
                "SH000300": f.WARM + f.WINDOW, "SH000001": f.WARM + f.WINDOW}
        f.build_views(at, ah, {"SH000300": f.WINDOW[:2]})

        def cli(args):
            r = subprocess.run([sys.executable, "-B", "-X", "utf8",
                                str(review.CLOSURE / "staging_gate.py")] + args,
                               capture_output=True, text=True, encoding="utf-8", check=False)
            return r.returncode, r.stdout + r.stderr

        code, out = cli(["snapshot", "--archive-trading", str(at), "--archive-history", str(ah),
                         "--calendar", str(f.CALENDAR), "--baseline-out", str(baseline)])
        assert code == 0, out
        protected = {p: f.sha(p) for p in (at, ah, baseline, f.CALENDAR, f.REAL_MANIFEST)}
        args = ["validate", "--staging-trading", str(st), "--staging-history", str(sh),
                "--archive-trading", str(at), "--archive-history", str(ah),
                "--calendar", str(f.CALENDAR), "--baseline", str(baseline),
                "--pilot-manifest", str(manifest), "--pricing-basis", "none",
                "--history-basis", "none", "--transformation", "identity",
                "--warmup-consumers", "both", "--warmup-sessions", "250", "--warmup-required"]

        def status(output, gate):
            line = next(s.strip() for s in output.splitlines()
                        if s.strip().split() and s.strip().split()[0] == gate)
            return re.search(r"\s(PASS|FAIL|UNKNOWN|NOT_APPLICABLE)(?:\s|$)", line)[1]

        f.build_views(st, sh, plan)
        code, out = cli(args)
        assert code == 1, out
        assert all(status(out, gate) == "PASS" for gate in ("M1", "M2", "M3", "W1_pricing", "W1_history", "W2")), out
        assert status(out, "V3b") == "FAIL", out
        assert "correctly_empty=1 empty_domain=allow" in out, out
        assert "required gate(s) not satisfied: V3b" in out, out
        print(json.dumps({"case": "IPO_empty_warmup", "coverage_gates": "PASS",
                          "V3b": "FAIL", "only_blocking_gate": "V3b"}))

        bad = {s: list(ds) for s, ds in plan.items()}
        bad["BJ920002"].append(f.WARM[5])
        f.build_views(st, sh, bad)
        code, out = cli(args)
        assert code == 1 and all(status(out, gate) == "FAIL" for gate in ("W1_pricing", "W1_history")), out
        assert "ineligible_records" in out and f.WARM[5] in out, out
        print(json.dumps({"case": "IPO_ineligible_warmup_in_both_views", "W1_pricing": "FAIL",
                          "W1_history": "FAIL", "injected_date": f.WARM[5]}))
        assert all(f.sha(p) == h for p, h in protected.items())
    assert before == review.metadata()
    print(json.dumps({"bounded_acceptance": "PASS", "production_unchanged": True,
                      "protected_inputs_unchanged": True}))


if __name__ == "__main__":
    main()
