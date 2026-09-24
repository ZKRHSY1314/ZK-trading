# M2a — offline pilot runner

**Status: `ready_for_review` (R1-R4 closure). Offline-only. No network or plugin call, no download, no production write, no real staging collection, no service, no Git staging/commit/push, no training, no promotion.**

New artifacts live only in `claude methods/_m2_pilot/`. Production runtime code, the accepted M1 gates in `_m1_closure/`, existing datasets, strategies and methodology/knowledge materials are unchanged — M2a *imports* the M1 gate and never modifies it.

---

## R2 binding closure (2026-09-06, responding to `M2A_FINAL_BINDING_CODEX_REVIEW.md`)

> Status: `ready_for_review`. Offline-only. R1, R3 and R4 fixes preserved; accepted M1 code imported and unmodified; reviewer artifacts untouched; the live decoder deliberately not implemented.

### Resolution table

| ID | Reproduced defect | Fix | Changed file |
|---|---|---|---|
| **R2.1** | `bind_inputs()` only checked that *a* fingerprint was supplied and copied it into the verdict, so the gates never entered the binding. Candidate A's untouched M1 report plus candidate B's genuine fingerprint produced two accepted public verdicts, and B — which really contains 45,934 rows/view and whose own research gate exits 1 on M1/M3 — **published**. | A runner-owned `validate_candidate(mode, ...)` now **owns the M1 invocation**: it selects these exact view paths and frozen inputs, fingerprints **before and after** the gate, refuses a candidate that changed mid-run, and passes the fingerprint *it measured* to acceptance. It returns a `ValidationReceipt`. The raw-text acceptance helpers still exist but return `Verdict`s, which finalization refuses. | `pilot_runner.py` |
| **R2.2** | Both finalization slots only required `accepted=True` and a matching fingerprint, so `finalize(collection, research_verdict, research_verdict)` published a candidate whose real warm-up gate had **W1_pricing=FAIL** — an integrity gap, not the approved IPO depth exception. | `finalize(collection, receipts)` takes a collection of receipts and requires **one `research` and one `warmup_collection`** receipt for the same run, candidate and frozen inputs. Mode is carried explicitly on the receipt and never inferred from argument position; two receipts of the same mode are refused. | `pilot_runner.py` |

### Exact commands and actual results

```bash
cd "claude methods/_m2_pilot"
../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2a.py                 # exit 0, 79 cases, 0 unexpected

cd "../_m1_closure"                                                            # accepted M1, unmodified
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py         # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py     # exit 0, 46 cases
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py     # exit 0, 67 checks
```

**Changed files:** `_m2_pilot/pilot_runner.py` (receipt type, `validate_candidate`, `finalize`), `_m2_pilot/test_m2a.py`. `acceptance.py`, `transport.py`, `decoder.py` and `provenance.py` are unchanged in this closure, as are all M1 artifacts and the reviewer's files.

### New regressions (all passing)

```
[ok] B-R2.1 a short candidate is refused by its OWN official validation
[ok] B-R2.1 candidate A's receipt cannot publish candidate B
[ok] B-R2.1 there is no public way to mint a receipt from raw gate text
[ok] B-R2.2 a research receipt cannot satisfy the warm-up requirement
[ok] B-R2.2 a single receipt is not enough to publish
[ok] B    a candidate mutated during the gate run is refused by the same binding
[ok] B-FULL the approved 50+2 publishes through the OFFICIAL validation path
```

`B-R2.1` builds the short candidate the way the review did — omitting one eligible research day for `SH688001` from **both** response envelopes, so the shortfall is genuine rather than doctored afterwards. Its own research validation reports `gate_exit=1` and is not accepted. `B-R2.2` removes one warm-up day instead: research legitimately passes while warm-up integrity reports `W1_pricing=FAIL`, and neither two research receipts nor the honest pair can publish.

