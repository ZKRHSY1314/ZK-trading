"""Render claude_03b/REPORT.md from the single run folder under claude_03b/runs/ (numbers only from the receipts).

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_03b/build_report.py"
"""
from __future__ import annotations

import collections
import gzip
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_counter(d: dict) -> str:
    return ", ".join(f"`{k}`={v}" for k, v in sorted(d.items())) if d else "—"


def main() -> int:
    run = HERE / "runs" / "829d42809e978c04"                       # original guarded historical run (delivery 01, byte-identical)
    revised = HERE / "runs" / "829d42809e978c04-rev02"             # export-only repair (revision 2)
    receipt, funnel, recon, depths = load(run / "receipt.json"), load(run / "funnel.json"), load(run / "reconciliation.json"), load(run / "warmup_depths.json")
    synth = load(HERE / "evidence" / "synthetic_test_receipt.json")
    synth2 = load(HERE / "evidence" / "synthetic_test_receipt_rev02.json")
    rev = load(revised / "revision_receipt.json")
    b = {name: load(run / "branches" / name / "summary.json") for name in receipt["branches"]}
    b2 = {name: load(revised / "branches" / name / "summary.json") for name in receipt["branches"]}
    a = b["assumed_full_fill"]
    rp = receipt["read_phase"]
    L = []
    L.append("# M4-03B development replay — REPORT (delivery 02 / revision 2, `ready_for_review`)\n")
    L.append("Revision 2 after Codex `M4_03B_REVIEW_01.md` (`a0fc04e7…`). Three distinct activities are kept apart throughout: **(a)** the original guarded two-connection historical run `runs/829d42809e978c04/` (delivery 01, every file byte-identical, numbers unchanged); **(b)** a zero-connection, deterministic **export-only repair** `runs/829d42809e978c04-rev02/` that adds benchmark endpoint provenance / initial-cash / listed-default metadata to the four performance wrappers and nothing else; **(c)** corrected synthetic validation (17 tests: 13 original + non-default-cash zero-trade and hand-calculated-return + assumed/raw benchmark endpoint provenance). No historical runner invocation and no SQLite connection occurred in this revision.\n")
    L.append(f"Task `M4-03B-DEVELOPMENT-REPLAY-20260912` (task file `8290d8c8…`). Run id `{receipt['run_id']}` (= sha256(input hash + model hash)[:16]); run folder `{receipt['run_dir']}`; sealed input hash `{receipt['sealed_input']['input_hash']}`; model hash `{receipt['sealed_input']['model_hash']}`. Frozen engines `83a28b54…` / `2b3eec83…` / `faec444e…` (policy hashes `{receipt['engine_policy_hashes']['kernel'][:8]}…` / `{receipt['engine_policy_hashes']['ledger'][:8]}…` / `{receipt['engine_policy_hashes']['risk'][:8]}…`), accepted mapping `276cb037…`. Status: **ready_for_review — not accepted; M4_complete=false.**\n")
    L.append("## 0. Three distinct outcomes (read this first)\n")
    L.append("1. **Already validated synthetic engine evidence** (M4-01 / M4-02A / M4-02B / M4-03A, unchanged): the kernel, ledger, risk layer and the causal mapping are deterministic and correct on synthetic fixtures; re-confirmed here by 13 focused synthetic tests run inside this task's guard before any historical access (two-symbol global order, causal other-held marks, halts, capacities, censoring, hash determinism, future-suffix control, raw refusals).")
    perf = a["performance"]
    L.append(f"2. **This actual assumed historical-shape replay** (calendar slice {recon['calendar']['slice_first']}…{recon['calendar']['slice_last']} = 250 warmup sessions + 378 decision sessions 2023-09-04…2025-03-31 + the next legal session as metadata only; B0 fixed, nothing tuned): under the declared assumption set the frozen chain produced the observed counts in §3 — primary branch `assumed_full_fill`: buy attempts {sum(v for k, v in a['funnel']['attempt_outcomes'].items() if k.startswith('buy:'))}, buy fills {a['funnel']['attempt_outcomes'].get('buy:filled', 0)}, exit intents {sum(v for k, v in a['funnel']['exit_intents'].items() if not k.startswith('held:'))}, hypothetical end equity `{perf.get('equity')}` (return `{perf.get('return')}`, realized `{perf.get('realized_pnl_total')}`) versus benchmark SH000300 `{(perf.get('benchmark') or {}).get('return')}` — **conditional on assumptions, every record graded `assumed`, every position `adjustment_uncertainty=true`; not historical execution evidence.**")
    raw = b["raw"]
    L.append(f"3. **Unmet genuine historical execution evidence**: the raw branch (capture instants kept as availability) produced {raw['funnel']['intents_by_status'] or 'no'} intents and {len(raw.get('ledger_records', [])) if isinstance(raw.get('ledger_records'), list) else raw['ledger_records_file']['records']} ledger records; decisions refused the marks/benchmark/signals as `future_evidence` ({raw['funnel']['decision_refusals']}). The M4 acceptance item \"at least one deliberately simple baseline generates expected non-zero trades … on eligible historical data\" remains **unmet**: no frozen field carries historical availability, ST/bands/capacity/fees/corporate actions/delistings are assumed or missing (M4-03A matrix), and the pool is a 2026 survivor selection. Assumed nonzero fills and passing guards do not make historical eligibility pass.\n")
    L.append("## 1. Guarded read (exactly two immutable connections)\n")
    L.append("(Activity (a) — the original delivery-01 run; unchanged.)\n")
    L.append(f"* Guard self-check before anything: {receipt['guard_self_check']}. Synthetic validation inside the runner: {synth['tests_run']} tests, {synth['failures']} failures, {synth['errors']} errors, guard denials during tests {synth['guard_denials_during_tests']}.")
    for key, c in rp["connections"].items():
        L.append(f"* `{key}`: `{c['uri']}` (uri=True, isolation_level=None, extension loading {c['extension_loading']}, `PRAGMA query_only` read back = {c['query_only_read_back']}, authorizer: {c['authorizer']}).")
    L.append(f"* Connections opened: **{rp['connections_opened']}**; denials during the read: {rp['denials_during_read']}; Q10 omitted. Stores before/after/final: identical sha256 / size / mtime_ns, no `-wal`/`-shm`/`-journal` (receipt `stores_before_read`, `stores_after_read`, `stores_final`).")
    L.append("* SQL executed (text, bound parameters, rows):")
    L.append("| # | store | SQL | params | rows |")
    L.append("|---|---|---|---|---|")
    for q in rp["sql_log"]:
        L.append(f"| {q['name']} | {q['store']} | `{q['sql']}` | `{q['parameters']}` | {q['rows']} (expected {q['expected_rows']}) |")
    L.append("")
    L.append("## 2. Reconciliation and sealed input\n")
    L.append(f"* Rows: {recon['counts']}; accepted price keys **{recon['accepted_price_keys']}**, accepted halt keys **{recon['accepted_halt_keys']}**, exclusions **{recon['exclusion_count']}**; numeric digest `{recon['numeric_rows_sha256'][:16]}…` equals the prior development audit's `numeric_rows_sha256` → **{recon['numeric_digest_matches_prior_audit']}**; bars by role/segment {recon['bars_by_role_and_segment']}; rows before the warmup window reconciled but not consumed: {recon['rows_before_warmup_start_reconciled_not_consumed']}.")
    L.append(f"* Calendar: `{recon['calendar']['normalization']}`; slice {recon['calendar']['slice_first']} … {recon['calendar']['slice_last']} ({recon['calendar']['slice_sessions']} sessions = 250 warmup + 378 development + the next legal session {recon['calendar']['next_legal_session_after_end']}, whose prices are never read).")
    L.append(f"* Warmup depths inside the fixed window {depths['window'][0]}…{depths['window'][1]} (recomputed here, not asserted from the audit): stocks with 250 bars **{depths['stocks_with_full_250']}**, with 0 bars **{depths['stocks_with_zero']}**; partial: " + ", ".join(f"{s}={d['bars_in_window']}" for s, d in sorted(depths['per_symbol'].items()) if receipt['sealed_input'] and 0 < d['bars_in_window'] < 250 and not s.startswith('SH000')) + ".")
    L.append(f"* Sealed input hash `{receipt['sealed_input']['input_hash']}` over {receipt['sealed_input']['bars']} bars and {receipt['sealed_input']['halt_keys']} halt keys for {receipt['sealed_input']['stocks']} stocks + 2 indices; all repeats and branches consumed this one in-memory snapshot without reconnecting.\n")
    L.append("## 3. Branch results (each from a fresh ledger; two repeats per branch, hashes identical)\n")
    L.append("| branch | variant / capacity | decision stages | entry outcomes | buy attempts | sell attempts | exit intents | intents by status | end status |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for name, s in b.items():
        f = s["funnel"]
        buys = {k[4:]: v for k, v in f["attempt_outcomes"].items() if k.startswith("buy:")}
        sells = {k[5:]: v for k, v in f["attempt_outcomes"].items() if k.startswith("sell:")}
        other = {k: v for k, v in f["attempt_outcomes"].items() if not k.startswith(("buy:", "sell:"))}
        p = s["performance"]
        L.append(f"| `{name}` | {s['variant']} / {s['capacity_variant']} | {fmt_counter(f['decision_stage'])} | {fmt_counter(f['entry_outcomes'])} | {fmt_counter(buys)}{('; ' + fmt_counter(other)) if other else ''} | {fmt_counter(sells)} | {fmt_counter(f['exit_intents'])} | {fmt_counter(f['intents_by_status'])} | status `{p.get('status')}`, cash `{p.get('cash')}`, equity `{p.get('equity')}`, return `{p.get('return')}`, realized `{p.get('realized_pnl_total')}`, benchmark `{(p.get('benchmark') or {}).get('return')}`, open positions {len(s['censored']['open_positions'])}, live intents beyond window {len(s['censored']['live_intents_beyond_window'])}, ledger reconcile ok {s['ledger_reconcile']['ok']} |")
    L.append("")
    L.append("Refined attempt classification derived from the exported research records (side, engine intent status, kernel status, fill, kernel reasons) — the raw `attempt_outcomes` keys above group a partially filled order whose remainder expired under `buy:expired`:\n")
    L.append("| branch | side | intent status | kernel status | filled shares | kernel reasons | attempts |")
    L.append("|---|---|---|---|---|---|---|")
    for name in b:
        c = collections.Counter()
        with gzip.open(run / "branches" / name / "research_records.jsonl.gz", "rt", encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r["kind"] != "attempt":
                    continue
                e = r["engine_record"]; o = e.get("outcome") or {}; kr = ((e.get("ledger_record") or {}).get("kernel") or {})
                c[(r["side"], e["status"], kr.get("status") or e.get("reason"), "yes" if o.get("filled_quantity") else "no", "+".join(sorted(q["code"] for q in kr.get("reasons", []))) or "—")] += 1
        for key, n in sorted(c.items()):
            L.append(f"| `{name}` | {key[0]} | {key[1]} | {key[2]} | {key[3]} | {key[4]} | {n} |")
    L.append("")
    L.append("Funnel semantics: `decision_stage` counts are mutually exclusive per (symbol, session) in the order not_listed → halt_key → missing_unconfirmed_row → price_row, and inside price_row: new_listing_exclusion (attempt session within the first five listing sessions, listing age = index(session) − index(listing_date)) → insufficient_history (fewer than 21 consecutive price-bar sessions ending at the decision session) → no_signal → signal; `entry_outcomes` are the engine's decisions for signals (buy intent / zero_size / refused with the engine's reason); attempt keys carry the kernel's reason codes; `swept_expired_at_decision` counts intents expired by the next decision's sweep; a signal on 2025-03-31 becomes a live intent for 2025-04-01 that is never attempted (censored).\n")
    L.append("## 4. Determinism, chronology and provenance\n")
    for name, d in funnel["determinism"].items():
        L.append(f"* `{name}`: repeat 1 `{d['repeat_1_output_hash'][:16]}…` = repeat 2 `{d['repeat_2_output_hash'][:16]}…` → identical **{d['identical']}**; engine chain `{d['engine_chain_hash'][:16]}…`, ledger state `{d['ledger_state_hash'][:16]}…`.")
    L.append("* Global event order: for every session, due open attempts (exits before entries, then symbol / intent id) run at 09:30 with their original bound decision contexts before the 16:00 decision; the engine's policy event clock is monotone across the whole run (proved on the synthetic two-symbol case; the historical records carry the same `state_summary.event_clock`).")
    L.append("* Buys at the open value OTHER held symbols at their last already-available close (model instant of that earlier session, actual dates and ages recorded under `raw_provenance[role=other_held_mark]`); a held symbol without an eligible prior close makes the re-check `valuation_incomplete` (refusal), never zero. Decisions use closes of the same session only (`max_mark_age_sessions=0`); a halted holding makes the valuation incomplete.")
    L.append("* Every exported research record keeps the unmodified engine record plus: `grade` (`assumed` / `raw`), `model_time`, `assumption_ids`, and `raw_provenance` with symbol / trade_date / `raw_sha256` / `point_index` / 2026 `captured_at` for every bar consumed. Model instants are never written into source fields; the engine's `source_ref` strings carry `captured=<raw instant>` verbatim.")
    L.append("* Future-suffix control (synthetic, inside this runner): changing high/low/close/volume of the attempt session and later bars leaves the earlier decision and the open attempt records byte-identical (`synthetic_test_receipt.json:scenarios.future_suffix_control`). Volume enters only the post-hoc `order_quantity_over_full_day_volume` diagnostic. Known ex-dates are post-hoc flags only.")
    L.append(f"* Endpoint censoring at 2025-03-31 16:00: open positions and live intents are reported with their engine states (§3 columns); no forced liquidation, no fabricated expiry, no 2025-04-01 price. Hypothetical last-close valuation status per branch: " + ", ".join(f"`{n}`={s['performance'].get('status')}" for n, s in b.items()) + ".\n")
    L.append("## 5. What stays assumed or missing (unchanged from M4-03A)\n")
    L.append("Historical availability of every bar (all captured 2026-09-09/10; model instants declared), historical ST status and true daily bands (assumed not_st / previous-close band by code-prefix board), phase-level capacity (exogenous full_fill / fixed_5000 / none), sourced fee tariffs (hypothetical fixture), corporate-action completeness (3 known ex-dates flagged post hoc; `adjustment_uncertainty=true` everywhere), delisting handling (survivor pool, untested on real data), security status (`listed` default of the declared pool), board/lot/tick (code-prefix / fixture), calendar publication time (assumed). The two stores mirror one Tonghuashun capture; vendor value accuracy was not re-proved. Nothing here upgrades an assumption to evidence.\n")
    L.append("## 5b. Revision 2 — the two corrections\n")
    L.append("* **P2-1 performance denominator** (`replay_core.py`): `Replay` now stores the instance's `initial_cash` and passes it to the frozen risk layer's `performance()` (delivery 01 passed the module constant 1 000 000). The historical run used 1 000 000, so no historical number changes; synthetic proof in `evidence/synthetic_test_receipt_rev02.json`: non-default cash 100 000 with zero trades → equity 100 000.00, return `0.000000` (delivery 01 would have reported −0.900000); non-default cash 50 000 with one round trip (200 @ 10.02 cost 2 010.04; stop exit 200 @ 9.48 proceeds 1 888.44) → cash 49 878.40, realized −121.60, return `-0.002432` (hand-calculated).")
    twice = ", ".join(f"`{n}` identical={v['identical']}" for n, v in rev["applied_twice"].items())
    L.append(f"* **P2-2 benchmark endpoint provenance**: (i) `replay_core.py` performance wrappers now carry `raw_provenance` roles `benchmark_start_level` / `benchmark_end_level` (symbol, trade_date, raw_sha256, point_index, captured_at), `benchmark_endpoints.model_time` (assumed 15:00→16:00 of each endpoint session, raw = capture instant), the engine's benchmark status/refusals, `initial_cash_used` and the listed-status default assumption id (assumed branches); tests `test_assumed_performance_wrapper_carries_both_benchmark_endpoints` / `test_raw_performance_wrapper_keeps_capture_instants_and_refusals`. (ii) For the delivered historical outputs, `repair_export_revision_02.py` derived both endpoints strictly from the existing first (2023-09-04) and last (2025-03-31) decision wrappers of each branch (SH000300 capture `ec6c5a9d…`, point_index 250 / 627, captured 2026-09-09T17:12:13.572989+00:00) — it fails on absent or conflicting endpoints — and wrote `runs/829d42809e978c04-rev02/`. Applied twice from identical original bytes: {twice}. Invariants asserted: engine records unchanged, ledger records byte-identical, all non-performance research records unchanged, numerical values unchanged; guard connections {rev['safety']['sqlite_connections']}, historical runner invocations {rev['safety']['historical_runner_invocations']}.")
    hashes = ", ".join(f"`{n}` `{h[:16]}…` (original `{b[n]['output_hash'][:16]}…`)" for n, h in rev["revised_output_hashes"].items())
    L.append(f"* Output hashes: the original historical two-repeat hashes are preserved in `funnel.json:determinism_original_two_historical_repeats`; the revised export hashes are {hashes}. These are export-repair hashes, not new historical replays.")
    L.append(f"* Synthetic validation after the corrections: {synth2['tests_run']} tests, {synth2['failures']} failures, {synth2['errors']} errors, connections {synth2['safety']['sqlite_connections']}, guard self-check {synth2['guard']['self_check']}.\n")
    L.append("## 6. Files\n")
    L.append("`runs/829d42809e978c04/` (original: `receipt.json` incl. guard log, store states, SQL, determinism, safety flags; `sql_log.json`, `reconciliation.json`, `warmup_depths.json`, `funnel.json`, `branches/<branch>/{summary.json, research_records.jsonl.gz, ledger_records.jsonl.gz}`); `runs/829d42809e978c04-rev02/` (export repair: `revision_receipt.json` with code/input/output lineage, repaired `branches/<branch>/research_records.jsonl.gz`, byte-identical ledger copies, `funnel.json` with original and revised hashes); `evidence/{prework,postwork}_verification.json`, `evidence/synthetic_test_receipt.json` (13 tests, inside the original runner), `evidence/synthetic_test_receipt_rev02.json` (17 tests); `superseded/delivery_01/` (delivery-01 scripts, report, manifest, evidence and the in-place pins of the original run); `artifact_manifest.json` written last.\n")
    L.append("Safety: `review_only=true`, `live_trading_enabled=false`, `training_eligible=false`, `strict_pit=false`, `M4_complete=false`, `M5_started=false`; production SQLite connections 0; network 0; holdout/validation price rows read 0; no self-acceptance.\n")
    (HERE / "REPORT.md").write_text("\n".join(L), encoding="utf-8")
    print("report written for run", receipt["run_id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
