"""Independent bounded P1 module review; synthetic changes only in temporary copies."""
import contextlib
import copy
import hashlib
import io
import json
import runpy
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / 'claude methods' / '_m2_smoke'
REVIEW = Path(__file__).resolve().parent
V3 = SMOKE / 'revision_20260908T082833Z_r2abc_v2'
BLOCKED = []

def audit(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.bind',
                 'sqlite3.connect', 'subprocess.Popen', 'os.system'}:
        BLOCKED.append(event)
        raise RuntimeError('Codex review prohibits ' + event)

sys.addaudithook(audit)
sys.dont_write_bytecode = True
sys.path.insert(0, str(SMOKE))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def snapshot():
    files = [p for p in SMOKE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += list((ROOT / 'claude methods').glob('M2*.md'))
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in files}

def db_stats():
    return {n: {'size': (ROOT/n).stat().st_size, 'mtime_ns': str((ROOT/n).stat().st_mtime_ns)}
            for n in ['market_history.sqlite3', 'market_history.sqlite3-shm',
                      'market_history.sqlite3-wal', 'trading_local.sqlite3']}

before, db_before = snapshot(), db_stats()
suite_out = io.StringIO()
with contextlib.redirect_stdout(suite_out):
    try:
        runpy.run_path(str(SMOKE / 'test_basis_record.py'), run_name='__main__')
        suite_exit = 0
    except SystemExit as exc:
        suite_exit = exc.code

import basis_record as br
probes = []

def probe(name, fn):
    try:
        ok, detail = fn()
        probes.append({'name': name, 'passed': bool(ok), 'detail': detail})
    except Exception as exc:
        probes.append({'name': name, 'passed': False,
                       'detail': 'unexpected %s: %s' % (type(exc).__name__, exc)})

def reject_mutation(mutator):
    with tempfile.TemporaryDirectory(prefix='codex_basis_review_') as temp:
        revision = Path(temp) / V3.name
        shutil.copytree(V3, revision)
        mutator(revision)
        try:
            v = br.verify(revision)
        except br.VerificationError as exc:
            return True, {'rejected': exc.code}
        records = br.derive_records(v['manifest'], v['checks'],
            upstream_pins=v['upstream_producer_pins']['declared'], pins_stale=v['pins_stale'])
        return False, {'accepted': True, 'verified_inputs': len(v['verified_inputs']),
                       'transforms': {n:r['adapter_transform'] for n,r in records.items()}}

def remove_hashes(revision):
    p = read(revision/'PROVENANCE.json')
    p.pop('input_hashes', None)
    write(revision/'PROVENANCE.json', p)

def partial_hashes(revision):
    p = read(revision/'PROVENANCE.json')
    p['input_hashes'] = {'capture_manifest.json': p['input_hashes']['capture_manifest.json']}
    write(revision/'PROVENANCE.json', p)
    ref = revision/'reference'/'reference_extract.json'
    a = read(ref); a['content_sha256'] = '0'*64; write(ref,a)

probe('missing v3 input_hashes must refuse', lambda: reject_mutation(remove_hashes))
probe('partial input_hashes plus unverified reference drift must refuse',
      lambda: reject_mutation(partial_hashes))

def guard(path):
    try:
        value = br._guard_output_path(path)
        return False, {'accepted_path_without_writing': str(value)}
    except br.VerificationError as exc:
        return True, {'rejected': exc.code}

probe('reviewer directory is not an output root',
      lambda: guard(REVIEW/'basis_eval_guard_probe_never_created'))
probe('case-insensitive protected prefix cannot be bypassed',
      lambda: guard(SMOKE/'EVIDENCE_codex_guard_probe_never_created'/'basis_eval_probe'))

v = br.verify(V3)
baseline_records = br.derive_records(v['manifest'], v['checks'],
    upstream_pins=v['upstream_producer_pins']['declared'])

def derive_mutation(mutate):
    m, c = copy.deepcopy(v['manifest']), copy.deepcopy(v['checks'])
    mutate(m,c)
    record = br.derive_records(m,c,upstream_pins=v['upstream_producer_pins']['declared'])['sh600011']
    return record['adapter_transform']=='unknown', {
        'adapter_transform':record['adapter_transform'], 'reasons':record['adapter_transform_reasons']}

