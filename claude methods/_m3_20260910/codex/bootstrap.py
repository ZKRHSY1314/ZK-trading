"""M3 baseline only: byte hashes, static sources, read-only Git; no SQLite."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tomllib

HERE = Path(__file__).resolve().parent
PHASE = HERE.parent
CM = PHASE.parent
ROOT = CM.parent
M2 = CM / '_m2_codex_implementation_20260910'


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write_new(path, obj):
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main():
    base = PHASE / 'baseline'
    base.mkdir(exist_ok=False)
    closure = M2 / 'closure_review/completion.json'
    c = json.loads(closure.read_bytes())
    assert sha(closure) == '6e3828ef41d344dadbf409558d82faa3bcb702593442fa28a7653dc173383ca7'
    for name, p in c['immutable_artifacts'].items():
        assert sha(name) == p['sha256'], name
    spec = importlib.util.spec_from_file_location('m3_m2_pin_review', M2 / 'closure_review/verify_final.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pins = mod.verify_inputs()
    prod_baseline = json.loads((M2 / 'baseline/production_files_before.json').read_bytes())
    prod = {}
    for name, item in prod_baseline['files'].items():
        p = Path(name)
        if item.get('exists') is False:
            assert not p.exists(), name
            prod[name] = dict(exists=False)
        else:
            st = p.stat(); value = sha(p); after = p.stat()
            assert value == item['sha256'] and st.st_mtime_ns == after.st_mtime_ns == item['mtime_ns'] and st.st_size == after.st_size == item['size'], name
            prod[name] = dict(exists=True, sha256=value, size=st.st_size, mtime_ns=st.st_mtime_ns)
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    tracked_pins = {n:sha(ROOT / n) if (ROOT / n).is_file() else None for n in tracked if n}
    status = subprocess.run(['git','status','--short'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
    prior_state_path = CM / '_m2_codex_review/m2_claude_coordination_state.json'
    prior = prior_state_path.read_bytes()
    assert hashlib.sha256(prior).hexdigest() == c['coordination_snapshot']['sha256']
    (base / 'm2_coordination_before.json').write_bytes(prior)
    a_path = Path(r'C:\Users\Administrator\.codex\automations\claude\automation.toml')
    automation = tomllib.loads(a_path.read_text(encoding='utf-8'))
    write_new(base / 'automation_before.json', automation)
    write_new(base / 'tracked_files_before.json', tracked_pins)
    write_new(base / 'production_files_before.json', prod)
    write_new(base / 'm2_inputs_before.json', dict(completion_sha256=sha(closure), immutable_artifacts=c['immutable_artifacts'], pin_checks=pins))
    (base / 'git_status_before.txt').write_text(status.stdout, encoding='utf-8')
    report = dict(schema='m3.bootstrap.v1', at_utc=datetime.now(timezone.utc).isoformat(),
        user_instruction='开始M3吧，一样的流程', M2_verified=True, M3_complete=False,
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        tracked_files=len(tracked_pins), production_positions=len(prod),
        no_new_m3_source_preexists=not (ROOT / 'backend/app/research/m3_labels.py').exists() and not (ROOT / 'backend/tests/test_m3_labels.py').exists(),
        source_snapshot={str(ROOT/n):sha(ROOT/n) for n in (
            'backend/app/learning/phase_replay.py','backend/app/learning/structure_scoring.py',
            'backend/app/agent_control/outcome_labeling.py','backend/app/research/offhour.py',
            'claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md','AGENTS.md','CODEX_CLAUDE_COLLABORATION.md')},
        policy_or_case_counts_not_selected=True, production_sqlite_connections=0, market_requests=0, live_trading=False)
    assert report['no_new_m3_source_preexists']
    write_new(base / 'baseline.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
