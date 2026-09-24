# G-3 retained-artifact analysis — Codex independent review

Date: 2026-09-09. **Verdict: numerical findings reproduced; implementation acceptance requires two corrections.** No P1/U-6/source-capability upgrade or new operational authority follows.

## Version and ownership

The original Claude session `Fable 5.1 project advice` reported a four-file delivery, with analysis script `178eee2c…` and test script `ad8f3d9e…`. During this review the running `Fable 5.1 project advice (fork)` replaced files in that same directory and added PROVENANCE.json. The reviewer initially encountered an API mismatch while that replacement was occurring; that aborted attempt is not counted as a product test failure. The following findings apply to the subsequent stable five-file version only.

Current directory: `claude methods/_m2_smoke/g3_ratio_analysis_20260909/`.

| File | SHA-256 |
| --- | --- |
| `g3_ratio_analysis.py` | `557003e2d160cebd6bf848c8300169a3ea2de22b06dd8832d9ccda45ef67b8f6` |
| `test_g3_ratio_analysis.py` | `baa32b5ce119cb412cf1a325a31899f68e28e261d91e069cec4960406a5ee66b` |
| `results.json` | `41bbea11506c0953d7fe7477ce7eec080e94a38a624979e028be1c84231a676b` |
| `REPORT.md` | `75d114b35763933f14a9d3056ec86296825c56b845a18292bc77f86c9b9d3643` |
| `PROVENANCE.json` | `28185984fa7ebd738699918b2f4ca6f7ddf8c2ae1a1112ec1dd385929b39fc22` |

Use the fork as the sole G-3 implementation owner for subsequent work. Preserve this version now; implement corrections in one separately named new directory. Do not let both Claude sessions write the same files. A coordination message requesting a stable handoff was visibly submitted to the fork; submission alone is not proof of acknowledgment.

## Verified numerical findings

- Claude's current suite: **15/15 passed**.
- Independent review: **16/20 expectations passed**, four failures grouped into the two findings below.
- All results reproduce from the retained inputs; the Markdown report reproduces when the producer's original iteration order is used (JSON serialization sorts object keys).
- Independently joined vendor and reference dates reproduce every ratio and price difference: SH600011 538 dates, BJ920000 501, SH000300 538.
- Independent source/updated_at segmentation reproduces stock partitions 37/470/1/30 and 470/1/30; index 2/1/475/60. Both documented 470-row segments are confirmed.
- The stock ratios are not flat across the wider overlap: SH600011 ranges 1 to about 1.10610; BJ920000 1 to about 1.04991. BJ920000 has five reported price-difference plateaus: +0.29, +0.23, +0.15, +0.08, 0. These are observations, not an established corporate-action explanation. The index comparison remains separate.
- Current selected revision independently passes the already-reviewed basis verifier, with source digest `099640a2…`. The analysis output's five consumed-input hashes and recorded producer hashes match current files.

## G3-R1 — P2: invalid-price handling diverges between full-span and segment analysis

Locations: `g3_ratio_analysis.py:134` (`compare_series`) and `:214` (`per_segment`).

Synthetic changes to a copied in-memory reference, passed through the public `analyse()` path, reproduce:

1. A `None` close raises TypeError in `per_segment`, so no invalid-price report can be generated.
2. `True` is accepted as price 1.0 instead of being marked invalid.
3. Positive infinity is excluded by the full-span comparison (537 usable dates) but retained by the segment comparison (538), creating contradictory denominators and spurious segment statistics.

The current retained overlap does not contain these invalid reference values, so its reproduced numeric results remain useful. The defect is in the requested invalid-price reporting behavior, not a claim that retained prices were altered.

Required correction: use one strict finite-positive numeric validator in both paths; exclude booleans and do not coerce arbitrary strings. Report invalid rows consistently and preserve matched/missing counts. Add full `analyse()` regressions for null, boolean, nonnumeric and non-finite prices on both sides; assert agreement between overall usable counts and segment totals.

## G3-R2 — P2: requested consecutive-date change output is missing

The current version emits per-date ratio levels and `vendor_close - reference_close` differences plus rounded runs. It does not emit consecutive-date changes in the ratio. A cross-source price difference on one date is not a time-series change between two dates. This part existed in the earlier overwritten version but is absent from the reviewed fork version.

Required correction: add explicit from/to dates and unrounded `ratio(t)-ratio(previous_usable_date)` records, including boundary flags for source/updated_at and a clear statement that pairs use consecutive usable common dates, not necessarily consecutive exchange sessions. Keep price differences as an additional measurement. Do not invent a threshold or label jumps as corporate actions. Test ordinary changes, zero changes, missing/invalid intervening dates and metadata boundaries.

## Commands and preservation

```powershell
& 'backend/.venv/Scripts/python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_g3_ratio_codex.py'
```

Result: `_m2_codex_review/g3_ratio_codex_review_results.json`. Driver exit 0 records completed review execution; it does not override the four failed expectations.

The final review run preserved all **86** smoke/analysis files in its before/after map. The previous documentation checkpoint also matched. Network and database guards were active; audit rules blocked external connections, SQLite connections, subprocesses and os.system while permitting the decoder engine's local loopback self-pipe. No network capture, adapter replay, service action, production data mutation, staging, commit or push was performed. The scientific inference limitations remain: no independent corporate-action reference, incomplete earlier reference overlap, P1 open, U-6 deferred, all eligibility false, source capability FAIL, both capture authorizations consumed.

## Next-stage instructions for Claude

As the sole G-3 implementation owner, fix G3-R1 and G3-R2 in one fresh directory `claude methods/_m2_smoke/g3_ratio_analysis_20260909_r2/`. Preserve the current five-file directory and all earlier evidence, producer files, basis outputs and Codex artifacts. Share one strict price-validity rule across overall and segment analysis, and add explicit consecutive-usable-date ratio changes with boundary flags. Add the focused regressions described above, rerun only offline synthetic and retained-artifact validation, and report exact hashes and results at `ready_for_review`.

No corporate-action inference, threshold, basis/eligibility change, P1 closure, source verdict upgrade, adapter replay, network, SQLite, capture, services, production mutation, training, staging, commit or push. Do not update the goal/request documents merely to acknowledge this review. Stop modifying the new directory once handed off.
