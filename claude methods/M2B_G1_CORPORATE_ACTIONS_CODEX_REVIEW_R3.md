# G1 revision 3 — Codex independent review

Reviewed 2026-09-09, approximately 06:40–06:46 UTC. Task reviewed: G1-COMPLETE-20260909-R2. Verdict: **cash-evidence completion validated; two material documentation corrections required before accepting the bounded G1 research delivery**. This is not M2 completion, basis acceptance or policy adoption.

## Frozen delivery and verification

All 46 delivered files were copied to `claude methods/_m2_codex_review/g1_review_20260909_r3/reviewed_delivery/`. Hashes were stable before/after the copy and again at verification. Claude's sole implementation fork was refreshed and observed **Idle**, with its completed `ready_for_review` response and an empty composer.

| Reviewed file | SHA-256 |
|---|---|
| REPORT.md | afd1961455e71fd4c44230268b582354338ac1bf0dc4194c8eca23da0963dba6 |
| events.json | a20ab2ce8ed2f2e82610822978feef8c536b3ec6d2ce0b97bf60ae8a19bd73c1 |
| PROVENANCE.json | 8ae523e8ea00234c9008458f127dee9a567163edaf7a9da318c2ed4d5eaf933f |
| search_coverage.md | 62f2eff9fc87aedbb7d23b0f72856eb4759b615f677b3fa6c1ef43c3cbdd5a76 |

The snapshot's `delivery_hashes.json`, `review_results.json` and `official_refetch_results.json` hold the full evidence. Independent HTTPS retrieval of the four newly retained implementation documents returned HTTP 200 and byte-identical PDFs, with TLS verification enabled:

- BJ 2024-068: `https://static.cninfo.com.cn/finalpage/2024-09-20/1221258690.PDF`, hash `6f22f7be…`.
- BJ 2025-047: `https://static.cninfo.com.cn/finalpage/2025-05-07/1223491665.PDF`, hash `aba4cb40…`.
- BJ 2026-037: `https://static.cninfo.com.cn/finalpage/2026-05-15/1225310540.PDF`, hash `c8bcf19f…`.
- SH 2026-036: `https://static.cninfo.com.cn/finalpage/2026-06-25/1225385939.PDF`, hash `269ed39f…`.

The public web reader could not open these URLs in this round; direct official HTTPS retrieval succeeded. The PDFs were independently read for issuer, announcement number, amount and implementation dates. The earlier E-1/E-3 evidence remains preserved. The cash closures G-a/G-b/G-c and E-2's upgrade to retained Tier A are validated. The historical mirror remains non-evidence; byte identity is now actually measured and does not retroactively justify v1's unsupported assertion.

Independent recount of retained query JSON confirms BJ 190 distinct announcements across 7 pages and SH 227 across 8, with tail queries of 10 and 11. This establishes pagination completeness for those exact queries. All 25 individual file/hash entries in provenance checked successfully. Re-reading the retained G3 artifact confirms six event pairs, five exact date/magnitude matches, and E-1's unresolved 0.28 versus 0.27 discrepancy. Both boundary flags are false for each of the six pairs. No replay or tests were run.

The 91 previously protected paths have no hash mismatch; all five accepted G3 r2 file pins still match. HEAD is `73f266d`, staging is empty. This is a file-integrity observation, not a forensic claim that no unobserved action ever occurred.

## G1-R3-A — UTC date was mistaken for a different announcement date

Affected: REPORT lines 80–83 and 381; events identity and announcement-date explanations; disclosure_index/README lines 68–73; provenance standing position; related coverage text.

The retained epoch timestamps explain the one-day difference directly:

| Record | Epoch milliseconds | UTC | UTC+08:00 / finalpage date |
|---|---|---|---|
| Last stored old-code announcement | 1759161600000 | 2025-09-29 16:00 | **2025-09-30 00:00** / 2025-09-30 |
| First stored new-code announcement | 1760371200000 | 2025-10-13 16:00 | **2025-10-14 00:00** / 2025-10-14 |

