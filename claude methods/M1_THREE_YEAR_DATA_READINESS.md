# M1 三年数据契约与只读就绪度审计报告

> **本文件已于 2026-09-06 转为历史诊断材料，不再是可执行路径。**
> 当前唯一可执行入口是 [`M1_CLOSURE.md`](M1_CLOSURE.md) 与 `_m1_closure/`。
> 本文第 9.6 节的验收指令、`_m1_evidence/backfill_acceptance.sql`、`backfill_acceptance_BEFORE.json`、
> `coverage_05_manifest.py`、`coverage_manifest.csv`、`coverage_gap_shape.csv` **全部作废**
> （已重命名为 `*.SUPERSEDED.*`）。凡本文数字与 `M1_CLOSURE.md` 冲突，以后者为准。
> 已知需以收口件覆盖的三处：日历运行时来源声明（已撤回）、单位污染作用域（已收紧为 293 只科创板）、
> 7.43%/7.46% 的分母解释（NULL 说法错误）。


- 里程碑：M1（read-only 三年数据就绪度审计）
- 状态：`ready_for_review`（待 Codex 独立复核）
- 固定研究窗口：`2023-09-04` .. `2026-09-04`（1,097 个自然日）
- 审计方式：全部连接以 `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` 只读打开；未运行任何 migration、`SQLiteStore.init()`、服务构造器、网络抓取、服务进程或写入。未修改任何受版本控制的文件。
- 证据目录：`D:\codex-A股交易\claude methods\_m1_evidence\`（**557** 个脚本/输出，见第 11 节索引）
- 本报告由 9 个独立只读审计维度 + 对其中重大结论的对抗性复核（adversarial verification）合成。凡复核给出 `adjusted` / `refuted` 的结论，本报告一律采用复核后的数字，并在正文显式标注（汇总见附录 B）。
- **阅读约定**：凡标注 **估算** 的数字，均在同一处注明其推导输入；未标注者为直接 SQL 实测值。本报告**不给出任何历史日期的全市场完整度百分比**——该分母不存在（见第 4 节）。

---

## 0. 置顶修正（完整性复核后，优先于正文任何冲突数字）

> 正文由 9 个审计维度合成后，又经过一轮独立的完整性批判（completeness critique）。批判发现的 5 项 BLOCKING 问题已由主线用只读查询逐条复算确认。**本节数字优先于正文。** 复核脚本：`_m1_evidence/critic_01_calendar_and_inventory.py` .. `critic_12_benchmark.py`；主线复算见 `_m1_evidence/claude_independent_crosscheck.md`。

### C-1【BLOCKING·已确认】交易日历不需要估算，磁盘上就有权威离线日历；正文三个"估算"分母是错的

`backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json`（123 KB，**8,797 个交易日**，1990-12-19..2026-12-31）是 akshare 随包分发的上交所日历，而 `backend/app/data/trading_calendar.py:61` **本来就在调用同一份数据**（`ak.tool_trade_date_hist_sina()`）。读取它零网络。

| 口径 | 正文（估算） | 实测（本日历） | 影响 |
|---|---|---|---|
| 名义窗口 2023-09-04..2026-09-04 | 约 733 | **728** | 覆盖率分母 |
| 头部空档 2023-09-04..2024-04-08 | 约 146 | **141** | G-A 回填量 |
| 全市场空档 2023-09-04..2024-06-21 | 约 196 | **191** | 缺口描述 |
| 爬坡段 2024-04-09..2024-06-21 | 50 | 50 | 一致 |
| 诚实窗口 2024-06-24..2026-09-03 | 536 | 536 | 一致 |
| 2025 全年 | 243 | 243 | 一致 |

后三行完全吻合，证明这份日历与数据本身同源可信。**修正后的覆盖率上限：538/728 = 73.90%，中位 536/728 = 73.63%**（正文写 73.4% / 73.1%）。**G-A 回填行数修正为 5,167 × 141 = 728,547 行**（正文 754,382，高估 3.5%）。第 10 节的 **U1「窗口内真实有多少个交易日」应就此关闭**——它一直是可回答的。

### C-2【BLOCKING·已确认】单位污染不止在 `market_history`，**定价库 `daily_bar_cache` 同样存在**，而正文的检验方法结构上看不到它

正文 A18 把 100 倍 volume 问题限定为「`market_history` 冻结的 tencent 系行」。该结论的检验只用了 `cache.amount` 存在的行，而**全部 tencent cache 行的 `amount` 都是 NULL**——受污染的样本被检验方法本身排除了。

主线独立复算（`daily_bar_cache` 内部按 symbol 做 `LAG`，仅 ready+qfq+volume>0）：

| 度量 | 值 |
|---|---|
| 数据源切换边界 | 6,243 |
| 边界上 volume 骤降 20–500 倍 | **555** |
| 边界上接近 100 倍 | **293** |
| 非边界对 | 2,878,584 |
| 非边界上接近 100 倍 | **19** |
| 近 100 倍边界中 close 波动 ≤ ±11% | **291 / 293**（均值比 1.0061） |

close 正常波动即排除拆股/公司行动，这是**单位切换（股 ↔ 手）**。可疑总体上界：`source LIKE '%tencent%'` 的 **306,543 行 / 4,946 只，100% `amount IS NULL`、306,414 行 `quality_status='ready'`**——正是 `execution.py` 的 `volume × SHARES_PER_HAND × price` 流动性代理所依赖的那批行。

**方向是乐观的**：流动性被放大约 100 倍，回测会成交现实中吃不下的委托。因此 A18 必须由「market_history 冻结行」重新定级为「**两库皆有，含定价库**」，第 9 节的 G-D′（163,174 行 UPDATE）**不是完整修复**。`CHECK(volume_unit IN (...))` 只保证枚举合法，不保证语义正确。

### C-3【BLOCKING·已确认】验收门 G1/G2 的目标值不可达，正确的回填反而会被判失败

`_m1_evidence/backfill_acceptance.sql` 原写 G1「~146 sessions/symbol」、G2「rise toward the ~733 estimate」。真值是 **141 / 728**，完美回填最多只能到 728。**已修正**，并在注释中写明该值为实测而非估算。

### C-4【BLOCKING·已确认】V 系列验收项此前只存在于正文散文里，既无可执行 SQL 也无冻结基线

原 `backfill_acceptance.sql` 只有 G1–G5 与 N1–N10；`backfill_acceptance_BEFORE.json` 只有 A1–A9 九个键。V1/V2/V3/V5/V6/V7 **一条都没有落地**，意味着 A18 修复、OHLC 修复、ERROR 行清理、裸符号清理、vintage 保全在提升后**无法证明生效、也无法证明没破坏**。已补齐：**V1、V2、V3、V5、V5b、V5c、V7**，其中 **V5b 是针对 C-2 新增的定价库单位门**，V7 是 vintage 保全门。

### C-5【BLOCKING·已确认】第 8.4 节的 A2 过滤条件在现有 schema 上不可执行；"746 行 policy 版本全为 NULL"不是一个可测量的陈述

生产库 `forecast_evaluations` 的实际列为：
`id, evaluation_id, as_of, scope, horizon_days, status, sample_count, fold_count, coverage, precision_at_k, spearman_rank_ic, brier_score, metrics_json, review_only, created_at`。

`canonical_policy_version` / `run_kind` / `evidence_quality` **三列全部 ABSENT**，且 746 条 `metrics_json` 解析后只有 `{horizon_days, metrics, scope}` 三个键。所以「全为 NULL」描述的是一个**不存在的列**——正确表述是「**该列尚未存在；生产库未迁移**」（与 M0 结论一致：A1 迁移新增此列，生产库有意保持未迁移）。

**因此 A2 必须显式包含一次 schema 迁移**，否则 §8.4 的过滤无法作用于任何已持久化的行。另外 746 行与 `forecast_decisions` 之间**没有任何关联键**，所以对 evaluations 做血缘/孤儿检查在当前 schema 下不可能——正文的孤儿检查只覆盖了 `forecast_outcomes`。

### C-6【BLOCKING·已确认】§4.3 低估了**本项目已有的**退市证据：快照差分可直接观测到 **5** 个移除事件，不是 2 个

对 `universe_members` 按相邻 `snapshot_date` 差分：

| 区间 | 移除 | 标的 |
|---|---|---|
| 2026-07-15 → 2026-07-16 | 3 | `SH605081`、`SZ000004`、`SZ002808` |
| 2026-07-16 → 2026-07-17 | 1 | `SZ002898` |
| 2026-07-19 → 2026-09-03 | 1 | `BJ920305` |

全部 5 只 `status='inactive'` 的标的都能从快照差分中还原。这不改变「幸存者偏差 UNRESOLVED」的结论（7 个快照日只覆盖窗口最后 53 天），但它是**本项目现有的最强补救证据**，正文把自己的筹码报低了：继续采集快照差分是可行且已被验证的退市登记路径。

### C-7【BLOCKING·已确认·已修复】交付物 `coverage_manifest.csv` 内部使用了正文自己批评的循环分母

契约第 4 条要求的**头号交付物**此前把 `eligible_sessions` 写成 **587**（数据自身足迹），却标注 `eligibility_basis='listing_interval'`。例如 `BJ920000`（list_date 2020-12-23）真值应为 **728**。§11.1 又指示 Codex 优先读这两个 CSV——复核者会拿到 0.913 的产物，而正文写 0.736。两文件还带 UTF-8 BOM，且没有名义窗口列。

**已重新生成**（`coverage_manifest.csv`，5,567 只，无 BOM），分母改为**日历口径**：`eligible_sessions_calendar` = `max(list_date, 2023-09-04)` 到 `min(delist_date, 2026-09-04)` 之间的**真实交易日数**；同时把足迹口径保留为**单独标注**的 `coverage_ratio_observed_spine` 列，并新增 `nominal_window_sessions` / `coverage_ratio_nominal`。

| 口径 | 值 |
|---|---|
| 可计算分母的证券 | **5,543** / 5,567 |
| 日历口径 median / mean | **0.7363 / 0.7485** |
| ≥0.99 / ≥0.95 / ≥0.90 / ≥0.80 | 247 / 269 / 278 / 318 |
| **窗口起点前已上市的 5,167 只：max / median / ≥0.95** | **0.7390 / 0.7363 / 0** |

**必须注意**：≥0.99 的 247 只**全部**是 2024-06-20 之后上市的新股，其 `eligible_sessions` 中位数只有 **248** ——它们分母天然落在数据已覆盖的区间内，高比值是 IPO 造成的假象，不代表历史深度。**唯一可用于横截面研究的口径是 5,167 只那一行：没有任何一只达到 0.95。**

---

## 1. 结论摘要

**诚实回答：不能。以今天磁盘上的数据，无法开展 `2023-09-04..2026-09-04` 的三年研究。可开展的是一个约 2.2 年、且带有 5 项未解决阻断项的缩短窗口研究。**

三条互相独立、任何一条都足以阻断三年结论的事实：

1. **窗口前段完全为空。** 两个 bar 存储的最早 `trade_date` 都是 `2024-04-09`；`2023-09-04..2024-04-08`（218 个自然日）在两库中均为 **0 行**；`< 2023-09-04` 的 warm-up 区同样为 **0 行**。
   `SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date>='2023-09-04' AND trade_date<'2024-04-09' AND length(trade_date)=10;` -> `0`
   `SELECT COUNT(*) FROM daily_bars WHERE trade_date<'2023-09-04';` -> `0`
2. **真正可用于截面研究的起点更晚。** `2024-04-09` 当日全市场只有 **1 只**股票有 bar，`2024-04-19` 只有 10 只；首个 >=4,000 只股票的交易日是 **`2024-06-24`**（4,985–5,032 只，两库一致）。因此全市场空档为 `2023-09-04..2024-06-21`，即 **292 个自然日 / 210 个工作日 / 约 196 个交易日（估算）**。
   —— 此处采用复核修正值：原审计报的「156 工作日 / ~146 交易日」只覆盖到 `2024-04-09`，低估了空档；复核指出 `2024-04-09` 是「单只股票地板」，5,560 只股票中有 4,952 只首个 bar 落在 2024-06。
3. **历史 universe 无法重建，幸存者偏差 UNRESOLVED。** `market_history.instruments` 5,561 行中 `delist_date` 非空者 **0 行**；`universe_snapshots` 仅 12 行、**7 个不同 snapshot_date**，全部落在 `2026-07-14..2026-09-04`（窗口最后 53 天）。两库合计 5,566 只有效证券中，**没有任何一只的价格序列在 2026-01-01 之前终止**。这不是「数据稀疏」，而是「退市证据完全不存在」。因此本报告**不给出任何全市场完整度百分比**。

另外三项直接影响可信度的阻断项：

4. **两个 bar 库对同一 (symbol, trade_date) 的 close 大面积不一致，且不能用 adjustment_mode 解释。** 2,787,696 个共同键中 1,059,740 行（**38.01%**）close 差异 > 0.005，207,831 行（**7.46%**）相对差 > 1%，涉及 3,713 只股票；两侧 `adjustment_mode` 都是 `'qfq'`。
5. **qfq 不是 point-in-time 数据，并且缺口处发生了「拼接」（splice）。** 5,333 只股票存在数据源切换边界；在与 `market_history` 可交叉验证的边界上，**2,096 个边界（35.7%）**出现 >0.5% 的价格水平位移，**636 个 >2%**，**107 个 >5%**。同日期对照组的收益一致性检验决定性地区分了二者：边界样本 43.9% 出现 >0.5pp 的收益分歧，对照组仅 0.8%。
6. **`available_at` 不是可用性时间，是入库时钟。** `market_history.daily_bars` 中 `available_at <> fetched_at` 的行数为 **0**；全表只有 **4 个**采集日；严格 PIT 过滤 `available_at <= as_of` 在 `as_of=2025-09-04` 与 `2026-06-30` 时返回 **0 行**。

7. **`volume_unit` 的取值是被 CHECK 保证「合法」而非「正确」的，且已被证伪。**（本轮复核新增，见 5.1 A18）在 `market_history` 缺 `amount` 而 `daily_bar_cache` 有值的 1,652,094 行中，**163,174 行（9.9%，涉及 576 只证券）** 的 `daily_bars.volume` 恰为 `daily_bar_cache.volume` 的 **100 倍**，而 `volume_unit` 仍声明为 `'hand'`（手）。这些行落入 `engine.py` 的代理成交额公式（`volume × 100 × 典型价`）后，流动性上限被放大约 100 倍（实测代理/真值比：均值 10.15、p99 100.2、max 218.2），**方向为「乐观偏差」**——回测会成交它在现实中根本吃不下的委托。`CHECK(volume_unit IN ('hand','share','unknown'))` 只校验了枚举字面量，从未校验语义。

**上述 7 项的分级判定**：1、2、3、5、6、7 为 **blocking**；4 为 blocking（不可复现性）。第 5 节另列 18 项完整性异常并逐项标注 blocking / field-limiting。

### 1.1 今天可以做什么（可计算子集）

| 项目 | 值 | 依据 |
|---|---|---|
| 名义窗口 | 2023-09-04 .. 2026-09-04，约 733 个交易日（**估算**） | 由实测密度 587/629 = 0.9332 乘以 785 个工作日推得；另一锚点：数据自身完整的 2025 年为 243 个交易日，3x243 = 729。范围 729–733 |
| 实际存在的交易日 | **587** 个（2024-04-09 .. 2026-09-04） | `SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND length(trade_date)=10;` |
| 全市场稠密交易日（固定阈值口径 >=5,000 只） | **536** 个（2024-06-24 .. 2026-09-03） | `SELECT trade_date FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND quality_status='ready' GROUP BY trade_date HAVING COUNT(*)>=5000` |
| **全市场稠密交易日（当日在册口径 >=99%）** | **500** 个（首个为 **2024-08-13**） | 复核修正：固定阈值 5,000 是人为选定的；以「当日 `list_date<=d` 且未退市的在册股票数」为分母，536 天中有 **36 天只有 95.26%–99.0%**（最差 `2024-06-25` = 5,027 / 5,277 = 95.26%；`2024-07-08` = 5,032 / 5,281 = 95.28%）。**非代表性交易日因此是 87 天，不是 51 天** |
| 任一股票的最大历史深度 | 538 根（cache）/ 537 根（market_history）；**>=730 根者 0 只** | `WITH per AS (SELECT symbol,COUNT(*) n FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol) SELECT MAX(n), SUM(n>=730) FROM per;` |
| 名义窗口覆盖上限 | 538/733 = **73.4%**；中位数 536/733 = **73.1%**；达到 80% 者 **0 只** | 复核修正值（原审计以 587 为分母得 91.3%，分母错误） |
| 建议的诚实研究窗口 | **2024-06-24 .. 2026-09-03（536 个交易日，约 2.2 年）**；若采用 >=99% 在册口径则应为 **2024-08-13 起、500 个交易日** | 上表；两种口径都必须在运行清单中显式声明，不得混用 |
| 扣除 120 日特征 warm-up 后的可标注决策日 | **396 天**（2024-12-18 .. 2026-08-06） | `pointintime_10_folds.py`；20 日标签无法结算的尾部为 2026-08-07..2026-09-03 |

### 1.2 判定

- 三年（36 个月）研究：**阻断**。缺口是「从未抓取」，不是「抓取后丢失」——磁盘上 9 个数据库快照（含全部备份）中最早的 `trade_date` 都是 `2024-04-09`。
- 2.2 年（536 个交易日）研究：**技术上可跑，但在第 5、6、7 节列出的阻断项修复前，其结果不可复现、不可比较、不可对外声明**。最小可执行前提是三件**零网络**的事：修 A6（3 行零价，否则引擎抛 `ZeroDivisionError`）、修 A18（163,174 行成交量单位，否则流动性上限失效）、剔除 A8/A9（482 行裸符号 + 1,076 行指数，否则截面分母被污染）。
- 「今天能不能出一个可对外的收益率数字？」——**不能**。即使跑通，该数字建立在 survivor-only universe（第 4 节）、当期视图 qfq（6.2）与含拼接边界的价格序列（6.3）之上；这三项都不是精度问题，而是**符号错误方向已知的系统性偏差**（幸存者与流动性代理都偏乐观）。
- 现有 39 次 `historical_backtest_runs`：**全部作废**。39/39 的 `data_source='daily_bar_cache'`，全部 `trade_count=0`、`final_cash == initial_cash`；且 39 次运行的 `created_at`（2026-06-12..2026-06-29）**早于当前 cache 中每一行 bar 的 `created_at`（最早 2026-06-30 04:55:30）**——它们不可能被今天的数据复现。

---

## 2. 数据源清单与血缘

### 2.1 存储清单（实测）

| 库 / 表 | 行数 | 证券数 | 日期范围 | 关键约束 |
|---|---|---|---|---|
| `trading_local.sqlite3` / `daily_bar_cache` | 2,891,617（有效日期 2,891,616） | 5,567（有效日期 5,566） | 2024-04-09 .. 2026-09-04 | 仅 `UNIQUE(symbol,trade_date)`；**无任何 CHECK**；OHLC 可空 |
| `market_history.sqlite3` / `daily_bars` | 2,787,736 | 5,560 | 2024-04-09 .. 2026-09-03 | `PRIMARY KEY(symbol,trade_date,adjustment_mode)`；CHECK：`adjustment_mode IN ('none','qfq','hfq')`、`volume_unit IN ('hand','share','unknown')`、`high>=low`、`high>=open/close`、`low<=open/close`、价格非负、`length(trade_date)=10` |
| `market_history` / `instruments` | 5,561（SH 2,317 / SZ 2,902 / BJ 342，全部 `asset_type='stock'`） | — | `list_date` 1990-12-19 .. 2026-09-04 | `delist_date` 非空 **0 行**；`status` active 5,556 / inactive 5；`list_date` 为空 18 行 |
| `market_history` / `universe_snapshots` | 12（7 个不同日期） | — | 2026-07-14 .. 2026-09-04 | 全部晚于 bar 数据约两年 |
| `market_history` / `universe_members` | 50,555 | 5,561 | — | — |
| `market_history` / `ingest_runs` | 100（completed 27 / partial 73） | — | 2026-07-15 06:48 .. 2026-09-04 03:44 | `provider` 100/100 = `'trading_local.daily_bar_cache'` |
| `market_history` / `bar_quality_issues` | **0** | — | — | 质量闸门表从未写入 |
| `market_history` / `training_dataset_manifests` | **0** | — | — | 无数据集清单 |
| `trading_local` / `forecast_decisions` | 20,082 | 90 stock + 15 sector | cutoff 2026-07-12 .. 2026-09-04（6 个日历日） | 见第 8 节 |
| `trading_local` / `forecast_outcomes` | 18,682 | — | observed_at 30 个日期 | — |
| `trading_local` / `forecast_evaluations` | 746（`status='ready'` 113） | — | — | 见第 8 节 |
| `trading_local` / `historical_backtest_runs` | 39 | — | 2026-06-12 .. 2026-06-29 | trades 0 / closed_trades 0 / daily_equity 6,915 |
| `trading_local` / `global_market_bars` | 416 | 5（BTC/CL/GC/NVDA/SMH） | 2026-05-22 .. 2026-09-04 | 与 A 股无关；96/416 行来自 `#revision-` 源 |

