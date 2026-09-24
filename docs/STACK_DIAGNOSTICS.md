# 无服务依赖的运行诊断

`scripts/check_stack.ps1` 是只读检查入口，不需要 FastAPI、行情客户端或 worker 已启动。

```powershell
.\scripts\check_stack.ps1 -SaveReport
# 或仅输出、不保存诊断文件：
.\scripts\ensure_stack.ps1 -CheckOnly
```

PowerShell `-File` / Python CLI 退出码：0 表示全部检查合格，2 表示需处理；脚本启动异常为其他非零值。`-SaveReport` 仅原子替换 `logs/stack_diagnostics.json`。底层 Python 的 `--output` 只接受这个诊断文件位置，不能指向数据库或历史证据。

检查分为三层：

- 运行：固定数字 loopback 的 `/health`、`/readyz` 和前端 GET；不跟随 HTTP 重定向。PID 必须同时符合创建时间、可执行路径、完整命令行和命令标记。诊断输出不包含命令行或原始异常正文。
- 执行：worker 心跳与保存的 runtime PID 一致，且进程身份成立，才评价运行状态。失败、未知状态、未来时间、陈旧时间、PID 不符分别报告；旧 completed 心跳不能证明当前进程存活。明确停用的 Codex worker 单列 disabled。
- 行情：SQLite 使用 `mode=ro` 与 `query_only=ON`，不导入 app、不初始化 schema。非法日期和未来日期单独计数；比较预期日期行数与最近 45 个自然日的最高 ready 行数，避免单个新日期掩盖缺失横截面。

持久监督任务存在时，复用 `control_plane_task.ps1 -Action Status` 的任务定义、用户身份、触发器和最近运行检查。任务存在本身不算正常。此诊断不安装、启动或删除任务。

日历与覆盖率的限制：当前独立诊断不请求外部交易日历，因此明确返回 `weekday_proxy` 和 `calendar_verified=false`；工作日代理不是交易所日历。15:15 前排除当天、周末退回前一工作日，但节假日仍需有来源且覆盖该区间的交易日历才能认证。横截面比值是近期峰值代理，不是历史当时股票总体完整率。即使行情看起来齐全，缺日历资格时仍返回 `calendar_unverified`，不会宣称全面健康。

应用内 `DataFreshnessDiagnosticsService` 同时修正了空缓存误报：没有任何合法 ready 日线时返回 `refresh_recommended`。全局和候选日期聚合排除非法/非规范日期、无效日历日与未来日期。其现有 `max_lag_days` 仍是自然日参数，本次没有悄悄改成交易日。

## 重启与写入边界

`ensure_stack.ps1` 不带 `-CheckOnly` 时仍保留原有受跟踪 stop/start 行为。它不是只读命令；`run_stack.ps1` 默认启动多个写入生产 SQLite 的后台任务：

| 组件 | 已确认的影响 |
| --- | --- |
| 后端 lifespan | `SQLiteStore.init()`，可能创建/迁移 schema |
| adaptive control worker | 舆情持久化、行情刷新、决策与预测记录；full 阶段还可进入受控模拟任务链 |
| reference-data worker | 参考数据与相应刷新记录 |
| full-market-feature worker | `full-market-scan/run?persist=true`，候选/特征记录 |
| market-history-refresh worker | 日线刷新、缺口恢复、候选扫描持久化；不是只启动一个空进程 |
| capital-flow worker | 供应商资金流数据；不等于用户账户资金，但仍有数据写入 |
| instrument-catalog worker | `apply=True` 的股票目录与 manifest 更新 |
| full-market-calibration worker | 研究校准结果持久化 |
| 两个 Codex worker | 默认开启模型调用和审计记录；恢复范围未包含它们时应显式关闭 |

受控恢复应先界定需要恢复的 worker、数据库与 manifest 位置、日期/证券范围、来源回退规则以及停止条件；保存可恢复备份与前后表级核对。保留现有实盘禁用检查，不修改原冻结研究材料，不把休市期间数据源失败当作必须重启整栈的理由。

本次交付是诊断与新鲜度防误报增量，不是自动恢复上线或行情补齐验收。下一增量应把最小运行组合从全量 worker 启动中拆出，经过临时数据库和故障注入验证后，再恢复明确范围的生产任务。