`B-FULL` drives the approved 50 stocks + 2 benchmarks through fake transport → decoder → both staging views → **`validate_candidate` for each mode**, which itself calls the unchanged M1 `validate`. Research `gate_exit=0`, warm-up `gate_exit=1` with exactly the pinned **14**-security shortfall, and publication records `validated_modes: ["research", "warmup_collection"]` alongside the candidate fingerprint. The previous `FULL` case, which called the acceptance helpers directly, is superseded by it.

Preserved and still green: the wrong-run rejection, the post-validation mutation rejection, the R1 body-override removal, the R3 sticky abort and every R4 pointer protection.

### Correction to this document's earlier claim

The previous section said acceptance was "bound to … the candidate fingerprint". It was bound to *a fingerprint the caller supplied*, which is not the same thing and is exactly what the review exploited. The binding is now produced by the code that runs the gate.

### Unchanged limitations

The real Sina JS-encoded payload decoder remains **KNOWN-UNSUPPORTED** and is not implemented here. No strict point-in-time evidence exists or can be created retroactively; historical universe, ST, suspension, delisting and BJ code mapping remain UNKNOWN; corpus unit evidence remains UNKNOWN with the 293 STAR-board events still a hypothesis; `identity` is the only supported transformation; A2 and the 746 legacy evaluations remain a separate prerequisite. Warm-up collection acceptance is data integrity, never feature readiness.

Passing M2a proves none of live connectivity, source semantics, a three-year corpus, feature readiness or training. Neither live sampling nor the 52-symbol collection is proposed as ready.

---

## (superseded) Closure of the seven remaining counterexamples (2026-09-06, responding to `M2A_CLOSURE_CODEX_REVIEW.md`)

> Status: `ready_for_review`. Offline-only. Accepted M1 code in `_m1_closure/` is imported and unmodified and still passes. Reviewer artifacts in `_m2_codex_review/` were not touched. The live decoder is **not** implemented in this closure.

### Resolution table

| ID | Reproduced counterexample | Fix | Changed file |
|---|---|---|---|
| **R1** | The deleted `fetcher` callback had become the public `responses` mapping; `_one()` preferred `responses[url]` over `response.text`. With every HTTP body `<html>NOT MARKET DATA</html>` and valid envelopes supplied through the mapping, the runner completed **52 jobs / 102 attempts**, wrote **45,935 rows per view**, and both acceptance paths accepted it — every stored body hash matching the replacement, not the response. | The `responses` parameter is **removed**. One captured response object is the sole source of the body, its hash and its lineage. Injecting data now requires the injected transport to actually return it. | `pilot_runner.py` |
| **R2a** | `accept_research(..., enforce=False)` accepted a report containing only `P4=PASS`. The delivered happy-path test used that flag itself. | The `enforce` switch is **removed** from both public functions. Reduced fixtures now call the private `_warmup_decision` / `enforce_inventory` helpers, so a test's convenience cannot widen what production accepts. | `acceptance.py` |
| **R2b** | Swapping `SH688001` for `SH600998` preserved 50+2 and was accepted; hashes were optional and compared by prefix. | `expected_manifest_sha`, `calendar_path`, `expected_calendar_sha` and `candidate_fingerprint` are all **mandatory**, compared by **full-hash equality**. | `acceptance.py` |
| **R2c** | A `RESULT: FAILED … P4` line followed by an all-pass report and `RESULT: SUCCEEDED` was accepted; the parser took the last verdict. | More than one verdict line is a rejection: a report carrying conflicting verdicts is not one interpretable run. | `acceptance.py` |
| **R2d/R4** | Run A's collection and acceptance Boolean were handed to a runner B that had never collected; B published and `CURRENT.json` pointed at **two nonexistent databases**. | `publish(collection, acceptance_ok)` is replaced by `finalize(collection, research_verdict, warmup_verdict)`, which verifies run identity, file existence, and that **both verdicts were issued against this candidate's exact bytes**, re-checked immediately before the pointer moves. | `pilot_runner.py` |
| **R3** | The first transport-raised `RunAborted` propagated but never set `aborted_reason`, so the next call succeeded with 200 and attempts climbed to 2. | The reason is **latched** before propagating. A second call raises without touching the transport and without incrementing attempts. | `transport.py` |
| **R4** | `CURRENT.json` and `CURRENT.json.tmp` were not path roles. A hardlink planted at the fixed temp name pointed at a protected sentinel, and publication **overwrote it**. | Publication roles are included in the guard at construction **and re-checked at publication**. The temp is run-specific and created with `O_CREAT\|O_EXCL`; a pre-existing one is refused, never followed or deleted. On write/replace failure only our own temp is removed and the previous pointer and pair are preserved. | `pilot_runner.py` |

