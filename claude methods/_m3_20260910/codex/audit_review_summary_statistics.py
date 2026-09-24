"""Check descriptive report arithmetic, without issuing any review verdict."""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE / 'case_review_bundle_01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = Path(sys.argv[1]).resolve()
    assert output.parent == HERE and not output.exists()
    manifest = json.loads((BUNDLE / 'manifest.json').read_bytes())
    assert sha(BUNDLE / 'manifest.json') == 'fa234fded7e448f1d8313ee26f43f1e81902e9294426faf1dc2164747ac887fc'
    margins, thin = {}, {key: [] for key in ('position', 'spread', 'return_120')}
    control_records, control_symbols, case_symbols = Counter(), Counter(), Counter()
    for path in sorted((BUNDLE / 'cases').glob('C*.json')):
        assert sha(path) == manifest['written'][str(path.relative_to(BUNDLE)).replace('\\', '/')]['sha256']
        packet = json.loads(path.read_bytes())
        features = [r['features'] for r in packet['prefix_records']]
        values = {'position': min(.65-f['position_250'] for f in features),
                  'spread': min(.09-f['ma_spread_20_60'] for f in features),
                  'return_120': min(.25-f['return_120'] for f in features)}
        margins[path.stem] = values
        for key, value in values.items():
            if value < .01:
                thin[key].append(path.stem)
        case_symbols[packet['representative_record']['symbol']] += 1
        for record in packet['control_records']:
            control_records[(record['symbol'], record['cutoff']['decision_date'], record['record_hash'])] += 1
            control_symbols[record['symbol']] += 1
    union = sorted(set().union(*map(set, thin.values())))
    assert len(margins) == 32 and len(union) == 15
    assert len(control_records) == 127 and max(control_records.values()) == 1
    assert len(control_symbols) == 37 and max(control_symbols.values()) == 10
    result = {'passed': True, 'at_utc': datetime.now(timezone.utc).isoformat(),
              'criterion': 'descriptive reviewer convention only: minimum deciding margin across three prefix members < 0.01',
              'frozen_policy_changed': False, 'review_judgments_generated': 0, 'case_count': 32,
              'thin_by_leg': thin, 'thin_union': union, 'thin_count': len(union), 'per_case_min_margins': margins,
              'case_symbol_counts': dict(case_symbols), 'control_record_uses': sum(control_records.values()),
              'unique_control_records': len(control_records), 'max_uses_per_control_record': max(control_records.values()),
              'control_symbol_uses': dict(control_symbols), 'unique_control_symbols': len(control_symbols),
              'max_uses_per_control_symbol': max(control_symbols.values()), 'sqlite_connections': 0, 'network_requests': 0,
              'producer_sha256': sha(Path(__file__))}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in {'per_case_min_margins', 'control_symbol_uses'}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
