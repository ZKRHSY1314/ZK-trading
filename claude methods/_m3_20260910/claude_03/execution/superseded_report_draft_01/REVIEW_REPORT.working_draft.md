# M3-03 actual cutoff-only individual case review — Claude agent reviewer report

Task `M3-03-CASE-REVIEW-20260910` (task file sha256 `8a3245704350d71fd465f73d63bcd6901a9e2ddd08f1bcd0b9c9336f514f9a7c`; Codex M3-02 acceptance `4c1fcc2376c93c5ebf233b28b1d2f6608108eadadd8754ca30cb3e79124648dd`). Status: **ready_for_review**. This delivery contains my individual reviews only; Codex reviews the same inputs independently and assembles the canonical ledger. Nothing here calls M3 complete or training-ready.

## 1. Who reviewed what

* **Reviewer**: `claude-agent:ZK-trading-Fable-5.1-project-advice-fork:claude-opus-5`, `reviewer_kind = agent` (Claude Opus 5 in the existing Claude Code session `a4a3be61-cd46-4bdf-9381-23d97fee303a`). One reviewer; no subagents, workflows or second reviewer were used (the task prohibits dispatching other agents); no Codex or human review is claimed or imitated.
* **Execution**: `execution_id 63ade8b0-7150-46cb-ad5e-7ff1aa9af6a5` (execution/execution_receipt.json). Every review carries `execution_ref = M3-03-CASE-REVIEW-20260910:claude_03:execution=<id>:session=<session>:receipt=execution/execution_receipt.json`.
* **Inputs actually inspected** (all pins verified before every use): the pinned bundle `codex/case_review_bundle_01/` (manifest `fa234fde…`, index `77e29df6…`, 43 files, all 32 `cases/C001..C032.json` and 8 `diagnostics/D001..D008.json`), the accepted `backend/app/research/m3_labels.py` (`e20eb21c…`, policy hash `d436ba14…`), `policy_freeze.json` (`925ae86f…`), `claude_01_r3/LABEL_POLICY.json` (`70180fa3…`), `codex/CASE_REVIEW_RUBRIC.md` (`a2f5c645…`), and the four in-task Codex notes (§7). No full chronology file, no `episode_audit/`, no SQLite, no network, no later outcomes, no Codex opinions.
* **Evidence of inspection**: `execution/evidence_inspection_log.jsonl` (82 entries, two generations of dossiers for all 40 ids; 474 core verifications with 0 problems) and `execution/dossiers/<id>.txt` (one per case/diagnostic, generated only from the bundle file). Each review's `evidence_inspected_at` equals the log timestamps for that id and precedes its `reviewed_at`.

## 2. Method (what a script did vs. what I did)

1. `tools/show_case_evidence.py` (display + arithmetic only, no verdict): re-checks all bundle pins; verifies every embedded core with the accepted kernel (`verify_record` — record hash and decision fingerprint — and `validate_ledger`, empty ledgers); recomputes the frozen phase/liquidity/regime/limit rules from the stored features and the margin to every threshold; checks prefix consecutiveness (session indices), member/representative/proof/packet-hash/index bindings, each control's frozen matching conditions, the |ln amount ratio| ranking and `revalidate_match`; prints the dossier and logs what it inspected. Result: 0 verification problems on all 231 embedded cores (96 prefix + 127 control + 8 diagnostic).
2. I read every dossier in full and wrote the judgment for each case by hand into `authored_notes/C0xx.json` (case-specific reasoning with numbers, control-by-control assessments, verdict, disposition, counting eligibility) and `authored_notes/diagnostics.json`.
3. `tools/serialize_reviews.py` binds each authored note to the exact input hashes, adds identity/timestamps/execution reference and a `ReviewRecord`-compatible `raw_review` validated by the kernel (never attached to an input core), and refuses inconsistent notes (control list must equal the packet controls; verdict must be allowed; no empty reasoning).
4. `tools/validate_reviews.py` is the separate executed validation (§8).

