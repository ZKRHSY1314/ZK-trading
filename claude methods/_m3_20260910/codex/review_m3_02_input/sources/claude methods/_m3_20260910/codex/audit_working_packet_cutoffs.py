"""Inspect working M3-02 packet dates, without SQLite, network or price extraction.

This checks whether the review-facing packet contains episode information after
its own representative cutoff. The global retrospective episode inventory may
retain later metadata separately. This script does not review any actual case.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RUN = ROOT / 'claude methods/_m3_20260910/claude_02/runs/dev_run_01'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    output = HERE / 'reader_working_packet_cutoff_audit_01'
    output.mkdir()
    episodes_path = RUN / 'episodes.json'
    raw_index = episodes_path.read_bytes()
    episodes = json.loads(raw_index)
    (output / 'episodes_input.json').write_bytes(raw_index)
    inputs = [{'path': str(episodes_path), 'sha256': sha(raw_index)}]
    findings = []
    matched = 0
    for item in episodes['packets']:
        path = RUN / 'packets' / (item['episode_key'] + '.json')
        raw = path.read_bytes()
        assert sha(raw) == item['packet_sha256']
        packet = json.loads(raw)
        inputs.append({'path': str(path), 'sha256': sha(raw)})
        cutoff = packet['representative']['decision_date']
        is_matched = bool(packet.get('match') and not packet['match']['unmatched'])
        matched += int(is_matched)
        future_contradictions = [value for value in packet['contradicting_evidence']
            if any(date > cutoff for date in re.findall(r'\d{4}-\d{2}-\d{2}', value))]
        end = packet.get('known_end_so_far')
        if (end and end > cutoff) or future_contradictions:
            findings.append({'episode_key': item['episode_key'], 'symbol': packet['symbol'],
                'representative_cutoff': cutoff, 'end_in_review_packet': end,
                'full_episode_status_in_review_packet': packet.get('status'),
                'future_dated_contradictions': future_contradictions,
                'matched_potential_positive': is_matched, 'packet_sha256': sha(raw)})
            # Preserve actual review-facing evidence; no packet mutation or new reviews.
            if len(findings) <= 2 or (is_matched and future_contradictions):
                (output / ('packet_' + item['episode_key'] + '.json')).write_bytes(raw)
    result = {'schema': 'm3.codex.working_packet_cutoff_audit.v1',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'run': str(RUN),
        'status': 'working_delivery_feedback_not_final_acceptance',
        'packets_checked': len(episodes['packets']), 'matched_potential_positives': matched,
        'packets_with_later_episode_metadata': len(findings),
        'matched_packets_with_later_metadata': sum(x['matched_potential_positive'] for x in findings),
        'packets_with_future_dated_contradictions': sum(bool(x['future_dated_contradictions']) for x in findings),
        'findings': findings, 'inputs': inputs,
        'real_sqlite_connections': 0, 'reviews_performed': 0,
        'producer_sha256': sha(Path(__file__).read_bytes())}
    (output / 'source.py').write_bytes(Path(__file__).read_bytes())
    data = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    (output / 'result.json').write_bytes(data)
    print(json.dumps({k: v for k, v in result.items() if k not in ('findings', 'inputs')}, ensure_ascii=False))
    print('result_sha256=' + sha(data))


if __name__ == '__main__':
    main()