SQL（逐条，全部只读）：

```sql
SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache;
SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) FROM daily_bars;
SELECT COUNT(*) total, SUM(delist_date IS NOT NULL) has_delist, SUM(list_date IS NULL) null_list FROM instruments;
SELECT COUNT(*), COUNT(DISTINCT snapshot_date), MIN(snapshot_date), MAX(snapshot_date) FROM universe_snapshots;
SELECT provider, COUNT(*) FROM ingest_runs GROUP BY provider;
SELECT COUNT(*) FROM bar_quality_issues;           -- 0
SELECT COUNT(*) FROM training_dataset_manifests;   -- 0
```

### 2.2 血缘：`market_history.daily_bars` 是 `daily_bar_cache` 的派生副本，不是独立数据源

这是本维度最重要的结论，已被对抗性复核 **confirmed 并强化**：

- 唯一写入者是 `backend/scripts/seed_market_history.py`；其取数语句为 `... FROM daily_bar_cache WHERE quality_status='ready' AND adjustment_mode='qfq' AND {TRUSTED_QFQ_SOURCE_SQL}`（seed_market_history.py:1230-1236），插入语句在 :599，并把运行记录写成 `ingest_runs.provider='trading_local.daily_bar_cache'`（:589）。
- 数据侧完全印证：**`market_history` 中不存在任何 cache 没有的 (symbol, trade_date)**（0 行），反向则有 102,711 行（ready+qfq+可信源口径）尚未提升。

```sql
-- market_history 独有键（ATTACH 两库，均 mode=ro）
SELECT COUNT(*) FROM main.daily_bars b
 WHERE NOT EXISTS (SELECT 1 FROM cache.daily_bar_cache c
                    WHERE c.symbol=b.symbol AND c.trade_date=b.trade_date);          -- 0

-- cache 侧未提升（seeder 自身过滤口径）
SELECT COUNT(*) FROM daily_bar_cache c
 WHERE c.adjustment_mode='qfq' AND c.quality_status='ready'
   AND NOT EXISTS (SELECT 1 FROM mh.daily_bars m
                    WHERE m.symbol=c.symbol AND m.trade_date=c.trade_date
                      AND m.adjustment_mode='qfq');                                  -- 102711
```

- 算术闭合（朴素 `c.symbol = b.symbol` 口径）：2,891,617 − 1（`ERROR` 行）− 103,880（cache 独有）= **2,787,736**，与 `daily_bars` 行数**精确相等**。该等式成立本身就是「派生副本」的算术证据；但 103,880 这个中间量含两类误计，见下。

**本轮复核对该项的三处修正（verdict = adjusted，本报告采用复核值）：**

1. **cache 独有行数应为 102,322，不是 103,880。** 朴素 `c.symbol = b.symbol` 连接忽略了符号命名空间分裂：cache 中有 2,891,135 行属前缀符号（SH/SZ/BJ，5,563 只）、**482 行属裸 6 位符号（4 只）**，而 `market_history` 只有前缀符号。这 482 行**全部**已以前缀形式存在于 `market_history`（`SELECT COUNT(*) FROM bare b WHERE EXISTS(SELECT 1 FROM main.daily_bars h WHERE h.symbol IN ('SH'||b.symbol,'SZ'||b.symbol,'BJ'||b.symbol) AND h.trade_date=b.trade_date)` -> **482 / 482**），被误计为缺失。剔除后 103,398；再按本报告规则剔除 1,076 行指数（**指数不得计入股票分母**）得 **102,322**，且全部落在研究窗口内。
2. **缺失机制不是质量筛选，是「每股票最近 N 根」截断。** seeder 自身过滤只解释 93 行 `not_ready` + 1,169 行 `not_qfq` + 0 行 `untrusted_sina`；**102,711 行同时满足 ready 且 qfq 却仍然缺失**，其中 **99,610 行早于 `market_history` 为该符号保留的最早 bar**（涉及 2,671 只），且 **4,688 只符号的 bar 数恰为 536**。即 `ROW_NUMBER() <= bars_per_symbol` 的近期截断，不是筛选。
3. **`hist_only_rows = 0` 是「键级」事实，不能推出「market_history 没有任何 cache 缺少的信息」——该推论已被否证。** 在 2,787,736 个匹配键上，**1,710,969 行（61.4%）与当前 cache 的值不同**：OHLC 不同 1,175,452、close 不同 1,153,127、volume 不同 1,358,073、amount 不同 1,668,962、provider 不同 1,700,666；完全一致者仅 1,076,767（38.6%）。且分歧**方向完全单向**：1,710,969 / 1,710,969 行的 `hist.updated_at` 严格早于 `cache.updated_at`，**更新者 0、相等者 0**。由于 `daily_bar_cache` 只有 `UNIQUE(symbol,trade_date)` 且就地覆盖，每次重抓都销毁上一个 vintage——**`market_history` 是这些被覆盖值的唯一幸存记录**，包括 11,259 行 `provider='tencent.newfqkline.qfq'`（该来源已从 cache 的 `source` 词表中彻底消失）。
   独立血缘证明（比集合差更强）：复核重实现了 `seed_market_history._normalize_bar` + `_row_hash`，仅用 cache 行重算 `market_history.row_hash`，6,926 个抽样匹配对中 **2,708 个 SHA256 精确重现、0 个无法重建**，且**哈希命中集合与「值完全相同」集合 1:1 重合**——只有该代码路径产出的拷贝才会有这种行为。

**结论（修正后）：本系统只有一个 bar 数据来源，但两库是同一来源的两个 vintage。** `market_history` 的 CHECK 约束只是在校验一份已通过无约束 cache 与 Python normalizer 的拷贝；把两库互相比对**不是交叉验证，是自我比对**。同时——**禁止以「它只是副本」为由删除或覆盖 `market_history`**：它是 1,153,127 个历史 close 的唯一存世记录，删掉即永久失去「过去的决策当时看到的是什么」的证据。真正的缺陷不是重复，而是**静默分歧**：定价路径读 cache、研究路径读 history，两者在 61.4% 的共享行上不一致。

### 2.3 消费者到数据源的映射（代码读取路径）

| 消费者 | 实际读取 | 是否过滤 `adjustment_mode` | 证据 |
|---|---|---|---|
| `BacktestEngine`（`backend/app/backtest/engine.py`） | `daily_bar_cache` | **否**（:443 仅 `quality_status='ready'`；:717 benchmark 同） | :45-46 硬编码 `SQLiteStore(settings.database_path)`，无 store 注入点；:935 把字面量 `'daily_bar_cache'` 写入 `historical_backtest_runs.data_source` |
| `SimulationMarketDataService`（`app/simulation/market_data.py`） | `daily_bar_cache` | 是（:47 `qfq`） | :40,:47 |
| `PhaseReplayService`（`app/backtest/phase_replay.py`） | `daily_bar_cache` | 是（:169） | — |
| `StrategySelectionV2Service`（`app/candidates/selection_v2.py`） | `daily_bar_cache` | **否**（:790,:844,:2038） | 另在 :19,:74 构造 `FullMarketScoreCalibrationService(store=..., history_store=MarketHistoryStore())`，即 **`market_history` 确实影响候选打分**（复核补充，原审计遗漏） |
| `OutcomeLabelingService`（`app/forecasting/outcome_labeling.py`） | `daily_bar_cache` | **否**（:218） | — |
| `full_market_scan.py` / `full_market_score_calibration.py` / `full_market_research_routes.py` / `instrument_catalog.py` | `market_history` | — | 均不定价、不执行回测 |

实测印证：`SELECT data_source, COUNT(*) FROM historical_backtest_runs GROUP BY 1;` -> `daily_bar_cache | 39`（39/39）。

**复核修正（adjusted）**：原审计将「回测被硬绑定到无约束库」定为 blocking。复核指出三点必须修正：

1. 引擎口径下的证券数是 **5,560 只可交易股票**，不是 5,566（另 2 只是指数 `SH000001`/`SH000300`，4 只是无前缀重复码）。
2. 「研究库对模拟 P&L 零影响」在今天是**空洞成立**——`SELECT COUNT(*), SUM(final_cash<>initial_cash) FROM historical_backtest_runs;` -> `39 | 0`，根本不存在 P&L。
3. **今天把回测切到 `market_history` 会丢数据而不是得数据**：`market_history` 仅有 40 个 cache 没有的 (symbol,trade_date)（0.0014%），且 `instruments` 中 INDEX 行数为 **0**、`daily_bars` 中 `SH000300` 行数为 **0**，无法为全部 39 次运行都请求过的 SH000300 基准定价。

因此本报告将该项**从 blocking 降级为 medium（治理与血缘缺陷）**。真正的缺陷是：**定价路径所在的库没有任何完整性 CHECK、没有 PIT 列，bar 可以在决策记录之后被就地改写且无法追溯版本**。

### 2.4 基准（benchmark）血缘

- 基准符号 `SH000300`：仅存在于 `daily_bar_cache`，538 行，`2024-06-19 .. 2026-09-02`，`source='akshare.stock_zh_index_daily'`，`adjustment_mode='none'`，`quality_status='ready'`；`market_history.daily_bars` 中为 **0 行**。
- 与 A 股会话日历比对：窗口内会话日 547（>=100 只股票口径），基准自身跨度内**缺口 0 天**；但基准整体只覆盖 538/547 天，且**首日 2024-06-19 晚于窗口起点 289 天**。
- 39 次回测中 **37 次**的 `benchmark_json.status = "insufficient_benchmark_data"`，仅 run 38/39 为 `ready`（run 39: `benchmark_return=0.069608`、`excess_return=-0.069608`、`correlation_to_benchmark=null`）。
- 风险：`SH000001` 与无前缀符号 `000001`（= 平安银行，`tonghuasun.local.quotes.candle`，121 行）在同一张表内同时存在；2026-09-02 当日 `000001` close=11.91 而 `SH000001` close=3941.386。

```sql
SELECT symbol, COUNT(*), MIN(trade_date), MAX(trade_date), MIN(source), MIN(adjustment_mode)
  FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001','000001') GROUP BY symbol;
SELECT id, substr(benchmark_json,1,60) FROM historical_backtest_runs ORDER BY id;
```

---

## 3. 研究窗口覆盖度（2023-09-04 .. 2026-09-04）

### 3.1 可计算子集与不可计算余量（分开陈述）

| 区段 | 自然日 | 工作日 | 交易日 | bar 行数 | 状态 |
|---|---|---|---|---|---|
| warm-up：`< 2023-09-04` | — | — | — | **0 / 0**（两库） | **不可计算**：无任何前置数据，任何回看指标在窗口起点无法初始化 |
| 窗口段 A：`2023-09-04 .. 2024-04-08` | 218 | 156 | 约 146（估算） | **0 / 0**（两库） | **不可计算**：完全为空 |
| 窗口段 B：`2024-04-09 .. 2024-06-21`（爬坡） | 74 | 54 | 50（实测） | 4,682 行 / 935 只（股票口径） | **不可用于截面**：40 个交易日 <100 只、10 个 100–999 只、1 个 1000–2999 只 |
| 窗口段 C：`2024-06-24 .. 2026-09-03`（稠密） | 802 | — | **536**（实测） | 约 2.88M 行 | **可计算**：唯一可做全市场截面的区间 |
| 窗口段 D：`2026-09-04`（当日） | 1 | 1 | 1 | 2,608 只（前一日 5,552 只） | **部分日**：不得作为评估日 |

- 窗口内实际存在交易日 **587** 个；名义应有约 **733** 个（**估算**，依据见 1.1）。差额约 146 个交易日在段 A，另有 50 个交易日在段 B 属「存在但不可用」。
- **复核修正：段 C 内部并非一致稠密。** 以「当日在册股票数」为分母而非固定阈值 5,000，536 个稠密日中只有 **500 天达到 >=99%**（首个为 `2024-08-13`），另有 **36 天落在 95.26%–99.0%**（最差 `2024-06-25` 5,027/5,277 = 95.26%）。因此**非代表性交易日为 87 天（51 天 <50% + 36 天 95–99%），不是 51 天**。分档实测：>=99.5% 496 天 / 99–99.5% 4 天 / 95–99% 36 天 / 50–95% 0 天 / <50% 51 天。
- 段 B 的成因**不是 watchlist 逐步纳入**（此为复核修正）：`daily_bar_cache.created_at` 最早为 `2026-06-30 04:55:30`，2026-07 单月写入 2,614,909 行；每股票 bar 数呈固定预算分布（536 根 2,590 只 / 537 根 2,309 只 / 501 根 248 只 / 538 根 94 只）。对 935 只「爬坡」股票，`(537 - 稠密期实得根数) - 爬坡期根数` 的中位数**恰为 0**，919/935（98.3%）落在 ±3 内 —— 说明左边缘参差是**「固定根数回溯 + 个股停牌」**的产物，而非选择性纳入。

  本轮复核给出了决定性的写入时间证据：

  ```sql
  -- 段 B 的全部 4,682 行股票 bar 是在同一天、5 小时内写入的
  SELECT MIN(created_at), MAX(created_at), COUNT(*), COUNT(DISTINCT substr(created_at,1,10))
    FROM daily_bar_cache
   WHERE <STOCK> AND trade_date>='2024-04-09' AND trade_date<='2024-06-21';
  -- ('2026-07-15 06:11:58', '2026-07-15 11:21:06', 4682, 1)

  SELECT COUNT(*) FROM daily_bar_cache WHERE <STOCK> AND created_at < '2026-01-01';   -- 0
  SELECT substr(created_at,1,7), COUNT(*) FROM daily_bar_cache WHERE <STOCK> GROUP BY 1;
  -- 2026-06: 850 | 2026-07: 2,613,903 | 2026-09: 275,306
  ```

  即：**没有任何一行股票 bar 是在 2026 年之前写入的**，段 B 的 4,682 行全部产生于 `2026-07-15` 一次回填，且 4,097 / 5,561 只符号的首个 bar 恰好落在 `2024-06-24`。这一区分对补救方向是决定性的：**「历史从未被采集」是可以重新拉取的回填深度问题，而不是「当时没记录、现在永久丢失」**。

