"""Synthetic integration probe against immutable R2; no real price/DB reads."""
from dataclasses import replace
from datetime import date, timedelta, datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
MODULE = HERE / 'review_02_input/files/backend/app/research/m3_labels.py'
PIN = 'fe6046476f492aca4487492e47477166f47d1cfe052167adf021c0bf238d17e7'
OUTPUT = HERE / 'frozen_r2_benchmark_probe.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert digest(MODULE) == PIN
assert not OUTPUT.exists(), 'preserve an existing receipt'
sys.dont_write_bytecode = True


def audit(event, args):
    if event == 'sqlite3.connect' or event.startswith('socket.') or event in {
        'subprocess.Popen', 'os.system', 'os.startfile', 'os.posix_spawn', 'os.spawn', 'os.exec',
        'os.remove', 'os.rmdir', 'os.mkdir', 'os.rename', 'os.link', 'os.symlink'}:
        raise PermissionError('offline probe blocked: ' + event)
    if event == 'open':
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writing and (not isinstance(path, (str, os.PathLike)) or Path(path).resolve() != OUTPUT):
            raise PermissionError('offline probe blocks writes outside its receipt')


sys.addaudithook(audit)
spec = importlib.util.spec_from_file_location('frozen_r2_benchmark_target', MODULE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
days = []
day = date(2023, 1, 2)
while len(days) < 270:
    if day.weekday() < 5:
        days.append(day.isoformat())
    day += timedelta(days=1)
cal = m.SessionCalendar(tuple(days), 'syn:benchmark-probe-calendar', '2022-12-01T00:00:00+08:00', True)


def observations(symbol, volume_unit='share', index_scale=False):
    # Invented data only; the index example deliberately has aggregate turnover
    # per volume unrelated to its index level. No actual M2 prices are read.
    return tuple(m.Observation(symbol, d, 'price', d+'T15:00:00+08:00',
        'syn:benchmark-probe:'+symbol+':'+d,
        3000. if index_scale else 10., 3100. if index_scale else 11.,
        2900. if index_scale else 9., 3000. if index_scale else 10.,
        2_000_000., 20_000_000., volume_unit=volume_unit) for d in days)


results = []
for name, unit, index_scale in (
    ('existing_share_fixture_baseline', 'share', False),
    ('m2_not_applicable_unit_preserved', 'not_applicable', True),
    ('illustration_of_unsafe_unit_relabel', 'share', True),
):
    req = m.LabelRequest(symbol='SYN001001', observations=observations('SYN001001'),
        cutoff=m.Cutoff(days[-1], days[-1]+'T16:00:00+08:00'), calendar=cal, synthetic=True,
        benchmark_symbol='SYN900001', benchmark_observations=observations('SYN900001', unit, index_scale),
        universe_coverage_on_decision_date=m.Coverage(1., 'syn:coverage', '2022-12-01T00:00:00+08:00'))
    try:
        record = m.generate_labels(req)
        results.append(dict(name=name, accepted=True, regime=record['labels']['regime']))
    except m.LabelInputError as exc:
        results.append(dict(name=name, accepted=False, error=str(exc)))
assert results[0]['accepted']
assert 'unsupported_volume_unit' in results[1]['error']
assert 'vwap_outside_range' in results[2]['error']
assert digest(MODULE) == PIN
receipt = dict(schema='m3.synthetic_benchmark_integration_probe.v1',
    checked_at_utc=datetime.now(timezone.utc).isoformat(), module=str(MODULE), module_sha256=PIN,
    producer_sha256=digest(Path(__file__)), synthetic_only=True,
    sqlite_connections_allowed=0, network_allowed=False, raw_price_body_read=False,
    results=results, conclusion='Frozen R2 rejects the retained M2 benchmark unit; renaming units also invokes an inapplicable stock VWAP rule. Current R3 was not executed or judged.')
OUTPUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False))