### Exact commands and actual results

```bash
cd "claude methods/_m2_pilot"
../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2a.py                 # exit 0, 73 cases, 0 unexpected

cd "../_m1_closure"                                                            # accepted M1, unmodified
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py         # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py     # exit 0, 46 cases
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py     # exit 0, 67 checks
```

**Changed files** (all inside `_m2_pilot/`): `pilot_runner.py`, `acceptance.py`, `transport.py`, `test_m2a.py`. Plus this document and the progress ledger. `decoder.py` and `provenance.py` are unchanged in this closure.

### The full 50+2 chain, enforcement on, no bypasses

`FULL 50 stocks + 2 benchmarks, research + warm-up, enforcement enabled` drives the approved manifest and pinned calendar through fake transport → decoder → both staging views → the unchanged M1 `snapshot`/`validate` → **both public acceptance functions with full hashes and the candidate fingerprint** → `finalize`. Actual results: 52/52 jobs, research exit **0**, warm-up exit **1** with exactly the pinned **14**-security shortfall, both verdicts accepted, publication succeeds and the pointer records the candidate fingerprint.

Eleven new `C-` regressions cover each counterexample on the **public** path, including a verdict issued against a different candidate, an unowned pointer temp, a hardlinked pointer temp aliasing a protected sentinel, and an injected `os.replace` failure during publication.

### Corrections to this document's earlier claims

- The previous text said the callback was "deleted" and there was "no second data path". A second path existed as the `responses` mapping. It is gone now, and the earlier claim was wrong.
- It said acceptance was "bound to the run's manifest hash, calendar hash and the approved 50+2 population". Those bindings were **optional** and prefix-compared. They are now mandatory and exact.
- It described the abort as "sticky"; only the first call was tested and the reason was never latched.
- It said the integrated chain was proven end to end; the delivered happy path used `enforce=False` with a reduced population, and the publication-failure test injected an HTTP failure rather than a pointer failure. Both are now genuine.

### Unchanged limitations

The real Sina JS-encoded payload decoder remains **KNOWN-UNSUPPORTED** and is deliberately not implemented here. No strict point-in-time evidence exists or can be created retroactively; historical universe, ST, suspension, delisting and BJ code mapping remain UNKNOWN; corpus unit evidence remains UNKNOWN with the 293 STAR-board events still a hypothesis; `identity` is the only supported transformation; A2 and the 746 legacy evaluations remain a separate prerequisite. Warm-up collection acceptance is data integrity, never feature readiness.

Passing M2a proves none of live connectivity, source semantics, a three-year corpus, feature readiness or training. Neither live sampling nor the 52-symbol collection is proposed as ready.

---

## (superseded) R1-R4 closure (2026-09-06, responding to `M2A_CODEX_REVIEW.md`)

> Status: `ready_for_review`. Offline-only. The accepted M1 gates in `_m1_closure/` are **imported and unmodified** and still pass. Neither a live smoke test nor the 52-symbol collection is proposed as ready.

### Resolution table