For example, E-5's `1726761600000` is 2024-09-20 midnight UTC+08:00, matching its publication date. Rendering UTC is legitimate if labelled UTC, but it does not demonstrate that the platform announced the filing one day earlier. Remove that interpretation throughout. Raw query JSON must stay byte-identical; derived lists may remain explicitly UTC, or be regenerated with both timezones and updated hashes.

Separately, per-announcement `secCode` metadata is not a legal effective-date observation. Even the corrected local dates **must not be promoted into an exchange-effective-date bracket**: historical tagging can lag or be maintained retrospectively. Record 2025-09-30 / 2025-10-14 as the transition in the retained platform metadata. Keep the earlier retained filing-header observations, 832000 on 2025-09-10 and 920000 on 2026-04-21, separately labelled as observations rather than proof of the exact legal date. G-g remains unknown. Replace “the issuer filed nothing/no code-change announcement” with the bounded statement that none was identified in the retained query results.

## G1-R3-B — G-e's universal absence conclusion exceeds the evidence

Affected: REPORT section 4, especially lines 236–245 and the G-e CLOSED ledger; events lines 424–446 and its gap ledger; provenance and coverage summaries.

The new search is substantive, but it does not warrant “No bonus-share issue, capital-reserve conversion or rights issue took effect for either A-share instrument inside the interval.” Three specific problems remain:

1. The query filters **publication dates** from 2024-08-01. It does not cover an announcement published before that date whose implementation falls after 2024-08-13. A publication window wider than the event window is not itself complete event coverage.
2. Keyword filtering was of titles, not all bodies; the response is one platform's holdings. Those already documented limits are inconsistent with claiming an exhaustive absence proof.
3. SH's reports contain an explicit statement of no share-count/structure change for FY2024, FY2025 and H1 2026 (independently read on pages 95, 74 and 34). BJ's three summaries report opening/closing counts and net change zero. They are not six equivalent no-change statements. Repeated distribution bases are sampled dates, not continuous proof. July 2026 has no covering period statement.

**Required correction is documentation-only, not another search pass.** Preserve the confirmed cash evidence and enumeration counts. State that no matching bonus/conversion/rights implementation was identified in the retained publication-window/title search, distinguish SH's period statements from BJ's net-balance evidence, list the coverage limits, and leave whole-interval G-e absence unestablished. A bounded research pass can be complete with an evidence gap honestly open. Do not invent an event to fill the gap, and do not initiate further retrieval to force it closed.

Also qualify exhaustive cash-count wording as six **established/identified** in-interval implementations in the retained evidence, rather than a proof that no other implementation could exist.

## Small consistency repairs in the same edit

- README line 41 and provenance line 52: “column is effectively ignored” contradicts the reported zero results for bse/third/neeq versus full results for sse/szse. State the observed parameter outcomes without the ignored claim.
- PROVENANCE line 53: there are **17** `cninfo_hisAnnouncement_*.json` files plus **2** topSearch files, **19** raw responses total.
- A prior reviewer-supplied 2025-04-14 PDF lead turned out to concern another issuer. Claude correctly rejected it. It is not evidence for this issuer; retain that limitation in search history rather than expanding scope.

## Next instruction — G1-DOC-20260909-R3

Read this review and correct G1-R3-A and G1-R3-B consistently across only the existing G1 documentation/structured indexes and, if needed, the two derived title listings. Preserve all original PDF/HTML notices and raw query JSON byte-for-byte. Preserve the accepted six cash facts, E-1 discrepancy, G3, basis/smoke, historical revisions, reviewer snapshots/reports, proposals and goal/request. Correct provenance hashes for any changed derived files. No new evidence retrieval, network, code/tests/replay, market-data capture, SQLite, services/tokens/accounts, production/dataset/strategy/knowledge changes, policy/threshold/gate/label/eligibility changes, training, pilot, source integration, Git staging/commit/push or live trading. No acknowledgment-only artifact. Stop at ready_for_review with changed paths and hashes. P1 remains open, U-6 deferred, every eligibility false, source capability FAIL, and both capture authorizations consumed. Completion of this bounded G1 pass must not be presented as closure of every evidence gap or of M2.
