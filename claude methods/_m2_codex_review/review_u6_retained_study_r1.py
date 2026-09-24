"""Independent JSON-only arithmetic review; no adapter/decoder/database imports."""
from pathlib import Path
from fractions import Fraction as Q
from decimal import Decimal
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "_m2_smoke"
RESULT = SMOKE / "g3_ratio_analysis_20260909_r2/results.json"
REF = SMOKE / "revision_20260908T082833Z_r2abc_v2/reference/reference_extract.json"
PINS = {RESULT: "538adc5c1912c06d1756e5da8fe702d98548b165656fabe9e5f216f8063a26bd",
        REF: "ea021004a7b387fccfacd5bfec55b327cb90333811b8a4e27c6ef1390ec036b2"}
for path, pin in PINS.items():
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin, path
data = json.loads(RESULT.read_text("utf-8"), parse_float=Decimal)
ref = json.loads(REF.read_text("utf-8"), parse_float=Decimal)
EVENTS = {"sh600011": {"2024-07-11": 20, "2025-07-10": 27, "2026-07-03": 40},
          "bj920000": {"2024-09-30": 6, "2025-05-15": 8, "2025-09-18": 7, "2026-05-25": 8}}
EXPECTED = {"sh600011": [(14,820,894,0,True,False),(23,669,830,0,True,False),
    (218,569,725,15,False,True),(237,637,925,16,False,True),(15,670,743,0,True,True),
    (1,709,709,0,True,True),(30,660,729,0,True,True)],
    "bj920000": [(32,581,668,0,True,False),(147,737,3577,0,True,False),
    (89,2005,2585,0,True,False),(159,1477,2672,0,True,False),(43,1122,1498,0,True,True),
    (1,1418,1418,0,True,True),(30,1280,1547,0,True,True)]}
out = {"method": "Decimal parsing, exact rational interval intersections; reconstructed cent values explicitly conditional", "symbols": {}}
for sym, events in EVENTS.items():
    comp = data["results"][sym]["comparison"]
    differences = dict(comp["difference"]["series"])
    ratios = dict(comp["ratio"]["series"])
    rows = ref["rows"][sym.upper()]
    assert len({r['trade_date'] for r in rows}) == len(rows)
    rows = {r['trade_date']: r for r in rows}
    assert set(differences) == set(ratios) == set(rows)
    records, groups = {}, []
    max_cent_residual, max_ratio_residual = Q(0), Q(0)
    for date in sorted(rows):
        row = rows[date]
        raw_rc = Q(row['close']) * 100
        assert raw_rc.denominator == 1 and raw_rc > 0
        rc = int(raw_rc)
        raw_dc = Q(differences[date]) * 100
        dc = round(raw_dc)
        vc = rc + dc
        assert vc > 0
        max_cent_residual = max(max_cent_residual, abs(raw_dc-dc))
        max_ratio_residual = max(max_ratio_residual, abs(Q(vc,rc)-Q(ratios[date])))
        key = (row['source'], row['updated_at'], sum(d <= date for d in events))
        rec = {'date':date,'rc':rc,'vc':vc,'dc':dc,'key':key}
        records[date] = rec
        if not groups or groups[-1][0]['key'] != key:
            groups.append([])
        groups[-1].append(rec)
    intervals, by_date = [], {}
    for group in groups:
        cs = [(Q(r['dc'])-1,Q(r['dc'])+1) for r in group]
        ks = [(Q(2*r['vc']-1,2*r['rc']+1),Q(2*r['vc']+1,2*r['rc']-1)) for r in group]
        c = max(x[0] for x in cs), min(x[1] for x in cs)
        k = max(x[0] for x in ks), min(x[1] for x in ks)
        dspread = max(r['dc'] for r in group)-min(r['dc'] for r in group)
        iv = {'start':group[0]['date'],'end':group[-1]['date'],'n':len(group),
              'rc_min':min(r['rc'] for r in group),'rc_max':max(r['rc'] for r in group),
              'difference_spread_cents':dspread,'add_feasible':c[0]<=c[1],
              'mul_feasible':k[0]<=k[1],'C_cents':c,'K':k,
              'mul_gap':max(Q(0),k[0]-k[1])}
        intervals.append(iv)
        for row in group: by_date[row['date']] = iv
    measured = [(i['n'],i['rc_min'],i['rc_max'],i['difference_spread_cents'],i['add_feasible'],i['mul_feasible']) for i in intervals]
    assert measured == EXPECTED[sym], (sym, measured)
    checks = []
    dates = sorted(records)
    for date, cash in sorted(events.items()):
        prev = dates[dates.index(date)-1]
        a,b = by_date[prev],by_date[date]
        assert records[prev]['key'][:2] == records[date]['key'][:2]
        entry = {'date':date,'observed_step_cents':records[prev]['dc']-records[date]['dc'],'cash_cents':cash}
        if a['add_feasible'] and b['add_feasible']:
            window = a['C_cents'][0]-b['C_cents'][1],a['C_cents'][1]-b['C_cents'][0]
            entry.update(C_step=window,contains_cash=window[0]<=cash<=window[1],continuous_width_cents=window[1]-window[0])
        if a['mul_feasible'] and b['mul_feasible']:
            window = a['K'][0]/b['K'][1],a['K'][1]/b['K'][0]
            p=Q(records[prev]['vc'],100);r=Q(records[prev]['rc'],100);factor=p/(p-Q(cash,100))
            # Stronger feasibility witness: fix latent prior vendor price to the reconstructed cent value.
            lo=max(b['K'][0],a['K'][0]/factor,p/(r+Q(1,200))/factor)
            hi=min(b['K'][1],a['K'][1]/factor,p/(r-Q(1,200))/factor)
            entry.update(K_ratio=window,assumed_factor=factor,contains_assumed_factor=window[0]<=factor<=window[1],joint_fixed_prior_witness=lo<=hi)
        checks.append(entry)
    out['symbols'][sym] = {'matched':len(records),'max_cent_reconstruction_residual':max_cent_residual,
        'max_ratio_reconstruction_residual':max_ratio_residual,'intervals':intervals,'events':checks}
out['all_14_interval_rows_match'] = True
out['inputs_unchanged'] = all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in PINS.items())
def encode(v):
    if isinstance(v,Q): return {'exact':str(v),'decimal':float(v)}
    raise TypeError(type(v).__name__)
print(json.dumps(out,ensure_ascii=False,indent=2,default=encode))