Corrections requested in-task were applied as **hash-linked addenda** (original text untouched, pre-addendum snapshots under `authored_notes/history/`); no verdict was changed by any correction.

## 3. Reviewer framework (applied uniformly; not a policy change)

*positive* = the cutoff-known evidence supports the frozen observable accumulation-proxy episode without material fragility; *ambiguous* = rule-conformant but the evidence is mixed or the episode hangs on a thin margin; *negative* = a competing observable process (advance, rebound, break, decline, limit-lock) dominates and the rule is met only incidentally; *failed* / *reject_data* were not needed (every core verified and the bundle is intact). A margin on the deciding leg below 0.01 (position, spread, return_120; or, for a control, its markup/failed-markup/distribution leg) is called **thin/fragile**; a prefix with any thin margin is not called positive. Control **contrast** is *strong* (markup/distribution/failed_markup phase) or *weak* (rule-level accumulation vetoed by a recent distribution/failed markup — admissible under the frozen rules, informative only about history). `counting_eligible` is true only for a positive verdict with an admissible control set; same-day matched controls never establish causal identification.

## 4. Per-case verdicts (32/32)

| Case | Symbol | Rep. date | Verdict | Disposition (short) | k | fragile ctl | robust ctl |
|---|---|---|---|---|---|---|---|
| C001 | SZ000002 | 2023-11-20 | ambiguous | spread margins 0.0008/0.0041/0.0072 in a decelerating downtrend | 3 | 0 | 3 |
| C002 | SH600129 | 2023-11-23 | negative | post-markup consolidation; markup missed by volume 1.0499 vs 1.05 | 3 | 0 | 3 |
| C003 | SH600129 | 2023-12-05 | negative | advance (closes 9–13% above ma20, return_60 +18–21%) | 3 | 0 | 3 |
| C004 | SH600777 | 2024-01-24 | negative | sharp decline below both averages, −5.6% start bar | 5 | 0 | 5 |
| C005 | SH600777 | 2024-02-01 | ambiguous | early stabilisation after the C004 break | 3 | 0 | 3 |
| C006 | SH600362 | 2024-02-28 | negative | advance with diverging averages, alternating markup legs | 3 | 0 | 3 |
| C007 | SZ002237 | 2024-02-29 | ambiguous | post-decline base, spread margins 0.0037/0.0072/0.0109 | 3 | 0 | 3 |
| C008 | SZ002255 | 2024-03-12 | negative | V-rebound, return_20 +36% with volume leg unmet | 3 | 1 | 2 |
| C009 | SZ002354 | 2024-03-18 | negative | rebound, markup return leg exceeded on all members | 4 | 0 | 4 |
| C010 | SH600011 | 2024-03-21 | ambiguous | quiet pause in the upper range, position margin 0.025 | 3 | 0 | 3 |
| C011 | SZ002255 | 2024-03-26 | ambiguous | post-markup pullback 3% from the failed-markup trigger | 3 | 0 | 3 |
| C012 | SH600777 | 2024-05-07 | negative | three zero-range ~−5% bars at the window minimum (possible limit locks; state unknown) | 5 | 0 | 5 |
| C013 | SH600011 | 2024-05-17 | negative | post-top decline below both averages | 3 | 0 | 3 |
| C014 | SH600280 | 2024-05-22 | ambiguous | low-range rebound on 1.8x volume, spread margin 0.0019 | 4 | 0 | 4 |
| C015 | SH600176 | 2024-06-05 | ambiguous | pullback to ma60, spread margin 0.0003 | 5 | 0 | 5 |
| C016 | SH600280 | 2024-07-10 | negative | capitulation decline near the range floor, −6.1% on 2.5x volume | 3 | 0 | 3 |
| C017 | SZ301529 | 2024-09-25 | ambiguous | 250-bar minimum warmup, IPO-dominated range window | 3 | 0 | 3 |
| C018 | SH600289 | 2024-09-27 | negative | post-markup advance on a 2.3x volume spike, thin 1.4 CNY stock | 3 | 0 | 3 |
| C019 | SZ002731 | 2024-12-18 | negative | advance, return_60 > 0.35 on two members, band flip L2→L3 | 5 | 1 | 4 |
| C020 | SZ002342 | 2024-12-25 | negative | break below both averages on volume | 4 | 0 | 4 |
| C021 | SH600176 | 2024-12-31 | ambiguous | quiet drift at the position ceiling (0.0028), regime bull→range→bear | 5 | 1 | 4 |
| C022 | SH600777 | 2025-01-06 | negative | −5.1% break day on 1.57x volume at the representative | 3 | 0 | 3 |
| C023 | SH600259 | 2025-01-17 | ambiguous | upper-range consolidation opened by a 2x-volume down day | 5 | 0 | 5 |
| C024 | SH600176 | 2025-01-20 | ambiguous | converged range broken by a 2.07x-volume −3.1% bar | 5 | 0 | 5 |
| C025 | SH600176 | 2025-02-17 | ambiguous | same range, 1.81x-volume −3.6% bar, position margins 0.018/0.0093 | 5 | 2 | 3 |
| C026 | SH600259 | 2025-02-25 | ambiguous | truest range-bound state; return_120 margin 0.0054 | 5 | 1 | 4 |
| C027 | SH600176 | 2025-03-03 | ambiguous | quietest prefix; position margin 0.0088 on member 1 (positive defensible) | 5 | 0 | 5 |
| C028 | SH600129 | 2025-03-12 | ambiguous | post-decline bounce, spread margin 0.0014 | 5 | 2 | 3 |
| C029 | SH603075 | 2025-03-14 | ambiguous | quiet upper-range drift, position margin 0.0095, thin band (positive defensible) | 3 | 0 | 3 |
| C030 | SH688248 | 2025-03-21 | ambiguous | quiet drift; return_120 margin 0.0022, band 0.36M above L2 | 5 | 0 | 5 |
| C031 | SZ002237 | 2025-03-25 | ambiguous | converged base lifting on expanding volume; return_120 margin 0.0107 | 5 | 0 | 5 |
| C032 | SZ002297 | 2025-03-31 | negative | three-session decline from the position ceiling | 5 | 0 | 5 |

