"""Freeze the complete M3-02 declared delivery; no implementation/SQLite execution.

The two exact candidate database sources are hash-checked but not copied. All
declared output files and ordinary source documents are copied after scope/pin
validation. This is a candidate delivery snapshot, not an acceptance verdict.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PHASE = HERE.parent
DELIVERY = PHASE/'claude_02'
MANIFEST = DELIVERY/'artifact_manifest.json'
DBROOT = ROOT/'claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09'
DBPINS = {DBROOT/'trading.sqlite3':'c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca',
          DBROOT/'history.sqlite3':'eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003'}


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    expected = sys.argv[1]
    assert sha(MANIFEST)==expected
    raw=MANIFEST.read_bytes(); m=json.loads(raw)
    assert m['task_id']=='M3-02-FROZEN-READER-20260910' and m['status']=='ready_for_review'
    assert m['final_run']=='dev_run_02'
    assert len(m['written'])==816 and len(m['sources_read'])==32 and len(m['preserved_originals'])==20
    output=HERE/'review_m3_02_input'
    assert not output.exists()
    ordinary_sources={}; written={}; source_pins={}
    for rel,pin in m['written'].items():
        path=(ROOT/rel).resolve(strict=True)
        assert path.is_relative_to(ROOT) and (path.is_relative_to(DELIVERY) or path in {ROOT/'backend/app/research/m3_frozen_reader.py',ROOT/'backend/tests/test_m3_frozen_reader.py'})
        blob=path.read_bytes()
        assert hashlib.sha256(blob).hexdigest()==pin['sha256'] and len(blob)==pin['bytes'], rel
        written[rel]=blob
    for rel,pin in m['sources_read'].items():
        assert not pin.get('missing'),rel
        path=(ROOT/rel).resolve(strict=True)
        assert path.is_relative_to(ROOT),rel
        assert sha(path)==pin['sha256'] and path.stat().st_size==pin['bytes'],rel
        if path.suffix.lower() in {'.db','.sqlite','.sqlite3'}:
            assert path in DBPINS and pin['sha256']==DBPINS[path]
            for suffix in ('-wal','-shm','-journal'):
                assert not Path(str(path)+suffix).exists()
            source_pins[rel]={**pin,'snapshot_policy':'hash_only_exact_candidate_sqlite_no_connection'}
        else:
            ordinary_sources[rel]=path.read_bytes()
            source_pins[rel]={**pin,'snapshot_policy':'full_byte_copy'}
    for rel,pin in m['preserved_originals'].items():
        path=(ROOT/rel).resolve(strict=True)
        assert path.is_relative_to(ROOT) and sha(path)==pin['sha256']==pin['expected'] and pin['match'] is True,rel
    assert sha(MANIFEST)==expected
    output.mkdir()
    (output/'artifact_manifest.json').write_bytes(raw)
    for kind,blobs in [('files',written),('sources',ordinary_sources)]:
        for rel,blob in blobs.items():
            target=output/kind/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(blob)
    for rel,pin in m['written'].items():
        assert sha(ROOT/rel)==pin['sha256'],'changed_during_snapshot:'+rel
    assert sha(MANIFEST)==expected
    (output/'coordination_at_snapshot.json').write_bytes((PHASE/'coordination_state.json').read_bytes())
    receipt=dict(schema='m3.codex.reader_delivery_snapshot.v1',frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        manifest_sha256=expected,written=m['written'],sources_read=source_pins,preserved_originals=m['preserved_originals'],
        copied_output_count=len(written),copied_ordinary_source_count=len(ordinary_sources),
        source_databases_hash_checked_only=2,sqlite_connections=0,actual_case_reviews=0,
        status='candidate_delivery_pinned_pending_terminal_confirmation_and_acceptance',producer_sha256=sha(Path(__file__)))
    (output/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'manifest_sha256':expected,'written':len(written),'ordinary_sources_copied':len(ordinary_sources),
        'database_sources_hash_only':2,'receipt_sha256':sha(output/'receipt.json')},ensure_ascii=False))


if __name__=='__main__':
    main()
