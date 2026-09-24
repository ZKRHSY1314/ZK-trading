# M3/M4 research evidence: what would unblock them

Status: `proposed`. This is a plan only. It authorises no collection, relabelling, threshold change, universe expansion, holdout use or M5 work.

The two milestones stay as they are:

- **M3** and **M4** remain `technically_closed_evidence_target_not_met`.
- `M3_complete=false`, `M4_complete=false`, `training_eligible=false`, `strict_pit=false`.

The sources are:

- `claude methods/M3_FINAL_ACCEPTANCE_20260910.md` and `claude methods/M4_FINAL_ACCEPTANCE_20260912.md`;
- the corrections in `claude methods/06_CODEX_进度建议复核_2026-09-13.md`.

The cloud run had none of the frozen data, so every count below is quoted from those documents. None was re-derived.

## M3: the gap is label semantics, not sample size

**The recorded state.** The fixed development population yields at most 32 matched stages. All 32 are disputed:

| Reviewer | Positive | Negative | Uncertain |
| --- | --- | --- | --- |
| Codex | 31 | — | 1 |
| Claude | 0 | 14 | 18 |

There are no jointly positive cases. Both reviewers' original opinions are preserved, and this plan does not resolve them.

**Why more stocks would not fix it.** The disagreement is about what the proxy label means, compared with the stricter pattern reading. It is not about how many cases exist. Scaling 50 stocks to 500 would give more disputed cases under the same ambiguity. It would also do nothing about:

- contemporaneous universe membership;
- ST status;
- delistings;
- corporate-action evidence.

**Smallest next evidence, in order:**

1. **Observable definition.** From the existing 32 case files alone, write a versioned label-policy successor (for example `m3_labels` successor v2; the frozen `m3_labels.py` is never edited). It must state:
   - which observable facts, available at the cut-off, make a stage positive, negative or uncertain;
   - which facts neither reviewer can observe from daily bars.

   Keep the old policy and both reviewers' opinions unchanged, and record the successor's differences from the old policy explicitly.
2. **Pre-registered blind review.** Before anyone looks at new cases, fix the review protocol:
   - the reviewer instructions;
   - the rules for eligible controls;
   - the handling of uncertain cases;
   - the agreement statistic;
   - the threshold for "jointly positive".

   Then re-review the existing 32 cases under the successor, blind to the earlier opinions. The result is evidence about the definition, not new positives.
3. **Size from rates, not from a round number.** Only if step 2 produces a non-zero jointly-positive rate, estimate the population needed to reach 50 positives from:
   - the observed candidate rate;
   - dependency groups (23 groups and 18 stocks among the matched stages);
   - sector and period strata.

   Any expansion is then a separate, scoped data task, with its own availability evidence and no holdout use.
4. **Exit condition.** If the successor's jointly-positive rate is zero or unstable across reviewers, stop. Record that the proxy label is not a trainable target, rather than scaling the capture.

## M4: the gap is historical input qualification

The engineering is proven on synthetic data and on explicitly assumed replays. The qualified raw path produced **0 intents and 0 fills**, because the inputs were captured in 2026.

The branch results from the frozen replay are kept as recorded:

| Replay branch | Return |
| --- | --- |
| `assumed_full_fill` | −4.56% |
| `assumed_fixed_5000` | +5.04% |

**Evidence needed before any historical execution claim.** Each item is a static source-and-availability review first, meaning which source, and when it was knowable. Reading data comes after.

| Input | Needed | Why the current data fails |
| --- | --- | --- |
| Historical ST / price-band status | a dated source for each security and session | the production engine infers the board from the code; ST is never detected |
| Fee schedule | effective-dated commission, stamp duty and transfer fee | the configured rates are constants |
| Corporate actions / adjustment basis | complete events per security, with announcement dates | only partial cash events exist for two stocks |
| Delistings / contemporaneous universe | the universe as known on each date | the fixed 2026 list carries survivorship bias |
| Capacity | a session- and phase-appropriate volume source | the daily amount is observed at the close; M4 refuses to derive opening capacity from it |
| Signal-input availability | proof that each input existed at decision time | the 2026 capture is refused by the raw path |

**The production path is not a substitute.**

- The production engine now commits intents from pre-open information, which removes the same-day close and range leaks (see `docs/EXECUTION_CAUSALITY.md`).
- That fixes causality only. None of the missing historical facts above is supplied by it.
- The `pre_open_causal` A/B harness can compare configurations, but it cannot produce qualified historical evidence.

**No adapter until the evidence exists.** A production-to-M4 adapter should only be built once at least ST/price band, fees and corporate actions have dated sources. Before that, it would only restate the assumptions under a stricter name.

## Forecast evidence, for the live ledger

The canonical scoreboard (`docs/FORECAST_EVIDENCE.md`) will show how many **confirmed** decision dates exist. The September 13 inspection found 0 confirmed and 5 inferred snapshots; that is a dated local observation, not a figure to reuse.

Until at least 20 confirmed, matured decision dates accumulate under scheduled claims, no horizon can be strategy-eligible. That is expected, not a defect. No backfill can create confirmed history retroactively.

## Explicitly not done

- No collection of market, reference or fundamental data.
- No new capture authorisation requested.
- No threshold tuning.
- No forced labels.
- No use of the validation or holdout windows.
- No M5.