### 3.2 每股票覆盖度（per-symbol manifest）

清单文件：

- `claude methods\_m1_evidence\coverage_manifest.csv`（每只股票：`list_date`、`eligible_sessions`、`observed_sessions`、`coverage_ratio`、`window_first`、`window_last`）
- `claude methods\_m1_evidence\coverage_gap_shape.csv`（每只股票：`leading_gap` / `interior_gap` / `trailing_gap`）

**分母定义**：每只证券在窗口内、其上市区间 `[max(list_date, 2023-09-04), min(coalesce(delist_date,2026-09-04), 2026-09-04)]` 内的**合格交易日**。由于 `delist_date` 全为空，右端一律取窗口末端——这是幸存者偏差的直接后果，必须与覆盖率一并陈述。

| 口径（分母） | 分母 | 可计算证券数 | 中位数 | 均值 | >=0.99 | >=0.95 | >=0.90 | <0.50 |
|---|---|---|---|---|---|---|---|---|
| **名义窗口**（约 733 交易日，估算） | 733 | 5,560 | **0.731** | — | 0 | **0** | **0**（>=0.80 亦为 0） | — |
| 已观测 spine（587 交易日） | 587 | 5,560 | 0.913118 | **0.912638** | 247 | 269 | 5,289 | 2 |
| 全市场稠密期（536 交易日），`daily_bar_cache` | 536 | 5,542 | **1.0000** | 0.9953 | 5,001 (90.2%) | 5,279 (95.3%) | 5,540 (100.0%) | 1 |
| 全市场稠密期（536 交易日），`market_history` | 536 | 5,542 | 1.0000 | 0.9609 | 4,919 (88.8%) | 5,194 (93.7%) | 5,211 (94.0%) | **310** |

**必须向读者讲清的四点**（均为复核修正）：

1. 以 587 为分母得到的「95.4% 的股票覆盖率 >=0.90」是**分母造成的假象**。587 是数据自身的足迹，不是窗口。4,891/5,560（88.0%）的股票覆盖率恰好落在**两个值**上：`536/587 = 0.913118` 与 `537/587 = 0.914821`；这两个值的差别**只取决于该股票是否拿到了残缺的最后一个交易日 2026-09-04**，与数据质量无关。
2. 以名义窗口为分母，**上市早于 2024-04-09 的股票中，达到 95% 覆盖率的为 0 只**；全市场最好的一只也只有 73.4%。原审计给出的均值 0.914902 与「5,543 只可计算」经复核更正为 **0.912638 / 5,560 只**（5,561 只 SH/SZ/BJ 股票中恰有 1 只观测为 0）。该「窗口前已上市」子集的规模，原审计记为 5,268 只，复核以 list/delist 感知分母重算为 **5,286 只**（最大覆盖率 **0.916525**，>=0.95 者 **0**）；两个口径的结论完全相同，本报告并列记录以便 Codex 复算时不把 5,286 当作矛盾。

3. **爬坡并不能解释全部缺口（复核修正：约 94–96%，不是 100%）。** 爬坡段实为 **50** 个交易日（`2024-04-09..2024-06-21`），而众数 536 根的股票相对 587 天缺 **51** 天，其中只有 46–49 天属爬坡段，余下 2–5 天是稠密期内真实的零散空洞：`SH600530` 缺 `2026-09-04`、`SH600165` 缺 `2026-08-25`、`SH600238` 缺 `2026-07-31`。原文「完全由爬坡造成」应更正为「约 94–96% 由爬坡造成」。

4. **稠密期内部的数据本身是干净的。** 以 536 天稠密 spine 为分母，`daily_bar_cache` 的每股票覆盖率中位数为 **0.9981**，**5,035 / 5,560 只 >= 0.95**。因此本节的缺陷性质是**窗口起点被截断**，不是稠密期内部的逐条 bar 腐蚀——这两件事的补救方式完全不同。

**截断（truncation）而非伪造**：

```sql
SELECT COUNT(*) FROM (SELECT symbol, MIN(trade_date) ft FROM daily_bars GROUP BY symbol) f
  JOIN instruments i ON i.symbol=f.symbol
 WHERE i.list_date IS NOT NULL AND i.list_date <> '' AND f.ft < i.list_date;   -- 0
```

没有任何股票存在早于其 `list_date` 的 bar。历史是「缺失」，不是「被捏造」。复核同时把截断比例从 94.6% 更正为 **5,132/5,132 = 100%**（分母应为窗口前已上市的股票，原分母误含 376 只窗口内 IPO 与 18 只 `list_date` 为空者）。

### 3.3 缺口分类（gap taxonomy，禁止混用分母）

对 5,560 只股票、3,174,832 个合格 spine 槽位：

| 类别 | 数量 | 判定依据 | 能否从本地数据分类 |
|---|---|---|---|
| 已观测 | 2,890,058 | — | — |
| **前置缺失（leading）** | 276,934（8.72%） | 首个 bar 晚于合格起点；P50 = 50 个交易日，max 584 | 能（= 抓取深度限制） |
| **内部空洞（interior）** | 4,673（0.15%，759 只） | 位于该股票自身首末 bar 之间；P50=0, P90=2, P99=10, max=50 | **不能** —— 停牌 / 抓取失败 / 退市前静默三者证据相同 |
| **尾部缺失（trailing）** | 3,167（0.10%） | 末个 bar 早于窗口末端 | 部分（5 只由 `status='inactive'` 解释） |
| 新上市（非缺口） | 376 只 | `list_date` 落在窗口内 | 能 |
| 上市历史证据不可得 | 18 只 | `list_date IS NULL` | —（明确排除在所有分位数之外） |
| 无效日期 | 1 行 | `trade_date='ERROR'` | 能 |
| 陈旧未刷新 | 187,025 行 | `updated_at` 仍停留在 2026-07 | 能 |

内部空洞的间接证据：759 只有内部空洞的股票中，194 只名称含 `ST/*ST/退`，占内部缺失槽位的 777/4,673（16.6%），与真实停牌一致——但**没有停牌日历表**，无法确证。`bar_quality_issues` 表 0 行，说明系统从未把「应有 bar 而缺失」记录为质量事件。

### 3.4 中途换血：北交所整体在 2025-11-17 才进入（复核补充，原审计遗漏）

```sql
WITH f AS (SELECT symbol s, MIN(trade_date) ft, COUNT(DISTINCT trade_date) n FROM daily_bars GROUP BY symbol)
SELECT i.exchange, COUNT(*), MIN(f.ft), ROUND(AVG(f.n),1),
       SUM(CASE WHEN f.ft<='2024-06-24' THEN 1 ELSE 0 END)
FROM f JOIN instruments i ON i.symbol=f.s WHERE i.exchange IN ('SH','SZ','BJ') GROUP BY 1;
-- SZ 2902 | 2024-04-12 | 526.7 | 2798
-- SH 2317 | 2024-04-09 | 518.8 | 2187
-- BJ  341 | 2025-11-17 | 167.3 |    0     <-- 2025-11-17 之前不存在任何北交所名称
```

其中 238 只北交所股票 `list_date < 2024-01-01` 却在 2025-11 之后才出现。另有 246 只 BJ 股票覆盖率恰为 `501/587 = 0.853492`，与 `920xxx` 代码改号（2024-08-12/13）吻合，旧 `8xxxxx` 代码下的历史在两库中均不可达，且**没有任何 symbol 别名映射表**。

**后果**：截面**成分**在窗口中途改变，不只是起点变晚。任何跨越 2025-11-17 的横截面研究，其可选股票池会突然增加 341 只。

### 3.5 warm-up 单独计量（不并入窗口覆盖率）

| 指标 | 值 | SQL / 依据 |
|---|---|---|
| `< 2023-09-04` 的行数 | **0**（两库） | `SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date<'2023-09-04' AND length(trade_date)=10;` |
| 稠密日历上首个可算 60 日特征的日期 | 2024-09-13 | 536 个稠密日的第 60 个 |
| 首个可算 120 日特征的日期 | 2024-12-17 | 第 120 个 |
| 首个可算 250 日特征的日期 | 2025-07-03 | 第 250 个 |
| 若保留 250 日 warm-up，剩余可用于训练/验证/测试的天数 | 286 天（2025-07-04..2026-09-03） | `pointintime_09_splits.py` |
| 若保留 120 日 warm-up，剩余可标注决策日 | 396 天（2024-12-18..2026-08-06） | `pointintime_10_folds.py` |

**结论：250 日 warm-up 在当前数据下只剩 286 天可分割，不足以支撑 4 折 walk-forward；120 日 warm-up 是唯一可行的折中。**

---

## 4. universe 与幸存者偏差

### 4.1 判定：**UNRESOLVED（未解决，且从磁盘数据无法量化）**

| 证据 | 值 | SQL |
|---|---|---|
| `instruments` 中带 `delist_date` 的行 | **0 / 5,561**（`typeof()` 普查确认全部为 `null`，无空串/哨兵值） | `SELECT typeof(delist_date), COUNT(*) FROM instruments GROUP BY 1;` -> `null｜5561` |
| `status <> 'active'` | 5（`SZ002808 恒久退`、`SZ000004 国华退`、`SH605081 退市太和`、`BJ920305 云创退`、`SZ002898 赛隆退`） | `SELECT status, COUNT(*) FROM instruments GROUP BY 1;` |
| `universe_snapshots` | 12 行 / **7 个不同日期** / 2026-07-14 .. 2026-09-04 | `SELECT COUNT(*), COUNT(DISTINCT snapshot_date), MIN(snapshot_date), MAX(snapshot_date) FROM universe_snapshots;` |
| 窗口内**有** universe 记录的天数（复核修正） | **7 / 1,097 自然日 = 0.64%**；按交易日为 **5 / 586 = 0.85%** | 复核指出「12 行 = 53 天跨度」是把 `MIN..MAX` 当作覆盖区间，实际只有 7 个不同 `snapshot_date`，且其中 `2026-07-19 -> 2026-09-03` 是一个 **46 天的空洞**却被计入「已覆盖」。<br>`SELECT COUNT(*), COUNT(DISTINCT snapshot_date) FROM universe_snapshots;` -> `12` 行 / `7` 个不同日期；`SELECT COUNT(*) FROM (SELECT DISTINCT trade_date d FROM daily_bars WHERE d BETWEEN '2023-09-04' AND '2026-09-04') WHERE d IN (SELECT snapshot_date FROM universe_snapshots);` -> `5` |
| 窗口内**无** universe 记录的天数（复核修正） | **1,090 / 1,097 自然日**；按交易日为 **581 / 586** | 同上。原审计的 1,044 / 548 高估了覆盖度约 7.5 倍，**本报告采用复核值** |
| **决定性证据：无任何提前终止的价格序列** | `daily_bar_cache` 5,566/5,566 只证券的末个 bar 均在 2026 年；2025 年终止者 0，2024 年终止者 0 | `WITH ls AS (SELECT symbol, MAX(trade_date) mx FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol) SELECT substr(mx,1,4), COUNT(*) FROM ls GROUP BY 1;` -> `2026｜5566` |
| 截面证券数单调递增、无任何剔除 | 2024-09-04: 4,998 -> 2025-03-03: 5,032 -> 2025-09-04: 5,077 -> 2026-03-02: 5,459 -> 2026-09-03: 5,549 | `SELECT trade_date, COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date IN (...) GROUP BY 1;` |
| bar 中存在但 catalog 中没有的证券 | **0** | `SELECT COUNT(DISTINCT b.symbol) FROM daily_bars b LEFT JOIN instruments i USING(symbol) WHERE i.symbol IS NULL;` |

一个真实的三年 A 股面板会包含数十只在期间退市、序列在中途终止的证券。本面板**一只都没有**。这不是「退市信息稀疏」，而是**面板本身由 2026-07/2026-09 的在册名单向后回填而成**（`instruments.created_at`：2026-07-15 写入 5,531 行，2026-07-16 写入 1 行，2026-09-04 写入 29 行）。

### 4.2 直接测试：「2024-03-15 的可交易 universe 是什么？」

四条路径全部失败或构造性有偏：

| 路径 | 结果 |
|---|---|
| A. 该日或之前的 `universe_snapshots` | **0 行** |
| B. `list_date` / `delist_date` 推算 | 5,259 只——但 `delist_date` 项恒为真空，且 `instruments` 只含 2026-09-04 仍在册者，**构造性有偏** |
| C. 该日的 bar 出现情况 | 两库均 **0 只** |
| D. `available_at <= '2024-03-15'` 的 PIT 过滤 | **0 行** |

### 4.3 已知的两次退市检出（复核修正：机制可用，只是历史太短）

原审计称「5 个已知退市名称无法置于任何时间线上」，**此说法被复核否证**：

- `MAX(trade_date)` 给出各自明确的末交易日：`SH605081 2026-06-29`、`SZ000004 2026-07-13`、`SZ002808 2026-07-13`、`SZ002898 2026-07-15`、`BJ920305 2026-07-17`。
- `instruments` 的失活 UPDATE 带 `AND status='active'` 条件，因此 `updated_at` 在状态翻转后**冻结**，与末 bar 相差 3/3/4/17/49 天，可作为「首次观测到缺席」的时间戳。
- 快照间差分可直接观测到 2 次移除事件：`SZ002898` 在 2026-07-15 -> 2026-07-17 之间消失，`BJ920305` 在 2026-07-19 -> 2026-09-03 之间消失。

原审计对成因的归因（`instrument_catalog.py:477` 的 `delist_date = NULL`）也被复核更正：该赋值位于 `ON CONFLICT(symbol) DO UPDATE` 分支，只对**出现在新目录中的**符号生效，退市符号根本走不到这一行。它是潜在隐患（复牌时会抹掉已有 `delist_date`），不是 5,561 个 NULL 的成因；真正成因是**两个写入者都从不写该列**（`instrument_catalog.py:469` 的 INSERT 直接写字面量 NULL；`seed_market_history.py:466-481` 的列清单与 DO UPDATE SET 中都不含 `delist_date`）。

**结论修正**：退市检出机制**是可用的**，只是只有 51 天的运行历史与 2 个事件。补救方向是「给一个能用的机制回填历史」，不是「从零建机制」。

### 4.4 名称 / ST 历史被每次刷新销毁

- `instrument_catalog_refresh_heartbeat.json` 记录一次刷新的 `changes = {'added':1,'inactivated':1,'reactivated':0,'renamed':5211}` —— 5,556 个名称中 **5,211 个在单次刷新中被覆盖**，旧值不留存于任何表。
- 当前 203 只名称含 `ST`。任何「排除 ST」的策略都**无法诚实回测**：用今天的标记去过滤 2024 年是 look-ahead，忽略标记则交易了规则本应排除的股票。
- `market_history.sqlite3` 共 9 张表（`schema_metadata`、`instruments`、`universe_snapshots`、`sqlite_sequence`、`universe_members`、`ingest_runs`、`daily_bars`、`bar_quality_issues`、`training_dataset_manifests`），**没有任何一张存储带日期的名称 / ST / 停牌历史**。

### 4.5 缺失的证据清单（要解决幸存者偏差，必须补齐）

1. 逐证券的 `delist_date` + `delist_reason` + 观测时间（来源：SSE/SZSE/BSE 官方退市登记，而非「当前在册代码」接口）；
2. 每个交易日的 universe 快照（`available_at` 与该交易日同期，而非事后两年）；
3. 带生效区间的名称 / ST 标记历史（`symbol, name, st_flag, effective_from, effective_to, observed_at, source`）；
4. 停牌（停牌 / 复牌）日历；
5. `8xxxxx -> 920xxx` 等代码变更映射及生效日。

**在上述五项到位之前，任何回测结论都必须显式标注「survivor-only universe，偏差规模未知」，并且本报告不给出、也不允许下游给出任何历史日期的全市场完整度百分比。**

