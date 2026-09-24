# 复算脚本

诊断报告里的每个数字都可以用这三个脚本重跑。在 `backend/` 目录下用项目 venv 执行。

```bash
cd D:\codex-A股交易\backend
.venv\Scripts\python.exe -X utf8 "..\claude methods\verify\repro_backtest_zero_trades.py"
.venv\Scripts\python.exe -X utf8 "..\claude methods\verify\measure_rank_bucket_returns.py"
.venv\Scripts\python.exe -X utf8 "..\claude methods\verify\measure_feature_ic.py"
```

| 脚本 | 验证的结论 |
|---|---|
| `repro_backtest_zero_trades.py` | 完美灯盏 K 线在回测字段集合下只得 44.44 分 → rejected；补上 pb/market_cap 后 100 分 → strong |
| `measure_rank_bucket_returns.py` | Top5 次日基准中性超额 −2.25%、胜率 35.6%，随排名下降反而变好 |
| `measure_feature_ic.py` | 全部动量特征 1 日 IC 为负（ma5_slope −0.40），回撤类特征为正（+0.26），综合分 IC −0.18 |

三个脚本都是**只读**（`mode=ro`），不会写任何数据。
修完 P0 之后重跑，数字应该变化 —— 这就是修复是否生效的判据。

## 2026-09-03 新增

| 脚本 | 验证的结论 |
|---|---|
| `backtest_sample_250.py` | 跨板块均匀抽 250 只、2025-09 → 2026-07，逐规则统计 + 入场漏斗（signal → attempt → fill）+ 流动性依据。修复前 0 成交，修复后 4 signal / 4 fill / 4 closed |
| `measure_dengzhan_signal_rarity.py` | 全市场 5,534 只、2024-12 → 2026-07：S0（低位+涨停+市值 50–200 亿）只有 145 次；同根 K 线量比≥1.5 为 77 次，5 日内为 124 次；67% 集中在 2026-06/07 |
| `profile_backtest.py` | cProfile：修复前 91% 时间在 `MarketRegimeService.get_latest_regime`（`lower(symbol)` 使索引失效） |

`backtest_sample_250.py` 需要 `symbol_fundamental_snapshot` 表已由 `scripts/ingest_fundamentals.py --apply` 填充；它以 `allow_projected_fundamentals=True` 运行，结果标记 `fundamental_point_in_time=False`。
