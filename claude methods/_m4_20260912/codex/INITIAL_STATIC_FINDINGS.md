# M4 启动静态检查（非运行验收）

2026-09-12，Codex；所有结论来自源码阅读，未实例化旧引擎或连接数据库。

- backend/app/backtest/engine.py:45–47 构造时建立 SQLiteStore 并调用 init；即使 run(persist=False) 也不能防止构造阶段影响。新内核必须纯输入，无settings/服务/数据库依赖。
- engine.py:229 调用 _positions_value 当前日估值分配次日开盘买入预算；engine.py:666–674 读取同日 close；按开盘执行解释存在未来值依赖。源码路径确定，改变close的影响尚需受控复现。
- execution.py:59–64 按完整日线low/high判一字板，76起用当日完整amount或 high/low/close×volume容量；这些字段不能在当日open时被当成已观察值。旧模型还隐含手数×100，不能直接套用M2已有明确股数口径。
- engine.py:243–249 先追加交易记录再判断 total_cost > cash，需验证是否会留下无资金/持仓对应的“成交”；现阶段为可复现风险而非已运行事实。
- engine.py:661–664 与 ledger.py:77附近使用自然日差，不能直接代表注入交易日历中的持有/结算/冷却时长。
- tests/conftest.py 导入 app.main、settings/SQLiteStore 并配置临时数据库；本阶段独立unittest应避免加载这些全局服务。

后续修复不能通过调低样本门槛或制造当时不可得信息来满足非零成交。先用明确合成证据建立可检验执行契约，旧引擎保留作后续差异分析。