**可立即使用的部分能力（复核补充）**：`list_date` 在 5,543/5,561 只（99.68%）上有值，因此「某个历史日期尚未上市的股票」**可以被正确排除**——IPO 侧的 look-ahead 偏差今天就能消除；无法消除的只有退市侧。
---

## 5. 数据完整性与异常

分类口径：**阻断研究（blocking）** = 会使结论错误或不可复现；**限制字段（field-limiting）** = 只影响某个字段/子集，可通过声明限制继续研究。

### 5.1 异常清单

| # | 异常 | SQL | 最小示例 | 影响行数 / 证券数 | 判定 |
|---|---|---|---|---|---|
| A1 | 两库 close 大面积分歧（同为 `qfq`） | `SELECT COUNT(*) common_rows, SUM(ABS(d.close-b.close)>0.005) differs, SUM(ABS(d.close-b.close)/NULLIF(b.close,0)>0.01) gt1pct, COUNT(DISTINCT CASE WHEN ABS(d.close-b.close)>0.005 THEN d.symbol END) syms FROM daily_bar_cache d JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq' WHERE d.quality_status='ready' AND d.adjustment_mode='qfq';` | `SZ301590 2025-09-30`：ops_close=166.086 / hist_close=233.32（abs_diff=67.234，source `tencent.fqkline.qfq`） | 1,059,740 / 2,787,696（38.01%）；>1% 者 207,831（7.46%）；3,713 只。按年：2024 46.68%、2025 57.93%、2026 4.13% | **阻断** |
| A2 | 分歧不是单一 re-basing 因子 | `WITH j AS (SELECT d.symbol, MAX(d.close/NULLIF(b.close,0))-MIN(d.close/NULLIF(b.close,0)) spread FROM daily_bar_cache d JOIN mh.daily_bars b ON ... GROUP BY d.symbol HAVING COUNT(*)>20) SELECT COUNT(*), SUM(spread<0.0001), SUM(spread>=0.0001) FROM j;` | `SZ000001`：2024-06-24 ratio=1.0，2024-12-31 ratio=1.001676，2025-06-30 ratio=0.997908，2025-12-31 ratio=1.0 | 5,542 只中 **3,749 只比值随日期漂移**，1,793 只恒定；恒定且偏离 1 的（经典拆并因子）**0 只** | **阻断** |
| A3 | 数据源拼接造成价格水平跳变 | 见 6.3 的 level-shift SQL | `SZ002582 2024-08-12 -> 08-13`：cache 3.2570 -> 4.1400（+27%），mh 3.2570 -> 3.2070（-1.5%）；ratio 由 1.0000 跳到 1.2909 | 5,333 只有源切换；可测边界 5,865 个中：>0.5% 位移 2,096（35.7%）、>1% 1,327、>2% 636、>5% 107、>10% 35 | **阻断** |
| A4 | `market_history` 缺 `amount`（成交额） | `SELECT SUM(amount IS NULL), COUNT(*) FROM daily_bars;` | provider `tencent.fqkline.qfq` 1,942,030 行，100% `amount IS NULL` | 1,955,651 / 2,787,736（70.15% 绝对口径）。**相对当前定价库的净退化为 1,652,094 行 = 59.26%**（复核修正：其余 303,562 行在 cache 中同样为 NULL，属现状而非新增损失）。**时间分布高度不均（本轮复核新增）**：`2024-06..2025-12` 逐月 NULL 率 96.9%–97.6%，`2026-01` 为 64.2%，`2026-02` 起降至 5.0%–5.1%；1,652,094 个可修复单元中 **1,644,108 个（99.5%）早于 2026-02** | **限制字段**（`engine.py:849` 输出 `liquidity_basis_counts`，回退不是静默的；除 5 行外均有 `volume>0`，代理口径可算）。**性质澄清**：这是一个**已经停止扩大的历史积压**（2026-02 起新数据基本带 amount），因此补救是一次性回填作业，不是管线重构。**但代理口径本身的安全性由 A18 否证** |
| A5 | `daily_bar_cache` 缺 `amount` | `SELECT source, COUNT(*), SUM(amount IS NULL) FROM daily_bar_cache GROUP BY source;` | `tencent.fqkline.qfq` 303,449 行全 NULL；`akshare.stock_zh_a_daily` 2,426,883 行 0 NULL | 307,620 / 2,891,617（10.64%）；涉及 4,948 只；8 个交易日整日全 NULL | 限制字段 |
| A6 | OHLC 关系违规 + 零价 | `SELECT symbol, trade_date, open, high, low, close, source FROM daily_bar_cache WHERE high<low OR high<open OR high<close OR low>open OR low>close;` | `SH688089 / SH688143 / SH688173`，均在 `2024-11-06`，`open=high=low=0.0`，`close` 非零，`source='akshare.stock_zh_a_daily'` | 3 行 / 3 只 | **阻断（局部崩溃）**：`engine.py:231-233` 以 `open` 作 `reference_price`，`int(alloc / buy_price)` 在 `open=0` 时抛 `ZeroDivisionError`。这三行在 `market_history` 中不存在（被 CHECK 拒绝） |
| A7 | 伪日期 `trade_date='ERROR'` | `SELECT rowid, symbol, trade_date, source, quality_status FROM daily_bar_cache WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]';` | `rowid=6811635, symbol=BJ920289, source='error', quality_status='error'`，全部价格 NULL，`created_at='2026-09-04 03:42:54'` | 1 行 / 1 只 | 限制字段：`quality_status<>'ready'` 且被 `BETWEEN` 与 `dropna` 双重排除（实测 `ready` 口径下命中 0 行）。但它证明**抓取失败被当作数据行持久化** |
| A8 | 无前缀重复代码（命名空间冲突） | `SELECT symbol, COUNT(*), MIN(trade_date), MAX(trade_date), MAX(source) FROM daily_bar_cache WHERE symbol NOT LIKE 'SH%' AND symbol NOT LIKE 'SZ%' AND symbol NOT LIKE 'BJ%' GROUP BY symbol;` | `000001`（121 行，平安银行，THS 源）与 `SH000001`（538 行，上证指数）在同一表；2026-09-02 close 分别为 11.91 与 3941.386 | 4 只 / 482 行（`000001`/`300750`/`600519`/`920099`，均始于 2026-03-12） | **阻断（分母污染）**：`COUNT(DISTINCT symbol)` 得 5,567，比 `instruments` 多 6，且 600519 被计两次 |
| A9 | 指数混入股票表 | `SELECT adjustment_mode, quality_status, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE adjustment_mode<>'qfq' GROUP BY 1,2;` | `SH000001` / `SH000300`，各 538 行，`adjustment_mode='none'`、`quality_status='ready'`、`source='akshare.stock_zh_index_daily'` | 1,076 行 / 2 只 | **阻断（截面污染）**：`engine.py:443` 在 symbol 列表为空时仅按 `quality_status='ready'` 取数，指数会与股票并列进入 frame |
| A10 | demo / 未复权残留 | 同 A9 的 SQL | `demo_seed_fixture` 4 行（2026-05-25/26）；`review_only_unadjusted` 129 行 / 48 只 | 133 行 | 限制字段（被 `quality_status` 过滤排除，但仍在生产库中） |
| A11 | 零成交行 | `SELECT symbol, trade_date, volume, amount FROM daily_bar_cache WHERE volume=0;` | `SH688189 2026-06-10`，volume=0, amount=0，两库一致 | 16 行（volume=0 与 amount=0 同为 16） | 限制字段（真实停牌/无成交，需在收益计算中显式处理） |
| A12 | 末日为部分日 | `SELECT trade_date, COUNT(DISTINCT symbol), SUM(amount IS NULL) FROM daily_bar_cache WHERE trade_date IN ('2026-09-03','2026-09-04') GROUP BY 1;` | 2026-09-04 仅 2,608 只（amount NULL 353），前一日 5,552 只（amount NULL 33） | 1 个交易日，缺 2,944 只 | **阻断（若被当作评估日）**：`MAX(trade_date)` 取到的正是这一天 |
| A13 | 内部空洞不可归因 | `WITH sess AS (...), span AS (...), expect AS (...) SELECT SUM(expected-n), COUNT(*), SUM(expected>n) FROM ...;` | 见 3.3 | 4,673 行 / 759 只 | 限制字段（必须归入「不可分类缺席」，不得静默前向填充） |
| A14 | 陈旧未刷新 | `SELECT substr(updated_at,1,7), COUNT(*) FROM daily_bar_cache GROUP BY 1;` | 2026-07 187,025 行；2026-09 2,704,592 行 | 187,025 行 / 5,045 只涉及 | 限制字段 |
| A15 | 14 只股票缺最后一个完整交易日 | `SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bar_cache WHERE quality_status='ready' EXCEPT SELECT symbol FROM daily_bar_cache WHERE trade_date='2026-09-03');` | — | 14 只 | 限制字段 |
| A16 | 质量事件表空 | `SELECT COUNT(*) FROM bar_quality_issues;` | — | 0 行 | **阻断（可审计性）**：上述 A6/A7/A13 无一被记录 |
| A17 | 重复键 | `SELECT COUNT(*) FROM (SELECT symbol, trade_date FROM daily_bar_cache GROUP BY 1,2 HAVING COUNT(*)>1);` | — | **0**（大小写/空白归一化后仍为 0） | 通过 |
| **A18** | **`volume_unit` 语义错误：以「股」计的成交量被标为「手」，使流动性代理放大约 100 倍**（本轮复核新增） | `WITH t AS (SELECT b.volume/c.volume vr FROM daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date WHERE (b.amount IS NULL OR b.amount<=0) AND c.amount>0 AND c.volume>0 AND b.volume>0) SELECT COUNT(*), SUM(vr BETWEEN 0.99 AND 1.01), SUM(vr BETWEEN 99 AND 101) FROM t;` -> `1652094 \| 1488916 \| 163174`；再 `SELECT b.volume_unit, COUNT(*) ... WHERE b.volume/c.volume BETWEEN 99 AND 101 GROUP BY 1;` -> `('hand', 163174)` | 163,174 行 `daily_bars.volume` 恰为 cache 的 100 倍且 `volume_unit='hand'`。按 `engine.py` 的代理公式 `volume × SHARES_PER_HAND(100) × (H+L+C)/3` 对这 1,652,094 行回算并与 cache 真值 `amount` 比对：**均值 10.1491、min 0.3133、max 218.2048**；<0.8 者 106,171、0.8–1.25 者 1,382,738、**>1.25 者 163,185** | **163,174 行 / 576 只证券**（占可修复集 9.9%） | **阻断**：偏差方向是**乐观**（流动性上限被放大 ~100 倍 -> 参与率上限形同虚设 -> 成交现实中吃不下的委托），而不是代码注释承诺的保守低估。同一公式作用于 cache 行时表现正常（均值 0.9659、max 2.45、>1.25 仅 14 行），说明该缺陷特定于 `market_history` 冻结的 tencent 系行。**`CHECK(volume_unit IN (...))` 只保证字面量合法，从不保证语义正确** |
| A19 | 代码注释与现实脱节 | `backend/app/backtest/execution.py:68` 注释称「97.6% 的缓存 bar 来自无成交额的源」 | — | — | 限制字段（可审计性）：该数字描述的是 `market_history` 的冻结 vintage，**不是** `daily_bar_cache`（后者今天为 10.64% NULL）。按注释判断「哪个库更差」会得出相反结论 |

### 5.2 未发现的问题（同样是结论）

- `daily_bar_cache` 无重复 `(symbol,trade_date)`、无大小写变体、无首尾空白、`typeof(trade_date)` 全为 `text`、无未来日期、无不可能月/日、无负价、`close<=0` 为 0 行。
- `market_history.daily_bars`：`high<low` / `high<open` / `low>close` / `close<=0` / `length(trade_date)<>10` / 非法 `adjustment_mode` / 非法 `volume_unit` **全部为 0**——CHECK 确实在生效。
- `volume_unit`：cache 中 `hand` 2,890,536 行 / `unknown` 1,081 行（即 2 只指数 + 3 只异常）。
  **更正（本轮复核）**：先前「单位混用风险已被限制在指数与异常行上」的说法**不成立**。枚举值合法不等于语义正确——`market_history` 中至少 163,174 行标注 `'hand'` 的成交量实际是以「股」计的（见 A18）。因此 `volume_unit` 必须被视为**未经验证的声明**，而不是已校验的事实；任何依赖它做单位换算的代码（含 `execution.py` 的代理成交额）在使用前都要先做 100 倍一致性检验。

### 5.3 结论

`daily_bar_cache` 是**没有任何 CHECK 的定价库**，其中确实存在（虽少但真实的）不可能行；`market_history` 有完整 CHECK 却是它的派生副本、丢失了 59.26% 的成交额，并且**它的 CHECK 挡不住 A18 这类语义错误**（`volume_unit` 声明与实际单位相差 100 倍，枚举校验全部通过）。

因此今天的选择既不是「多数据但无约束」也不是「有约束就安全」——**约束的价值取决于它约束的是不是真正会错的东西**。正确的解法有三条，且必须一起做：

1. 把 `market_history` 的结构性 CHECK 移植到 `daily_bar_cache`（需重建表，SQLite 无法原地加 CHECK），违规行隔离进 `bar_quality_issues` 而非 bar 表；
2. **新增语义级校验**，而不只是枚举校验：`amount ≈ volume × unit_multiplier × 典型价` 的量级一致性检查（容忍区间建议 [0.5, 2.0]），偏离即拒绝入库并记 `bar_quality_issues`；
3. **不切换存储**：切库不解决任何一项，且会丢掉 102,322 行与 SH000300 基准（见 2.3、2.4）。

---

## 6. 复权与公司行动

### 6.1 现状

| 指标 | 值 | SQL |
|---|---|---|
| `market_history.daily_bars` 的 `adjustment_mode` | `qfq` **2,787,736 行（100%）**，`none`/`hfq` 各 0 行；无任何 (symbol,trade_date) 拥有多个模式 | `SELECT adjustment_mode, COUNT(*) FROM daily_bars GROUP BY 1;` |
| `daily_bar_cache` 的 `adjustment_mode` | `qfq` 2,890,407（ready）/ `none` 1,076（2 只指数，ready）+ 129（48 只，`review_only_unadjusted`）/ `unknown` 5 | `SELECT adjustment_mode, quality_status, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1,2;` |
| 未复权（`none`/`hfq`）股票基线 | **不存在**（除 129 行 review-only） | 同上 |
| 公司行动（分红/送转/拆并）表 | **两库均无任何一张**（`market_history` 共 9 张表，见 4.4；`trading_local` 中亦无 dividend/split/corporate_action 表） | `SELECT name FROM sqlite_master WHERE type='table';` |
| 复权因子列 | **不存在**（两库 schema 中均无 `adj_factor` / `qfq_factor` 列） | `PRAGMA table_info(daily_bar_cache); PRAGMA table_info(daily_bars);` |

**因此：系统只保存「某一时刻抓到的 qfq 收盘价」，既没有原始价，也没有因子，也没有事件表。任何公司行动都无法被独立重算或校验。**

### 6.2 qfq 是否 point-in-time？—— **否，且可量化**

qfq 的定义决定了它随每次除权事件被整段重算。本系统只保留一个版本，且事实上已经发生过大规模重述：

1. **同源重述（纯 qfq 重算，排除跨源干扰）**
   ```sql
   SELECT substr(m.fetched_at,1,10) AS mh_fetch_day, COUNT(*) keys,
          SUM(CASE WHEN c.close>0 AND abs(m.close/c.close-1.0)>0.001 THEN 1 ELSE 0 END) d_gt_0p1pct,
          SUM(CASE WHEN c.close>0 AND abs(m.close/c.close-1.0)>0.01  THEN 1 ELSE 0 END) d_gt_1pct
     FROM daily_bar_cache c JOIN mh.daily_bars m
       ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq'
    WHERE c.adjustment_mode='qfq' AND c.source=m.provider
    GROUP BY 1;
   -- 2026-07-15: 269,185 keys, 9,253 差异>0.1%, 5,874 差异>1%
   -- 2026-07-19:   9,196 keys,   752 差异>0.1%,   535 差异>1%
   -- 2026-09-03: 808,653 keys,   294 差异>0.1%,   110 差异>1%
   ```
   同一 provider、同一 (symbol,trade_date)，仅因抓取时点不同，**2026-07-15 那批有 2.2% 的行相差超过 1%**。

2. **双版本对照（300 只样本，94,922 个匹配键）**：close 有差异 63.0%，差异 >1% 19.0%，最大相对变化 **30.05%**（`SH600262 2025-05-29`：23.774 -> 16.630）；volume 有差异 81.2%。
   诚实拆分：其中 91,174/94,922（96.1%）同时发生了 provider 变化，因此该差值混合了 qfq 重述与跨源分歧；纯同源对照只有 632 对（`SH600392`），其中 316 对（50%）变动 >1%，均值 -2.41%。

