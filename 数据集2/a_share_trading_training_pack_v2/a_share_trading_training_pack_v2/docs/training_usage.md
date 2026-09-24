# 训练使用建议

## 适合做什么

1. 规则识别分类：输入量价/分时/盘口特征，输出 `pattern_id`、`expected_bias`、`action_label`。
2. 候选股解释：为软件候选池输出“为什么入选/为什么风险高”。
3. 模拟盘策略归因：把每笔模拟交易和触发的 pattern_id 绑定，后续统计胜率、盈亏比和回撤。
4. LLM 指令微调：使用 `instruction_tuning_examples.jsonl` 学习安全输出格式。

## 不适合做什么

- 不适合直接训练成实盘自动下单模型。
- 不适合在没有历史回测的情况下扩大仓位。
- 不适合忽略涨跌停、T+1、停牌、手续费、滑点、流动性约束。

## 推荐回测字段

`pattern_id`, `signal_date`, `stock_code`, `entry_price`, `exit_price_1d`, `exit_price_3d`, `exit_price_5d`, `exit_price_10d`, `max_favorable_excursion`, `max_adverse_excursion`, `drawdown`, `turnover_rate`, `volume_ratio`, `limit_status`, `sector_strength`, `benchmark_return`。
