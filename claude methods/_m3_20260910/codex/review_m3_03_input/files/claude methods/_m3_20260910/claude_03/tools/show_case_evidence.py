"""Display and arithmetically verify the cutoff-only evidence of one M3-03 case (or diagnostic).

This tool never produces a verdict.  It (1) re-checks the bundle pins, (2) verifies every embedded
core with the accepted label kernel (record hash + decision fingerprint + empty ledger), (3) recomputes
the frozen rules from the stored features and reports the margins to each threshold, (4) re-checks the
match conditions and the control ranking from the embedded cores, and (5) prints a dossier that the
reviewer reads before authoring the judgment.  Every invocation appends an entry to
execution/evidence_inspection_log.jsonl (what was inspected, when, with which hashes).

No SQLite, no network, no chronology/episode_audit access: only the bundle file of the case and the
accepted m3_labels.py are read.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/claude_03/tools/show_case_evidence.py" C001
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAUDE_03 = HERE.parent
PROJECT = CLAUDE_03.parents[2]
BUNDLE = PROJECT / "claude methods" / "_m3_20260910" / "codex" / "case_review_bundle_01"
LABELS = PROJECT / "backend" / "app" / "research" / "m3_labels.py"
LABELS_SHA256 = "e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393"
POLICY_HASH = "d436ba1402f9d0b53e1008c2a2bd50678a457c3e050561a59ded30dbbd21c025"
BUNDLE_MANIFEST_SHA256 = "fa234fded7e448f1d8313ee26f43f1e81902e9294426faf1dc2164747ac887fc"
BUNDLE_INDEX_SHA256 = "77e29df61a9ffa85379a1505a9f1065574968255ff30249dab4d97b99dcb8fec"
LOG = CLAUDE_03 / "execution" / "evidence_inspection_log.jsonl"
DOSSIERS = CLAUDE_03 / "execution" / "dossiers"

ACC = {"position_250_lt": 0.65, "ma_spread_20_60_lt": 0.09, "return_120_lt": 0.25}
MARKUP = {"return_20_gt": 0.18, "or_return_60_gt": 0.35, "volume_ratio_20_gt": 1.05}
DIST = {"position_250_gt": 0.78, "volume_ratio_20_gt": 1.45, "close_to_high_lt": 0.97, "or_return_20_lt": -0.03}
FAILED_DD = -0.1
ENTRY_VR = 1.5
BANDS = [("L1_thin", 30_000_000.0), ("L2_low", 100_000_000.0), ("L3_mid", 500_000_000.0), ("L4_deep", None)]
STD_CALENDAR = "calendar.json sha256=f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656 slice 2022-06-30..2025-03-31"
STD_PILOT_REF = "pilot_symbols.csv sha256=97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe list_date; grade="
STD_SEMANTICS = {"adjustment_uncertainty": True, "hidden_actor_claim": False, "observable_behavioural_proxy": True, "realized_return_claim": False,
                 "strict_pit_eligible": False, "trade_recommendation": False, "training_eligible": False}
COMPACT = True


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_labels():
    if sha(LABELS) != LABELS_SHA256:
        raise SystemExit("accepted label module hash mismatch")
    spec = importlib.util.spec_from_file_location("m3_labels_review_readonly", LABELS)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    if m.POLICY_HASH != POLICY_HASH:
        raise SystemExit("policy hash mismatch")
    return m


def check_bundle_pins() -> dict:
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    if sha(BUNDLE / "manifest.json") != BUNDLE_MANIFEST_SHA256 or sha(BUNDLE / "index.json") != BUNDLE_INDEX_SHA256:
        raise SystemExit("bundle manifest/index pin mismatch")
    bad = [rel for rel, v in manifest["written"].items() if sha(BUNDLE / rel) != v["sha256"] or (BUNDLE / rel).stat().st_size != v["bytes"]]
    if bad:
        raise SystemExit(f"bundle files changed: {bad}")
    return manifest


def fmt(x, nd=4):
    if x is None:
        return "None"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def band_of(amount):
    if amount is None:
        return "unknown"
    for band, lt in BANDS:
        if lt is None or amount < lt:
            return band
    return "unknown"


def rule_eval(f: dict) -> dict:
    """Recompute the frozen phase rules from the stored features (no quality gates)."""
    pos, spread, r120 = f.get("position_250"), f.get("ma_spread_20_60"), f.get("return_120")
    r20, r60, vr, c2h, dd = f.get("return_20"), f.get("return_60"), f.get("volume_ratio_20"), f.get("close_to_high"), f.get("drawdown_from_lookback_high")
    acc = pos is not None and spread is not None and r120 is not None and pos < ACC["position_250_lt"] and spread < ACC["ma_spread_20_60_lt"] and r120 < ACC["return_120_lt"]
    markup = vr is not None and ((r20 is not None and r20 > MARKUP["return_20_gt"]) or (r60 is not None and r60 > MARKUP["or_return_60_gt"])) and vr > MARKUP["volume_ratio_20_gt"]
    dist = None
    if pos is not None and vr is not None and c2h is not None:
        rejection = c2h < DIST["close_to_high_lt"] or (r20 is not None and r20 < DIST["or_return_20_lt"])
        dist = pos > DIST["position_250_gt"] and vr > DIST["volume_ratio_20_gt"] and rejection
    else:
        dist = False
    margins = {
        "position_250 vs <0.65": None if pos is None else ACC["position_250_lt"] - pos,
        "ma_spread_20_60 vs <0.09": None if spread is None else ACC["ma_spread_20_60_lt"] - spread,
        "return_120 vs <0.25": None if r120 is None else ACC["return_120_lt"] - r120,
        "return_20 vs markup >0.18": None if r20 is None else r20 - MARKUP["return_20_gt"],
        "return_60 vs markup >0.35": None if r60 is None else r60 - MARKUP["or_return_60_gt"],
        "volume_ratio_20 vs markup >1.05": None if vr is None else vr - MARKUP["volume_ratio_20_gt"],
        "volume_ratio_20 vs distribution >1.45": None if vr is None else vr - DIST["volume_ratio_20_gt"],
        "position_250 vs distribution >0.78": None if pos is None else pos - DIST["position_250_gt"],
        "drawdown vs failed_markup <=-0.10": None if dd is None else dd - FAILED_DD,
        "volume_ratio_20 vs entry >=1.5": None if vr is None else vr - ENTRY_VR,
        "close vs ma20 (close/ma20-1)": None if (f.get("ma20") in (None, 0) or f.get("close") is None) else f["close"] / f["ma20"] - 1.0,
    }
    return {"accumulation_rule": acc, "markup_rule": markup, "distribution_rule": dist,
            "failed_markup_drawdown_condition": (dd is not None and dd <= FAILED_DD), "margins": margins}


def boilerplate_checks(rec: dict, label: str, problems: list[str]) -> None:
    """Constant fields that the compact dossier omits; any deviation is reported instead of hidden."""
    if rec["calendar"]["source_ref"] != STD_CALENDAR or rec["calendar"]["sessions"] != 667:
        problems.append(f"{label}: non-standard calendar {rec['calendar']['source_ref']}")
    if rec["semantics"] != STD_SEMANTICS:
        problems.append(f"{label}: non-standard semantics {rec['semantics']}")
    if rec["pit"]["provenance_kind"] != "retrospective_capture_not_point_in_time" or rec["pit"]["mode"] != "retrospective":
        problems.append(f"{label}: non-standard pit {rec['pit']}")
    rd = rec["request_diagnostics"]
    if rd["rows_excluded_after_cutoff"] or rd["rows_excluded_late_availability"] or rd["benchmark"]["rows_excluded_after_cutoff"] or rd["benchmark"]["rows_excluded_late_availability"]:
        problems.append(f"{label}: request_diagnostics excluded rows {rd}")
    if rd["rows_offered"] != rec["input_availability"]["rows_consumed"] or rd["benchmark"]["rows_offered"] != rec["benchmark_availability"]["rows_consumed"]:
        problems.append(f"{label}: offered != consumed {rd}")
    refs = rec["security_context"]["evidence_refs"]
    if not refs or not refs[0].startswith(STD_PILOT_REF):
        problems.append(f"{label}: non-standard context evidence refs {refs}")
    if rec["provenance"]["benchmark_symbol"] != "SH000300" or rec["provenance"]["universe_source_ref"] != "pilot_symbols.csv sha256=97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe":
        problems.append(f"{label}: non-standard benchmark/universe provenance")
    if rec["input_availability"]["max_trade_date_consumed"] != rec["cutoff"]["decision_date"] and rec["current_state"] == "observed":
        problems.append(f"{label}: observed but last consumed trade date != decision date")
    if rec["input_availability"]["availability_violations_consumed"] != rec["input_availability"]["rows_consumed"]:
        problems.append(f"{label}: availability violations != rows consumed (unexpected mixed availability)")
    if rec["context_availability"]["status"] != "consumed_with_availability_violation" or not rec["context_availability"]["usable"]:
        problems.append(f"{label}: context availability {rec['context_availability']}")
    cov = rec["identity"]["decision_inputs"]["coverage"]
    if cov is None or cov["status"] != "consumed_with_availability_violation" or not cov["usable"]:
        problems.append(f"{label}: coverage state {cov}")


def core_lines(rec: dict, title: str, compact: bool = COMPACT) -> list[str]:
    f = rec["features"]; L = rec["labels"]; sv = rec["session_view"]; sc = rec["security_context"]
    ev = rule_eval(f)
    cov = rec["identity"]["decision_inputs"]["coverage"]
    out = [f"--- {title}: {rec['symbol']} {rec['cutoff']['decision_date']} session#{sv['decision_session_index']} state={rec['current_state']} record_hash={rec['record_hash']}",
           f"    episode_id={rec['episode_id']} split={rec['split_role']} role={rec['role']} synthetic={rec['synthetic']} in_universe={rec['universe']['in_frozen_universe']} policy={rec['policy_version']}/{rec['policy_hash'][:12]}",
           f"    phase={L['phase']['label']} rule={L['phase']['rule']} reasons={L['phase']['reasons']} markup_within_lookback={L['phase']['markup_within_lookback']}",
           f"    selection={L['selection']['label']} reasons={L['selection']['reasons']}",
           f"    entry={L['entry']['label']} reasons={L['entry']['reasons']} tradability={L['entry']['tradability']} legal_next_session={L['entry']['execution']['legal_next_session']}",
           f"    position_event={L['position_event']['label']} reasons={L['position_event']['reasons']} basis_verified={L['position_event']['basis_verified']}",
           f"    liquidity band={L['liquidity']['band']} amount_20_mean_cny={fmt(f.get('amount_20_mean_cny'),1)} (recomputed band={band_of(f.get('amount_20_mean_cny'))}) reasons={L['liquidity']['reasons']}",
           f"    regime={L['regime']['regime']} bench_r60={fmt(L['regime']['benchmark_return_60'])} bench_close_vs_ma60={fmt(L['regime']['benchmark_close_vs_ma60'])} price_only={L['regime']['price_only']} units={L['regime']['benchmark_units']} reasons={L['regime']['reasons']}",
           f"    limit board={L['limit']['board']} threshold={L['limit']['threshold_pct']} conf={L['limit']['confidence']} limit_like={L['limit']['limit_like_possible']} limit_down={L['limit']['limit_down_possible']}",
           f"    features: close={fmt(f.get('close'),3)} prev_close={fmt(f.get('prev_close'),3)} pct_change={fmt(f.get('pct_change'))} range_pct={fmt(f.get('range_pct'))} close_to_high={fmt(f.get('close_to_high'))} zero_vol={f.get('zero_volume_session')} scope_exc={f.get('scope_exception_on_bar')}",
           f"              ma20={fmt(f.get('ma20'),3)} ma60={fmt(f.get('ma60'),3)} ma_spread_20_60={fmt(f.get('ma_spread_20_60'))} high_250={fmt(f.get('high_250'),3)} position_250={fmt(f.get('position_250'))}",
           f"              return_20={fmt(f.get('return_20'))} return_60={fmt(f.get('return_60'))} return_120={fmt(f.get('return_120'))} drawdown_from_lookback_high={fmt(f.get('drawdown_from_lookback_high'))}",
           f"              volume_ratio_20={fmt(f.get('volume_ratio_20'))} known_days={f.get('volume_ratio_20_known_days')} bars_available={f.get('bars_available')}",
           f"    recomputed rules: accumulation={ev['accumulation_rule']} markup={ev['markup_rule']} distribution={ev['distribution_rule']} failed_dd_cond={ev['failed_markup_drawdown_condition']}",
           "    margins: " + "; ".join(f"{k}={fmt(v)}" for k, v in ev["margins"].items()),
           f"    session_view: interior_missing={sv['interior_missing_sessions']} suspensions_in_window={sv['suspensions_in_window']} longest_no_price_run={sv['longest_no_price_run_in_window']} since_last_price={sv['sessions_since_last_price']} window_first={sv['window_first_session']}",
           f"    data_quality={rec['data_quality']}",
           f"    security: listing={sc['listing_date']} st={sc['st_status']} CA={sc['corporate_action_status']} known_ex_dates={sc['known_ex_dates']} float_shares={sc['float_shares']} turnover={sc['turnover_available']} name={sc['name']} facts_available_at={sc['facts_available_at']}",
           (f"              evidence_refs={sc['evidence_refs']}" if (not compact or len(sc['evidence_refs']) != 1 or not sc['evidence_refs'][0].startswith(STD_PILOT_REF))
            else f"              evidence_refs=[standard pilot list_date ref; grade={sc['evidence_refs'][0].split('grade=')[-1]}]"),
           f"    availability: stock rows={rec['input_availability']['rows_consumed']} max_trade_date={rec['input_availability']['max_trade_date_consumed']} violations={rec['input_availability']['availability_violations_consumed']} captured_after_window={rec['input_availability']['captured_after_decision_window']} max_available_at={rec['input_availability']['max_available_at_consumed']}",
           f"                  bench rows={rec['benchmark_availability']['rows_consumed']} bench max_trade_date={rec['benchmark_availability']['max_trade_date_consumed']} bench violations={rec['benchmark_availability']['availability_violations_consumed']}",
           f"    coverage: ratio={cov['ratio'] if cov else None} evidence={cov['evidence_ref'] if cov else None} status={cov['status'] if cov else None} context_status={rec['context_availability']['status']}",
           f"    provenance: combined stock+benchmark locator union n={len(rec['provenance']['source_refs'])} (m3_labels.py:1585 sorted set union; NOT a stock-only range) first={rec['provenance']['source_refs'][0]} last={rec['provenance']['source_refs'][-1]}",
           f"                per-role consumption: stock observations consumed={rec['input_availability']['rows_consumed']} (bars_available={f.get('bars_available')}, position-window first session={sv['window_first_session']}, listing={sc['listing_date']}); benchmark rows consumed={rec['benchmark_availability']['rows_consumed']}; zero-index locators={[x for x in rec['provenance']['source_refs'] if x.endswith('#0')]}",
           f"                input_fp={rec['provenance']['input_fingerprint'][:16]} bench_fp={rec['provenance']['benchmark_fingerprint'][:16]} bench={rec['provenance']['benchmark_symbol']}"]
    if not compact:
        out += [f"                calendar={rec['calendar']['source_ref']} sessions={rec['calendar']['sessions']} fp={rec['calendar']['fingerprint'][:16]}",
                f"    pit: strict_pit_eligible={rec['pit']['strict_pit_eligible']} training_eligible={rec['pit']['training_eligible']} provenance_kind={rec['pit']['provenance_kind']} semantics={rec['semantics']}",
                f"    review_ledger status={rec['review_ledger']['status']} entries={len(rec['review_ledger']['entries'])} review_only={rec['review_only']} live_trading_enabled={rec['live_trading_enabled']}",
                f"    request_diagnostics={rec['request_diagnostics']}"]
    else:
        out.append("    [compact: calendar/pit/semantics/ledger/request_diagnostics verified against standard constants; deviations are listed under VERIFICATION PROBLEMS]")
    return out


def verify_core(m, rec: dict, label: str, problems: list[str]) -> None:
    try:
        v = m.verify_record(rec)
        m.validate_ledger(rec)
        if v["record_hash"] != rec["record_hash"]:
            problems.append(f"{label}: record_hash mismatch")
        if rec["review_ledger"]["entries"] or rec["review_ledger"]["status"] != "pending_review":
            problems.append(f"{label}: ledger not empty/pending")
        if rec["policy_hash"] != POLICY_HASH or rec["producer_sha256"] != LABELS_SHA256:
            problems.append(f"{label}: policy/producer pin mismatch")
        if rec["synthetic"] or rec["role"] != "stock" or rec["split_role"] != "development":
            problems.append(f"{label}: synthetic/role/split unexpected")
        if rec["cutoff"]["mode"] != "retrospective" or rec["cutoff"]["convention"] != "close+3600s":
            problems.append(f"{label}: cutoff convention unexpected")
        if rec["pit"]["strict_pit_eligible"] or rec["pit"]["training_eligible"] or not rec["review_only"] or rec["live_trading_enabled"]:
            problems.append(f"{label}: safety flags unexpected")
        if rec["cutoff"]["decision_date"] > "2025-03-31" or (rec["input_availability"]["max_trade_date_consumed"] or "0000") > "2025-03-31":
            problems.append(f"{label}: beyond development bound")
        # arithmetic self-consistency of the stored features
        f = rec["features"]
        if f.get("close") is not None and f.get("prev_close"):
            if abs((f["close"] / f["prev_close"] - 1.0) - f["pct_change"]) > 1e-12:
                problems.append(f"{label}: pct_change arithmetic")
        if f.get("ma20") is not None and f.get("ma60"):
            if abs(abs(f["ma20"] - f["ma60"]) / f["ma60"] - f["ma_spread_20_60"]) > 1e-12:
                problems.append(f"{label}: ma_spread arithmetic")
        ev = rule_eval(f)
        ph = rec["labels"]["phase"]
        if ph["rule"] != "quality_gate":
            expected = "distribution" if ev["distribution_rule"] else "markup" if ev["markup_rule"] else (
                "failed_markup" if (ph["markup_within_lookback"] and ev["failed_markup_drawdown_condition"]) else "accumulation" if ev["accumulation_rule"] else "indeterminate")
            if expected != ph["label"]:
                problems.append(f"{label}: phase rule recomputation {expected} != {ph['label']}")
        if rec["labels"]["liquidity"]["band"] != band_of(f.get("amount_20_mean_cny")):
            problems.append(f"{label}: liquidity band recomputation")
        rg = rec["labels"]["regime"]
        if rg["regime"] != "unknown":
            r60, cvm = rg["benchmark_return_60"], rg["benchmark_close_vs_ma60"]
            exp = "bull" if (cvm > 0 and r60 > 0.05) else "bear" if (cvm < 0 and r60 < -0.05) else "range"
            if exp != rg["regime"]:
                problems.append(f"{label}: regime recomputation {exp} != {rg['regime']}")
        lim = rec["labels"]["limit"]
        if f.get("pct_change") is not None:
            move = f["pct_change"] * 100.0
            if lim["limit_like_possible"] != (move >= lim["threshold_pct"]) or lim["limit_down_possible"] != (move <= -lim["threshold_pct"]):
                problems.append(f"{label}: limit recomputation")
        sel = rec["labels"]["selection"]
        if rec["current_state"] != "observed" and sel["label"] != "indeterminate":
            problems.append(f"{label}: selection vs current_state")
        if ph["label"] in ("markup", "distribution", "failed_markup") and sel["label"] != "non_candidate":
            problems.append(f"{label}: selection vs phase")
        if sel["label"] == "candidate" and (ph["label"] != "accumulation" or rec["labels"]["liquidity"]["band"] == "unknown"):
            problems.append(f"{label}: candidate without accumulation/known band")
        boilerplate_checks(rec, label, problems)
    except Exception as exc:  # noqa: BLE001 - report every failure
        problems.append(f"{label}: verify failed: {exc}")


def packet_hash(view: dict) -> str:
    content = {k: v for k, v in view.items() if k not in ("cutoff_packet_hash", "review_status", "reviews")}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def show_case(m, case_id: str, manifest: dict) -> tuple[list[str], dict]:
    rel = f"cases/{case_id}.json"
    path = BUNDLE / rel
    file_sha = sha(path)
    if file_sha != manifest["written"][rel]["sha256"]:
        raise SystemExit("case file pin mismatch")
    index = json.loads((BUNDLE / "index.json").read_text(encoding="utf-8"))
    idx = next(c for c in index["cases"] if c["case_id"] == case_id)
    if idx["sha256"] != file_sha:
        raise SystemExit("index pin mismatch")
    c = json.loads(path.read_text(encoding="utf-8"))
    p = c["cutoff_packet"]; rep = c["representative_record"]; prefix = c["prefix_records"]; controls = c["control_records"]
    problems: list[str] = []
    if c["reviews"] or c["review_status"] != "pending_actual_individual_reviews" or p["reviews"] or p["review_status"] != "pending_review":
        problems.append("input already carries reviews")
    if packet_hash(p) != p["cutoff_packet_hash"] or p["cutoff_packet_hash"] != idx["cutoff_packet_hash"]:
        problems.append("cutoff_packet_hash recomputation mismatch")
    proof = p["prefix_proof"]
    if proof["prefix_hash"] != idx["case_prefix_hash"] or proof["representative_record_hash"] != rep["record_hash"] or proof["representative_episode_id"] != rep["episode_id"]:
        problems.append("prefix proof / representative binding mismatch")
    if m.sha256_text(m.canonical_json({k: v for k, v in proof.items() if k != "prefix_hash"})) != proof["prefix_hash"]:
        problems.append("prefix_hash recomputation mismatch")
    if [r["record_hash"] for r in prefix] != proof["member_record_hashes"] or [r["episode_id"] for r in prefix] != proof["member_episode_ids"]:
        problems.append("embedded prefix records do not match the proof members")
    if [x["record_hash"] for x in p["members"]] != proof["member_record_hashes"]:
        problems.append("packet members do not match the proof")
    if prefix[-1]["record_hash"] != rep["record_hash"]:
        problems.append("representative is not the third prefix member")
    sess = [r["session_view"]["decision_session_index"] for r in prefix]
    if sess != [sess[0], sess[0] + 1, sess[0] + 2]:
        problems.append(f"prefix members not consecutive sessions: {sess}")
    if any(r["labels"]["phase"]["label"] != "accumulation" for r in prefix) or any(r["symbol"] != rep["symbol"] for r in prefix):
        problems.append("prefix member phase/symbol mismatch")
    if proof["policy_hash"] != POLICY_HASH or proof["calendar_fingerprint"] != rep["calendar"]["fingerprint"] or proof["start"] != prefix[0]["cutoff"]["decision_date"] or proof["established_at"] != rep["cutoff"]["decision_date"]:
        problems.append("prefix proof fields mismatch")
    for i, r in enumerate(prefix):
        verify_core(m, r, f"prefix[{i}] {r['cutoff']['decision_date']}", problems)
    if any(len(r["review_ledger"]["entries"]) for r in prefix + controls + [rep]):
        problems.append("a core already carries ledger entries")
    # match / controls
    match = p["match"]
    if match is None or p["exclusion"] is not None:
        problems.append("case is not a matched case")
    else:
        if match["positive_record_hash"] != rep["record_hash"] or match["positive_episode_id"] != rep["episode_id"] or match["decision_date"] != rep["cutoff"]["decision_date"]:
            problems.append("match positive binding mismatch")
        if [x["record_hash"] for x in match["controls"]] != [x["record_hash"] for x in p["controls"]] or [x["record_hash"] for x in p["controls"]] != [r["record_hash"] for r in controls]:
            problems.append("control refs / embedded control records mismatch")
        if not (3 <= len(controls) <= 5) or len({r["symbol"] for r in controls}) != len(controls) or rep["symbol"] in {r["symbol"] for r in controls}:
            problems.append("control count/distinctness")
        for i, r in enumerate(controls):
            verify_core(m, r, f"control[{i}] {r['symbol']}", problems)
            if r["cutoff"]["decision_date"] != rep["cutoff"]["decision_date"] or r["cutoff"]["mode"] != rep["cutoff"]["mode"] or r["cutoff"]["convention"] != rep["cutoff"]["convention"]:
                problems.append(f"control {r['symbol']}: date/cutoff mismatch")
            if r["labels"]["selection"]["label"] != "non_candidate":
                problems.append(f"control {r['symbol']}: not non_candidate")
            if r["labels"]["liquidity"]["band"] != rep["labels"]["liquidity"]["band"] or r["labels"]["regime"]["regime"] != rep["labels"]["regime"]["regime"]:
                problems.append(f"control {r['symbol']}: band/regime mismatch")
            if r["labels"]["liquidity"]["band"] == "unknown" or r["labels"]["regime"]["regime"] == "unknown":
                problems.append(f"control {r['symbol']}: band/regime unknown")
            if r["universe"]["universe_sha256"] != rep["universe"]["universe_sha256"] or not r["universe"]["in_frozen_universe"] or r["synthetic"] != rep["synthetic"]:
                problems.append(f"control {r['symbol']}: universe/synthetic mismatch")
            if r["policy_hash"] != rep["policy_hash"] or r["policy_version"] != rep["policy_version"] or r["calendar"]["fingerprint"] != rep["calendar"]["fingerprint"]:
                problems.append(f"control {r['symbol']}: policy/calendar mismatch")
            if r["current_state"] != "observed":
                problems.append(f"control {r['symbol']}: not observed")
            pc = p["controls"][i]["core_summary"]
            for key, val in (("record_hash", r["record_hash"]), ("phase", r["labels"]["phase"]["label"]), ("selection", r["labels"]["selection"]["label"]),
                             ("liquidity_band", r["labels"]["liquidity"]["band"]), ("regime", r["labels"]["regime"]["regime"]), ("amount_20_mean_cny", r["features"]["amount_20_mean_cny"])):
                if pc.get(key) != val:
                    problems.append(f"control {r['symbol']}: packet summary {key} disagrees with core")
        try:
            m.revalidate_match(match, m.RecordRegistry([rep] + controls))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"revalidate_match failed: {exc}")
        # ranking check from the cores: selected controls must be the k lowest |ln ratio| eligible entries
        rank = p["control_ranking"]
        elig = [x for x in rank if x["eligible"]]
        chosen = [r["symbol"] for r in controls]
        if [x["symbol"] for x in elig[: len(controls)]] != chosen:
            problems.append("selected controls are not the top-k eligible by ranking")
        for x in elig[: len(controls)]:
            r = next(cr for cr in controls if cr["symbol"] == x["symbol"])
            ratio = abs(math.log(r["features"]["amount_20_mean_cny"] / rep["features"]["amount_20_mean_cny"]))
            if abs(ratio - x["abs_ln_amount_ratio"]) > 1e-9:
                problems.append(f"control {x['symbol']}: |ln amount ratio| recomputation")
        pool_syms = {x["symbol"] for x in p["control_pool"]["pool"]}
        if rep["symbol"] in pool_syms or any(s.startswith(("SH000", "SZ399")) for s in pool_syms):
            problems.append("pool contains positive or benchmark")
    verify_core(m, rep, "representative", problems)
    # ---- dossier
    lines = [f"===== {case_id} {p['symbol']} representative {rep['cutoff']['decision_date']} | file {rel} sha256={file_sha}",
             f"cutoff_packet_hash={p['cutoff_packet_hash']} prefix_hash={proof['prefix_hash']} episode_key={p['episode_key']}",
             f"information_time: {p['information_time']}",
             f"prefix: start={proof['start']} established_at={proof['established_at']} members={[x['decision_date'] for x in p['members']]} prefix_path={p['prefix_path']}",
             f"packet supporting_evidence={p['supporting_evidence']}",
             f"packet contradicting_evidence={p['contradicting_evidence']}",
             f"packet uncertainties={json.dumps(p['uncertainties'], ensure_ascii=False)}",
             f"warmup_depth_at_representative={p['warmup_depth_at_representative']} price_context={json.dumps(p['price_context'], ensure_ascii=False)}",
             "NOTE: price_context.first/last_consumed_source_ref and consumed_observation_keys describe the combined stock+benchmark locator union (accepted m3_labels.py:1585); stock-only consumption is input_availability.rows_consumed / features.bars_available per core (M3_03_PROVENANCE_DISPLAY_CLARIFICATION.md 1bb8cb29...).",
             f"source_binding: delivery_manifest={c['source_binding']['delivery_manifest_sha256'][:16]} source_replay={c['source_binding']['source_replay_sha256'][:16]} packet_audit={c['source_binding']['packet_audit_sha256'][:16]} original_packet={c['source_binding']['original_packet_sha256'][:16]}",
             "", "##### PREFIX MEMBERS (cutoff-known cores)"]
    for i, r in enumerate(prefix):
        lines += core_lines(r, f"prefix member {i + 1}/3" + (" (= representative)" if i == 2 else ""))
    lines += ["", "##### CONTROL POOL / MATCH",
              f"match: k={match['control_count'] if match else None} k_min/k_max={match['k_min'] if match else None}/{match['k_max'] if match else None} pool_size={p['control_pool']['pool_size']} rejected={match['rejected_pool_counts'] if match else None} purpose={match['purpose'] if match else None} split={match['split_role'] if match else None} unmatched={match['unmatched'] if match else None}",
              "ranking (eligible first; selected marked *):"]
    chosen = [r["symbol"] for r in controls]
    same_band_ineligible = []
    other = {}
    for x in p["control_ranking"]:
        if x["eligible"]:
            mark = "*" if x["symbol"] in chosen else " "
            lines.append(f"  {mark} {x['symbol']} eligible={x['eligible']} sel={x['selection']} band={x['liquidity_band']} regime={x['regime']} state={x['current_state']} |ln amt ratio|={fmt(x['abs_ln_amount_ratio'])}")
        elif x["liquidity_band"] == rep["labels"]["liquidity"]["band"]:
            same_band_ineligible.append(f"{x['symbol']}({x['selection']},{x['regime']},{x['current_state']},{fmt(x['abs_ln_amount_ratio'], 2)})")
        else:
            key = (x["selection"], x["liquidity_band"], x["regime"])
            other[key] = other.get(key, 0) + 1
    lines.append("  same-band ineligible (selection,regime,state,|ln ratio|): " + (", ".join(same_band_ineligible) or "none"))
    lines.append("  other-band ineligible (selection,band,regime)->n: " + ("; ".join(f"{k}={v}" for k, v in sorted(other.items())) or "none"))
    pool_phase = {}
    for x in p["control_pool"]["pool"]:
        pool_phase[(x["phase"], x["selection"], x["liquidity_band"])] = pool_phase.get((x["phase"], x["selection"], x["liquidity_band"]), 0) + 1
    lines.append("pool composition (phase, selection, band) -> n: " + "; ".join(f"{k}={v}" for k, v in sorted(pool_phase.items())))
    lines.append("")
    lines.append("##### SELECTED CONTROL CORES")
    for i, r in enumerate(controls):
        rk = next(x for x in p["control_ranking"] if x["symbol"] == r["symbol"])
        lines += core_lines(r, f"control {i + 1}/{len(controls)} rank |ln amount ratio|={fmt(rk['abs_ln_amount_ratio'])}")
    lines += ["", f"##### VERIFICATION PROBLEMS: {problems if problems else 'none'}"]
    receipt = {"case_id": case_id, "file": rel, "file_sha256": file_sha, "cutoff_packet_hash": p["cutoff_packet_hash"], "prefix_hash": proof["prefix_hash"],
               "representative_record_hash": rep["record_hash"], "representative_episode_id": rep["episode_id"],
               "prefix_member_record_hashes": proof["member_record_hashes"], "control_record_hashes": [r["record_hash"] for r in controls],
               "control_symbols": chosen, "cores_verified": 3 + len(controls), "problems": problems}
    return lines, receipt


def show_diagnostic(m, diag_id: str, manifest: dict) -> tuple[list[str], dict]:
    rel = f"diagnostics/{diag_id}.json"
    path = BUNDLE / rel
    file_sha = sha(path)
    if file_sha != manifest["written"][rel]["sha256"]:
        raise SystemExit("diagnostic file pin mismatch")
    index = json.loads((BUNDLE / "index.json").read_text(encoding="utf-8"))
    idx = next(d for d in index["diagnostics"] if d["case_id"] == diag_id)
    if idx["sha256"] != file_sha:
        raise SystemExit("index pin mismatch")
    d = json.loads(path.read_text(encoding="utf-8"))
    rec = d["record"]
    problems: list[str] = []
    if d["reviews"] or d["counts_as_positive_episode"] is not False:
        problems.append("diagnostic input state unexpected")
    if rec["record_hash"] != idx["record_hash"] or rec["symbol"] != idx["symbol"] or rec["cutoff"]["decision_date"] != idx["decision_date"]:
        problems.append("index binding mismatch")
    verify_core(m, rec, "diagnostic record", problems)
    lines = [f"===== {diag_id} kind={d['diagnostic_kind']} | file {rel} sha256={file_sha}", f"selection_rule: {d['selection_rule']}",
             f"counts_as_positive_episode={d['counts_as_positive_episode']} origin(provenance only)={d['origin']['chronology_file']}#{d['origin']['line']}"]
    lines += core_lines(rec, "diagnostic core")
    lines += ["", f"##### VERIFICATION PROBLEMS: {problems if problems else 'none'}"]
    receipt = {"case_id": diag_id, "file": rel, "file_sha256": file_sha, "record_hash": rec["record_hash"], "episode_id": rec["episode_id"],
               "diagnostic_kind": d["diagnostic_kind"], "cores_verified": 1, "problems": problems}
    return lines, receipt


def main() -> int:
    ids = sys.argv[1:] or ["C001"]
    manifest = check_bundle_pins()
    m = load_labels()
    DOSSIERS.mkdir(parents=True, exist_ok=True)
    for cid in ids:
        started = datetime.now(timezone.utc).isoformat()
        lines, receipt = show_case(m, cid, manifest) if cid.startswith("C") else show_diagnostic(m, cid, manifest)
        text = "\n".join(lines) + "\n"
        dossier = DOSSIERS / f"{cid}.txt"
        dossier.write_bytes(text.encode("utf-8"))
        entry = {"tool": "show_case_evidence.py", "tool_sha256": sha(Path(__file__)), "inspected_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                 "bundle_manifest_sha256": BUNDLE_MANIFEST_SHA256, "labels_sha256": LABELS_SHA256, "policy_hash": POLICY_HASH,
                 "dossier": str(dossier.relative_to(PROJECT)).replace("\\", "/"), "dossier_sha256": sha(dossier), **receipt}
        with open(LOG, "ab") as fh:
            fh.write((json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8"))
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