3. **不存在「整段恒定因子」的干净重述**：
   ```sql
   SELECT COUNT(*) FROM (
     SELECT symbol FROM (SELECT c.symbol, m.close/c.close AS rel FROM daily_bar_cache c
       JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq'
      WHERE c.adjustment_mode='qfq' AND c.close>0)
     GROUP BY symbol HAVING MAX(rel)-MIN(rel) < 0.02 AND (MIN(rel) > 1.02 OR MAX(rel) < 0.98));
   -- 0
   ```
   即：**没有任何一只股票是被整体乘以一个常数因子重述的**；3,749/5,542 只的比值随日期漂移（见 A2）。这说明重述是「只重算尾部、不重算全序列」的部分改写，正是最难察觉的一类污染。

**结论：`daily_bar_cache` / `daily_bars` 中的 qfq 价格是「以最近一次抓取时点为基准的当期视图」，不是任何历史日期的 point-in-time 价格。用它回测等价于让 2024 年的策略看见 2026 年才确定的除权基准。**

### 6.3 公司行动不连续 vs 数据源拼接：可分离，且已分离

- 源切换边界：6,294 个（5,333 只股票），集中在少数几天：`2024-08-13` 4,074 个、`2026-07-27` 601 个、`2026-07-24` 526 个、`2026-09-04` 333 个；主要转移为 `tencent.fqkline.qfq -> akshare.stock_zh_a_daily`（4,850 个）。**这是抓取日历，不是市场事件。**
- **仅看跳变幅度无法区分**（这是必须承认的对照结果）：
  ```
  BOUNDARY pairs     n=6,294   p50|ret|=1.74%  p90=4.89%  >2%=44.0%  >5%=9.3%
  NON-boundary pairs n=400,000 p50|ret|=1.48%  p90=4.95%  >2%=38.6%  >5%=9.7%
  ```
  同日截面标准化后，边界样本 median(|ret| / 当日中位|ret|) = 1.070，非边界 0.996；超过当日 p90 的比例 11.7% vs 9.9%（零假设为 10.0%）。**幅度检验只给出微弱信号。**
- **决定性检验是跨库收益一致性**：
  ```
  边界样本（|cache_ret|>2%，n=2,635）：|cache_ret - mh_ret| > 0.5pp 占 43.9%，>1pp 35.5%，>2pp 21.3%
  同日期对照组（无源切换，n=2,092）： >0.5pp 仅 0.8%，>1pp 0.6%，>2pp 0.5%
  ```
  55 倍的差距。**源切换边界处的跳变确实主要是拼接产物，而不是真实公司行动。**
- 逐笔交叉核对（2,767 个 |jump|>2% 的边界）：`market_history` 重现该跳变 1,477 个、**该处平滑（即 cache 侧为拼接假象）870 个**、结果不同 288 个、缺失 132 个。
- 超涨跌停幅度的相邻跳变共 424 个：`market_history` 显示相同跳变 203、缺失 173、**显示无跳变（cache 未复权/拼接）37**、跳变不同 11。
- 市场级污染量（`2024-08-13`）：
  ```sql
  -- 当日发生源切换的 4,073 只 vs 未切换的 979 只
  -- spliced: mean_ret=+1.239%, median=+1.213%, pct_up=76.5%
  -- control: mean_ret=+0.702%, median=+0.679%, pct_up=67.4%
  -- 同日 SH000001 指数真实收益 = +0.341%
  ```
  即 **2024-08-13 当天，被拼接的股票整体多出约 +0.537pp 的虚假横截面收益**。任何跨越该日的动量/反转/事件研究都会读到这个人造信号。

### 6.4 复权契约建议（提交复核）

1. **保留三份价格**：`raw`（未复权）、`qfq`、以及 `adj_factor`，并在 bar 行上记录 `factor_vintage`（因子计算日）。当前 schema 三者皆无。
2. **复权重算必须整只股票原子重写**，禁止只重写最近抓取的尾部——这是 A2/6.2 中「比值随日期漂移」的直接成因。
3. **一个符号在一个研究运行内只允许一个 provider**；跨 provider 拼接必须在 `bar_quality_issues` 中留痕，并在特征层将边界日标为不可用。
4. 在 3 之前，**任何跨 `2024-08-13`、`2026-07-24`、`2026-07-27`、`2026-09-04` 的日收益都应视为可疑**，建议在这些日期设置 1 日 mask。

---

## 7. 时间契约（point-in-time contract）

### 7.1 实测：现有时间字段各自代表什么

| 字段 | 实际含义 | 证据 |
|---|---|---|
| `market_history.daily_bars.available_at` | **入库时钟**，不是可用性时间 | `SELECT COUNT(*) FROM daily_bars WHERE available_at <> fetched_at;` -> **0**；全表仅 4 个采集日（2026-07-15 1,781,251 / 2026-09-03 824,705 / 2026-07-19 181,220 / 2026-07-16 560）；`available_at - trade_date` 分位数 p1=7, p25=181, **p50=338**, p75=547, p99=747, max=827 天；lag>365 天者 1,295,496 行（46.47%） |
| 严格 PIT 过滤后果 | `as_of=2025-09-04` 可见 **0 行**（按 trade_date 应有 1,488,254 行）；`as_of=2026-06-30` 可见 **0 行**（应有 2,527,771 行）；`as_of=2026-08-01` 可见 1,963,031 行 | `SELECT COUNT(*) FROM daily_bars WHERE trade_date<=? AND available_at<=?;` |
| 代码来源 | `seed_market_history.py:1312-1313` 直接把 `source_updated_at`（即 cache 的可变 `updated_at`）同时写入 `fetched_at` 与 `available_at` | 源码 |
| `daily_bar_cache.created_at` / `updated_at` | **物理装载/改写时间戳**，无 PIT 语义。`created_at` 为 UTC，`updated_at` 为本地 CST（同一行相差恰好 +8h） | `MIN(created_at)=2026-06-30 04:55:30` 而 `MIN(trade_date)=2024-04-09`；仅 8 个不同 `created_at` 日期；2,559,702 行（88.52%）来自 2026-07-15 单次批量装载 |
| cache 装载性质 | 实时/准实时（<=3 日）捕获 **52,358 行 = 1.81%**；回填（>3 日）**2,839,258 行 = 98.19%**。仅 2026-07 与 2026-09 两个交易月存在当日行 | `pointintime_04_cache_created.py` |
| 重述规模 | 2,574,102 行（89.0%）的 `updated_at` 与 `created_at` 不在同一天；「2026-07-15 建 / 2026-09-03 改」的行有 2,369,295 行 | 同上 |
| `forecast_decisions.available_at` | 恒等于 `decision_cutoff`，**未记录任何可用性滞后** | `SELECT COUNT(*), SUM(available_at=decision_cutoff) FROM forecast_decisions;` -> 20,082 行中 20,082 行相等（`control_plane/service.py:642`） |
| `market_history.rule_regime` | 存在两个制度分区：`cn_a_share_pre_2026_07_06` 2,544,312 行 / `cn_a_share_2026_07_06_onward` 243,424 行 | `SELECT rule_regime, COUNT(*) FROM daily_bars GROUP BY 1;` |

### 7.2 一项被否证的指控，必须如实记录（verdict = REFUTED）

原审计曾提出「3,900 个 decision×subject 对中 2,915 个（74.7%）引用了在其 cutoff 时刻尚不存在的 bar，涉及 580,097 bar-rows，severity=blocking」。**对抗性复核判定其为 REFUTED**，理由如下，必须原样保留：

1. 数值可复现（归一化时间戳后确为 2,915 / 74.74%），但**原 SQL 写错**：`created_at` 为 `'YYYY-MM-DD HH:MM:SS'`、`decision_cutoff` 为 `'YYYY-MM-DDTHH:MM:SS.ffffffZ'`，`' '(0x20) < 'T'(0x54)`，字符串直比会漏掉同日违规（原 SQL 只得 2,100 对 / 53.85%）。
2. **对照组直接证伪**：随机取 90 只从未被任何决策引用的股票、同样的 130 个 cutoff，违规率 **8,741/11,700 = 74.71%**，与决策股票的 74.74% **无法区分**。该统计量测的是 `daily_bar_cache` 的装载日历，与决策无关。
3. **决策自身的 `bars_count` 反证**：在 cutoff `2026-07-12T03:18:51Z`，按 `created_at` 模型整个 cache 只有 1,850 行，但当日 30 条决策都记录了 `bars_count` 260–269 且 `features_json.data_quality='daily_bar_cache'`（例：`SH688108` 记录 269 根，而模型允许 0 根）。1,290/3,900（33.08%）的决策记录的 bar 数多于模型允许值，且该现象在 2026-07-15 批量装载后完全消失。
4. `580,097` **不是行数**，而是「对×bar」计次；去重后的 (symbol,trade_date) 仅 **13,678** 行，而这 90 只股票在 cache 中共 47,692 行——原数字把物理足迹夸大了约 42 倍。
5. 方向也反了：「cutoff 时 bar 不存在」是**缺数据**，不是 look-ahead。真正的 look-ahead 探针（cutoff 之后日期的 bar 在 cutoff 时已存在）实测为 **0/3,900**。

**保留下来的真实问题（非 blocking，但必须解决）**：`daily_bar_cache` **没有任何 PIT 列**，`ON CONFLICT DO UPDATE` 就地改写 OHLC 且不动 `created_at`。因此 **2026-07-15 重建之前记录的任何决策，都无法针对它当时真正看到的 bar 进行重放**；该库根本无法支撑 look-ahead 审计。这是可复现性/可审计性缺陷。

补充实测（无泄漏证据）：`forecast_outcomes` 中 `写入时间 < observed_at` 的行为 **0**；1/3/5/10/20 五个 horizon 在 `2026-09-03 11:55:09` 起一批写入，即在成熟之后；成熟滞后实测 h=1 为 1–15 日、h=3 为 3–19、h=5 为 5–21、h=10 为 12–28、h=20 为 **26–42 日**。

### 7.3 时间契约提案（提交复核）

**契约 T1 — 字段语义（必须先于 M2 落地）**

| 字段 | 定义 | 落地方式 |
|---|---|---|
| `trade_date` | 交易发生日 | 已有 |
| `available_at` | **该行内容对决策者首次可得的时刻** = 该交易日收盘 + 声明的发布滞后（建议 T+0 18:00 CST，可配置），由交易日历推导，**回填时不得改写** | 新增/重定义；现有列改名为 `ingested_at` |
| `ingested_at` | 物理入库时刻 | 现 `available_at` / `fetched_at` 的真实语义 |
| `factor_vintage` | 该行 qfq 因子的计算日 | 新增（见 6.4） |
| `row_version` | 同一 (symbol,trade_date) 的重述序号 | 新增；配合双时态表或 append-only 影子表 |

**契约 T2 — 特征 / 选股 / 模拟决策**：只允许读取 `available_at <= cutoff` 的行；在 T1 落地前，**必须以 `trade_date < 决策日` 作为唯一近似**，并在运行清单中显式声明「本次运行未使用 PIT 数据，qfq 为当期视图」。

**契约 T3 — 标签**：前瞻收益与阶段结果标签**允许**使用 cutoff 之后的观测，但（a）只能在成熟之后写入，(b) 绝不可反向进入更早的特征或任何早于其成熟日的切分。现有 `forecast_outcomes` 已满足 (a)。

**契约 T4 — walk-forward 切分（两个候选方案，请复核选一）**

基础参数：稠密日历 536 天（2024-06-24..2026-09-03）；warm-up 取 120 日（d[0..119] = 2024-06-24..2024-12-17，仅供特征，永不作为样本）；可标注决策日 d[120..515] = 2024-12-18..2026-08-06，共 396 天；**2026-08-07..2026-09-03 为无法结算 20 日标签的尾部，必须丢弃**。

方案 A（4 折，test=50 日，purge=20 日，embargo=20 日）：

| 折 | 训练 | purge | 验证 | purge | 测试 | 标签结算日 |
|---|---|---|---|---|---|---|
| fold1 | 训练仅 56 天 | — | — | — | — | **不可用** |
| fold2 | 2024-12-18..2025-06-27（126d） | 20 | 2025-07-28..2025-09-19（40d） | 20 | 2025-10-28..2026-01-07（50d） | 2026-02-04 |
| fold3 | 2024-12-18..2025-10-13（196d） | 20 | 2025-11-11..2026-01-07（40d） | 20 | 2026-02-05..2026-04-24（50d） | 2026-05-27 |
| fold4 | 2024-12-18..2026-01-21（266d） | 20 | 2026-02-27..2026-04-24（40d） | 20 | 2026-05-28..2026-08-06（50d） | 2026-09-03 |

方案 B（3 折，test=70 日，测试功效更高，全部可用）：

| 折 | 训练 | 验证 | 测试 | 标签结算日 |
|---|---|---|---|---|
| fold1 | 2024-12-18..2025-03-28（66d） | 2025-04-29..2025-06-27 | 2025-07-28..2025-11-10 | 2025-12-08 |
| fold2 | 2024-12-18..2025-08-08（156d） | 2025-09-08..2025-11-10 | 2025-12-09..2026-03-26 | 2026-04-24 |
| fold3 | 2024-12-18..2025-12-22（246d） | 2026-01-22..2026-03-26 | 2026-04-27..2026-08-06 | 2026-09-03 |

**推荐：方案 B**。理由：方案 A 的 fold1 不可用，实际只有 3 折；方案 B 三折全可用且每折测试期更长。两方案的最终测试期都止于 2026-08-06，**该测试期不得用于任何规则或参数选择**。

**契约 T5 — purge / embargo（针对 20 日标签）**
- **purge = 20 个交易日**：训练集必须剔除其标签窗口与验证/测试期重叠的全部样本。20 日标签的重叠长度就是 20 个交易日，因此 purge 不得小于 20。
- **embargo = 20 个交易日**：在验证/测试期结束后再禁用 20 个交易日，防止通过横截面同期效应（同一市场日的共同因子）反向泄漏。
- 若同时使用 1/3/5/10/20 五个 horizon，**purge/embargo 一律按最长 horizon（20）取**，不得按各自 horizon 分别取，否则 20 日标签会跨过 5 日标签的 embargo。
- 附加约束：由于成熟滞后实测最高达 **42 个自然日**（h=20），任何「实时评估」的 as_of 必须比最后一个决策日晚至少 42 天，否则样本量会被系统性低估。

**契约 T6 — 250 日特征的限制**：250 日回看在当前数据下首次可算是 2025-07-03，剩余仅 286 天，不足以切分。**在回填完成前，禁止使用 >120 日回看的特征**；否则必须把 warm-up 提到 250 日并接受只有 1 折。
---

## 8. 既有研究记录与 746 条 legacy evaluations

### 8.1 账本现状（实测）

| 指标 | 值 | SQL |
|---|---|---|
| `forecast_decisions` | 20,082 行 / **155 个 decision_id 快照** / 31 个 `(scope,data_version)` vintage / 每快照 129.56 行 | `SELECT COUNT(*), COUNT(DISTINCT decision_id), COUNT(DISTINCT scope\|\|'~'\|\|data_version) FROM forecast_decisions;` |
| 决策覆盖的日历日 | **6 天**（2026-07-12 .. 2026-09-04）；窗口外 0 行 | `SELECT COUNT(DISTINCT substr(decision_cutoff,1,10)), MIN(...), MAX(...) FROM forecast_decisions;` |
| 主体数 | stock 90 只（占 5,556 只目录的 1.6%）/ sector 15 个 | `SELECT scope, COUNT(DISTINCT subject) FROM forecast_decisions GROUP BY 1;` |
| 最密集主体 | `SZ300166` 122 个快照 / 610 行 | `SELECT subject, COUNT(DISTINCT decision_id), COUNT(*) FROM forecast_decisions WHERE scope='stock' GROUP BY 1 ORDER BY 2 DESC;` |
| 最糟 vintage | `stock / 2026-07-15`：44 个快照、6,600 行、59 个主体，全部落在 22.19 小时内 | `SELECT scope, data_version, COUNT(DISTINCT decision_id), COUNT(*), COUNT(DISTINCT subject) FROM forecast_decisions GROUP BY 1,2 ORDER BY 3 DESC;` |
| `forecast_outcomes` | 18,682 行 / 30 个 observed 日；孤儿行 **0** | `SELECT COUNT(*) FROM forecast_outcomes o LEFT JOIN forecast_decisions d ON ... WHERE d.id IS NULL;` -> 0 |
| `forecast_evaluations` | **746 行**，其中 `status='ready'` **113 行**（stock 108 / sector 5） | `SELECT status, COUNT(*) FROM forecast_evaluations GROUP BY 1;` |
| 指标缺失度 | 746 行中 `brier_score` 非空 **17**、`precision_at_k` 非空 **151**、`spearman_rank_ic` 非空 **168** | `SELECT COUNT(*), COUNT(brier_score), COUNT(precision_at_k), COUNT(spearman_rank_ic) FROM forecast_evaluations;` |
| `forecast_decision_days` | 1 行（claimed_at 2026-09-04T12:43:08+08:00） | `SELECT COUNT(*), MIN(claimed_at), MAX(claimed_at) FROM forecast_decision_days;` |
| `forecast_decisions.probability` | stock 19,500 行**全为 NULL**；sector 582 行中 282 非空 | `SELECT scope, COUNT(*), COUNT(probability) FROM forecast_decisions GROUP BY 1;` |

