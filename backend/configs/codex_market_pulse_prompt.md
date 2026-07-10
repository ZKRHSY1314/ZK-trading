# Codex Market Pulse capture

只执行网络研究，不修改任何文件，不控制桌面软件，不接触券商、账户、凭据、资金或真实订单。

搜索截至当前时间最新的 A 股相关证据：

1. 最近 6 小时的市场行情、资金风向、行业或主题板块变化。
2. 最近 72 小时的国务院、证监会、央行、发改委、财政部、沪深北交易所政策或监管信息。
3. 证券时报、东方财富、新浪财经等市场媒体的最新报道，但同一事件避免重复转载。

要求：

- 官方来源优先；市场方向至少尝试两家独立来源交叉验证。
- 只保留能直接打开的原始文章或官方页面 URL，不使用搜索结果页 URL。
- 明确发布时间；找不到发布时间时设置 `published_at_status=unknown` 且 `published_at=null`。
- 每条写 1 至 3 句事实摘要和可核验 claims，不预测个股收益，不生成买卖指令。
- `sector_hints` 只使用与证据直接相关的板块名称或以下稳定标识：`ai_compute`、`digital_economy`、`brokerage_finance`、`state_owned_reform`、`new_energy`、`low_altitude`、`medicine`、`consumer`、`infrastructure`、`defense`。
- 输出 8 至 20 条高质量证据。严格按提供的 JSON schema 输出，不要添加 Markdown。
