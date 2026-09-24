"""Read-only/offline review of M2b-1a closure round 2.

All response bodies and writes below are synthetic, confined to task-owned temporary
directories. No armed CLI, production database access, or real HTTP requests.
"""
from __future__ import annotations

import copy
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
import transport as tp
import requests


def verdict(result):
    return result['deterministic']['verdicts']['capability']


def case_check(result, name):
    return [c for c in result['deterministic']['checks'] if c['id'] == name]


def pipeline(root, scene, *, cleanup_delay=0):
    clock = f.Clock()
    run = cap.SmokeRun('20260907T010000Z', out_root=root / 'capture',
                       evidence_root=root / 'evidence', clock=clock, sleeper=clock.advance)
    f.FAKE_REPLAY_DATES = {k: [r['date'] for r in v] for k, v in scene['live'].items()}
    original = run.cleanup

    def slow_cleanup(**kwargs):
        clock.advance(cleanup_delay)
        return original(**kwargs)

    with f.synthetic_preflight(scene['extract']), patch.object(run, 'cleanup', slow_cleanup):
        result = run.run_pipeline(session=f.FakeSession(f.wire_handler(scene)),
                                  requests_module=requests, supervise_jobs=False,
                                  routine=f.FAKE_ROUTINE, routine_sha256=f.FAKE_ROUTINE_SHA,
                                  racer_factory=scene['racer'], replay_fn=f.fake_replay)
    return result, run


