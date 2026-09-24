# Supplement to the active M3-01-R3 task

Codex, 2026-09-10. This is one integration finding for the already-running R3 task, not a second task or another writer. Preserve the six R3 fixes and its current write/side-effect boundaries. Do not change the hashed R3 instruction file.

Static M2 metadata proves both SH000001 and SH000300 are benchmarks whose volume_unit, amount_unit and unit_status are `not_applicable`. See `claude methods/_m2_codex_implementation_20260910/qualification_v2_reviewed.json`, SHA-256 `992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37`, and `contract_v2.py:250-255`. These units must remain honest in the later reader. An index level is not a stock price in CNY, and aggregate index turnover divided by volume need not equal the index level.

Codex reproduced the incompatibility against the immutable R2 module (`fe6046476f492aca4487492e47477166f47d1cfe052167adf021c0bf238d17e7`) using invented observations only. Receipt: `claude methods/_m3_20260910/codex/frozen_r2_benchmark_probe.json`; producer: `probe_frozen_r2_benchmark.py`. The existing share-unit fixture generates a range regime. The otherwise valid index-level fixture with the retained `not_applicable` unit fails `unsupported_volume_unit`. Renaming it to share still fails the stock `vwap_outside_range` check. No real price body or SQLite was opened; these results do not claim to execute the changing R3 module.

Please include a role-aware benchmark input contract in R3, in the same two backend files and `claude_01_r3` output folder already allowed:

1. Admit the retained benchmark unit and explicit index-level OHLC semantics, while preserving positive finite ordered OHLC, dates, identity, calendar, availability, and adjustment checks. Do not apply stock VWAP/CNY-per-share semantics to index levels. Decide and document treatment of benchmark volume/amount as uninterpreted retained fields or omitted fields; do not consume them as stock liquidity features or fake share/CNY values. Reject malformed supplied numerics rather than using this as a broad validation bypass.
2. Keep stock share-unit/VWAP validation and the scoped M2 stock exception intact. Stocks cannot claim benchmark semantics, and benchmark symbols cannot become positive/control stocks.
3. Add synthetic positive and negative integration controls through generate_labels: preserved M2 benchmark units produce a price-only regime; changing unused turnover cannot change the regime; invalid benchmark OHLC/availability/identity still reject; stock unit/VWAP failures still reject. Keep existing synthetic fixtures meaningful and make any API changes explicit.
4. Document this as an integration correction, without tuning any phase/liquidity/regime/matching thresholds. Pin this supplement and its evidence in the final R3 manifest, keep previous snapshots intact, and retain the original R3 completion/independent acceptance gate.

No real reader, corpus extraction, database access, network, new agents, client manipulation or M4 is authorized by this supplement. Codex continues the independent review and the existing 15-minute inspections.
