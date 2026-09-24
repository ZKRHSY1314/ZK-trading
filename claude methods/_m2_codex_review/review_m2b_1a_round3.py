"""Independent round-3 acceptance probes. Synthetic/offline; no production DB opens.

Reuses fixture data, not the delivered test case functions. Never invokes the armed CLI.
All writable data is in one task-owned TemporaryDirectory. Old reviewer files stay intact.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'claude methods' / '_m2_smoke'))
import test_m2_smoke as f
import smoke_capture as cap
import smoke_checks as chk
import requests


def tree(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def check(result, name):
    return next(c for c in result['deterministic']['checks'] if c['id'] == name)


def verdict(result):
    return result['deterministic']['verdicts']['capability']


def new_run(root):
    clock = f.Clock()
    run = cap.SmokeRun('20260908T010000Z', out_root=root / 'capture',
                      evidence_root=root / 'evidence', clock=clock, sleeper=clock.advance)
    return run, clock


def pipeline(run, scene):
    f.FAKE_REPLAY_DATES = {k: [r['date'] for r in rows]
                           for k, rows in scene['live'].items()}
    with f.synthetic_preflight(scene['extract']):
        return run.run_pipeline(session=f.FakeSession(f.wire_handler(scene)),
                                requests_module=requests, supervise_jobs=False,
                                routine=f.FAKE_ROUTINE, routine_sha256=f.FAKE_ROUTINE_SHA,
                                racer_factory=scene['racer'], replay_fn=f.fake_replay)


def join_new_workers(before):
    for t in set(threading.enumerate()) - before:
        t.join(5)
        assert not t.is_alive(), 'synthetic worker did not terminate: ' + t.name


def late_stage(root, scene, failure):
    run, clock = new_run(root)
    entered, release = threading.Event(), threading.Event()
    original = Path.write_bytes
    prefix = 'failed_' if failure else ''
    expected_name = prefix + f.PLANNED[0]['filename']
    before = set(threading.enumerate())
    seen = []

    def paused(path, data):
        if path.parent.name.endswith(cap.PENDING_SUFFIX) and path.name.endswith(expected_name):
            entered.set()
            clock.advance(10000)
            assert release.wait(5), 'review did not release staged write'
        return original(path, data)

    overrides = {1: lambda item: f.FakeHttpResponse(404, b'absent', item['url'])} if failure else {}
    with f.synthetic_preflight(scene['extract']), patch.object(Path, 'write_bytes', paused):
        try:
            manifest = run.capture(session=f.FakeSession(f.wire_handler(scene, override=overrides,
                                                                       seen=seen)),
                                   requests_module=requests, supervise_jobs=True, poll_sec=.01,
                                   routine=f.FAKE_ROUTINE, routine_sha256=f.FAKE_ROUTINE_SHA,
                                   racer_factory=scene['racer'])
            assert entered.is_set() and run.store.sealed
            assert manifest['run_status'] == 'aborted' and seen == [1]
            sealed_tree = tree(run.out_root)
        finally:
            release.set()
            join_new_workers(before)
    assert tree(run.out_root) == sealed_tree, 'late staged write changed sealed evidence'
    assert not list((run.out_root / 'raw').iterdir())
    return {'failed_response': failure, 'requests': seen, 'sealed_tree_unchanged': True}


def blocked_finalization(root, scene, rename):
    run, clock = new_run(root)
    entered, release = threading.Event(), threading.Event()
    before = set(threading.enumerate())
    original_write, original_rename = Path.write_bytes, cap.os.rename
    captured_tree = {}

    def pause():
        captured_tree.update(tree(run.out_root))
        entered.set()
        clock.advance(cap.FINALIZE_BUDGET_SEC + 1)
        assert release.wait(5), 'review did not release finalization'

    def write(path, data):
        if not rename and path.name.endswith('_owner_checks.json'):
            pause()
        return original_write(path, data)

    def move(source, destination):
        if rename and Path(source) == run.out_root:
            pause()
        return original_rename(source, destination)

    with patch.object(Path, 'write_bytes', write), patch.object(cap.os, 'rename', move):
        try:
            result = pipeline(run, scene)
            assert entered.is_set()
            assert result['phase'] == 'incomplete_finalization'
            assert result['finalize']['status'] == 'abandoned'
            assert cap.exit_code_for(result) == 1
        finally:
            release.set()
            join_new_workers(before)
    location = run.evidence_dir if run.evidence_dir.exists() else run.out_root
    assert tree(location) == captured_tree
    assert run.evidence_dir.exists() is rename
    assert not (run.evidence_dir.exists() and run.out_root.exists())
    return {'operation': 'retention rename' if rename else 'staged checks write',
            'status': result['finalize']['status'], 'contents_unchanged_after_release': True}


def main():
    results = {}
    with patch.object(requests.Session, 'request', side_effect=AssertionError('offline review')), \
            cap.db_guard('no database opens in the independent round-3 review'), \
            tempfile.TemporaryDirectory(prefix='m2b_codex_round3_') as temporary:
        root = Path(temporary)
        scene = f.scenario(root / 'scene')
        run, manifest, _ = f.capture_scene(root / 'baseline', scene, f.wire_handler(scene))
        baseline = f.check_captured(run, manifest, scene)
        assert verdict(baseline) == 'PASS'
        results['baseline'] = {'capability': 'PASS', 'attempts': len(manifest['attempts'])}

        results['R1'] = [late_stage(root / ('late_%s' % flag), scene, flag)
                         for flag in (False, True)]
        results['R2_blocked'] = [blocked_finalization(root / ('blocked_%s' % flag), scene, flag)
                                 for flag in (False, True)]
        delayed, clock = new_run(root / 'overrun')
        cleanup = delayed.cleanup

        def late_cleanup(**kwargs):
            clock.advance(cap.FINALIZE_BUDGET_SEC + 1)
            return cleanup(**kwargs)

        with patch.object(delayed, 'cleanup', late_cleanup):
            record = pipeline(delayed, scene)
        assert record['finalize']['status'] == 'overrun'
        assert record['finalize']['remaining_sec'] < 0 and cap.exit_code_for(record) == 1
        results['R2_returning'] = {'status': record['finalize']['status'],
                                  'remaining_sec': record['finalize']['remaining_sec'], 'exit': 1}

        variants = {
            'empty': lambda m: m.update(attempts=[]),
            'truncated': lambda m: m['attempts'].pop(),
            'wrong_terminal': lambda m: m['attempts'][0].update(status=503),
            'wrong_binding': lambda m: m['requests'][0].update(attempt_positions=[2]),
            'wrong_source': lambda m: m['attempts'][0].update(source='substitute'),
            'wrong_url': lambda m: m['attempts'][0].update(url='https://example.invalid/'),
        }
        observed = {}
        for name, alter in variants.items():
            bad = copy.deepcopy(manifest)
            alter(bad)
            result = f.check_captured(run, bad, scene)
            assert check(result, 'T3')['status'] == 'FAIL' and verdict(result) == 'FAIL', name
            observed[name] = 'FAIL'
        bad = copy.deepcopy(manifest)
        bad['attempts'] = []
        (run.out_root / 'capture_manifest.json').write_text(json.dumps(bad), encoding='utf-8')
        replay = chk.replay(run.out_root, replay_fn=f.fake_replay, routine=f.FAKE_ROUTINE,
                            routine_sha256=f.FAKE_ROUTINE_SHA, racer_factory=scene['racer'])
        assert verdict(replay) == 'FAIL' and check(replay, 'T3')['status'] == 'FAIL'
        results['R3_corruption'] = dict(observed, retained_replay='FAIL')

        retry, _ = new_run(root / 'retry')
        calls, disk = [], []
        ordinary = f.wire_handler(scene)

        def retry_handler(url):
            if url == f.PLANNED[0]['url']:
                calls.append(url)
                disk.append(json.loads((retry.out_root / 'capture_manifest.json').read_text('utf-8')))
                if len(calls) < 3:
                    return f.FakeHttpResponse(503, b'busy', url)
            return ordinary(url)

        with f.synthetic_preflight(scene['extract']):
            retries = retry.capture(session=f.FakeSession(retry_handler), requests_module=requests,
                                    supervise_jobs=False, routine=f.FAKE_ROUTINE,
                                    routine_sha256=f.FAKE_ROUTINE_SHA, racer_factory=scene['racer'])
        assert len(calls) == 3 and len(retries['attempts']) == 7
        assert disk[1]['attempts'][0]['transport_outcome'] == 'retryable'
        assert disk[1]['attempts'][1]['finished_at_monotonic'] is None
        assert verdict(f.check_captured(retry, retries, scene)) == 'PASS'
        results['R3_durable_retries'] = {'attempts': 7, 'previous_attempt_durable_before_retry': True}

        outcomes = []
        for index, status in ((4, 404), (4, 410), (5, 404), (5, 410), (5, 403), (5, 429)):
            modified, evidence, _ = f.capture_scene(root / ('bj_%s_%s' % (index, status)), scene,
                f.wire_handler(scene, override={index: lambda item, code=status:
                                                f.FakeHttpResponse(code, b'absent', item['url'])}))
            result = f.check_captured(modified, evidence, scene)
            value = verdict(result)
            expected = ('PASS_WITH_DOCUMENTED_BJ_NON_SERVICE' if index == 4 else
                        'INCONCLUSIVE' if status in (404, 410) else 'FAIL')
            assert value == expected, (index, status, value)
            bj_checks = [c for c in result['deterministic']['checks'] if c.get('symbol') == 'bj920000']
            if index == 5 and status in (404, 410):
                assert any(c['id'] == 'D2' for c in bj_checks), 'served history checks disappeared'
            outcomes.append({'index': index, 'status': status, 'capability': value})
        results['R4'] = outcomes
    print(json.dumps(results, indent=2))
    print('Independent round-3 probes: PASS; all task-owned temporary data removed.')


if __name__ == '__main__':
    main()