def main():
    results = {'closed': {}, 'remaining': {}}
    # Stronger than a socket-host guard: also disallow HTTP via loopback proxies.
    with patch.object(requests.Session, 'request', side_effect=AssertionError('offline review')):
        clock, calls = f.Clock(), []

        def tls(url):
            calls.append(url)
            raise requests.exceptions.SSLError('synthetic TLS failure')

        live = cap.LiveSinaTransport(f.FakeSession(tls), deadline=cap.Deadline(100, clock=clock),
                                    requests_module=requests, clock=clock)
        paced = tp.PacedTransport(live, clock=clock, sleeper=clock.advance,
                                  min_interval=1.5, ceiling=15)
        try:
            paced.get_with_retries(f.PLANNED[0]['url'], source='sina')
        except tp.TransportError as exc:
            assert len(calls) == 1 and not exc.retryable
            results['closed']['TLS'] = {'calls': len(calls), 'retryable': exc.retryable}

        stops = []
        for status in (403, 429):
            clock, calls = f.Clock(), []

            class Stop(f.FakeHttpResponse):
                def iter_content(self, chunk_size):
                    raise AssertionError('stop body must not be read')
                    yield b''

            def handler(url):
                calls.append(url)
                return Stop(status, b'', url)

            live = cap.LiveSinaTransport(f.FakeSession(handler), deadline=cap.Deadline(100, clock=clock),
                                        requests_module=requests, clock=clock)
            paced = tp.PacedTransport(live, clock=clock, sleeper=clock.advance, min_interval=1.5)
            try:
                paced.get_with_retries(f.PLANNED[0]['url'], source='sina')
            except tp.RunAborted:
                assert len(calls) == 1 and paced.aborted_reason
                stops.append({'status': status, 'calls': len(calls), 'latched': True})
        assert len(stops) == 2
        results['closed']['vendor_stops'] = stops

        with tempfile.TemporaryDirectory(prefix='m2b_codex_closure_') as temporary:
            root = Path(temporary)
            scene = f.scenario(root / 'scene')
            baseline = f.run(scene)
            assert verdict(baseline) == 'PASS'
            run, manifest, _ = f.capture_scene(root / 'normal', scene, f.wire_handler(scene))
            result = f.check_captured(run, manifest, scene)
            assert verdict(result) == 'PASS' and case_check(result, 'T3')[0]['status'] == 'PASS'
            results['closed']['paced_capture'] = [a['started_at_monotonic'] for a in manifest['attempts']]

            seen = []
            overrides = {i: lambda item: f.FakeHttpResponse(200, f.HTML, item['url']) for i in (1, 3, 4)}
            run, manifest, _ = f.capture_scene(root / 'html', scene,
                f.wire_handler(scene, override=overrides, seen=seen))
            result = f.check_captured(run, manifest, scene)
            assert seen == [1, 3] and manifest['run_status'] == 'aborted'
            assert case_check(result, 'T3')[0]['status'] == 'PASS' and verdict(result) == 'FAIL'
            results['closed']['payload_job_stop'] = seen

            invalid = copy.deepcopy(scene)
            invalid['manifest'].update(run_valid=False, invalidating_changes=['synthetic change'])
            assert verdict(f.run(invalid)) == 'FAIL'
            results['closed']['explicit_invalidation'] = 'FAIL'
            invalid = copy.deepcopy(scene)
            invalid['manifest']['reference_extract_sha256'] = '0' * 64
            invalid['extract']['content_sha256'] = 'f' * 64
            assert verdict(f.run(invalid)) == 'FAIL'
            results['closed']['reference_hash_mismatch'] = 'FAIL'
            invalid = copy.deepcopy(scene)
            for rows in invalid['extract']['rows'].values():
                for row in rows:
                    row.update(volume_unit='unknown', updated_at='2099-01-01T00:00:00Z')
            result = f.run(invalid)
            assert verdict(result) != 'PASS'
            assert result['deterministic_sha256'] != baseline['deterministic_sha256']
            results['closed']['changed_reference'] = verdict(result)
            invalid = copy.deepcopy(scene)
            invalid['manifest']['deadline']['remaining_sec'] = -1
            entered = []
            try:
                f.run(invalid, replay_fn=lambda *args: entered.append(True))
            except cap.DeadlineExceeded:
                assert not entered
                results['closed']['expired_check_entry'] = 'refused before replay'
            assert 'expired_check_entry' in results['closed']

            # Actual worker is paused at the real raw-body write, then resumes AFTER
            # capture's supervisor has aborted and finalized the manifest.
            clock = f.Clock()
            late_run = cap.SmokeRun('20260907T010000Z', out_root=root / 'race' / 'capture',
                                    evidence_root=root / 'race' / 'evidence', clock=clock,
                                    sleeper=clock.advance)
            target = late_run.out_root / 'raw' / f.PLANNED[0]['filename']
            waiting, release, written = threading.Event(), threading.Event(), threading.Event()
            original_write = Path.write_bytes
            writes = []

            def gated_write(path, data):
                if path == target:
                    waiting.set()
                    clock.advance(10000)
                    if not release.wait(5):
                        raise RuntimeError('review failed to release synthetic worker')
                    writes.append({'cancelled_at_write': late_run.cancelled})
                    value = original_write(path, data)
                    written.set()
                    return value
                return original_write(path, data)

            workers_before = set(threading.enumerate())
            with f.synthetic_preflight(scene['extract']), patch.object(Path, 'write_bytes', gated_write):
                try:
                    manifest = late_run.capture(session=f.FakeSession(f.wire_handler(scene)),
                        requests_module=requests, supervise_jobs=True, poll_sec=.01,
                        routine=f.FAKE_ROUTINE, routine_sha256=f.FAKE_ROUTINE_SHA,
                        racer_factory=scene['racer'])
                    assert waiting.is_set() and late_run.cancelled
                    assert manifest['run_status'] == 'aborted' and not target.exists()
                    before = (late_run.out_root / 'capture_manifest.json').read_bytes()
                finally:
                    release.set()
                assert written.wait(2)
                for worker in set(threading.enumerate()) - workers_before:
                    if worker.name.startswith('m2b-'):
                        worker.join(2)
                        assert not worker.is_alive(), worker.name
                assert target.exists() and writes == [{'cancelled_at_write': True}]
                assert (late_run.out_root / 'capture_manifest.json').read_bytes() == before
                results['remaining']['late_raw_write_after_finalization'] = {
                    'writes': writes, 'raw_exists_after_abort': True,
                    'manifest_unchanged_but_body_unindexed': True}

            record, _ = pipeline(root / 'slow_finalization', scene,
                                  cleanup_delay=cap.FINALIZE_BUDGET_SEC + 1)
            assert record['phase'] == 'done' and record['capability'] == 'PASS'
            assert record['finalize']['remaining_sec'] < 0
            results['remaining']['finalization_overrun_reports_success'] = {
                'phase': record['phase'], 'capability': record['capability'],
                'finalize': record['finalize']}

            # A genuinely captured valid manifest loses ALL attempt evidence.
            run, manifest, _ = f.capture_scene(root / 'missing_attempts', scene, f.wire_handler(scene))
            manifest['attempts'] = []
            result = f.check_captured(run, manifest, scene)
            assert verdict(result) == 'PASS'
            results['remaining']['zero_attempts_with_five_successes'] = {
                'capability': verdict(result), 'T3': case_check(result, 'T3')[0]}

            # Failure of the supplementary share endpoint must not answer the distinct
            # question whether the KLC history endpoint serves this BJ symbol.
            overrides = {5: lambda item: f.FakeHttpResponse(404, b'not found', item['url'])}
            run, manifest, _ = f.capture_scene(root / 'bj_share_404', scene,
                                               f.wire_handler(scene, override=overrides))
            result = f.check_captured(run, manifest, scene)
            assert manifest['requests'][3]['payload_state'] == 'decoded'
            assert verdict(result) == 'PASS_WITH_DOCUMENTED_BJ_NON_SERVICE'
            results['remaining']['share_endpoint_404_misclassified_as_BJ_history_absence'] = {
                'capability': verdict(result), 'history_request': manifest['requests'][3]['status'],
                'share_request': manifest['requests'][4]['status'], 'C2': case_check(result, 'C2')}

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print('8 prior scenarios verified closed; 4 remaining boundary defects reproduced. Offline only.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
