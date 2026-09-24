# M4-02B 第二轮独立复核：两类剩余阻断

修订版的29项交付测试和原5项独立检查全部通过；Codex仅适配明确新增的 `entry_phase="continuous"`，原语义预期未变。新增执行时估值与乱序路径检查发现两类剩余P1，暂不进入M4-03。

源码SHA：`ebd7d80514161477c95261c1eb782383238ea5c47c35bb6e4acb48a0d3c1e5da`；测试SHA：`122ada3893f77e820061ac690be27d909762d78daee22259d1c2cc922b13ff97`；清单SHA：`1626385eb77da0377051051d9a04adeb9ad160a0930a8ff04322af2fd10ff867`。

证据目录 `codex/risk_review_02/`：原5项 `results.json`；29项 `delivery_suite_receipt.json`；新增6项 `additional_results.json`；完整字节核对 `delivery_verification.json`。39项交付文件、25项读取来源、两级冻结49+74项、316项原跟踪文件、42项历史冻结、16项生产文件位置均符合基线。纯合成隔离执行，没有app/conftest、SQL、网络或生产写入。Claude原生界面已显示最终停止等待复核；UIA存在滞后，使用刷新同一任务后的截图核实。

## Remaining P1-1: current-risk mark selection chooses the oldest print and accepts conflicts

In `execute` (around lines 640–656), candidates are sorted by `(age, observed_at)` ascending, and element0 is used. Thus, within the same session it selects the oldest eligible observation, despite the declared latest-mark contract. It also does not apply the decision valuation's conflicting-same-instant rejection.

Independent fixture `codex/probe_risk_additional_02.py`: initial cash10000 and OTHER1000 shares; prior-close OTHER mark1 and target mark10 generate a4500 target budget under50% gross cap. At the10:00 attempt, OTHER has a09:00 mark1 and09:45 mark20, both available. With only the latest mark, OTHER value20000 already exceeds50% exposure and the target buy does not fill. Adding the older observation (either input ordering) makes gross_now1000/equity11000 and allows400 target shares to fill. Two contradictory marks at the exact same timestamp are likewise input-order dependent instead of being refused.

Use one consistent causal mark-selection/validation contract for decision, execution and performance valuation: compare aware instants, choose the latest eligible observation, reject conflicting values at the latest timestamp, normalize equivalent numeric spelling and make input order irrelevant. Bind the selected mark's provenance/observation/availability in the risk recheck evidence. Do not weaken freshness or treat missing/conflicting marks as zero. Regression controls: latest-only vs old+latest vs reversed, both orders of same-time conflicts (atomic refusal), equivalent numeric duplicate marks, and a genuinely missing/stale/future-only held mark. Preserve normal valid current-risk execution.

## Remaining P1-2: backdated execute can cancel before the ledger chronology check

The new chronology guard covers `decide` and `performance`, but not pre-ledger mutation branches in `execute`. Independent fixture: apply a100-share partial fill atMarch19 11:00, then supply a structurally valid earlier attempt at10:00 with contemporaneous price100 and an explicit valid upper band200. The early affordability path values the11:00 holdings and cancels the intent/releases its reservation at10:00. A normal fill would reach the ledger's out-of-order guard; cancellation does not.

Enforce the policy layer's chronology before every state-changing execute branch, including zero-affordability cancellation and expiry; do not rely on the eventual ledger call. Track the relevant policy event clock as well as consumed ledger time so non-ledger cancellation/expiry/decisions cannot subsequently be followed by earlier state-changing events. Invalid/earlier events may append a refusal audit record but must preserve economic intent/reservation/cooldown state. Same-instant deterministic ordering stays supported. Test the exact backdated cancellation, backdated affordable attempt, expiry/cancellation clock followed by an earlier attempt/decision, and valid chronological and same-instant controls. Keep cancelled/expired/partial semantics explicit; do not manufacture cash or roll back frozen ledger state.

## Next instructions to Claude

Continue SAME M4-02B-RISK-EXIT-20260912 task in its original exclusive write scope. Preserve delivery_02 byte-for-byte before replacement. Reproduce the saved additional cases, fix these two contract gaps across the related paths, retain all29 regressions and the original5 independent expectations, and replay Codex checks only into your own evidence. Update correction matrix/contract/hand expectations, run guarded final suites and preservation checks, write the complete manifest LAST, and report ready_for_review with hashes then stop. Both frozen modules, Codex evidence, historical data and automation remain untouched; no M4-03/M5 or other agents.