| ID | Reproduced defect | Fix | File | Regressions |
|---|---|---|---|---|
| **R1** | The runner kept only `response.url`, discarded the body, and took rows from an independent `fetcher` callback. With every response `<html>NOT MARKET DATA</html>` and the callback returning a full grid, it reported `completed`, `promoted=True` and wrote **45,935 rows per view**; the unchanged M1 gate passed it, correctly. | The callback is **deleted**. A pure `decoder.py` parses the captured bodies; there is no second data path. Provenance now requires the observed URL path **and** the payload's declared basis to corroborate, applies to benchmarks too, and records body SHA-256, schema, run id and run mode. | `decoder.py`, `provenance.py`, `pilot_runner.py` | 21 |
| **R2** | Acceptance passed with only `P4=PASS` and every other gate absent; with `P4=UNKNOWN` marked advisory; with `V3b` absent; with `V3b=UNKNOWN`; with `V3b=FAIL` advisory. | The gate inventory is **owned internally** (20 research / 25 warm-up gates), not supplied by the caller. Missing, duplicated or weakened-requiredness gates fail closed. `V3b` must exist, be required and be exactly `FAIL`. Acceptance is bound to the run's manifest hash, calendar hash and the approved 50+2 population. | `acceptance.py` | 12 |
| **R3** | 52 consecutive 404 jobs returned `completed`/`promoted=True`. A transport-raised `RunAborted` was caught generically and retried 3x. A `ValueError` was retried 3x. An infinite connect timeout was accepted. | Consecutive-failure stop at 20 with reset-on-success; honest rollups (`collected` / `completed_with_failures` / `incomplete` / `aborted`) and publication only from a complete collection. `RunAborted` is re-raised before any wrapping; only `TimeoutError`/`ConnectionError` are transient; `math.isfinite` validation; the hidden-retry check runs **at construction**. | `transport.py`, `pilot_runner.py` | 13 |
| **R4** | The guard accepted trading and history resolving to the same file, and one destination equal to the other's `.partial`. Two sequential `os.replace` calls left **new trading + old history** with a stray partial. | Pairwise distinctness across **all four** final and temporary roles. Each run writes into a **fresh run directory** that must not exist. Publication is a single pointer write performed only after complete collection **and** successful acceptance; the previous pair stays intact and referenced. No unowned partial is ever unlinked. | `pilot_runner.py` | 14 |

### Exact commands and actual results

```bash
cd "claude methods/_m2_pilot"
../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2a.py                 # exit 0, 60 cases, 0 unexpected

cd "../_m1_closure"                                                            # accepted M1, unmodified
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py         # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py     # exit 0, 46 cases
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py     # exit 0, 67 checks
```

Production unchanged (`trading_local.sqlite3` 2026-09-04 18:27, `market_history.sqlite3` 11:44); no `staging/` directory; manifest sha `97e251ae84fc9274`; HEAD `73f266d`; index empty.

### The integrated chain, proven end to end

Four `INT` cases drive **fake transport -> decoder -> staging -> the unchanged M1 `validate` command -> M2a acceptance -> publication**:

- **good bodies** — collection completes, the real M1 gate exits 0, acceptance accepts, publication succeeds.
- **HTML bodies** — every job is `rejected` with a `markup` reason, **0 rows** reach the staging table, collection is incomplete, and publication is refused. This is the exact counterexample that previously produced 45,935 rows.
- **a qfq-declaring payload on the raw path** — every job rejected as `UNKNOWN`, 0 rows stored. The right URL is no longer sufficient.
- **provenance rows** — body SHA-256, run id and `run_mode=offline_synthetic_fixture` are recorded, `fetched_at` carries the fixture marker, and the lineage note states that copying one fetch into two stores is **lineage consistency, not independent source corroboration**.

### Two defects this pass found in its own new code

- The decoder accepted `2025-13-99` because it matched the date *shape* — the same defect class the M1 review found in the D1 gate. It now parses the date and rejects impossible ones.
- The decoder silently dropped `volume` for benchmarks, so every index job failed downstream. Benchmark rows now require and retain `volume`.

Both were caught by the new tests before delivery.

### Deliberately unimplemented, failing closed

