# G1 bounded research delivery — Codex technical validation

2026-09-09, 07:11 UTC. Reviewed task: `G1-DOC-20260909-R3`; delivery: revision 3, documentation correction 1.

**结论：本次有界 G1 官方公司行动研究交付技术通过。G1-R3-A、G1-R3-B 已关闭。不是全部证据缺口关闭，不是用户政策采纳、供应商复权口径认证、M2 完成或训练就绪。**

## Evidence and preservation

The sole Claude implementation fork was observed Idle with a completed `ready_for_review` response. The stable 46-file delivery was frozen at `claude methods/_m2_codex_review/g1_review_20260909_r3_doc1/reviewed_delivery/`; `review_results.json` records independent checks and all delivery hashes.

Exactly seven paths changed relative to the frozen r3 delivery, with no added or removed G1 file. The other 39 files are byte-identical, including all 19 PDF/HTML notices, all 19 raw query responses and CLASSIFICATION.md.

| Changed artifact | Reviewed SHA-256 |
|---|---|
| REPORT.md | 77941f8c1344ebe20be93c8377e15e68188670c69021d7b03f3925f016e6617a |
| events.json | 7eb0e34d07b158bc8e46001d83faff4d6f62c0cc89b1212943c885b4214f366b |
| PROVENANCE.json | b2d7b5c782d4afd99b0cb03d61f6bf957b6b8ff3e4cad90772d576f7a127f3b1 |
| search_coverage.md | bb249cb8d88d77df5cb2e2c50867802d82eb0c11b947473883a454a84279b8f4 |
| disclosure_index/README.md | 8077fcfa2150202685a9e0b8085ebfe645280202d6876623933940c9d66b2e92 |
| disclosure_index/derived_920000_announcement_titles.txt | 5527f93fe30915640cc1190de4d236856cc8c77019632ec8fdbb5eb98e5de7d0 |
| disclosure_index/derived_600011_announcement_titles.txt | a91e3d8fbb061f1c25c327167aed9f88b9e3faa555ba989553f3c087b11e29ac |

Independent recomputation from unchanged raw JSON confirms all **438** local dates equal their finalpage dates; **437** epochs are local midnight, with one 08:38 exception. The derived listings reproduce the raw records exactly as row multisets: **200 BJ and 238 SH**, including their explicitly labelled tail queries. Their hashes match provenance. All 25 individual file/hash entries checked successfully.

All 91 previously protected paths still match; the five accepted G3 r2 pins match, goal/request retain `f8b699e5…` / `c39726d0…`, HEAD remains `73f266d`, staging is empty. No tests, replay, network, SQLite or production actions were performed by Codex during this documentation review. This is bounded file-integrity verification, not proof of every unobserved historical action.

## Findings closed and facts retained

- **G1-R3-A closed:** UTC and UTC+08:00 are distinguished; the erroneous effective-date bracket is withdrawn. Platform tagging and filing-header observations remain separate. G-g stays unknown.
- **G1-R3-B closed:** G-e is now NOT ESTABLISHED/open. Publication-window/title-search limits, SH explicit period statements versus BJ net balances, sampled bases and July's uncovered tail are stated consistently. Six cash events are labelled identified events in retained evidence, not an exhaustive universe.
- The parameter-outcome contradiction and 17 announcement responses plus 2 issuer responses count are corrected.
- The six cash-event records differ from r3 only in four `announcement_date_basis` explanations. All amounts and actual dates remain unchanged. The prior independent official PDF downloads are preserved in the r3 reviewer folder. Five comparisons match date and amount; E-1 remains 0.28 observed versus 0.27 disclosed. No tolerance or causal/basis conclusion has been introduced.

**Correction to Codex's own r3 report:** I conflated two leads. The retained official index identifies `finalpage/2025-04-14/1223097471.PDF` as **安徽凤凰 / 832000**, an earnings-call preview. It was not a wrong-issuer document. Claude's separately reported wrong-issuer hit was `finalpage/2025-05-14/1223537409.PDF` (not retained and not independently re-fetched in this documentation round). My claim about the April lead is withdrawn. The old review remains unchanged as history; this correction supersedes that sentence.

**Non-blocking wording caveat:** README's phrase “UTC shifts every date back one day” is too broad: it applies to 437 midnight records; the explicitly documented 08:38 exception remains the same calendar date in UTC. The actual derived rows and measured counts are correct. No additional correction round is required for this isolated wording; future citations should use the measured 437/438 distinction.

## What is complete and what needs a separate decision

The authorized public corporate-action research pass and its corrections are technically validated. G-a/b/c/d are closed for the specific identified facts; whole-interval absence G-e and legal code-change date G-g remain unestablished/unknown. P1 is open, U-6 deferred, every eligibility false, source capability FAIL on retained EV6 disagreements, and both capture authorizations consumed.

The old U-6 proposal's premise that no corporate action is established in a compared span and no wider ratio has been computed is now outdated: G1 and G3 supplied those bounded observations. That changes the basis for considering a review; it does not adopt U-6 or create a positive eligibility rule. Missing early reference coverage and E-1's discrepancy remain.

**Recommended next user decision:** authorize one standalone, documentation-only **U-6 reopening/readiness assessment** using the accepted G1/G3 artifacts and existing proposal. It should distinguish newly resolved prerequisites from remaining evidence gaps, assess whether a discriminating basis rule can yet be proposed, and list necessary further evidence if it cannot. No threshold calibration, rule adoption, code/gate wiring, labels, network or data access follows from that proposed task. The existing proposal and validated artifacts should remain frozen. This next work is not dispatched under the narrower G1 authorization.

Pause the 20-minute heartbeat after recording this acceptance and notifying Claude to hold, rather than repeat empty research or assume new authority.

## English handoff — hold, not another implementation task

Codex has technically validated the bounded G1 research delivery at the seven hashes above. G1-R3-A and G1-R3-B are closed. Preserve all files and evidence; create no acknowledgment artifact and perform no further work. G-e remains not established, G-g unknown, E-1 discrepant, P1 open, U-6 deferred, all eligibility false, source capability FAIL, and both capture authorizations consumed. Await a separately scoped user decision before any U-6 reassessment, policy, implementation, data access or retrieval. This is not M2 completion or vendor-basis acceptance.
