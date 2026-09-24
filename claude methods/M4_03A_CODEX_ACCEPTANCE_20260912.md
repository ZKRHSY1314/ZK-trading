# M4-03A 历史输入资格技术验收

结论：delivery_02通过静态资格及重放方案技术验收，可以进入固定来源、固定开发区间的M4-03B只读假设重放。当前没有真实历史交易被验证，M4原要求中的“合格历史数据非零基线”仍未满足。

最终交付清单SHA-256：5166dec377d61f86d20b87dae264bd8c037e3a629dd2204c10a52747d6640df1。
资格文件SHA-256：0902992ff4a375ee8bb9d099e6071d476883d40bc6dc544a84a355a5fed0ae1b。
映射代码SHA-256：276cb037575f8d05a313b3266ecad46008e015d17c99ca98786c403d0c3e70de。
验证器SHA-256：d29989a5bdaabff6ce0a42d6114664bdb3a903181e93f97a3db263068f5c62a5。
下一步方案SHA-256：b7c9c3346341ba38b597c36d18f80f34ed0ab532168ea45d22283555731b5203。

## 复核证据

Codex在自己的输出目录重放未经修改的验证函数，仅调整HERE/EVIDENCE/ALLOWED_WRITE_ROOT，未覆盖Claude证据：24个输入pin、12条要求、65处代码定位、元数据统计、9项内核合成检查、5项分类检查及10项映射/完整链路检查全部通过。五种守卫自检均阻止操作，实际验证期间拒绝0次，未导入app/conftest。

额外6项Codex独立样本通过：独立手算往返；原始时间与模型时间分开保留；原始采集时间的信号不产生意图；100/400股容量数学；未来OHLCV不能进入开盘映射。独立手算初始10000，买400股@10.02支出4014.08，现金5985.92；收盘9.4触发止损，下一合法日卖400股@9.38，净收入3742.92，最终现金9728.84、盈亏-271.16、持仓0，冷却拒绝及账本勾稽通过。费用均为假设样本。

26项交付、47项读取来源、执行/账本/风险冻结49/74/82项、316项原跟踪文件、42项旧冻结项、16项生产文件位置全部保全。原生Claude最终消息明确Stopping here。Codex没有修改其代码，数据库连接0次。冻结日历的日期格式归一后，2022-08-24至2023-09-01恰为开发首日前250个交易日。

最终证据位于`claude methods/_m4_20260912/codex/qualification_review_02/`，重点为verification.json、evidence/validation_receipt.json和independent_mapping_checks_verified.json；运行器为review_qualification_02.py及probe_qualification_mapping_verified.py。Codex早期容量夹具有位置参数顺序、calendar_ref未绑定映射后来源两项自身错误，初始回执保留，最终按真实契约修正后通过，不归因于Claude。旧失败方案保留在qualification_review_01及Claude superseded/delivery_01。

## 修复与结论边界

开盘涨跌停状态改为开盘价与前收盘假设价格带推导；未来收盘、高低价及成交量只进入事后诊断或随后合法决定。原始2026采集时间保留，模型开盘时间09:30及收盘可用时间16:00分别明确为假设。严格原始路径在证据可用性处拒绝；移除容量只作为假设链路敏感性，不冒称严格历史路径。容量采用事前固定的full_fill、fixed_5000及none，参与率1.0，不读取全日成交量制造开盘容量。已知除权日只作事后绩效标记，不回删决定。

12项资格为4项字段存在、3项仅可假设、5项缺失；对应378开发日、17402股票价格行及152确认停牌键。上述数字来自既有冻结审计，本步没有重读价格行。历史ST/真实价格带、公司行动完整性、退市终值、阶段成交容量、带有效期的官方费率等仍缺证据；2026采集也不能证明2023—2025系统当时可用。两库同源同花顺，不是独立来源佐证。

M3仍为双审正例0/50、32争议，M3_complete=false、strict_pit=false、training_eligible=false。M4_complete=false，实盘关闭。M4-03B可证明假设条件下的引擎行为与数据关联，不能补齐上述历史证据。正式读取范围和保护要求由单独M4-03B任务书固定；本验收不授权其他来源或留出期读取。

冻结文件：`claude methods/_m4_20260912/historical_qualification_freeze.json`。状态为technically_validated，用户accepted不代填。

## Next instructions to Claude

Proceed only under the separate M4-03B bounded task. Read the two pinned candidate stores in read-only immutable mode, reconcile the fixed development slice, run the predeclared assumed baseline and sensitivities, preserve raw provenance and strict refusals, then stop for Codex acceptance. Do not change freezes, access holdout price rows, tune outcomes, start M5 or training.
