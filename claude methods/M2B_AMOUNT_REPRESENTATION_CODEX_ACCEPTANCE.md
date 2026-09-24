# Amount representation audit — bounded technical validation

2026-09-09. **Technically validated within the reviewed static scope.**
`M2B_AMOUNT_REPRESENTATION_AUDIT.md`, revision 2, 467 lines,
SHA-256 `cecc8c7a7f22f3e3d05a1cabffbb765b4fa6cc29973a85bd11e118f976e953a2`.
Snapshot: `_m2_codex_review/amount_representation_review_20260909_r2/`.

AR-R1 through AR-R3 are closed for these bytes. The corrected audit distinguishes the
stock unit gate from excluded benchmarks, the actual batch UPDATE guard from first
inserts and preceding deletes, caller-stamped metadata from vendor evidence, and the
comparison's reconstructed frames from hypothetical identical-input reasoning examples.
The delegated Tencent path is accounted for. Retained U2/U3 counts and ratios were
cross-checked against v2 JSON and their source definitions; they do not certify other
providers, cache contents or index liquidity.

The unsupported minimal-fix proposal is withdrawn. The stock refresh's quality-status
overwrite and the possible effect of a new flag on conflict decisions are now explicit.
Any future semantic change remains a policy/implementation question, not an authorized
fix. No active turnover-rate-to-amount substitution is established on the inspected
concrete returned schemas. A Tencent qfq path can construct ready candidate bars with
amount None, which comparison would flag; actual writes and stored contents were not
observed. Benchmark null amount is a separate case.

Verification: 19 document-table pins match; the additionally consulted smoke checker is
also pinned in verification JSON. All 91 protected baseline files and 46 G1 files match,
with identical G1 path sets. Relevant source bodies and the correction diff were reviewed;
no tests or production module execution were needed. No SQLite, network, replay/decoder,
services, production/data changes or Git writes. HEAD `73f266d`, nothing staged.

This closes the bounded static alias/null/unit audit, not a production gap or M2 itself.
P1 open; U-6 deferred; every eligibility false; source capability FAIL including historical
EV6; both capture authorizations consumed. No policy adoption, corpus certification,
training readiness or new operational authorization follows.

## English next instruction

Preserve the accepted audit. Continue with the decision dependency map described in
`_m2_codex_review/m2_remaining_dependencies_dispatch_20260909.txt`, identifying only
material remaining work, its evidence and authorization dependencies. Do not invent
another cosmetic audit or redefine M2 completion.