### 8.2 样本 / 折数膨胀的量级（这是 746 行不可直接采信的核心原因）

以 canonical 快照策略（`app/forecasting/canonical.py`，M0 新增）重算同一 `as_of`：

| 存储值（`forecast_evaluations`） | canonical 真值 | 膨胀倍数 |
|---|---|---|
| stock，`as_of=2026-09-04T04:43:08Z`，`sample_count=3630`、`fold_count=121` | `canonical_samples_any_kind=150`、`canonical_folds_any_kind=5` | **24.2 倍 / 24.2 倍** |
| sector，`as_of=2026-09-04T03:24:31Z`，`sample_count=107`、`fold_count=22` | `canonical_samples=104`、`canonical_folds=24` | 约 1.03 倍（sector 的 `data_version` 就是决策瞬间，canonical 规则几乎不去重） |
| 全部 `ready` 行的 `canonical_folds_confirmed` | **0**（无一行） | — |

`forecast_outcomes` 侧同样：stock 每个 horizon 3,630 行中 canonical 仅 150 行、非 canonical 3,480 行。

M0 迁移演练已实测：迁移后历史 claim 变为 `run_kind='legacy_unknown'`，canonical 结果为 `{"inferred": 29, "confirmed": 0}`，stock canonical 快照由 6 降到 5。**即 A2 之后，official confirmed 证据将暂时为空。**

### 8.3 read-path 清单（谁在读这 746 行）

| 读取方 | 读取内容 | 实测状态 |
|---|---|---|
| `agent_calibration_proposals`（表内证据） | 10 条 `proposal_type='forecast_calibration'` 全部 `status='pending'`，`created_by='control_plane_forecast_feedback'`；其 `evidence_json` 各自引用一个 `evaluation_id`（如 `forecast-eval-3cdfb653978f1c8b8901afdd`），并复制了 `sample_count=3630 / fold_count=121` | **10/10 条的 `evidence_quality=None`、`canonical_policy_version=None`** —— 即它们引用的正是未经 canonical 去重的膨胀数字 |
| `ForecastCalibrationService.persist()` | 由 evaluation 指标决定是否生成校准提案 | M0 已改为 fail-closed：要求 `evidence_quality=='official'` **且** `canonical_policy_version==CANONICAL_POLICY_VERSION`；未提供者持久化为 NULL。**746 行的 policy 版本全部为 NULL**，因此在当前代码下它们已无法产生新提案 |
| `ForecastFeedbackService.evaluate()` | 默认闸门 `min_samples=20`、`min_folds=3` | 以 canonical confirmed 证据计算，stock 5 个 horizon 各只有 1 折、0 个成熟样本 -> **全部不过闸** |
| `agent_sandbox_experiments` | 1 行 | 需在 A2 中确认其是否引用上述提案 |
| cockpit / scoreboard 展示层 | 直接读取 `forecast_evaluations.status='ready'` 的 113 行 | **这是最危险的读取路径**：113 行中带正 Rank IC 的有 stock 1d/5d/10d 各 9 行、sector 1d/20d 各 1 行，若直接展示会呈现为「有效绩效」 |

### 8.4 A2 作为显式前置条件（不在本次审计中实施）

**主张**：在任何「官方历史评估 / scoreboard / 自动校准」消费持久化历史之前，A2 必须先落地，且必须满足：

1. **不删除、不重标**任何既有行（746 行原样保留，`canonical_policy_version` 保持 NULL 即为其身份标识）。
2. 过滤条件：只有同时满足 `run_kind='scheduled'`、`evidence_quality='official'`、`canonical_policy_version = CANONICAL_POLICY_VERSION`、且通过 canonical 快照去重的证据，才可进入官方口径。
3. **零 confirmed 证据必须显示为「证据不足」，而不是「成绩良好」**（Codex 在 M0 复核中的明确要求）。
4. 报告样本量时一律使用**有效独立决策日 / 折数**，不使用行数。以现有数据，stock 的诚实表述是「5 折、150 个成熟样本」，不是「121 折、3,630 个样本」。
5. `agent_calibration_proposals` 中现存的 10 条 pending 提案，在 A2 落地前**不得被批准**，因为它们引用的是膨胀证据。

**本次 M1 审计未实施 A2、未修改任何行、未变更任何标签。**

---

## 9. 回填方案（M2 提案，需用户显式授权后执行）

> 本节所有吞吐与体积均为**估算**，其推导输入在每行注明；未调用任何 provider、未下载任何数据。

### 9.1 精确缺口定义

| 缺口 | 时间范围 | 涉及符号 | 需新增行数（估算） | 依据 |
|---|---|---|---|---|
| **G-A 头部空档** | `2023-09-04 .. 2024-04-08`（约 146 个交易日，估算） | 窗口起点前已上市的 **5,167** 只（`list_date <= '2023-09-04'`） | **754,382**（= 5,167 × 146） | `SELECT COUNT(*) FROM instruments WHERE list_date<='2023-09-04' AND exchange IN ('SH','SZ','BJ');` -> 5167 |
| **G-A′ 头部空档上界** | 同上 | 全部 **5,561** 只在册股票 | **811,906** | 上界口径 |
| **G-B 爬坡段补全** | `2024-04-09 .. 2024-06-21`（50 个交易日） | 当前仅 935 只有数据，需补至约 5,100 只 | 约 **208,000**（估算：(5,100-935) × 50） | 3.1 节实测 |
| **G-C 内部空洞** | 分散 | **759** 只 | **4,673** | `backfill_08_holes.py` 实测 |
| **G-D′ 成交量单位修复（离线，本轮新增）** | 全窗口 | `market_history` 侧 **163,174 行 / 576 只** | **0 新增**，163,174 行原地 UPDATE（`volume` 除以 100 或 `volume_unit` 改为 `'share'`，二选一并写入 `bar_quality_issues`） | 见 5.1 A18。**必须与 G-D 同批执行**：若只补 `amount` 而不修 `volume_unit`，那些行的 `amount` 会正确、`volume` 仍错，任何按「成交量/流通股」计算换手率的特征依然被放大 100 倍 |
| **G-D 成交额修复（离线）** | 全窗口 | `market_history` 侧 | **0 新增**，1,652,090 行原地 UPDATE | `SELECT COUNT(*) FROM daily_bars d JOIN tl.daily_bar_cache c ON ... WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq';` -> 1652090 |
| **G-E 成交额修复（联网）** | 全窗口 | cache 侧仍缺 amount 的 **4,948** 只 | 0 新增，306,543 行原地 UPDATE | `SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE amount IS NULL AND length(trade_date)=10;` -> 4948 |
| **G-F 提升积压** | 全窗口 | — | **102,711** 行 cache→history 提升 | 见 2.2 |
| **G-G 北交所旧代码历史** | `2024-08-12` 之前 | 238 只 `920xxx` | **未知** | 需 `8xxxxx -> 920xxx` 映射；当前无任何数据源可提供 |
| **G-H 退市证券** | 全窗口 | **未知只数** | **未知** | 见第 4 节：无法从本地数据估算，必须外部登记表 |

### 9.2 可用 provider 与速率限制（明确区分已验证 / 未验证）

| provider | 现状（实测） | 是否带 `amount` | 速率 | 验证状态 |
|---|---|---|---|---|
| `akshare.stock_zh_a_daily`（新浪） | cache 主力：2,426,883 行 / 5,494 只 / 2024-06-04..2026-09-04；最近一次全量刷新 2026-09-03/04 | **是**（NULL 0 行） | 全量扫描均值 **0.776 只/秒**（5,020 只 / 6,470.1 秒）；瞬时区间 **0.45–0.79 只/秒** | **速率为我方日志实测**（`sina_resumable_20260903.log`）。**供应商侧配额未验证**——本次审计禁止探测 |
| `tonghuasun.local.quotes.candle`（同花顺本地插件） | 148,856 行 / 613 只 | 是 | 客户端自设节流：`min_request_interval` 默认 **1.0 秒/请求**（`app/config.py:46`，`tonghuasun_provider.py:173/179/276`）；实测全量刷新 0.519 只/秒、部分刷新 0.489、BJ 专项 0.451 | **客户端节流值已验证（读代码）；供应商侧真实限额未验证**。本次审计**未调用**该插件 |
| `tencent.fqkline.qfq` | 303,449 行 / 4,941 只 | **否**（100% NULL） | 未单独测量 | 仅作兜底；**不得用于需要成交额的回填** |
| `akshare.stock_zh_a_hist`（东方财富） | 8,254 行；最后一次成功写入 `2026-07-15T15:15:28`，最新 bar 停在 `2026-07-14` | 是 | — | **实测不可用**：`capital_flow_ingestion_runs` 32 次运行中仅 1 次 `completed`，26 次 `ProxyError`、5 次 `SSLError`（2026-07-19 .. 2026-09-04）。与项目既有记录一致 |
| `akshare.stock_zh_index_daily` | 1,076 行 / 2 只指数 | 否 | — | 仅用于 benchmark（`SH000300`/`SH000001`） |

**源优先级建议**：`sina_first`（与现有 `universe_backfill_checkpoint.json` 的 `source_policy` 一致）-> 同花顺本地插件（仅限新浪失败的符号，且受 1.0s 节流）-> 腾讯（**仅当不需要 amount**）。东方财富路径在恢复连通性前不纳入。

### 9.3 请求 / 行数 / 存储 / 运行时估算

存储单位成本（**dbstat 实测**）：`daily_bar_cache` 表 174.6 B/行、含索引 310.1 B/行；`daily_bars` 表 299.8 B/行、含索引 439.1 B/行。磁盘可用空间 **600 GiB**（`df -h /d` 实测，D: 705G 总 / 105G 已用）。

| 方案 | 符号数 | 请求数 | 新增行数 | 运行时（估算，0.45–0.79 只/秒） | trading_local 存储（表+索引） | market_history 存储（表+索引） | 合计 |
|---|---|---|---|---|---|---|---|
| **A. 仅补头部空档**（推荐起点） | 5,167 | 5,167（1 请求/符号，整段历史一次取回） | 754,382 | **1.8 – 3.2 小时** | 223 MiB | 316 MiB | **539 MiB** |
| A′. 头部空档全量上界 | 5,561 | 5,561 | 811,906 | 2.0 – 3.4 小时 | 240 MiB | 340 MiB | 580 MiB |
| **B. 全窗口重拉**（2023-09-04..2026-09-04） | 5,561 | 5,561 | 4,076,213 | **2.0 – 3.4 小时** | 1,205 MiB | 1,707 MiB | **2,912 MiB** |
| C. 仅补内部空洞 | 759 | 759 | 4,673 | 0.3 – 0.5 小时 | 1 MiB | 2 MiB | 3 MiB |
| D. 成交额修复（联网口径） | 4,948 | 4,948 | 0（306,543 行 UPDATE） | 1.7 – 3.1 小时 | 约 0（页面改写约 51 MiB） | 约 0 | 约 0 |
| D′. 成交额修复（**离线**，cache -> history） | 0 | **0** | 0（1,652,090 行 UPDATE） | **分钟级** | 0 | 0 | 0 |
| E. cache -> market_history 提升 | — | 0（DB 到 DB） | — | 头部空档 **6 分钟**；全窗口 **31 分钟**（实测 50.74 只/秒、2,161 行/秒） | — | — | — |

**关键判断**：方案 B（全窗口重拉）的运行时与方案 A 几乎相同（都是「每符号 1 个请求」），但同时解决 G-A、G-B、G-C、G-E 与第 6 节的**复权拼接问题**（一次性、单一 provider、单一因子 vintage 的全序列重建）。**代价仅为约 2.4 GiB 额外存储**，相对 600 GiB 可用空间可忽略。

**未纳入估算的项**：G-G（北交所旧代码）与 G-H（退市证券）**无法估算**，因为既没有映射表也没有退市登记来源。这两项必须作为独立的数据采购决策，不能包含在本次回填的工时/体积估算里。

### 9.4 重试与断点续传设计

现有能力（实测）：`backend/logs/universe_backfill_checkpoint.json` 记录 `days=500, batch_size=200, max_workers=3, source_policy='sina_first', universe_count=5555, status='running', last_processed_symbol='SH600351', processed=600`，即**已有按符号推进的断点机制**，但 `days=500` 正是造成 536/537 根固定预算的原因。

建议改动（M2 实施）：

1. `days` 改为**按日期范围**（`start_date`/`end_date`）而非固定根数——这是修复截断的根因。
2. 断点粒度保持「符号级」，并把 `(run_id, symbol, status, attempts, last_error, first_bar, last_bar, row_count)` 落到一张 `backfill_symbol_progress` 表，而不是仅 JSON 文件；JSON 无法并发安全。
3. 重试策略：单符号最多 3 次，指数退避 2s/8s/32s；连续 20 个符号失败即**暂停整轮**并置 `status='halted'`，等待人工判断（防止在 provider 限流时把整轮打成空数据——参照 `ingest_runs` 中 12 次写入 0 行的 `partial` 运行）。
4. 每轮写入必须绑定 `ingest_run_id`，并在结束时校验 `SELECT COUNT(*) FROM daily_bars WHERE ingest_run_id IS NULL;` = 0。
5. 每个符号回填后立即执行行级校验（OHLC 关系、日期格式、`amount IS NOT NULL`、根数 >= 期望值的 90%），失败行写入 `bar_quality_issues` 而**不是**写入 bar 表。
6. 并发上限沿用 `max_workers=3`，且同花顺路径必须继续走 `min_request_interval`（1.0s）节流；在供应商配额被验证之前不得提高。

### 9.5 staging 目标、备份、提升与回滚

| 环节 | 方案 | 依据 |
|---|---|---|
| **staging 目标** | 新文件 `D:\codex-A股交易\staging\market_history_staging.sqlite3` 与 `...\trading_local_staging.sqlite3`；回填**只写 staging**，生产库在整个 M2 期间保持只读 | M1/M2 门禁 |
| **备份** | 用 sqlite3 backup API 生成一致性副本（M0 演练已实测：1,284 MB 副本，5 张表计数完全保留，`quick_check` 通过） | M0 迁移演练记录 |
| **验收** | 在 staging 上跑 9.6 的 BEFORE/AFTER 全套；全部通过才允许提升 | — |
| **提升** | 优先「整文件替换」：停止所有写入者 -> 备份生产文件 -> 原子重命名 staging 文件 -> 复跑验收。次选：`ATTACH` + 事务内 upsert（可回滚但耗时更长） | — |
| **回滚** | 保留提升前的生产副本至少 7 天；回滚 = 停写 + 恢复文件 + 复跑 BEFORE 快照比对 | — |
| **禁止** | 不得在无备份的情况下 UPDATE 生产库；不得在同一事务里同时改两个库；不得让回填进程与 control-plane loop 同时写 `daily_bar_cache` | — |

### 9.6 验收查询（BEFORE / AFTER 对比）

完整脚本：`claude methods\_m1_evidence\backfill_acceptance.sql`；BEFORE 快照已固化于 `claude methods\_m1_evidence\backfill_acceptance_BEFORE.json`（采集时间 = 本次审计）。

**证明有收益（G 组）**

| 编号 | 查询 | BEFORE（实测） | AFTER 通过条件 |
|---|---|---|---|
| G1 | `SELECT COUNT(*), COUNT(DISTINCT symbol), COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2024-04-08';` | **0 / 0 / 0** | 行数 > 0，`sessions` 接近 146，`syms` 接近 5,167 |
| G2 | `SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04';` | **586** | 上升至 729–733 区间 |
| G3 | `SELECT COUNT(*), SUM(amount IS NULL) FROM daily_bars;` | 2,787,736 / **1,955,651** | `amount IS NULL` 降至 < 1% |
| G4 | 每股票根数直方图（见 `.sql` G4） | 众数 536/537 | 众数右移至 700+ |
| G5 | `SELECT COUNT(*) FROM daily_bars WHERE ingest_run_id IS NULL;` | 0 | 保持 0 |

**证明没有破坏（N 组）**

| 编号 | 查询 | BEFORE（实测） | AFTER 通过条件 |
|---|---|---|---|
| N1 | `market_history` 全部 CHECK 类计数（`high<low` 等 9 项） | 全部 **0** | 保持全 0 |
| N2 | 未触碰对照切片：`SELECT COUNT(*), ROUND(SUM(close),4), ROUND(SUM(COALESCE(amount,0)),2) FROM daily_bar_cache WHERE trade_date BETWEEN '2025-01-02' AND '2025-12-31';` | rows=**1,307,976**，close_sum=**30336732.878**，amt_sum=**398863106267567.44** | **必须逐位相同**（若回填也重写 2025 年，则此项改为「有意重写」并需单独批准） |
| N3 | `SELECT COUNT(*) FROM (SELECT symbol, trade_date, COUNT(*) c FROM daily_bar_cache GROUP BY 1,2 HAVING c>1);` | 0 | 保持 0 |
| N4 | `SELECT COUNT(*), SUM(adjustment_mode<>'qfq'), SUM(quality_status<>'ready'), SUM(amount IS NULL) FROM daily_bar_cache WHERE length(trade_date)=10;` | 2,891,616 / 1,209 / 133 / **307,619** | 前三项不上升，`amount IS NULL` 显著下降 |
| N5（新增） | `SELECT COUNT(*) FROM historical_backtest_runs;` | 39 | 保持 39（回填不得触碰研究记录） |
| N6（新增） | `SELECT COUNT(*) FROM forecast_evaluations;` | 746 | 保持 746 |
| N7（新增） | 源切换边界数：`SELECT COUNT(*) ...`（`adjrefute_01_control.py` 口径） | 6,294 个边界 / 5,333 只 | **应显著下降**；若不下降说明拼接问题未解决 |

