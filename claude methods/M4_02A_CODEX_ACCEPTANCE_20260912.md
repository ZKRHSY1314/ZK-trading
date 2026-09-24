# M4-02A 组合账本技术验收

结论：Claude delivery_03 通过 Codex 独立技术验收，可进入 M4-02B 的纯合成风险、退出及基准小步。M4 整体尚未完成；本验收不代表真实历史数据或策略有效性通过。

最终账本 `backend/app/research/m4_portfolio.py` SHA-256：`2b3eec837e4c3603661371fb94e8d942f45c9bfadbf018fc5d6ebee6fadb5360`。
测试 `backend/tests/test_m4_portfolio.py` SHA-256：`8d15f54411c628e859002bc3f3de383b7de79e860f852189c3d40a3e89f6e8e6`。
交付清单 SHA-256：`038f55b16abcc1eb96cb93228374aaa8c30c3bb9125594b60b6cb113314ef606`。
账本策略哈希：`633f78d987141b0e3dccad5d8e711b241a2eaf58b2a8dbe65e57603b5624d6f6`。

## 实际复核结果

- 42 项交付测试通过；隔离文件加载，无 app/conftest、SQL、网络或生产写入。
- 10 项 Codex 独立检查通过：手算完整往返、跨证券 T+1、拒绝原子性、返回视图隔离、原订单条款约束；原日历与修改收盘时间的两项到期反例；正常窗口内重试、追加无关会话、修改未消费后缀三项正向检查。原先失败的全部反例均保留，未改预期以适配实现。
- 手算现金 10000 → 买入100股@10 → 下一合法会话卖出100股@11，最终现金10089.43、已实现盈亏89.43、持仓0。费用为明确假设；不是现实收费依据。
- 多批次 FIFO、部分成交费用、累计股数/金额容量、幂等、异常账本一致性与前缀不变性由交付测试及逐事件记录覆盖。
- 独立核验57项交付文件、31项来源、49项M4-01冻结项、316项原跟踪文件、42项历史冻结项、16项生产文件位置，全部符合基线。没有连接数据库。

原生 Claude 会话已明确停止并报告 ready_for_review；Codex 随后只读复验。此次 Codex 没有修改 Claude 账本或测试源码。两轮问题及旧交付保留在 `codex/portfolio_review_01/`、`portfolio_review_02/` 和 Claude superseded 目录。最终证据在 `codex/portfolio_review_03/`，运行入口为同级 `probe_portfolio_03.py`、`probe_portfolio_calendar_03.py`、`probe_portfolio_suffix_03.py`、`run_portfolio_delivery_03.py`、`verify_portfolio_delivery_03.py`。

## 修复与验收范围

跨证券库存泄漏已改为目标证券库存加共享现金；失败事件先在副本计算再单点提交；公开读结果深拷贝；订单绑定首次登记的决定、条款、已消费日历前缀和实际到期时刻。改变日历收盘时间不能延长原订单；不影响已消费事实的未来后缀允许变化。

少量历史文档仍描述旧的 kernel `order_expired` 原因码；最终后续到期重试先由账本返回 `order_window_expired`。以最终代码、最新 CONTRACT 和测试为准，这是非阻断说明，无须重开冻结内核。

本阶段没有估值、仓位规模、最大暴露、止损/退出/冷却、基准或退市策略；没有历史成交证据、真实账户或客户端访问。每次部分成交独立收取最低佣金，初始批次成本为显式声明。M3仍为0/50双审正例、32争议，strict_pit=false、training_eligible=false；不启动M5。

最终可复验版本由 `_m4_20260912/portfolio_freeze.json` 固定。技术验收状态为 validated，用户最终接受状态不代填。

## Next instructions to Claude

Proceed only on the new bounded M4-02B task supplied by Codex. Keep both accepted M4-01 and M4-02A freezes read-only; implement synthetic deterministic sizing/risk, exit/cooldown, benchmark and delisting handling with explicit causal evidence. Stop for independent review before historical access or any later stage.