**Totals**: positive 0, negative 14, ambiguous 18, failed 0, reject_data 0. `counting_eligible` = 0. Control sets: 32/32 admissible under the frozen rules (k=3 in 15 cases, k=4 in 3, k=5 in 14); 127 control uses reviewed; 8 fragile control uses (C008 SH600176, C019 SH600869, C021 SH688181, C025 SZ301251 and SH688001, C026 SZ002254, C028 SZ301251 and SH600280) — in C025 and C028 the robust count falls to exactly k_min=3, in C008 to 2 (the case is negative regardless). No control set was rejected; no control was reselected or removed.

**Dissent preserved for reconciliation**: C027 and C029 would be positive if a 0.009–0.010 position margin were judged adequate; C006, C019 and C009 would be admitted by a literal application of the rule (my negatives are judgments about evidential support, not disputes with the kernel arithmetic); C011/C024/C025 are the cases where a post-markup or high-volume down bar leaves the state genuinely undecidable at the cutoff.

## 5. Recurrent findings across the 32 cases

* **The rule admits advances and rebounds.** 8 negatives are advances/rebounds where the markup return leg was met or nearly met and only the volume leg failed (C002 by 0.0001 of volume ratio, C003, C006, C008, C009, C018, C019) or a plain markup sat inside the lookback (markup_within_lookback=true in C002, C003, C009, C011, C018, C019).
* **The rule admits breaks and declines.** 6 negatives are price breaks below both averages with the failed-markup drawdown leg met but no labelled markup (C004, C013, C016, C020, C022, C032) plus the C012 zero-range sequence; the accumulation arithmetic is satisfied because a falling price stays below the position ceiling and the averages converge as ma20 rolls over.
* **Thin margins decide most episode starts.** 20 of 32 prefixes have at least one member within 0.01 of a threshold on the deciding leg (spread: C001, C007, C008, C014, C015, C016, C019, C028; position: C010, C021, C025, C026, C027, C029, C032; return_120: C019, C026, C030, C031). No prefix combined comfortable margins, quiet volume, converged averages, a stable regime/band and a non-fragile control set.
* **Matching keys flip inside prefixes**: regime changes across members in C002, C008, C009, C017, C018, C021, C022; liquidity band changes in C012, C019; C019 (0.09M), C030 (0.36M) and C022 (1.2M) sit within rounding distance of a band boundary.
* **Data-state caveats that the frozen gates tolerate**: zero-range bars consistent with possible limit locks (C012; also SZ002342 as a control in C029); suspensions inside the 250-window (C012, C018, C022; controls SH600777 ×4, SH688115 at the 10-session gate edge in C020/C022, SZ002656 with 39 pre-window suspensions in C018); minimum-warmup or IPO-dominated windows (C017, control BJ920627/BJ920001/SH688702 etc.); `limit_down_possible`/`limit_like_possible` flags that depend on unknown ST status.
* **Provenance**: `provenance.source_refs` / packet `price_context` ranges are the stock+benchmark locator union (accepted `m3_labels.py:1585`); per-role counts were used throughout and the notes for C012, C017, C018, C022, C029 say so explicitly (Codex clarification §7).
* **Dependence**: 18 symbols carry the 32 cases; SH600176 ×5 (C015, C021, C024, C025, C027), SH600777 ×4, SH600129 ×3, SH600011/SH600259/SH600280/SZ002237/SZ002255 ×2. Same-symbol representatives within 20 sessions chain C002–C003, C004–C005, C008–C011, C021–C024–C025–C027 (my simple session-distance chaining gives 26 chains; the accepted M3-02 dependence statistic is 23 groups — the policy's own `dependence_groups` is authoritative). Control reuse: 37 unique control symbols over 127 uses, maximum reuse 10 (SH600280), then SZ002317, SZ002731, BJ920001 (8 each).

## 6. Diagnostics (D001–D008, never positives)

| Id | Kind | Core | Finding |
|---|---|---|---|
| D001 | markup | SH600280 2023-09-04 | markup fires on the return_60 leg (+74.6%) with volume 1.80 while the 20-session picture (−5%, −12.5% drawdown) also satisfies the failed-markup legs; precedence keeps markup — an interpretive limit, rule-correct |
| D002 | distribution | SH600777 2023-12-08 | position 0.885, volume 5.05, rejection via close_to_high 0.9643 < 0.97 by 0.0057 on a +6.1% day — rule-correct but fragile |
| D003 | failed markup | SZ002281 2023-09-04 | markup in the (warmup) lookback, drawdown −14.6% — intended transition semantics |
| D004 | warmup indeterminate | BJ920001 2023-09-04 | 168 < 250 bars, position None → indeterminate; 0.58M CNY/day, 8.7x volume kept out correctly |
| D005 | suspended decision | SZ002309 2024-04-24 | suspension gate; features refer to the last price date 2024-04-23; collapsed name, halt reason unknown |
| D006 | known cash action | BJ920000 2023-09-04 | ex-date 2023-07-05 (document sha `27e5bbb3…`) inside the window → indeterminate despite accumulation arithmetic; partial_known keeps adjustment uncertainty |
| D007 | signal vs execution | SH600176 2023-09-04 | signal_eligible (close > ma20, volume 1.59); tradability unverified; `no_trade` is the result under absent declared position input, not evidence that nothing was held or filled |
| D008 | BJ scoped exception | BJ920006 2023-12-04 | exception applied to the single frozen bar (volume ratio None), record indeterminate; no general waiver |

Later-case mentions in the diagnostic bindings were moved to a separate `retrospective_collection_cross_reference` field (collection navigation only, excluded from evidence) per Codex's diagnostic wording check.

## 7. In-task corrections (all applied as hash-linked addenda; verdicts unchanged)

| Note (sha256) | What changed |
|---|---|
| `M3_03_PROVENANCE_DISPLAY_CLARIFICATION.md` (`1bb8cb29…`) | dossier tool now labels the locator union and prints per-role counts; C012 addendum; every serialized review carries `provenance_clarification` |
| `M3_03_WORKING_NARRATIVE_FACT_CHECK.md` (`e0c592bd…`) | C016 'new 250-session lows' withdrawn (implied low250 = 2.16, daily lows 2.28/2.19/2.22); C012/C019/C022 'locked' → 'consistent with possible limit locks, state unknown'; C013/C004 timing of the 250-session high withdrawn; C008/C009 denominator attribution marked as hypothesis |
| `M3_03_FINAL_WORDING_CHECK.md` (`4a2d5468…`) | C031 future-markup wording made conditional; C018 controls not all low-priced (SH688513 36.71 CNY); C027 representative return_120 margin ≈0.074 stated; C032 −7.7% (prev-close→rep) vs −5.7% (member-1→rep) distinguished |
| `M3_03_DIAGNOSTIC_WORDING_CHECK.md` (`e8698cbc…`) | D007 `no_trade` sentence corrected; later C-case references segregated into a cross-reference field |

Original notes are preserved verbatim: 13 pre-addendum snapshots in `authored_notes/history/` (each addendum records `original_note_sha256` and the snapshot path); the validator checks that the non-addenda text of every note equals its snapshot.

## 8. Executed validation (`tools/validate_reviews.py` → `execution/validation_receipt.json`, ok = true, 0 problems)

Verified: all 14 external pins and all 43 bundle files unchanged; exactly 32 case reviews and 8 diagnostics; 127 control uses, each bound to the packet control core hash, same date/mode/policy/band/regime/universe, non_candidate and observed; representative episode id / record hash / prefix hash / packet hash / case file hash equal to the bundle and index; representative cores still verify with the kernel; every `raw_review` passes `_validate_entry_fields` with its `entry_hash` recomputed and bound to (case_episode_id, case_record_hash, policy hash, case_prefix_hash); one non-synthetic agent reviewer identity throughout; `reviewed_at` timezone-aware, after the logged inspection times and equal to the execution receipt; verdicts allowed; no empty reasoning; embedded input ledgers still empty (no core mutated); authored-note hashes and addendum snapshots preserved. Re-run: `backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m3_20260910/claude_03/tools/validate_reviews.py"`.

## 9. Limitations, uncertainties and what this delivery is not

* Retrospective research on a 2026 capture: every consumed fact carries an availability violation; `strict_pit=false`, `training_eligible=false`, `review_only=true`, live trading off. Nothing here proves market prediction or trading effect.
* Corporate actions are unknown for 48 of 50 stocks (partial for SH600011/BJ920000), so all returns and range positions carry adjustment uncertainty; ST status, float shares, turnover and names are unknown; listing evidence is pilot metadata or exchange code mapping only.
* My verdicts are one agent's judgment of evidential support against the frozen proxy. The kernel arithmetic was not disputed anywhere; where a literal rule application would admit a case, I said so. Codex may reasonably disagree; those disagreements belong in the reconciled ledger, not in this file.
* The full frozen inventory holds at most 32 matched episodes / 23 dependence groups, below the original 50-positive target; with 0 positive verdicts here the target is not met and no tuning, replacement or universe change was made to approach it.
* Zero-range/limit-lock bars and post-markup advances passing the accumulation gate are recorded as reviewer observations about the frozen policy's coverage (C012, C002/C003, D001, D002); they are not policy changes and were not acted on.

## 10. Files

`reviews/C001..C032.json`, `diagnostics/D001..D008.json`, `authored_notes/` (+ `history/`), `execution/` (inspection log, 40 dossiers, execution receipt, validation receipt, validator stdout), `tools/` (three scripts), this report, `artifact_manifest.json` (written last; pins every output and every consumed source). Next step belongs to Codex: independent review of the same bundle, reconciliation of preserved opinions, canonical ledger and counts.