**另需新增的验收项（本次审计新提）**

- V1：`SELECT COUNT(*) FROM daily_bar_cache WHERE high<low OR high<open OR high<close OR low>open OR low>close;` BEFORE = **3**，AFTER 必须 = 0（或这 3 行已进入 `bar_quality_issues`）。
- V2：`SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]';` BEFORE = **1**，AFTER 必须 = 0。
- V3：`SELECT COUNT(*) FROM daily_bar_cache WHERE symbol NOT GLOB '[A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9]';` BEFORE = **482**，AFTER 必须 = 0。
- V4：跨库 close 一致性：BEFORE 1,059,740 / 2,787,696 行差异 > 0.005，AFTER 必须 < 1%（否则说明两库仍是两个 vintage）。**口径提示**：不加 NULL 保护的朴素重算得到 2,787,736 个共同键 / 1,059,744 行 / 相对差 >1% 者 207,159（7.43%），与报告的 7.46% 相差 40 个键，属分母口径差异而非矛盾（见 `claude_independent_crosscheck.md`）。M2 必须在 V4 中**固定一种口径并写明**。
- **V5（本轮新增）：`volume_unit` 语义一致性。** `SELECT COUNT(*) FROM daily_bars b JOIN tl.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date WHERE c.volume>0 AND b.volume/c.volume BETWEEN 99 AND 101;` BEFORE = **163,174**，AFTER 必须 = **0**。
- **V6（本轮新增）：代理成交额量级检验。** 对全部 `amount IS NULL` 的行计算 `volume × 100 × (high+low+close)/3 / <同键 cache.amount>`，BEFORE 的均值为 **10.1491**、max **218.2048**；AFTER 该比值必须全部落在 **[0.5, 2.0]**，否则说明单位问题未解决。
- **V7（本轮新增）：vintage 保全。** 提升前必须确认 `market_history` 的旧文件已被完整备份并保留，因为它是 1,153,127 个历史 close 的唯一存世记录（见 2.2）。`SELECT COUNT(*) FROM daily_bars;` BEFORE = 2,787,736，其备份副本的该值必须一致。

---

## 10. 未解决问题与建议的 M2 方案

### 10.1 未解决问题（明确列出「不知道什么」）

| # | 未解决问题 | 为什么现在无法回答 | 需要什么才能回答 |
|---|---|---|---|
| U1 | 窗口内真实有多少个交易日？ | 两库均无交易日历表；2023-09-04..2024-04-08 无任何行，密度只能外推 | 权威交易所日历 |
| U2 | 窗口内到底有多少只股票退市？ | `delist_date` 全空，`universe_snapshots` 最早 2026-07-14，面板中无任何提前终止序列 | 交易所退市登记 / 带 as-of 的第三方 instrument master |
| U3 | 两库价格谁对？ | 两者同源，无第三方仲裁；本次禁止联网 | 独立 provider 抽样对照 |
| U4 | 4,673 个内部空洞里，停牌 / 抓取失败 / 退市前静默各占多少？ | 无停牌日历，`bar_quality_issues` 为 0 行 | 停牌日历 |
| U5 | 238 只北交所股票 2024-08-12 之前的历史在哪？ | 无 `8xxxxx -> 920xxx` 映射表 | 代码变更映射 + 旧代码历史源 |
| U6 | 任一历史日期的 ST 标记？ | 名称被每次刷新覆盖（单次 renamed=5,211） | 带生效区间的名称历史 |
| U7 | 新浪 / 同花顺的**供应商侧**真实速率限额？ | 本次禁止探测；0.45–0.79 只/秒是我方含自设节流的观测值 | M2 授权后的小规模探测 |
| U8 | 现有 10 条 pending 校准提案是否已被任何下游消费？ | `agent_sandbox_experiments` 仅 1 行，未展开核对 | A2 范围内的读取路径完整枚举 |
| U9 | 回测为何 39/39 零成交？ | 本次为只读审计，未运行引擎；`rejected_by_risk_count` 分别为 1,626 / 1,558，提示被风控全量拒绝 | M4 单独诊断（与数据问题正交） |
| U10 | A18 的 100 倍单位错误在**无法交叉验证的行**上是否也存在？ | 该检验依赖「同键在 cache 中有 `amount` 且 `volume>0`」；对两库同时缺 `amount` 的 **303,562 行**没有可比对基准，无法判定其 `volume_unit` 是否也是错的 | 一个带 `amount` 的独立源（新浪重拉即可顺带解决），或流通股本数据用于换手率交叉校验 |
| U11 | 两库价格分歧中，「provider 分歧」与「qfq 因子过期」各占多少？ | 两库 schema 都不记录逐行的因子 vintage（`factor_vintage` 不存在），无法把 61.4% 的值级分歧做正交分解 | 契约 T1 的 `factor_vintage` 列落地后，向前积累即可分解；历史部分不可追溯 |
| U12 | 稠密期内 36 个 95%–99% 覆盖日的缺席原因？ | 缺席股票的 `bar_quality_issues` 为 0 行、无停牌日历，与 U4 同因 | 停牌日历 + 入库时的缺席登记 |

### 10.2 建议的 M2 方案（单一推荐）

**方案名：单源全窗口重建（staging 优先）**

推荐执行 **9.3 的方案 B（全窗口重拉）**，而不是只补头部空档。理由：

1. 运行时相同（都是每符号 1 请求，2.0–3.4 小时估算），存储代价仅 2.9 GiB（可用 600 GiB）；
2. 只有全序列重拉才能同时消除**拼接边界**（6,294 个）与**混合 vintage**（两库 38% close 分歧）——补头部空档做不到这一点；
3. 单一 provider（新浪，带 `amount`）+ 单一 factor vintage，可以让「同一份数据可复现」第一次成立。

分步（每步都可独立验收、可回滚）：

| 步骤 | 内容 | 门禁 |
|---|---|---|
| M2.0 | 用户显式授权；备份两个生产库（sqlite3 backup API） | 授权 + 备份校验通过 |
| M2.1 | **零网络**先做两件事：(a) 把 `daily_bar_cache.amount` 离线补进 `market_history`（1,652,090 行）——已验证 `amount` 与复权无关（832,080 个双有值单元格**全部**一致到 <0.01%，0 个不一致；其中 25,504 个单元格 close 不同而 amount 相同，证明 amount 是复权不变的原始 CNY 成交额，跨 vintage 拷贝合法）；(b) 同批修正 A18 的 163,174 行 `volume_unit` 语义错误 | G3 通过；N1 保持全 0；**V5 = 0、V6 全部落入 [0.5, 2.0]** |
| M2.2 | 小规模探测：50 只股票的全窗口拉取，验证供应商速率（回答 U7）、验证根数达到约 733、验证 `amount` 非空 | 逐符号根数 >= 期望的 90% |
| M2.3 | 全量拉取到 **staging**，按 9.4 的断点/重试设计；同时写 `bar_quality_issues` | G1/G2/G4 通过，V1/V2/V3 = 0 |
| M2.4 | staging 上跑 9.6 全套 BEFORE/AFTER + V1–V4 | 全部通过 |
| M2.5 | 提升（整文件替换）+ 复跑验收 + 保留回滚副本 7 天 | N2/N5/N6 逐位不变 |
| M2.6 | 数据契约落地：`daily_bar_cache` 加 CHECK（重建表）、加 `available_at`/`ingested_at`/`factor_vintage`、symbol 前缀约束、指数移入独立表 | 第 5、6、7 节的契约项 |
| M2.7 | 开始按日持久化 `universe_snapshots` + 名称/ST 历史 + 停牌日历（**只能向前积累，不能追溯**） | — |

**M2 明确不做的事**：不采购退市登记（U2）与北交所旧代码历史（U5）——它们是独立的数据采购决策，需要单独授权与预算；在它们到位之前，**所有结果继续标注「survivor-only universe，偏差规模未知」**。

**M2 的一条硬性禁止（本轮复核新增）**：**不得删除、清空或就地覆盖现有的 `market_history.sqlite3`**。它不是冗余副本，而是 1,153,127 个已被 `daily_bar_cache` 就地覆盖的历史 close、以及 11,259 行已从 cache 词表中消失的 `tencent.newfqkline.qfq` 行的**唯一存世记录**（见 2.2）。M2.5 的「整文件替换」必须把旧文件改名归档（建议 `market_history.vintage_20260715_20260903.sqlite3`）并永久保留，而不是覆盖。同时，M2.6 的契约必须给 `daily_bar_cache` 增加 **append-only 的 vintage 保留能力**（`row_version` + 影子表），否则下一次重抓会重演同样的静默销毁。

**M2 完成后仍然为真的限制**：即使 M2 全部成功，`2023-09-04` 之前依然没有 warm-up 数据；若要 250 日回看特征在窗口起点即可用，回填起点必须提前到约 `2022-09`，这需要在 M2 授权时一并决定（额外约 250 个交易日 × 5,167 只 ≈ 130 万行，存储约 0.9 GiB，运行时不增加，因为仍是每符号 1 请求）。

---

## 11. 证据文件索引

