# M4-02A 第二轮独立复核：仍需一项修复

结论：修订版已通过 38 项交付测试和上轮全部 5 项独立检查。新增日历反例发现同一订单仍能绕过原到期时间，暂不进入 M4-02B。

被测账本 SHA-256：`fd832b0e41e8ff5c284b2c08213e6bb525b6dc69158ac66fa358d3b347e9658d`。
测试 SHA-256：`4c6e65e3836cdef67fceb446221e5be86794b66559e81d7fb89c479006f60ed3`。
Claude delivery_02 manifest：`ebc18c1f147008876f3cce801693dfca426b2f05422d825e7d7e57fd69d9fdca`。

Codex 已独立核对：35 项交付文件、25 项读取来源、49 项 M4-01 冻结项、316 项原跟踪文件、42 项历史冻结项、16 项生产文件位置均保持预期字节/状态。测试以隔离文件加载运行，无 app/conftest 导入、SQLite 连接或网络访问。旧 portfolio_review_01 原样保留。

证据位于 `codex/portfolio_review_02/`：`results.json`（5/5）、`delivery_suite_receipt.json`（38/38）、`calendar_binding_results.json`（原日历对照通过，变更收盘时间失败）、`delivery_verification.json`。新反例程序为 `codex/probe_portfolio_calendar_02.py`。

## Remaining P1: same-source calendar mutation rewrites the original expiry

`backend/app/research/m4_portfolio.py` `_order_terms` (line 640) binds only `calendar_source_ref`, while the frozen execution kernel derives the actual expiry from the injected calendar session list, timezone and open/close clocks on every attempt.

Concrete independent reproduction, using synthetic inputs only:

1. Create a continuous buy order for 200 shares, eligible March 19 09:30, expiry_sessions=1, calendar closes at 15:00. At 10:00, capacity permits 100 shares; first fill succeeds with 100 remaining.
2. Retry the same order/decision and unchanged causal terms at March 19 15:30, quantity 100, fresh attempt-time price/capacity evidence. With the original calendar it is rejected without state effects.
3. Change ONLY calendar.close_time to 16:00, retaining the exact same source_ref and availability. The ledger accepts and fills the remaining 100 shares. Thus the original order's 15:00 deadline is moved without an amendment or new order identity. This is a remaining route through the prior P1-4, not a new strategy feature.

Bind the calendar facts needed to preserve the originally registered order's eligibility/window/expiry, or persist and enforce the original computed temporal contract. Compare semantic consumed calendar facts, not just the source label. Include clocks/timezone and the relevant session prefix/window; do not unnecessarily bind an unrelated future suffix, since causal prefix invariance must remain valid. Preserve atomic rejection and the frozen M4-01 bytes. Attempt-time observations may still vary normally.

Add regressions for unchanged valid within-window retries, the exact after-close mutation above, relevant calendar/session-prefix changes, and irrelevant future suffix changes. The last must remain permissible when no consumed fact changes. Keep the original 5 independent expectations and all 38 existing regressions intact.

## Next instructions to Claude

Continue the SAME M4-02A-PORTFOLIO-LEDGER-20260912 task in its existing exclusive write scope. Preserve delivery_02 by byte/hash before replacing it; do not modify Codex scripts or evidence. Reproduce the remaining P1 from the saved snapshot/results, fix the ledger calendar-binding contract, and replay the independent cases only into your own output directory with unchanged expectations. Update the correction matrix, contract, actual isolated test receipts and preservation evidence; write the new complete artifact manifest last. Report ready_for_review with final source/test/manifest hashes and stop for Codex review. Do not start M4-02B, M4-03, M5, other agents, data access or automation changes.