The real Sina history endpoint returns a JS-encoded payload. Decoding it needs the vendor's routine and a **real sample to validate against**, which an offline milestone does not have. `SINA_KLC_JS` is registered as **KNOWN-UNSUPPORTED** and raises with that reason rather than being guessed at. Any live work must build and validate that decoder first.

### Remaining limitations

Strict point-in-time evidence remains absent and cannot be created retroactively. Historical universe, ST history, suspension calendar, delisting register and BJ pre-2024-08-12 code mapping remain **UNKNOWN**. Corpus volume-unit evidence remains UNKNOWN; the 293 STAR-board near-100x events remain a hypothesis and nothing is rescaled on suspicion. `identity` is the only supported cross-view transformation. The 746 legacy evaluations and A2 remain a separate prerequisite. **Warm-up collection acceptance is data integrity, never feature readiness** — 14 of 50 stocks cannot reach 250 sessions and no download changes that.

Unresolved live-data questions carried forward: whether the live raw response carries `amount` for every pilot symbol; the real vendor limits; whether the raw path's `drop_duplicates` on OHLCVA drops legitimate identical sessions; whether the observed URL set is stable; whether index responses match the assumed shape.

**Neither the live smoke test nor the 52-symbol pilot is presented as ready for authorization on this implementation.**

---

## (superseded) initial M2a resolution table