全部文件位于 `D:\codex-A股交易\claude methods\_m1_evidence\`（**557** 个文件，均为本次审计新建的临时脚本与输出，未纳入版本控制）。所有脚本均以 `mode=ro` 打开数据库。

### 11.1 交付清单（Codex 优先阅读）

| 文件 | 内容 |
|---|---|
| `coverage_manifest.csv` | **每股票覆盖度清单**（list_date / eligible_sessions / observed_sessions / coverage_ratio / window_first / window_last） |
| `coverage_gap_shape.csv` | **每股票缺口形状**（leading / interior / trailing） |
| `coverage_FINDINGS.txt` | 覆盖度维度结论 |
| `pointintime_SUMMARY.txt` | **时间契约维度总结**（available_at、created_at、vintage、泄漏探针、fold 建议） |
| `pitrefute_FINDINGS.txt` | **对 74.7% 泄漏指控的 REFUTED 判决书** |
| `universe_verify_FINDINGS.txt` | universe / 幸存者偏差的对抗性复核判决 |
| `backfill_refute_VERDICT.txt` / `backfill_refute_VERDICT.sql` | 成交额缺失指控的 ADJUSTED 判决 |
| `backfill_acceptance.sql` / `backfill_acceptance_BEFORE.json` | **回填验收套件与 BEFORE 快照** |
| `backfill_10_estimate.out.txt` | 回填成本模型输出（含每行字节与吞吐来源） |
| `integrity_report.txt` .. `integrity_report4.txt` | 完整性审计逐节报告（含全部 SQL 与结果） |
| `lineage_table.txt` | 消费者到数据源的血缘表 |
| `claude_independent_crosscheck.md` | **主线（非 agent）对 15 项决定性数字的独立重算**，含 7.46% / 7.43% 分母口径差异说明 |
| `amtref_05_volumeunit.py` | **A18（100 倍成交量单位错误）的取数脚本** |
| `xstore_05.out.txt` | 两库**值级**分歧 61.4% 与单向陈旧性的输出 |
| `lineagerefute_02_rowhash.py` | 用 `_normalize_bar` + `_row_hash` 从 cache 重建 `market_history.row_hash` 的血缘证明 |
| `backfill_05_throughput.out.txt` | 100 次 `ingest_runs` 的逐次吞吐（0.45–0.79 只/秒区间的来源之一） |

### 11.2 按维度分组的全部文件

| 维度 | 文件 |
|---|---|
| 存储清单与血缘 | `lineage_probe.py`、`lineage_table.txt`、`lineage_reconcile.py`、`lineage_reconcile_output.txt`、`lineage_reconcile2.py`、`lineage_reconcile2_output.txt`、`lineage_reconcile3.py`、`lineage_reconcile3_output.txt`、`lineage_reconcile4.py`、`lineage_reconcile4_output.txt`、`lineage_reconcile5.py`、`lineage_reconcile5_output.txt`、`lineage_reconcile6.py`、`lineage_reconcile6_output.txt`、`lineage_refute_01.py`、`lineage_refute_02.py`、`lineage_refute_02_quick.py`、`lineage_refute_03.py`、`lineage_refute_03_divergence.py`、`lineage_refute_04.py`、`lineage_refute_04_values.py`、`lineage_refute_05_magnitude.py`、`refute_replica.sqlite3` |
| 窗口覆盖度 | `coverage_00_schema.py` .. `coverage_11_final.py`（12 个）、`coverage_10_fields.out.txt`、`coverage_FINDINGS.txt`、`coverage_manifest.csv`、`coverage_gap_shape.csv`、`win_00_schema.py` .. `win_06_sens.py`（7 个）、`win_recs.json`、`win_adv_00_schema.py` .. `win_adv_04_final.py`（5 个）、`window_refute_00_schema.py` .. `window_refute_04_final.py`（5 个）、`window_verif_A_schema.py` .. `window_verif_F_final.py`（6 个）、`refute_inventory_01.py` .. `refute_inventory_04.py` |
| 数据地板 / 备份核查 | `floorrefute_00_census.py`、`floorrefute_01_core.py`、`floorrefute_01_core.out.txt`、`floorrefute_02_elsewhere.py`、`floorrefute_02_elsewhere.out.txt`、`floorrefute_03_backups.py`、`floorrefute_03_backups.out.txt`、`floorrefute_04_final.py`、`floorrefute_04_final.out.txt` |
| universe 与幸存者偏差 | `survivorship_audit.py` .. `survivorship_audit7.py`（7 个）、`survivorship_out_part1.txt` .. `survivorship_out_part7.txt`（7 个）、`survivorship_evidence_all.txt`、`universe_verify_01.py`、`universe_verify_01_schema.py`、`universe_verify_02.py`、`universe_verify_02_probe.py`、`universe_verify_03.py`、`universe_verify_03_bars.py`、`universe_verify_04_final.py`、`universe_verify_FINDINGS.txt`、`verify_delist_01.py`、`verify_delist_02.py`、`verify_delist_03.py` |
| 完整性与异常 | `integrity_audit.py` .. `integrity_audit4.py`、`integrity_report.txt` .. `integrity_report4.txt`、`integrity_results.json` .. `integrity_results4.json`、`ohlc_refute_01_zeroprice.py`、`ohlc_refute_02_reach.py`、`ohlc_refute_03_repro.py`、`ohlcrefute_01_probe.py`/`.out.txt`、`ohlcrefute_02_probe.py`/`.out.txt`、`ohlcrefute_03_probe.py`/`.out.txt` |
| 复权与公司行动 | `adjustment_01_distributions.py`/`.out.txt`、`adjustment_02_probe.py`/`.out.txt`、`adjustment_03_mainpass.py`/`.out.txt`、`adjustment_03_events.json`、`adjustment_04_deepdive.py`/`.out.txt`、`adjustment_05_crosscheck.py`/`.out.txt`、`adjustment_06_final.py`/`.out.txt`、`adjustment_07_marketwide.py`、`adjustment_07_splice_marketwide.out.txt`、`adjustment_08_splice_control.py`、`adjverify_00_schema.py` .. `adjverify_04_stepvsshift.py`（5 个）、`adjrefute_00_probe.py`、`adjrefute_00_schema.py`、`adjrefute_01_control.py`/`.out.txt`、`adjrefute_01_independent.py`、`adjrefute_01_probe.py`、`adjrefute_02_core.py`、`adjrefute_02_explanations.py`、`adjrefute_02_namespace.py`、`adjrefute_03_ca_tables.py`、`adjrefute_03_levelshift.py`/`.out.txt`、`adjrefute_03_survivors.py`、`adjrefute_04_dates.py`、`adjrefute_04_limitclustering.py`、`adjrefute_04_restate.py`、`adjrefute_05_confirm.py`/`.out.txt`、`adjrefute_05_mechanism.py`、`adjrefute_05_verify_ipo.py`、`adjrefute_06_final.py`、`adjrefute_06b_final.py`、`adjrefute_v1_schema.py` .. `adjrefute_v6_final.py`（6 个）、`adjrefute_boundaries.json`、`adjrefute_nonb.json`、`adjrefute_over.json`、`adjrefute_over2.json`、`adjrefute_survivors.json`、`adjrefute_worst.json` |
| 时间契约 / PIT | `pointintime_00_schema.py` .. `pointintime_15_lagpct.py`（16 个脚本）、`pointintime_01_out.txt` .. `pointintime_15_out.txt`（15 个输出）、`pointintime_SUMMARY.txt`、`pit_v01_schema.py` .. `pit_v09_final.py`（9 个）、`pitrefute_00_schema.py`、`pitrefute_01_dist.py`、`pitrefute_01_independent.py`、`pitrefute_01_main.py`、`pitrefute_02_cutoff.py`、`pitrefute_02_main.py`、`pitrefute_02_wassystemlive.py`、`pitrefute_03_barscount.py`、`pitrefute_03_final.py`、`pitrefute_03_lineage.py`、`pitrefute_04_final.py`、`pitrefute_FINDINGS.txt`、`verify_availableat_01.py`、`verify_availableat_02.py`、`verify_availableat_03.py`、`refute_01_schema.py`、`refute_02_exec.py`、`refute_03_postmigration.py`、`refute_04_vintages.py` |
| 标签与预测账本（746 条） | `labels_00_schema.py`、`labels_01_ledger_audit.py`/`.out.txt`、`labels_02_canonical_cte.sql`、`labels_02_canonical_policy.py`/`.out.txt`、`labels_03_downstream.py`/`.out.txt`、`labels_04_remaining_evidence.py`/`.out.txt`、`labels_05_final_checks.py`/`.out.txt`、`labels_06_window_coverage.py`/`.out.txt`、`ledger_v01_schema.py` .. `ledger_v04_folds.py`（4 个）、`ledger_verify_00_schema.py`、`ledger_verify_01_core.py`、`ledger_verify_01_schema.py`、`ledger_verify_02_payload.py`、`ledger_verify_02_recompute.py`、`ledger_verify_03_population.py`、`ledger_verify_03_provenance.py`、`ledger_verify_04_rederive.py`、`ledger_verify_04_split.py` |
| 基准与回测记录 | `benchmark_00_schema.py` .. `benchmark_15_dup.py`（16 个）、`benchmark_ALL_OUTPUT.txt`、`benchmark_v1_meta.py` .. `benchmark_v6_softrisk.py`、`benchmark_v4_strong_bars.csv`、`benchmark_v6_strong_final.csv`、`benchadv_01_probe.py` .. `benchadv_08_verdict.py`（8 个）、`benchref_V1_inventory.py` .. `benchref_V7_verdict.py`（7 个）、`benchverify_00_schema.py` .. `benchverify_06_stale.py`（7 个） |
| 回填方案 | `backfill_01_inventory.py`、`backfill_02_storage.py`、`backfill_03_runs.py`、`backfill_04_sources.py`/`.out.txt`、`backfill_05_throughput.py`/`.out.txt`、`backfill_06_sessions.py`/`.out.txt`、`backfill_07_gap.py`/`.out.txt`、`backfill_08_holes.py`/`.out.txt`、`backfill_09_providers.py`/`.out.txt`、`backfill_10_estimate.py`/`.out.txt`、`backfill_11_acceptance.py`/`.out.txt`、`backfill_12_staleness.py`/`.out.txt`、`backfill_acceptance.sql`、`backfill_acceptance_BEFORE.json`、`backfill_ingest_runs_dump.json`、`backfill_import_runs_dump.json`、`backfill_capital_flow_ingestion_runs_dump.json`、`backfill_full_market_feature_runs_dump.json`、`backfill_ADV_01_sources.py`、`backfill_ADV_02_runs.py`、`backfill_ADV_03_amount.py`、`backfill_refute_00_tables.py` .. `backfill_refute_05_final.py`、`backfill_refute_A_schema.py` .. `backfill_refute_D_mechanism.py`、`backfill_refute_ths_01.py` .. `backfill_refute_ths_03.py`、`backfill_refute_VERDICT.sql`、`backfill_refute_VERDICT.txt`、`refute_amount_01.py`、`refute_amount_02.py`、`refute_amount_03.py` |

### 11.2b 第二轮对抗性复核新增文件（本次新增，共 8 组）

| 复核对象 | 文件 | 产出的判决 |
|---|---|---|
| 存储清单与血缘（重做） | `storeinv_V0_schema.py` .. `storeinv_V4_final.py`（5 个）、`lineagerefute_00_sanity.py` .. `lineagerefute_05_final.py`（6 个，含 `_02_rowhash.py` 的 SHA256 重建证明）、`lineage_adv_01_verify.py` .. `lineage_adv_03_final.py` | cache 独有键 103,880 -> **102,322**；缺失机制更正为 `bars_per_symbol` 截断；`hist_only_rows=0` 的推论被否证 |
| 跨库值级分歧 | `xstore_00_census.py` .. `xstore_05_final.py`（6 个脚本 + `xstore_01..05` 输出） | 值级分歧 **61.4%**、方向 100% 单向陈旧；market_history 为唯一存世 vintage |
| 窗口地板（三次独立重做） | `win3yr_v1_independent.py` .. `win3yr_v4_final.py`、`winadv2_01_probe.py` .. `winadv2_05_final.py`、`window_adv2_01_probe.py` .. `window_adv2_05_final.py`、`critic_01_gaps.py` .. `critic_05_lastgap.py` | 地板 2024-04-09 **confirmed**（三种日期比较法）；稠密日 536 -> **500（>=99% 在册口径）**；爬坡为单次回填 |
| universe / 幸存者（重做） | `univ2_00_probe.py` .. `univ2_04_final.py` + `univ2_VERDICT.sql`、`univref_00_schema.py` .. `univref_04_verdict.py` + `univref_VERDICT.sql`、`survivorverify_01_probe.py` .. `survivorverify_05_confirm.py` | snapshot 覆盖 4.83% -> **0.64%**；`list_date` 可消除 IPO 侧偏差；退市侧不可解 |
| 成交额与成交量单位 | `amtref_00_schema.py` .. `amtref_06_final.py`（7 个，`_05_volumeunit.py` 为 A18 的来源）、`refute_amount_01..03.py` | amount 缺失 **confirmed 并加重**；发现 **A18：163,174 行 100 倍单位错误** |
| 复权 / 拼接（重做） | `adjv2_00_probe.py` .. `adjv2_10_fixture.py`（11 个）+ `adjv2_events.json` / `adjv2_unexplained.json`、`adjverify2_00_probe.py` .. `adjverify2_07_backups.py`（16 个）+ `adjverify2_affected_615.csv` | 同源重述率按 fetch 批次分解（2026-07-15 批 2.18%、2026-07-19 批 5.82%、2026-09-03 批 0.014%）；27 只重述股票中 23 只比值近恒定、4 只随日期漂移 |
| OHLC / 符号命名空间 | `ohlcadv_01_zerodiv.py` .. `ohlcadv_04_types.py`、`dupsym_adv_01_probe.py` .. `dupsym_adv_04_verdict.py`、`verif_00_schema.py` .. `verif_03_final.py` | 零价 3 行与 482 行裸符号 **confirmed**；`ZeroDivisionError` 路径可算术复现 |
| 基准 / PIT / 账本（重做） | `benchref_V1..V7` + `benchref_v01..v08`（17 个）、`benchver_01..07` + `benchver_bars.pkl`、`pitverify_A_indep.py` .. `pitverify_C_alternatives.py`、`ledger_refute_01..03`、`ledger_v0..v4`、`backfill_verify_ths_*.py`（4 个） | SH000300 仅存于 cache **confirmed**；74.7% 泄漏指控 **REFUTED**；同花顺可达深度与 500 根上限复核 |
| 主线独立交叉复核 | `claude_independent_crosscheck.md` | 15 项决定性数字全部一致；记录 7.46% / 7.43% 的分母口径差异 |

### 11.3 外部只读引用（非本目录）

- `D:\codex-A股交易\backend\logs\current_a_share_universe.json`（5,556 成员，单一 `observed_at=2026-09-04T11:24:37+08:00`，全部 `status='active'`，0 个含 `退` 的名称）
- `D:\codex-A股交易\backend\logs\universe_backfill_checkpoint.json`（`days=500`、`batch_size=200`、`max_workers=3`、`source_policy='sina_first'`）
- `D:\codex-A股交易\backend\logs\instrument_catalog_refresh_heartbeat.json`（`renamed=5211`）
- `D:\codex-A股交易\backend\logs\sina_resumable_20260903.log`、`daily_close_refresh.log`、`refresh_to_close.log`（吞吐区间 0.45–0.79 只/秒的来源）

---

## 附录 A — 建议追加到 Progress Ledger 的条目（本次审计未修改 `THREE_YEAR_RESEARCH_EXECUTION_GOAL.md`）

> 依据安全边界，本次审计不修改既有方法论文档。以下条目请由用户或 Codex 决定是否追加至 `claude methods\THREE_YEAR_RESEARCH_EXECUTION_GOAL.md` 的 §10 Progress Ledger。

```
### 2026-09-05 — M1 三年数据就绪度只读审计（Claude）

- 里程碑：M1。状态：`ready_for_review`。
- 生产库未被写入、未迁移；未启动任何服务、未调用任何 provider、未提交/推送。所有连接 mode=ro。
- 核心结论：三年窗口 2023-09-04..2026-09-04 不成立。两库最早 trade_date 均为 2024-04-09，
  2023-09-04..2024-04-08（218 个自然日）为 0 行，warm-up 区亦为 0 行；全市场稠密起点为 2024-06-24。
  诚实可研究窗口为 2024-06-24..2026-09-03，共 536 个交易日（约 2.2 年）。
  以「当日在册 >=99%」口径则为 2024-08-13 起的 500 个交易日；非代表性交易日 87 天。
- 幸存者偏差 UNRESOLVED：instruments 的 delist_date 非空行为 0；universe_snapshots 仅 7 个不同日期，
  覆盖 7/1,097 自然日（0.64%）、5/586 交易日（0.85%）；5,566 只证券中无一序列在 2026 年之前终止。
  不给出任何全市场完整度百分比。
- 阻断项：(1) 两库 close 分歧 1,059,740/2,787,696（38.01%），值级分歧达 61.4% 且 100% 单向陈旧；
  (2) 数据源拼接造成 2,096 个 >0.5% 的价格水平位移，2024-08-13 单日造成约 +0.537pp 的虚假横截面收益；
  (3) available_at 为入库时钟，严格 PIT 过滤在 2026-06-30 返回 0 行；(4) daily_bar_cache 无任何 CHECK，
  存在 3 行零价 OHLC（会在 engine.py:231-233 触发 ZeroDivisionError）与 482 行无前缀重复代码；
  (5) 幸存者偏差；(6) 新增 A18：market_history 中 163,174 行 volume 为 100 倍却标注 volume_unit='hand'，
  使流动性代理放大约 100 倍（代理/真值均值 10.15、max 218.2），偏差方向为乐观。
- market_history 禁止删除：它是 1,153,127 个已被 cache 就地覆盖的历史 close 与 11,259 行已消失
  provider 的唯一存世记录；M2 的文件替换必须改名归档而非覆盖。
- 一项原指控被对抗性复核 REFUTED 并如实记录：「74.7% 的决策引用了 cutoff 时不存在的 bar」是
  daily_bar_cache 批量装载日历的产物（对照组 74.71%），不是时间泄漏证据。真实 look-ahead 探针为 0/3,900。
- 39 次 historical_backtest_runs 全部作废：39/39 零成交、final_cash==initial_cash，且其 created_at
  早于当前 cache 中每一行 bar 的 created_at。
- 746 条 legacy evaluations：stored sample 3,630/fold 121 对应 canonical 真值 150/5（24.2 倍膨胀），
  canonical confirmed 为 0。A2 仍为官方 scoreboard/自动校准消费的显式前置条件；本次未删除、未重标任何行。
- 交付物：`claude methods\M1_THREE_YEAR_DATA_READINESS.md`，证据 557 个文件位于
  `claude methods\_m1_evidence\`，含 coverage_manifest.csv 与 backfill_acceptance.sql / _BEFORE.json。
- 建议的 M2：单源全窗口重建（先零网络补 amount，再 50 只探测，再全量拉入 staging，验收后整文件提升）。
  估算 5,561 个请求、4,076,213 行、2.0–3.4 小时、约 2.9 GiB（磁盘可用 600 GiB）。速率为我方日志实测，
  供应商侧配额未验证。
- 下一步：等待 Codex 复核。生产迁移、批量写入、提交推送、服务启动、源策略变更均待单独授权。
```

## 附录 B — 本报告采纳的复核修正一览

| 原审计主张 | 复核判决 | 本报告采用值 |
|---|---|---|
| market_history 是派生的有损副本 | **confirmed（并强化）** | 采用；补充 amount 净损失 1,652,094 行、102,711 行属截断而非质量筛选 |
| 两库均止于 2024-04-09、缺口 156 工作日 / ~146 交易日 | **confirmed（范围调整）** | 头部空档 218 自然日；**全市场空档 292 自然日 / 210 工作日 / 约 196 交易日** |
| 回测硬绑定无约束库（blocking） | **adjusted** | 降为 medium；证券数 5,560；39 次运行零 P&L；切库会丢数据 |
| market_history 会让流动性数据损失 70% | **adjusted** | **净退化 59.26%（1,652,094 行）**；回退非静默；amount 与复权无关（比值恒 1.0） |
| 覆盖度中位数 0.9131、5,543 只可计算 | **adjusted** | 分母应为名义窗口：**上限 73.4%、中位 73.1%、0 只达 80%**；可计算 5,560 只、均值 0.912638 |
| 幸存者偏差 UNRESOLVED | **confirmed** | 采用；补充「7 个快照日期」「list_date 可消除 IPO 侧 look-ahead」 |
| delist_date 从不写入、退市无法定位时间 | **adjusted** | 「从不写入」成立；「无法定位时间」**否证**（末 bar + 冻结的 updated_at 可定位）；成因归因更正 |
| 爬坡是 watchlist 逐步纳入 | **adjusted** | 实为**固定根数回填 + 停牌**；截断比例更正为 5,132/5,132 = 100%；用词由「伪造」改为「截断」 |
| 74.7% 决策引用 cutoff 时不存在的 bar（blocking） | **REFUTED** | 不作为泄漏证据；保留「cache 无 PIT 列、无法重放」的可审计性缺陷 |
| market_history 的 provider 列 61% 是错的 | **adjusted** | 应为 **58.78%**，且性质是「陈旧」而非「标错」；补救是重新提升 |

**第二轮复核（本次新增，均已在正文对应处采用）**

| 原主张 | 复核判决 | 本报告采用值 / 处置 |
|---|---|---|
| cache 独有键 103,880 行 | **adjusted** | **102,322**（剔除 482 行裸 6 位重复表示 + 1,076 行指数）；见 2.2 |
| 缺失是 seeder 的质量筛选 | **adjusted** | 是 **`bars_per_symbol` 近期截断**：102,711 行 ready+qfq 仍缺失，其中 99,610 行早于该符号被保留的最早 bar；4,688 只符号恰为 536 根；见 2.2 |
| `hist_only_rows=0` ⇒ market_history 无独有信息 | **REFUTED（推论层面）** | 键级为 0，**值级 1,710,969 / 2,787,736 = 61.4% 不同且 100% 单向陈旧**；market_history 是被覆盖 vintage 的唯一存世记录，**禁止删除**；见 2.2、10.2 |
| 536 个全市场稠密交易日 | **adjusted** | 以当日在册为分母只有 **500 天 >=99%**，另 36 天为 95.26%–99.0%；**非代表性交易日 87 天而非 51 天**；见 1.1、3.1 |
| 爬坡 = watchlist 逐步纳入 / 爬坡解释全部缺口 | **adjusted** | 爬坡 4,682 行全部写于 `2026-07-15 06:11:58–11:21:06` 一次回填，无任何股票 bar 创建于 2026 年之前；爬坡为 **50** 天并只解释 **94–96%** 的缺口；见 3.1、3.2 |
| universe_snapshots 覆盖窗口最后 53 天（4.83%） | **adjusted** | 只有 **7 个不同日期**：**7/1,097 自然日 = 0.64%**、**5/586 交易日 = 0.85%**；未覆盖 1,090 自然日；原值高估覆盖度约 7.5 倍；见 4.1 |
| market_history 缺 amount 会使流动性数据损失（blocking） | **confirmed（并加重）** | 净退化 1,652,094 行；**且代理回退不安全**——163,174 行 `volume` 为 100 倍而 `volume_unit='hand'`，代理/真值比均值 10.15、max 218.2，偏差方向为乐观；新增异常 **A18（阻断）**、A19，新增验收项 V5/V6；见 5.1、9.6 |
| amount 缺失是持续性管线缺陷 | **adjusted** | 是**已停止扩大的历史积压**：`2024-06..2025-12` 为 97.5% NULL，`2026-02` 起降至 5.1%，99.5% 的可修复单元早于 2026-02；补救为一次性回填而非管线重构；见 5.1 A4 |
| 窗口前已上市股票 5,268 只 | **adjusted（口径）** | 复核以 list/delist 感知分母得 **5,286** 只（max 覆盖率 0.916525，>=0.95 为 0）；结论不变，两值并列记录；见 3.2 |
| 回测口径证券数 5,566 | **adjusted** | **5,560** 只可交易股票；39 次运行 `total_return=0.0`、6,915 行权益全部恒为 100000.0；见 2.3 |
