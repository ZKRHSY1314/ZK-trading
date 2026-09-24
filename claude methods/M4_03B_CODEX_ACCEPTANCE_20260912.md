# M4-03B 开发区间假设重放技术验收

结论：Claude delivery_02 经 Codex 独立复核通过，M4-03B 的限定工程任务已完成。真实历史执行资格仍不通过；`M4_complete=false`、`strict_pit=false`、`training_eligible=false`。此处的 validated 是技术验收，未代填用户 accepted。

验收清单 SHA-256：`3d557dd4edf805730d99a57e847fbf4450d031b169ac8a543a749fdb03cfff1f`。原生 Claude 窗口已显示 ready_for_review、Stopping here，随后确认 Idle、空输入框、Send 禁用。无在途派单，Codex未改写Claude实现。

## 实测与两项修正

17项交付合成测试全部通过；26项Codex独立检查全部通过；另30项导出修补与保全检查全部通过。三类检查分别落在 `_m4_20260912/codex/replay_review_02/` 的 `delivered_tests.json`、`independent_checks.json`、`export_repair_checks.json`。复验代码为同级目录外的 `review_replay_02.py`、`probe_replay_02.py`、`verify_export_repair_02.py`。这些脚本有固定输出位置，重跑须改用新目录，不能覆盖冻结证据。

- 自定义初始现金现保存于Replay实例并用于绩效分母。独立10万元无交易样本终值10万元、收益0，关闭原先误报−90%的反例。新增5万元买卖手算：买200股@10.02，支出2010.04；卖200股@9.48，净收入1888.44；终值49878.40、损益−121.60、收益−0.002432。历史原运行初始现金100万元，不受原分母错误影响。
- 四分支最终绩效均补齐基准起止点symbol/date/raw_sha256/point_index/captured_at；模型时刻、默认listed假设、原始基准拒绝原因分开保留。来源严格取自原始首末decision记录。缺失或冲突来源分别构造负例，均拒绝修补。
- 原运行17个文件与Codex第一轮快照逐字节一致。修补后四个分支的4216条研究记录中，只有各分支最后一个绩效wrapper的元数据改变；4216条嵌套engine_record全部不变，三分支2700条账本流水及raw空账本的压缩文件逐字节不变。旧数字、成交、费用、现金、FIFO、损益、风险状态和期末未执行意图均保留。
- Codex从原始字节独立调用纯修补函数两次，逐分支结果与交付修补输出完全一致。这是导出修补的重复验证，不是新执行两轮历史回测。

## 历史输入与实测结果

原运行 `claude_03b/runs/829d42809e978c04/` 于2026-09-12 14:24:33至14:45:18 UTC执行，采用任务指定的两份候选库，各一次`mode=ro&immutable=1`连接、query_only及白名单authorizer，Q1–Q9共12次显式查询；价格、来源、覆盖、停牌均以2025-03-31为上界。原读取回执、原源代码和两轮确定性证据保留。修正轮和Codex两次复核均没有新增SQL连接或重跑历史runner。未访问留出期价格。

每库27900价格行；28100覆盖键、200停牌行；52证券；开发期2023-09-04至2025-03-31共378交易日。两镜像数值摘要与既有冻结审计匹配。固定250日特征预热窗口内，33只股票有250根、12只无预热，另5只部分覆盖；48条更早价格只核对，不参与特征。两库同源同花顺，不代表独立行情佐证。

| 固定分支 | 买入有成交次数 | 卖出有成交次数 | 假设期末现金 | 假设期末权益 | 收益率 | 已实现损益 |
|---|---:|---:|---:|---:|---:|---:|
| full_fill | 392 | 382 | 518773.97 | 954371.97 | −4.5628% | −43144.69 |
| fixed_5000 | 439（含152次部分成交） | 429 | 650809.74 | 1050431.74 | +5.0432% | +53973.69 |
| capacity_none | 0 | 0 | 1000000.00 | 1000000.00 | 0 | 0 |
| raw | 0 | 0 | 1000000.00 | 1000000.00 | 0 | 0 |

以上按交付逐笔流水独立重算费用、现金、FIFO成本、T+1、累计容量与期末权益。SH000300两个端点3848.95和3887.31，条件基准收益+0.9966%；raw基准因未来可用时间被拒绝，收益为空。full_fill与fixed_5000不是收益优选；全部事前声明的分支保留。

全局每日09:30先卖后买，随后16:00决定；其他持仓开盘估值只用前已知收盘，全部导出事件顺序和前收盘来源已核对。未来OHLCV控制由合成测试覆盖。两非零分支期末均10个持仓，分别2/3个下一日待执行意图；capacity_none有1个待执行意图；没有强行平仓、伪造到期或读取2025-04-01价格。

raw保留2026采集可用时间，拒绝17402个mark、378个benchmark、959个signal的future_evidence，产生0意图、0账本事件。959个B0信号仅是不可用的事后诊断。假设分支并不证明历史当时可用、ST/价格带、费率、公司行动、容量或退市处理的真实有效性。固定2026证券池存在幸存者选择偏差。内核中的synthetic标记沿用冻结风险链实现；真实来源与assumed口径由外层证据明确区分，不能将它当作真实执行资格。

## 保全和后续

64/64交付文件、33/33消费来源当前哈希匹配；四份旧冻结分别49/74/82/49项，316原tracked、42历史immutable、16生产文件位置均保全。候选库hash/size/mtime及无sidecar状态不变。`git diff --check`通过（仅已有换行格式提示）；没有暂存、提交、推送、生产服务接入或训练。最终代码和证据以`development_replay_freeze.json`为准，原失败回执与交付01永远保留。

下一小步由Codex完成M4六项原始要求总验收和限制回执，不再增加Claude实现任务。具体结论见`M4_FINAL_ACCEPTANCE_20260912.md`。不得把本技术验收升级为M4研究目标达标。

## Next instructions to Claude

Keep the accepted delivery and every original/revised run unchanged. Remain stopped while Codex completes the M4 requirement reconciliation. Do not reconnect SQLite, rerun historical data, alter assumptions, start M5 or training, or create another task without a new bounded instruction.
