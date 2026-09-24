"""Preserve the previous reviewer and extend it for the explicitly renamed endpoints."""
from pathlib import Path
base = Path(__file__).with_name('review_g3_ratio_codex_r2.py').read_text(encoding='utf-8')
base = base.replace("x['source_changed']", "x['endpoint_source_changed']").replace("x['updated_at_changed']", "x['endpoint_updated_at_changed']")
base = base.replace("'g3_ratio_codex_review_r2_results.json'", "'g3_ratio_codex_review_r2b_results.json'")
extra = '''
    snapshot=REVIEW/'g3_r2_reviewed_54088a1d'
    previous=read(snapshot/'results.json')['results']
    for job,b in fresh.items():
        old=previous[job]
        numeric_keys=['from_date','to_date','ratio_from','ratio_to','change','is_zero_change','difference_from','difference_to','calendar_days_between']
        stable=(b['comparison']['ratio']==old['comparison']['ratio'] and b['comparison']['difference']==old['comparison']['difference'] and b['segments']==old['segments'] and
                [[r[k] for k in numeric_keys] for r in b['comparison']['ratio_changes']['records']]==[[r[k] for k in numeric_keys] for r in old['comparison']['ratio_changes']['records']])
        expect(job+' all retained numeric values preserved from reviewed snapshot',stable)
        refs_by_date={r['trade_date']:r for r in extract['rows'][b['manifest_symbol']]}
        expected_dates=[]; ordered=sorted(refs_by_date)
        for a,z in zip(ordered,ordered[1:]):
            if any(refs_by_date[a][k]!=refs_by_date[z][k] for k in ['source','updated_at']):expected_dates.append(z)
        records=b['comparison']['ratio_changes']['records']
        expect(job+' retained crossings independently partition reference boundaries',all([x['at_date'] for x in r['boundaries_crossed']]==[d for d in expected_dates if r['from_date']<d<=r['to_date']] for r in records))
    for field in ['source','updated_at']:
        for missing_vendor in [False,True]:
            rr=copy.deepcopy(refs[:3]);vv=copy.deepcopy(vs[:3]);rr[1][field]='DIFFERENT'
            if missing_vendor:vv.pop(1)
            else:rr[1]['close']=None
            b=scenario(rr,vv);c=b['comparison']['ratio_changes'];r=c['records'][0]
            ok=(not r['endpoint_metadata_boundary'] and r['interval_metadata_boundary'] and r['metadata_boundary'] and [x['at_date'] for x in r['boundaries_crossed']]==dates[1:3] and c['pairs_crossing_a_boundary_with_equal_endpoints']==1 and c['boundary_crossings_total']==2)
            expect(field+' round trip with '+('missing vendor' if missing_vendor else 'invalid price'),ok,r)
            rp=dict(stored,results={'sh600011':b},documented_segments=g3.documented_470_row_segments({'sh600011':b}))
            rendered=g3.render_report(rp)
            expect(field+' round-trip report includes actual crossing dates '+str(missing_vendor),dates[1]+', '+dates[2] in rendered and '1 have equal endpoint metadata' in rendered)
    rr=copy.deepcopy(refs[:3]);rr.pop(1);b=scenario(rr,vs[:3]);r=b['comparison']['ratio_changes']['records'][0]
    expect('vendor-only gap contributes no fabricated metadata crossing',r['skipped_vendor_only_dates']==[dates[1]] and r['boundaries_crossed']==[] and not r['metadata_boundary'])
    checkpoint=read(REVIEW/'g3_ratio_codex_review_r2_results.json')['protected_before']
    expect('reviewed five-file snapshot preserved',all(sha(p)==checkpoint[(HERE/p.name).relative_to(ROOT).as_posix()] for p in snapshot.iterdir() if p.is_file()))
'''
marker="    prior=read(REVIEW/'g3_ratio_codex_review_results.json')['protected_after']"
if base.count(marker)!=1: raise RuntimeError('review extension anchor changed')
base=base.replace(marker,extra+'\n'+marker)
exec(compile(base,str(Path(__file__)), 'exec'))
