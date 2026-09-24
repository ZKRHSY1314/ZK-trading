"""Independent, offline M2b-1a integration probes; never invokes the armed CLI.

Only synthetic temporary files are written. Claude's fixture builder is reused, but
the assertions and capture-to-check integration below are reviewer-owned.
Run from repository root with backend/.venv/Scripts/python.exe -B -X utf8.
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
import test_m2_smoke as fixture
import smoke_capture as cap
import smoke_checks as chk
import transport as tp
import requests


def capture_synthetic(root, scene, *, html=False):
    """Use real SmokeRun + LiveSinaTransport + PacedTransport; fake only HTTP/I/O inputs."""
    clock = fixture.Clock()
    seen = []
    by_url = {p['url']: p for p in fixture.PLANNED}

    def handler(url):
        item = by_url[url]
        seen.append({'index': item['index'], 'start': clock()})
        body = fixture.HTML if html and item['kind'] == 'klc' else scene['bodies'][item['index']]
        return fixture.FakeHttpResponse(200, body, url)

    run = cap.SmokeRun('20260907T010000Z', out_root=root / 'capture',
                       evidence_root=root / 'evidence', clock=clock,
                       sleeper=clock.advance)
    data = {'reference_extract': scene['extract'], 'protected_before': {},
            'adapter_constants': fixture.CONSTS}
    with patch.object(cap, 'preflight', return_value=([cap.Check('fixture', 'PASS', 'synthetic')], data)), \
            patch.object(cap, 'protected_fingerprints', return_value={}), \
            patch.object(cap, 'compare_fingerprints', return_value=([], [])):
        manifest = run.capture(session=fixture.FakeSession(handler),
                               requests_module=requests, supervise_jobs=False)
    result_scene = dict(scene, manifest=manifest, dir=run.out_root)
    result = fixture.run(result_scene)
    return manifest, result, seen


def main():
    findings = {}
    # Never allow a genuine HTTP request, including a loopback proxy tunnel.
    with patch.object(requests.Session, 'request', side_effect=AssertionError('review is offline')):
        clock = fixture.Clock()
        seen = []

        def tls_error(url):
            seen.append(url)
            raise requests.exceptions.SSLError('synthetic certificate verification failure')

        live = cap.LiveSinaTransport(fixture.FakeSession(tls_error),
                                    deadline=cap.Deadline(100, clock=clock),
                                    requests_module=requests, clock=clock)
        paced = tp.PacedTransport(live, clock=clock, sleeper=clock.advance,
                                  min_interval=1.5, ceiling=15)
        try:
            paced.get_with_retries(fixture.PLANNED[0]['url'], source='sina')
        except tp.TransportError as exc:
            findings['tls_actual_adapter'] = {
                'calls': len(seen), 'retryable': exc.retryable,
                'attempt_classifications': [a.outcome for a in paced.attempts]}
        assert len(seen) == 3, findings

        stopped = []

        class StopWithBrokenBody(fixture.FakeHttpResponse):
            def iter_content(self, chunk_size):
                raise requests.exceptions.Timeout('synthetic body timeout after stop headers')
                yield b''

        for status in (403, 429):
            clock = fixture.Clock()
            calls = []

            def stop_handler(url):
                calls.append(url)
                return StopWithBrokenBody(status, b'', url)

            live = cap.LiveSinaTransport(fixture.FakeSession(stop_handler),
                                        deadline=cap.Deadline(100, clock=clock),
                                        requests_module=requests, clock=clock)
            paced = tp.PacedTransport(live, clock=clock, sleeper=clock.advance,
                                      min_interval=1.5, ceiling=15)
            try:
                paced.get_with_retries(fixture.PLANNED[0]['url'], source='sina')
            except tp.TransportError as exc:
                stopped.append({'status_already_received': status, 'calls': len(calls),
                                'retryable': exc.retryable, 'abort_latch': paced.aborted_reason})
            assert len(calls) == 3 and paced.aborted_reason is None
        findings['stop_headers_lost_when_body_times_out'] = stopped

        with tempfile.TemporaryDirectory(prefix='m2b_codex_integration_') as temporary:
            root = Path(temporary)
            scene = fixture.scenario(root / 'scene')
            manifest, result, wire = capture_synthetic(root / 'normal', scene)
            t3 = next(c for c in result['deterministic']['checks'] if c['id'] == 'T3')
            findings['successful_capture_false_pacing_failure'] = {
                'actual_request_starts': wire,
                'recorded_starts': [r['started_at_monotonic'] for r in manifest['requests']],
                'check': t3}
            assert all(b['start'] - a['start'] >= 1.5 for a, b in zip(wire, wire[1:]))
            assert t3['status'] == 'FAIL'

            manifest, result, wire = capture_synthetic(root / 'html', scene, html=True)
            t3 = next(c for c in result['deterministic']['checks'] if c['id'] == 'T3')
            findings['payload_failures_do_not_control_capture'] = {
                'issued_indices': [x['index'] for x in wire],
                'capture_status': manifest['run_status'], 'check': t3}
            assert len(wire) == 5 and manifest['run_status'] == 'completed'
            assert 'after the skip trigger' in t3['detail']

            # An explicit invalidation must veto any otherwise successful check result.
            invalid = copy.deepcopy(scene)
            invalid['manifest'].update(run_valid=False, invalidating_changes=['production DB changed'])
            verdict = fixture.run(invalid)['deterministic']['verdicts']['capability']
            findings['invalidated_capture_can_pass'] = verdict
            assert verdict == 'PASS'

            unbound = copy.deepcopy(scene)
            unbound['manifest']['reference_extract_sha256'] = '0' * 64
            unbound['extract']['content_sha256'] = 'f' * 64
            verdict = fixture.run(unbound)['deterministic']['verdicts']['capability']
            findings['mismatched_reference_hashes_can_pass'] = verdict
            assert verdict == 'PASS'

            baseline = fixture.run(scene)
            changed = copy.deepcopy(scene)
            for rows in changed['extract']['rows'].values():
                for row in rows:
                    row['updated_at'] = '2099-01-01T00:00:00Z'
                    row['volume_unit'] = 'unknown'
            result = fixture.run(changed)
            findings['changed_reference_units_and_timestamps_not_detected'] = {
                'capability': result['deterministic']['verdicts']['capability'],
                'same_deterministic_hash': result['deterministic_sha256'] == baseline['deterministic_sha256']}
            assert result['deterministic_sha256'] == baseline['deterministic_sha256']

            # Exercise run_checks itself, not supervise(an unrelated busy function).
            entered, release, done = threading.Event(), threading.Event(), threading.Event()
            caught = []

            def delayed_replay(bodies, calls):
                entered.set()
                release.wait(3)
                return fixture.fake_replay(bodies, calls)

            expired = copy.deepcopy(scene)
            expired['manifest']['deadline'] = {
                'budget_sec': .01, 'grace_sec': .01,
                'elapsed_sec': 1000, 'remaining_sec': -999.99}

            def check_worker():
                try:
                    fixture.run(expired, replay_fn=delayed_replay)
                except BaseException as exc:
                    caught.append(repr(exc))
                finally:
                    done.set()

            worker = threading.Thread(target=check_worker, daemon=True)
            worker.start()
            assert entered.wait(3), 'did not reach the real run_checks replay call'
            try:
                blocked = not done.wait(.15)
                findings['real_check_path_ignores_expired_run_deadline'] = {
                    'entered_replay_after_expiry': entered.is_set(),
                    'still_blocked_past_budget_and_grace': blocked}
                assert blocked
            finally:
                release.set()
                worker.join(3)
            assert not worker.is_alive() and not caught, caught

    print(json.dumps(findings, ensure_ascii=False, indent=2))
    print('8 independent integration scenarios reproduced; synthetic temporary files cleaned up.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
