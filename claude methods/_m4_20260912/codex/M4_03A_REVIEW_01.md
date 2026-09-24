# M4-03A Codex 独立审查 01

结论：资格矩阵的主体结论和静态验证通过，但下一步方案尚不可执行，整体为 changes_required。不启动 M4-03B。请在原 M4-03A 独占目录内修订方案及必要验证，保留当前交付，然后再次停止等待复核。无需修改已冻结的执行、账本或风险代码。

交付清单 SHA-256：0b680bd58521dd1a7f00b9d24af4bac90f6da368f8e3221b564743b0bc33f41c。
验证器 SHA-256：1fc04da48b86ac0e7c2c847c54f4114c9888e44d31e1b724f0b5eab6eb2ce0d4。

Codex将原验证器输出重定向到自身目录后执行：24个输入pin、12条资格要求、65处源码定位、元数据汇总、9项内核合成检查、5项分类检查均通过；5种守卫探针被阻止，验证期间拒绝0次。11项交付、40项来源、三份冻结49/74/82项、316原跟踪文件、42旧冻结项、16生产文件位置均保全。数据库连接0次。原生Claude界面明确ready_for_review及Stopping here。

证据：`qualification_review_01/verification.json`、`replay_receipt.json`、`evidence/validation_receipt.json`、`independent_proposal_probes_02.json`；运行器为`review_qualification_01.py`、`probe_qualification_proposal_02.py`。后者只使用既有Codex合成输入及冻结引擎，不读取历史价格。

## 阻断项

### P1-1：开盘交易使用当日未来收盘状态

`claude methods/_m4_20260912/claude_03a/NEXT_READ_PROPOSAL.md` 第57行指定TradabilityEvidence.limit_state由close(D+1)对照假设价格带得出，却标记D+1 09:25可得并在09:30执行。这是未来信息依赖，假设标签不能使它因果有效。

独立反例保持所有开盘输入相同，仅令未来收盘为10或11，从方案得到none或limit_up；冻结内核买单结果由filled变为unfilled。不是冻结内核缺陷，而是映射提供了错误时点状态。

修订：开盘状态只能由已声明的开盘价假设与此前可用价格带推导，或以明确未知/假设状态处理。后续high/low/close/volume只能参与其可用时点后的决定或单独事后诊断。增加未来OHLCV后缀改变而开盘意图、预算、状态、成交不变的合成映射检查。已知除权日的“position window contains ex-date”排除也应明确是事后绩效标记，不能倒过来删除此前决定或改变账本；若用来阻止交易，必须声明实际或假设可用时点并验证因果性。

### P1-2：价格时间和STRICT/ASSUMED两种路径尚未定义为可运行契约

方案§4只定义价格kind和assumption_ref，§7又要求任何available_at不得早于该日线自身收盘；这与使用当日09:30开盘价执行冲突。冻结风险层`m4_risk.py:639`会在调用内核前拒绝任何晚于执行时点的price.available_at，即使kind=predeclared_assumption。现有验证器只证明直接内核接受该假设，不能证明完整风险→账本→内核路径。

Codex合成完整路径实测：价格available_at保留2026采集时刻时返回future_evidence；其余条件相同，只在独立模型输入中显式假设available_at=当日09:30时正常filled。原始采集时间和模型假设时间必须分字段保存，不能覆盖真实来源。内核的open价假设和风险层输入时间要求应同时满足。

修订：逐字段明确raw observed/captured时间、model observed/available时间和假设ID；原始来源不可变，模型记录必须整体标明assumed及所有假设。收盘字段使用收盘后，开盘字段只能使用明确假设的开盘时点，不写不可能的统一“不得早于整根日线收盘”要求。STRICT路径若沿用真实采集时间，可能先在日历/信号可用性被拒绝，根本没有意图；不得先注入假设制造STRICT意图再只清空capacity，把它称为严格历史完整链路。分别定义证据资格拒绝与仅移除容量的合成敏感性检查，记录实际拒绝原因，不预写所有严格结果都为capacity_unproven。

增加仅合成的完整policy→ledger→kernel→exit烟雾验证，证明映射的假设记录可运行且严格路径不会被假设抬升；这属于本步方案验证，不授权历史读取。

### P2-3：所谓full_fill容量与参与率不一致

方案§4的参数和第58行规定capacity.quantity=order_quantity，同时max_participation_rate=0.10。冻结内核实际allowance=floor(quantity×rate)。独立实测100股/400股订单分别仅允许10/40股，均capacity_below_minimum_lot，不是所谓full_fill。

修订：选择并固定一个数学上自洽、与当日全日成交量无关的显式容量假设；可保留部分成交模型并如实命名，也可明确定义固定外生容量和参与率，但不得根据真实运行结果反复改参数。给出手算100/400股样本，并说明同一容量ID的累计消耗。此处是方案内部一致性问题，不要求证明现实成交量。

## 保留结论与交付方式

保留现有378日、17402股价行、152停牌键及“严格历史非零基线不可证明”的主体资格结论；不得改变M3或strict_pit/training状态。现有旧版本全部保存在自己的superseded目录；只修改claude_03a内的方案、验证脚本、相关报告及新回执。增加CORRECTION_MATRIX，逐项给出原失败、修订和验证结果；清单最后写入，停止ready_for_review。

Codex探针初版中的完整风险正向控制因其自设max_gap=0.5产生带外限价；第二版改为方案原定0.02，正向控制filled，反例仍future_evidence。两版都保留，此项夹具修正不是Claude缺陷。验证器本身无失败；问题是方案没有经过完整链路和因果映射验证。

## Instructions to Claude

Revise M4-03A only. Preserve delivery_01 first. Fix the three proposal issues above and run small synthetic mapping and full-chain checks without SQL or network. Keep all accepted modules and historical evidence frozen. Write the correction matrix and manifest last, then stop for Codex review. Do not start M4-03B or M5.