| Req | Implementation | Proof |
|---|---|---|
| **1 Raw-basis provenance** | `provenance.py` — `adjustment_mode` is `none` **only** when the observed URL set is exactly the validated raw path for that instrument class; any missing URL, extra URL or missing response column yields `unknown`. `volume_unit` is *measured* from the response (`amount / (volume × k)` must land in the day's low/high band, one-sided) rather than stamped. `require_basis()` refuses to serve a basis the evidence does not establish. Stock and benchmark routed separately. | 11 cases |
| **2 Transport controls** | `transport.py` — `PacedTransport` paces, counts and bounds **every** HTTP attempt, so both internal GETs of a raw stock call are paced and counted. Finite `(10 s, 30 s)` timeouts on every attempt; redirects disabled and surfaced as failures; explicit bounded retries with backoff, only on timeout/5xx/connection errors; global ceiling; 403/429 abort the whole run without retry and stick. `assert_no_hidden_retries()` rejects a session whose adapter would retry underneath the counter. | 14 cases |
| **3 Machine-checkable acceptance** | `acceptance.py` — parses **every** gate line, cross-checks the parse against the gate's own verdict and against the exit code, and fails closed on any disagreement. The **complete** per-security warm-up shortfall is recomputed here from the unchanged manifest and pinned calendar, then compared to the pinned 14 including each eligible count. | 12 cases |
| **4 Staging safety** | `pilot_runner.py` — `plan()` is the default and writes nothing; `collect()` refuses unless explicitly armed *and* given a `PacedTransport` *and* a fetcher. Destinations must resolve inside the declared staging root and may not alias a protected input; the root may not contain one. Writes go to `.partial` files promoted only on success, so an abort leaves nothing. | 11 cases |

---

## Exact commands and actual results

```bash
# M2a (new)
cd "claude methods/_m2_pilot"
../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2a.py        # exit 0, 48 cases, 0 unexpected

# accepted M1 gates, unchanged and still green
cd "../_m1_closure"
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py       # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py   # exit 0, 46 cases
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py   # exit 0, 67 checks
```

Production databases unchanged (`trading_local.sqlite3` 2026-09-04 18:27, `market_history.sqlite3` 2026-09-04 11:44); no `staging/` directory exists; HEAD `73f266d`; index empty.

---

## What the tests actually establish

**Provenance never launders an unknown.** A response fetched from an unexpected URL, or missing a required column, is `unknown`, and `require_basis("none")` on it raises rather than relabelling. In the runner this surfaces as a **rejected** job whose rows are never written — asserted directly: after a run where the observed path was wrong, the staging table holds 0 rows for that symbol.

**Units are evidence, not a constant.** `hand` and `share` are each derived correctly from consistent fixtures; an amount consistent with neither, or with both, yields `unknown`. A benchmark carries no amount series, so its unit is `unknown` by construction and it is excluded from unit gates rather than given a manufactured value.

**Pacing sees what the network sees.** Both GETs of a stock call are paced and counted, so a 52-symbol run is 102 attempts, not 52. Redirects are refused precisely because following one would be an attempt outside the ceiling and the pacing. A 403 or 429 aborts on the first response and the abort is sticky — a later call raises without touching the transport.

**Acceptance cannot be satisfied by an exit code.** `exit 1` alone is explicitly insufficient: an integrity FAIL, an advisory integrity gate, or any required failure other than the depth gate each reject. The shortfall must equal the pinned set security by security — an unexpected symbol, a missing one, or a wrong eligible count all reject. The complete set is 14, derived independently, not the gate's three-row sample.

**Staging cannot escape.** A destination outside the root, a traversal path, one aliasing a production database, or a root containing a protected input are all rejected before any write. An aborted run leaves the staging directory empty; a clean run creates exactly the two declared files and nothing beside them.

---

## P2 reclassified

An unavailable fallback is a **declared limitation**, not a requirement to develop another source, and I retract the rev.2 wording that no source can supply the window. The primary path *can*: one `stock_zh_a_daily` call returns the entire series and is sliced client-side, so research and warm-up come from a single fetch. What is missing is a *second* source able to do the same — the Tonghuashun adapter caps at 500 bars. If the primary fails for a symbol, that job is a **reported failure**; the runner invents no substitute and reaches for no other provider, and there is a test asserting exactly that.

---

## Unresolved live-data questions

These cannot be answered offline and are deliberately left open:

1. **Does the live raw response actually carry `amount` for every pilot symbol?** The unit derivation depends on it. Offline fixtures prove the *logic*; only live data proves the *availability*.
2. **What are the real vendor limits?** Observed throughput is not a quota. Pacing is set slower than anything previously observed, and the ceiling is a budget, not a measurement.
3. **Does `drop_duplicates` on OHLCVA drop legitimate sessions?** The raw path deduplicates on all six fields, so two genuinely identical sessions collapse. Whether this occurs for these 52 symbols is measurable only against live data, and it would surface as missing keys the M1 gate correctly fails.
4. **Is the observed URL set stable?** Provenance keys off exact URLs. A vendor-side path change would make every series `unknown` — fail-closed, but it needs confirming against one real response.
5. **Do index responses match the assumed column set?** Only the shape is asserted offline.

---

## Proposed live smoke test — small, for later authorization

Not requested now; stated so the eventual ask is already bounded.

| | |
|---|---|
| Scope | **3 symbols**: one ordinary stock, one BJ stock, one benchmark (`SH000300`) |
| HTTP attempts | 2 + 2 + 1 = **5**, ceiling 15 with retries |
| Pacing | ≥ 1.5 s, concurrency 1 |
| Writes | a temporary staging directory, discarded afterwards |
| Purpose | answer questions 1, 4 and 5 only — confirm `amount` presence, the URL set, and the index column shape |
| Explicitly not | measuring vendor limits, collecting the pilot, or populating anything durable |

The full 52-symbol pilot remains a separate authorization after that.

---

## Limitations carried forward, not waived

Strict point-in-time evidence remains absent and cannot be created retroactively. Historical universe, ST history, suspension calendar, delisting register and BJ pre-2024-08-12 code mapping remain **UNKNOWN**. Volume-unit evidence for the existing corpus remains UNKNOWN; the 293 STAR-board near-100× events remain a hypothesis to test, and nothing is rescaled on suspicion. `identity` is the only supported cross-view transformation. The 746 legacy evaluations and A2 remain a separate prerequisite. **Warm-up collection acceptance is data integrity, never feature readiness** — on this corpus 14 of 50 stocks cannot reach 250 sessions and no download changes that.

M2 execution is not authorized. Nothing here starts it.