def bad_attempt_positions(m,c):
    m['requests'][0]['attempt_positions'] = [99999]

def bad_attempt_url(m,c):
    m['attempts'][0]['url'] = 'https://example.invalid/unrelated'

def no_replay_urls(m,c):
    c['deterministic']['checks'] = [x for x in c['deterministic']['checks'] if x['id']!='R1urls']

probe('out-of-range attempt_positions cannot support transform',
      lambda: derive_mutation(bad_attempt_positions))
probe('attempt URL mismatch cannot support transform',
      lambda: derive_mutation(bad_attempt_url))
probe('missing replay URL evidence cannot support transform',
      lambda: derive_mutation(no_replay_urls))

def units():
    actual = {n:r['volume_unit'] for n,r in baseline_records.items()}
    return actual=={'sh600011':'share','bj920000':'share','sh000300':'unknown'}, actual
probe('retained U2 stock volume units are preserved', units)

def consumed_reference():
    hashes = v['consumed_artifacts']
    return 'reference/reference_extract.json' in hashes, {'consumed_keys':list(hashes),
        'reference_was_hashed': 'reference/reference_extract.json' in v['verified_inputs']}
probe('consumed_artifacts records reference file actually hashed', consumed_reference)

def mixed_module():
    a = copy.deepcopy(baseline_records['sh600011']); b = copy.deepcopy(a)
    b['record_producer']['module_sha256'] = '0'*64
    result = br.evaluate_view([a,b])
    return ('incomparable_record_producers' in result['reasons'] and result.get('comparable_record_producers') is False), result
probe('view distinguishes mixed record-producer identities', mixed_module)

def false_paths():
    results=[]
    for basis in ['unverified','unadjusted','adjusted','inconsistent','invented',None]:
        a=copy.deepcopy(baseline_records['sh600011']);a['vendor_basis']=basis
        results.append(br.evaluate(a))
    return all(x['eligible'] is False for x in results), results
probe('all vendor-basis assertions remain ineligible', false_paths)

stored = read(SMOKE/'basis_eval_revision_20260908T082833Z_r2abc_v2__br_r1_r4'/'basis_records.json')
probe('stored output digest is valid', lambda: (
    br.cap.canonical_sha256({k:stored[k] for k in ['records','eligibility','view_eligibility']})
    == stored['records_sha256'], stored['records_sha256']))


# R2 additions: preserve the original reviewer and its output; the diagnostic name
# changed intentionally from mixed_view to incomparable_record_producers.
def inventory_variants():
    outcomes=[]
    for value in ({}, [], None, 'invalid'):
        def edit(revision):
            p=read(revision/'PROVENANCE.json');p['input_hashes']=value
            write(revision/'PROVENANCE.json',p)
        outcomes.append(reject_mutation(edit))
    return all(x[0] for x in outcomes),outcomes
probe('empty and malformed complete-schema inventories refuse',inventory_variants)

def omission_variants():
    outcomes=[]
    for key in v['verified_inputs']:
        def edit(revision):
            p=read(revision/'PROVENANCE.json');del p['input_hashes'][key]
            write(revision/'PROVENANCE.json',p)
        outcomes.append((key,reject_mutation(edit)))
    return all(x[1][0] for x in outcomes),outcomes
probe('each of seven required inputs is mandatory',omission_variants)

def association_variants():
    results=[]
    for positions in ([0,0],[-1],[True],[1],[]):
        results.append(derive_mutation(lambda m,c: m['requests'][0].update(attempt_positions=positions)))
    for count in (0,2,True):
        results.append(derive_mutation(lambda m,c: m['requests'][0].update(attempt_count=count)))
    return all(x[0] for x in results),results
probe('duplicate negative boolean cross-request positions and bad counts refuse claims',association_variants)

def replay_variants():
    results=[]
    for status,urls in [('FAIL',None),('PASS',[]),('PASS',['https://example.invalid/other'])]:
        def edit(m,c):
            entry=next(x for x in c['deterministic']['checks'] if x['id']=='R1urls')
            entry['status']=status
            if urls is not None:entry['measured']=urls
        results.append(derive_mutation(edit))
    return all(x[0] for x in results),results
