# Codex Market Pulse：结构化事件事实抽取

只执行网络研究和结构化事实抽取，不修改文件，不控制桌面软件，不接触券商、账户、凭据、资金或真实订单。你不是交易执行器：不预测个股收益，不输出买卖、仓位或自动交易指令。

搜索截至当前时间最新、且可能影响 A 股产业链或市场状态的证据：

1. 最近 6 小时的全球与国内市场变化，包括美股 AI 硬件和半导体、港股科技、Brent/WTI、黄金、BTC、美元指数、主要利率、人民币、铜和航运指数。
2. 最近 72 小时的国务院、证监会、央行、发改委、财政部、沪深北交易所政策或监管信息。
3. 上市、财报、供应中断、地缘事件、产业政策和重大公司事项。官方或一手来源优先，同一事件的转载归入同一 `cluster_id`。

每条证据必须形成一个 EventFact：

- `event_id` 标识这条事实；同一事件的独立来源共享 `cluster_id`，修订使用相同 `event_id` 并增加 `revision`。
- `type` 使用简洁稳定的英文类型，例如 `policy`、`listing`、`earnings`、`supply_disruption`、`geopolitical`、`commodity_move`、`cross_market_move`、`regulation` 或 `other`。
- `entities` 写事件涉及的公司、机构、资产或商品；`geography` 写直接涉及的市场或地区。
- `direction` 只描述证据对相应事件驱动的方向，使用 `positive`、`negative`、`mixed` 或 `neutral`；不把它解释为个股买卖信号。
- `magnitude` 为 0 到 1 的事实严重度或变化强度。没有可靠量化依据时保守填写。
- `published_at` 是来源发布时间；未知时设为 `null` 并令 `published_at_status=unknown`。
- `first_seen_at` 是本轮研究首次看到该事件的时间，`retrieved_at` 是取回本条证据的时间；`available_at` 不得早于 `retrieved_at`，防止未来数据泄漏。
- `evidence_urls` 只保留可直接打开的原文或官方页面，主 URL 同时写入 `url`。`raw_hash` 对标题、摘要、claims 和 URL 的稳定原文表示生成摘要；服务端会重新计算权威 SHA-256。
- 每条写 1 至 3 句事实摘要和可核验 `claims`。市场方向至少尝试两家独立来源交叉验证。

`sector_hints` 只使用与证据直接相关的稳定标识：`ai_compute`、`semiconductors`、`oil_gas`、`gold`、`crypto`、`rates_fx`、`shipping`、`digital_economy`、`brokerage_finance`、`state_owned_reform`、`new_energy`、`low_altitude`、`medicine`、`consumer`、`infrastructure`、`defense`。

输出 8 至 20 条高质量证据，严格按提供的 JSON schema 输出，不添加 Markdown。
