"""M3 read-only preservation check against the recorded start-of-stage baseline.

New M3 files are allowed, but no pre-existing tracked source or frozen M2 artifact
may change in M3-01. This creates one new receipt, never updates the baseline.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PHASE = HERE.parent
ROOT = PHASE.parents[1]


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def review():
    old = read(PHASE / 'baseline/m2_inputs_before.json')
    groups = dict(old['pin_checks']['groups'])
    groups['m2_closure_artifacts'] = old['immutable_artifacts']
    problems = []
    counts = {}
    for group, entries in groups.items():
        counts[group] = len(entries)
        for name, pin in entries.items():
            if not Path(name).is_file() or sha(name) != pin['sha256']:
                problems.append(dict(group=group, path=name))
    closure = ROOT / 'claude methods/_m2_codex_implementation_20260910/closure_review/completion.json'
    if sha(closure) != old['completion_sha256']:
        problems.append(dict(group='m2_completion', path=str(closure)))
    prior_state = ROOT / 'claude methods/_m2_codex_review/m2_claude_coordination_state.json'
    if sha(prior_state) != sha(PHASE / 'baseline/m2_coordination_before.json'):
        problems.append(dict(group='m2_coordination', path=str(prior_state)))
    tracked = read(PHASE / 'baseline/tracked_files_before.json')
    for name, expected in tracked.items():
        path = ROOT / name
        actual = sha(path) if path.is_file() else None
        if actual != expected:
            problems.append(dict(group='preexisting_tracked_file', path=name))
    production = {}
    for name, expected in read(PHASE / 'baseline/production_files_before.json').items():
        path = Path(name)
        if not expected['exists']:
            passed = not path.exists()
        elif not path.is_file():
            passed = False
        else:
            st = path.stat(); digest = sha(path); after = path.stat()
            passed = (st.st_size == after.st_size == expected['size'] and
                      st.st_mtime_ns == after.st_mtime_ns == expected['mtime_ns'] and
                      digest == expected['sha256'])
        production[name] = dict(passed=passed)
        if not passed:
            problems.append(dict(group='production_file', path=name))
    return dict(schema='m3.preservation.v1', checked_at_utc=datetime.now(timezone.utc).isoformat(),
                passed=not problems, problems=problems, pin_group_counts=counts,
                existing_tracked_checked=len(tracked), production_positions=production,
                baseline_policy='new M3-01 files only; pre-existing tracked source and frozen M2 bytes unchanged',
                producer_sha256=sha(__file__), production_sqlite_connections=0, network_requests=0)


if __name__ == '__main__':
    out = Path(sys.argv[1]).resolve()
    if not out.is_relative_to(HERE) or out.exists():
        raise SystemExit('new Codex-owned receipt path required')
    result = review()
    with out.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({k:result[k] for k in ('passed','problems','existing_tracked_checked','pin_group_counts')}))
    raise SystemExit(0 if result['passed'] else 1)