probe('failed empty and unrelated replay evidence refuses transform',replay_variants)

def identity_variants():
    results=[]
    for field in ('module_sha256','record_schema_version','derivation_rules_version','evaluator_rules_version'):
        a=copy.deepcopy(baseline_records['sh600011']);b=copy.deepcopy(a)
        b['record_producer'][field]='unknown_version'
        result=br.evaluate_view([a,b]);results.append((field,result))
    return all(x['eligible'] is False and x['comparable_record_producers'] is False and 'incomparable_record_producers' in x['reasons'] for _,x in results),results
probe('every record-producer identity dimension prevents pooling',identity_variants)

def path_variants():
    results=[]
    for part in ('ReViSiOn_probe','RECEIPTS_probe','Frozen_Impl_probe','_M2_CODEX_REVIEW'):
        results.append(guard(SMOKE/part/'basis_eval_probe_never_created'))
    results.append(guard(SMOKE.parent/'basis_eval_probe_never_created'))
    with tempfile.TemporaryDirectory(prefix='codex_basis_root_') as temp:
        p=Path(temp)/'basis_eval_new'
        results.append(guard(p))
        allowed=br._guard_output_path(p,allow_scratch_root=True)==p.resolve()
    return all(x[0] for x in results) and allowed,{'refusals':results,'explicit_temp_allowed':allowed}
probe('canonical root and case-insensitive protection with bounded temp opt-in',path_variants)

def ledger_matches():
    actual={k:sha(V3/k) for k in v['consumed_artifacts']}
    p=read(SMOKE/'basis_eval_revision_20260908T082833Z_r2abc_v2__br_r1_r4'/'PROVENANCE.json')
    ok=(v['consumed_artifacts']==p['consumed_artifacts'] and all(p['consumed_artifacts'][k]['sha256']==h for k,h in actual.items()))
    return ok,{'revision_files':len(actual),'ledger_equal':v['consumed_artifacts']==p['consumed_artifacts']}
probe('new output ledger matches all nine selected-revision files',ledger_matches)

def fresh_output():
    with tempfile.TemporaryDirectory(prefix='codex_basis_fresh_') as temp:
        result=br.write_evaluation(V3,temp,allow_scratch_root=True)
        fresh=read(result['output_dir']/'basis_records.json')
        keys=['records','eligibility','view_eligibility','records_sha256']
        equal=all(fresh[k]==stored[k] for k in keys)
        first_sha=sha(result['output_dir']/'basis_records.json')
        try:br.write_evaluation(V3,temp,allow_scratch_root=True)
        except br.VerificationError:refused=True
        else:refused=False
        return equal and refused and first_sha==sha(result['output_dir']/'basis_records.json'),{'stored_equals_fresh':equal,'overwrite_refused':refused,'digest':fresh['records_sha256']}
probe('fresh bounded writer reproduces delivered output and refuses overwrite',fresh_output)

previous=read(REVIEW/'basis_record_codex_review_results.json')['protected_after']
prior_drift=[p for p,h in previous.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
probe('previous protected snapshot differs only in two authorized source files',lambda:(set(prior_drift)=={'claude methods/_m2_smoke/basis_record.py','claude methods/_m2_smoke/test_basis_record.py'},prior_drift))

after, db_after = snapshot(), db_stats()
changed = sorted(p for p in set(before)|set(after) if before.get(p)!=after.get(p))
result = {'suite_exit':suite_exit,'suite_stdout':suite_out.getvalue(),'probes':probes,
          'protected_count':len(before),'changed_protected':changed,
          'database_metadata_unchanged':db_before==db_after,'blocked_operations':BLOCKED,
          'protected_before':before,'protected_after':after,'database_before':db_before,
          'database_after':db_after}
write(REVIEW/'basis_record_codex_review_r2_results.json', result)
print(suite_out.getvalue())
print(json.dumps({k:v for k,v in result.items() if k not in
    {'suite_stdout','protected_before','protected_after','database_before','database_after'}},
    ensure_ascii=False,indent=2))
