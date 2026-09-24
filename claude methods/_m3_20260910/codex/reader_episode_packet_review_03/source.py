"""Independent exhaustive M3-02 chronology/episode/control/packet audit; no SQLite.

Uses the accepted label kernel, not the reader or its verification script. Source
binding is inherited only when every chronology file matches the independently
replayed source-validation receipt supplied to this run.
"""
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
LABELS = ROOT / 'backend/app/research/m3_labels.py'
META = HERE / 'metadata_index_01/index.json'
LABEL_PIN = 'e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393'
META_PIN = '14f1bad7d393b4e15bf73111a9d96a78c8b156784f9ccbb084d6b606d3a152e9'


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def main():
    run = Path(sys.argv[1]).resolve(strict=True)
    source_review = Path(sys.argv[2]).resolve(strict=True)
    out = Path(sys.argv[3]).resolve()
    require(run.parent == ROOT / 'claude methods/_m3_20260910/claude_02/runs', 'run_scope')
    require(source_review.is_relative_to(HERE) and out.parent == HERE and not out.exists(), 'codex_scope')
    require(sha(LABELS) == LABEL_PIN and sha(META) == META_PIN, 'frozen_pins')
    out.mkdir()
    denials = []

    def inside(path):
        return isinstance(path, (str, os.PathLike)) and Path(path).resolve().is_relative_to(out)

    def deny(event):
        denials.append(event)
        raise PermissionError('Independent packet audit: ' + event)

    def audit(event, args):
        if event == 'sqlite3.connect' or event.startswith('socket.') or event in {'subprocess.Popen', 'os.system', 'os.startfile', 'os.spawn', 'os.exec', 'os.posix_spawn'}:
            deny(event)
        if event == 'open':
            path, mode, flags = args
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing and not inside(path):
                deny('write_outside_output')
        if event in {'os.mkdir', 'os.remove', 'os.rmdir'} and not inside(args[0]):
            deny(event)
        if event == 'os.rename' and not (inside(args[0]) and inside(args[1])):
            deny(event)
        if event in {'os.link', 'os.symlink'}:
            deny(event)

    sys.dont_write_bytecode = True
    sys.addaudithook(audit)
    inputs = {str(source_review):sha(source_review), str(LABELS):LABEL_PIN, str(META):META_PIN}
    replay = json.loads(source_review.read_text(encoding='utf-8'))
    require(replay['passed'] and replay['records_replayed'] == 17554 and replay['mismatch_count'] == 0, 'successful_source_replay_required')
    spec = importlib.util.spec_from_file_location('m3_labels_independent_packet_audit', LABELS)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)

    def read(name):
        path = run / name
        require(path.resolve().is_relative_to(run), 'delivery_path_escape')
        inputs[str(path)] = sha(path)
        return json.loads(path.read_text(encoding='utf-8'))

    index, inventory = read('chronology_index.json'), read('inventory.json')
    meta = json.loads(META.read_text(encoding='utf-8'))
    c = inventory['calendar']
    calendar = m.SessionCalendar(tuple(d for d in meta['calendar']['sessions'] if c['first'] <= d <= c['last']),
        c['source_ref'], c['available_at'], synthetic=False)
    require(calendar.record() == c, 'calendar_binding')
    records, keys, by_date, rebuilt = {}, {}, defaultdict(dict), {}
    core_phase, core_selection = Counter(), Counter()
    core_state = Counter({'observed': 0, 'suspended': 0, 'missing': 0})
    for symbol, info in index['files'].items():
        path = run / 'chronology' / (symbol + '.jsonl.gz')
        old_path = str(Path(replay['run']) / 'chronology' / path.name)
        digest = sha(path)
        require(digest == info['sha256_gzip'] == replay['input_files'][old_path], 'source_replayed_file_binding:' + symbol)
        inputs[str(path)] = digest
        plain = gzip.decompress(path.read_bytes())
        require(hashlib.sha256(plain).hexdigest() == info['sha256_jsonl'], 'plain_digest')
        rows = [json.loads(line)['record'] for line in plain.decode('utf-8').splitlines()]
        require(len(rows) == info['records'], 'chronology_count')
        records[symbol] = rows
        for row in rows:
            m.verify_record(row)
            m.validate_ledger(row)
            require(row['review_ledger']['entries'] == [] and row['review_ledger']['status'] == 'pending_review', 'invented_review')
            k = (symbol, row['cutoff']['decision_date'])
            require(k not in keys, 'duplicate_core')
            keys[k] = row
            by_date[k[1]][symbol] = row
            core_phase[row['labels']['phase']['label']] += 1
            core_selection[row['labels']['selection']['label']] += 1
            core_state[row['current_state']] += 1
        for episode in m.build_episodes(rows, calendar):
            require(episode['episode_key'] not in rebuilt, 'duplicate_episode')
            rebuilt[episode['episode_key']] = episode
    delivered = read('episodes.json')
    require('NOT cutoff-known' in delivered['information_time'], 'retrospective_inventory_marker')
    listed = {e['episode_key']:e for e in delivered['episodes']}
    require(set(listed) == set(rebuilt) and len(listed) == len(delivered['episodes']), 'exhaustive_episode_inventory')
    packets = {p['episode_key']:p for p in delivered['packets']}
    expected_packets = {k for k,e in rebuilt.items() if e['phase'] == 'accumulation' and m.episode_prefix_proof(e) is not None}
    require(set(packets) == expected_packets and len(packets) == len(delivered['packets']), 'exhaustive_packet_inventory')
    reasons, uses, matches = Counter(), Counter(), []
    checks = []
    for eid, ep in rebuilt.items():
        for key in set(listed[eid]) & set(ep):
            require(listed[eid][key] == ep[key], 'episode_field:' + eid + ':' + key)
        if eid not in packets:
            continue
        pi = packets[eid]
        packet = read('packets/' + eid + '.json')
        require(inputs[str(run/'packets'/(eid+'.json'))] == pi['packet_sha256'] == listed[eid]['packet_sha256'], 'packet_file_pin')
        proof = m.episode_prefix_proof(ep)
        day = proof['established_at']
        rep = keys[(ep['symbol'], day)]
        require(packet['prefix_proof'] == proof and packet['representative']['record_hash'] == rep['record_hash'], 'prefix_representative')
        require(packet['representative']['cutoff'] == rep['cutoff'] and packet['representative']['selection'] == rep['labels']['selection'], 'representative_labels')
        require(packet['review_status'] == 'pending_review' and packet['reviews'] == [] and packet['synthetic'] is False, 'packet_status')
        require(not set(packet) & {'known_end_so_far','status','end','selection_path','closed_reason','eligibility_changes','episode_audit'}, 'future_episode_metadata_in_review')
        prefix = [keys[(ep['symbol'], mm['decision_date'])] for mm in packet['members']]
        require([r['record_hash'] for r in prefix] == proof['member_record_hashes'] and len(prefix) == 3, 'member_bindings')
        for mm in packet['members'] + [packet['representative']] + packet['controls']:
            source_symbol = mm.get('symbol', ep['symbol'])
            source_row = records[source_symbol][mm['line']]
            require(source_row['record_hash'] == mm['record_hash'] and source_row['episode_id'] == mm['episode_id'], 'line_locator')
            require(mm['chronology_file'] == 'chronology/' + source_symbol + '.jsonl.gz', 'file_locator')
        require(packet['warmup_depth_at_representative'] == rep['features']['bars_available'], 'representative_warmup')
        require(all(packet['numerical_values'][k] == rep['features'].get(k) for k in packet['numerical_values']), 'packet_features')
        for k, field in [('regime','regime'),('liquidity','liquidity'),('limit','limit')]:
            require(packet[k] == rep['labels'][field], 'packet_context')
        require(all(d <= day for text in packet['supporting_evidence'] + packet['contradicting_evidence'] for d in re.findall(r'\d{4}-\d{2}-\d{2}', text)), 'future_text_in_review')
        require(all(x['decision_date'] <= day for x in packet['prefix_path']), 'future_prefix')
        require(packet['price_context']['max_trade_date_consumed'] <= day, 'future_price_context')
        require(all(x <= day for x in packet['uncertainties']['known_ex_dates_at_cutoff']), 'future_action')
        # Recompute the packet content binding without using the reader's hash helper.
        content = copy.deepcopy(packet)
        for key in ('cutoff_packet_hash', 'review_status', 'reviews'):
            content.pop(key)
        for ref in [content['representative'], *content['members'], *content['controls']]:
            ref.pop('chronology_file', None)
            ref.pop('line', None)
        bound = hashlib.sha256(canonical(content).encode()).hexdigest()
        require(bound == packet['cutoff_packet_hash'] == pi['cutoff_packet_hash'], 'packet_content_binding')

        pool = [r for symbol,r in sorted(by_date[day].items()) if symbol != ep['symbol']]
        pool_fields = ('symbol','episode_id','record_hash','selection','phase','liquidity_band','regime','current_state','amount_20_mean_cny')
        expected_pool = [{k:s[k] for k in pool_fields} for s in map(m.case_summary, pool)]
        require(packet['control_pool'] == {'date':day, 'pool_size':len(pool), 'pool':expected_pool}, 'complete_control_pool')
        if rep['labels']['selection']['label'] != 'candidate':
            require(packet['match'] is None and packet['exclusion'] == 'representative_selection_' + rep['labels']['selection']['label'], 'noncandidate_exclusion')
            reasons['representative_not_candidate'] += 1
        elif rep['labels']['liquidity']['band'] == 'unknown' or rep['labels']['regime']['regime'] == 'unknown':
            require(packet['match'] is None and packet['exclusion'] == 'representative_context_unknown', 'context_exclusion')
            reasons['representative_not_candidate'] += 1
        else:
            expected_match = m.match_controls(rep, pool)
            require(packet['match'] == expected_match, 'full_pool_match_recompute')
            m.revalidate_match(packet['match'], m.RecordRegistry([rep] + pool))
            require([x['record_hash'] for x in packet['controls']] == [x['record_hash'] for x in expected_match['controls']], 'chosen_controls')
            ranked = []
            ps = m.case_summary(rep)
            for cr in pool:
                s = m.case_summary(cr)
                eligible = s['selection']=='non_candidate' and s['liquidity_band']==ps['liquidity_band'] and s['regime']==ps['regime'] and s['current_state']=='observed'
                amt = abs(math.log(s['amount_20_mean_cny']/ps['amount_20_mean_cny'])) if s['amount_20_mean_cny'] and ps['amount_20_mean_cny'] else None
                ranked.append(dict(symbol=s['symbol'],episode_id=s['episode_id'],eligible=eligible,selection=s['selection'],liquidity_band=s['liquidity_band'],regime=s['regime'],current_state=s['current_state'],abs_ln_amount_ratio=amt))
            ranked.sort(key=lambda x:(not x['eligible'], x['abs_ln_amount_ratio'] if x['abs_ln_amount_ratio'] is not None else math.inf, x['symbol']))
            require(ranked == packet['control_ranking'], 'complete_control_ranking')
            reasons['unmatched' if expected_match['unmatched'] else 'matched_pending'] += 1
            if not expected_match['unmatched']:
                matches.append(ep)
                uses.update(x['episode_id'] for x in expected_match['controls'])
        checks.append({'episode_key':eid,'representative_date':day,'packet_sha256':pi['packet_sha256'],'prefix_hash':proof['prefix_hash'],'cutoff_packet_hash':bound,'exclusion':packet['exclusion']})

    waterfall = read('waterfall.json')['waterfall']
    require(waterfall['phase']==dict(core_phase) and waterfall['selection']==dict(core_selection) and waterfall['current_state']==dict(core_state), 'core_waterfall')
    require(waterfall['episodes_total']==len(rebuilt) and waterfall['episodes_by_phase']==dict(Counter(e['phase'] for e in rebuilt.values())), 'episode_waterfall')
    require(waterfall['matched_3_to_5_controls']==reasons['matched_pending'] and waterfall['unmatched']==reasons['unmatched'] and waterfall['representatives_not_candidate']==reasons['representative_not_candidate'], 'packet_waterfall')
    controls = read('controls.json')
    groups = m.dependence_groups(matches)
    require(controls['dependence_groups']==groups and controls['control_uses']==dict(uses), 'dependence_reuse')
    require(waterfall['independently_reviewed']==0 and waterfall['qualified_reviewed_positive_episodes']==0 and waterfall['target']['met'] is False, 'actual_review_count')
    require(waterfall['unique_controls_used']==len(uses) and waterfall['control_uses']==sum(uses.values()) and waterfall['control_reuse_max']==max(uses.values(),default=0), 'reuse_waterfall')
    for path,pin in inputs.items():
        require(sha(Path(path))==pin, 'input_changed')
    result = dict(schema='m3.codex.episode_packet_audit.v1',run=str(run),checked_at_utc=datetime.now(timezone.utc).isoformat(),
        passed=True, records=sum(map(len,records.values())), episodes=len(rebuilt), packets=len(checks), packet_reasons=dict(reasons),
        effective_dependence_groups=groups['effective_decision_groups'], unique_controls=len(uses),control_uses=sum(uses.values()),
        checks=checks,inputs=inputs,producer_sha256=sha(Path(__file__)),denied_events=denials,sqlite_connections=0,actual_case_reviews=0,M3_complete=False)
    (out/'source.py').write_bytes(Path(__file__).read_bytes())
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','inputs')},ensure_ascii=False))
    print('result_sha256='+sha(out/'result.json'))


if __name__ == '__main__':
    main()
