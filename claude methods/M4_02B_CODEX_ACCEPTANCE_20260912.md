# M4-02B 风险与退出技术验收

结论：Claude delivery_03 通过 Codex 独立技术验收，允许进入 M4-03A 历史数据资格静态审查。M4 整体仍未完成，本结论只覆盖合成输入下的确定性风险、退出、冷却、估值及基准链路。

最终源码 `backend/app/research/m4_risk.py` SHA-256：`faec444ee98ed6ee8c20da217a6cb29ced53d7de2ceae1e2198b1cbc73b665f2`。
测试 SHA-256：`bb1d3fd84260b3c56ce392eb07c3bda2dd2d8e43c85999a840988c9d2fb99596`。
交付清单 SHA-256：`9687d18fe2ace63e934286e8ad917903b42ab4083e789996478e6cb43371c5be`。
风险策略哈希：`013f1580f9b6c08092281202f012a567a8f2c743815345c505afe8ebd220ffdf`。

## 实际验证

- 隔离重放全部36项交付测试，0失败、0错误、0跳过；没有导入app/conftest，没有SQL或网络访问，守卫拒绝数0。
- Codex原始5项、追加6项及完整往返1项，共12项独立检查全部通过。旧失败样本和原预期保留；唯一接口适配为原10:00连续交易样本显式指定entry_phase=continuous。
- 独立手算：初始现金10000，买入400股@10，含假设费用支出4005.04；后续收盘价9触发止损，下一合法交易日以8.90卖出400股，净收入3553.18；最终现金9548.14、已实现盈亏-451.86、持仓0。退出当日再买被cooldown_active拒绝。组合收益-4.5186%，合成基准100至98，收益-2%。现金、持仓、成本及容量逐项勾稽一致。
- 63项交付文件、31项已读取来源、49项执行内核冻结项、74项账本冻结项、316项原跟踪文件、42项历史冻结项、16项生产文件位置均通过保全核验；数据库连接0次。

最终证据目录：`claude methods/_m4_20260912/codex/risk_review_03/`。其中results.json为原始5项，additional_results.json为追加6项，independent_roundtrip.json为完整链路，delivery_suite_receipt.json和delivery_verification.json为重放及保全回执。运行代码位于同级probe_risk_03.py、probe_risk_additional_03.py、probe_risk_roundtrip_03.py、run_risk_delivery_03.py、verify_risk_delivery_03.py。冻结后复跑须另用新输出目录，不覆盖既有证据。

## 已关闭问题与限制

第一轮发现的部分成交累计预算超限、未来证据触发取消、执行上下文延长到期、倒序决定读取未来库存，第二轮发现的旧估值优先/同刻冲突依赖输入顺序及倒序执行先取消后检查，均有最终回归证据。现按真实时间点选择最新可用估值，同刻不同值拒绝；决定、执行、取消先验证统一事件时钟，再进行状态变更。

原生Claude界面已明确停止并报告delivery_03。Codex只读复验，没有修改Claude源码或测试。两轮失败与旧交付在Codex历史审查目录及Claude superseded目录保留。

费用和成交容量是明确合成假设，不是历史市场收费或开盘可成交证明。无状态行时的listed默认只适用于本阶段已声明的合成证券池，不能解释为真实历史上市/ST/退市资格通过。performance是受账本时间约束的只读视图；实际状态变更采用政策事件时钟。直接绕过风险引擎写账本不属于本阶段工作流。

尚未完成真实历史输入资格、历史非零基线或策略有效性证明。冻结M3仍为双审正例0/50、32争议，M3_complete=false、strict_pit=false、training_eligible=false。实盘关闭，保持review_only=true，不启动M5或训练。

最终版本由`claude methods/_m4_20260912/risk_freeze.json`固定；状态为technically_validated，用户最终accepted不代填。

## Next instructions to Claude

Proceed only with M4-03A historical qualification under the separate hash-bound task. Keep all accepted M4 modules and M2/M3 evidence immutable. Produce a source-backed capability matrix and a concrete bounded development-read proposal; do not execute historical trades or infer missing execution evidence. Stop for Codex review.
