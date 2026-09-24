# M4-01 第一轮独立复核：需修复

本轮复核的是工作中快照，不是最终交付验收。Claude 已实际执行并生成内核、自测及回执；其回执报告 54 项通过。Codex 另行运行独立合成探针：9 项中 1 项符合预期，8 个反例暴露下列 6 类问题。因此 M4-01 尚不能冻结，也不能进入 M4-02。

被测源码 SHA-256：`7510c3a506426e85f2e8f4acf63775ce7ee66e4a3ed8b7fd51a65498fc77f53c`。

复现程序：`codex/probe_m4_working_01.py`；原始快照与逐项实际结果：`codex/working_review_01/`。只使用 Codex 自行定义的合成输入，没有复用 Claude 测试夹具。买入 100 股、10 元、假设最低佣金 5 元和过户费 0.01 元的现金变化 -1005.01 元正确。其他预期直接来自时间契约、注入的零股政策及输入身份一致性，并非从被测实现反推。无数据库、网络、子进程或越界写入；保护器拒绝次数 0；探针期间原文件未变。

## Required corrections within the existing M4-01 task

1. **P1 — premature expiry.** At 10:00 on an expiry session whose explicit `expires_at` is 15:00, both an unfilled continuous order and a partially filled continuous order have `order_live_after_attempt=false`. `_evaluate` and the `_Unfilled` handler use `exec_session == expiry_session` instead of the actual instant. Preserve the eligible remaining order until its actual expiry boundary. Test partial and zero fill at 10:00, a later eligible retry, and the boundary at/after close. Open-auction-only orders may have a separately documented final executable opportunity; do not let that convention silently expire continuous orders.

2. **P1 — declared odd-lot policy conflicts with capacity rounding.** Under `whole_odd_remainder_only`, selling the entire settled 50 shares with exactly 50 shares of available capacity returns unfilled; selling all 199 with capacity 199 fills only 100. Applying the 100-share increment to capacity before considering a permitted whole odd remainder destroys legitimate capacity. Respect requested odd-lot semantics within raw capacity; cover 50/50, 199/199 and genuinely insufficient capacities, both `whole_odd_remainder_only` and `any`, plus cumulative consumption. Do not simply widen the input policy to avoid the counterexample.

3. **P1 — unavailable calendar accepted.** Changing only `calendar.available_at` to 2025-01-01 still fills a March 2024 decision/execution. Validate availability of the calendar consumed to derive eligible/expiry/settlement sessions; document the earliest required instant and reject future publication. Keep injected calendar provenance visible; do not silently treat this field as decorative.

4. **P1 — consumed settlement calendar omitted from input identity.** Change the calendar suffix after the expiry session from next settlement session 2024-03-20 to 2024-03-22. `sellable_from_session` changes while `input_hash` stays the same. The result actually consumes the settlement session beyond expiry. Bind the minimal complete consumed prefix, including settlement where used, or explicitly separate a later-derived settlement result. Preserve suffix invariance only after the last genuinely consumed session. Update the contract and existing tests that currently overstate expiry-prefix invariance.

5. **P1 — ambient Decimal state controls execution / may crash.** The same valid positive fixture under caller `localcontext(prec=6, rounding=ROUND_DOWN)` raises uncaught `decimal.InvalidOperation`. Establish a deterministic local arithmetic context, precision/exponent/input bounds and controlled rejection for unsupported numeric magnitudes; do not rely on process-global precision/rounding/traps. Test multiple contexts, nonzero fee rounding, long numeric representations, and valid upper boundaries. Restore caller context unchanged.

6. **P2 — accepted integer money does not normalize to the same identity.** Replacing only price `'10.00'` by the accepted integer `10` changes identity/result despite equal economic inputs. Normalize every accepted numeric representation, including ints and Decimal, without ambient-context rounding. Keep identifiers and true quantity integers typed according to the schema; do not normalize arbitrary strings globally.

The timestamp-labeled field contracts and fee/assumption provenance also need to remain explicit; no historical execution proof is inferred from synthetic results. This review does not authorize adding data access, M4-02, external research, or modifying any Codex snapshot/probe or prior M2/M3 evidence.

## Next instructions to Claude

Continue the **same M4-01-EXECUTION-CONTRACT-20260912 task**, within its existing exclusive write scope. Read this review and the frozen raw probe results. Reproduce the six findings, repair the contract and implementation, add meaningful regression coverage, and rerun your guarded isolated unittest runner. Preserve your first delivery evidence in a versioned subdirectory before superseding it. Do not edit Codex evidence or weaken the independent expectations. If you disagree, supply a concrete contract-based counterexample and leave that item unresolved for Codex. Deliver a correction matrix, actual execution receipt and a final manifest last; report `ready_for_review` with its SHA and stop. Do not self-accept or start M4-02.
