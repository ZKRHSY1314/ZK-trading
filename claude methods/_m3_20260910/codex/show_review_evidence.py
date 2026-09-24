"""Read a compact, faithful view of already extracted evidence. No verdicts."""
import json,sys
from pathlib import Path
B=Path(__file__).resolve().parent/'individual_review_01'
for cid in sys.argv[1:]:
 d=json.loads((B/(cid+'_evidence.json')).read_text('utf-8'))
 print('\n'+cid)
 if 'prefix_records' in d:
  print('PREFIX',[(r['date'],r['phase']['label'],r['selection']['label'],tuple(round(r['features'][k],5) for k in ['position_250','ma_spread_20_60','return_120'])) for r in d['prefix_records']])
  rows=[d['representative']]+d['controls']
 else:rows=[d['record']]
 for i,r in enumerate(rows):
  f=r['features'];l=r['limit'];sv=r['session_view'];ctx=r['security_context']
  nums=' '.join(k+'='+str(round(f[k],5) if isinstance(f[k],float) else f[k]) for k in ['position_250','ma_spread_20_60','return_120','return_20','return_60','volume_ratio_20','drawdown_from_lookback_high','close','ma20','close_to_high','bars_available'])
  print(('CASE' if i==0 else 'CONTROL'),r['symbol'],r['date'],r['phase'],r['selection'],nums,'amountM',round(f['amount_20_mean_cny']/1e6,3) if f['amount_20_mean_cny'] else None,'band/regime',r['liquidity']['band'],r['regime']['regime'],'entry',r['entry']['label'],r['entry']['reasons'],'limitU/D',l['limit_like_possible'],l['limit_down_possible'],'quality',r['quality'],'state/susp/missing',sv['current_state'],sv['suspensions_in_window'],sv['interior_missing_sessions'],'coverage',r['coverage'].get('ratio'),'benchR',r['regime'].get('benchmark_return_60'),'stockrange',r['stock_range'])
