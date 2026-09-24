# 同花顺 M2 历史解析实现与实测

本交付由 Codex 完成。状态为实现及解析集成验证通过，尚不构成数据源复权/单位资格确认或 M2 完成。没有网络请求、数据库打开、账户访问、交易操作、Claude 派单或旧证据修改。

## 实现范围

- `backend/app/data/tonghuasun_provider.py` 仅修改证券代码解析及日线请求标识：显式 SH/SZ/BJ 优先于数字前缀推断；互相冲突或无效标识拒绝；只发送一个 `fullCode`，不同时提交会被宿主分别解析的裸 `code` / `codes`。
- 日常 `get_daily_bars` 保留原有最多 500 行、全量验证后取尾、股除以 100 转为手、默认 qfq 和现有市场端点。这并不自动给日常接口添加原生指数路由。
- 新 `backend/app/data/tonghuasun_history.py` 是无配置读取、无 transport、无数据库的纯请求构造/原始响应解析模块。按完整日期窗口返回，不作 500 行截断，不重采样、不补点、不去重、不缩小交易日域、不换算量额单位。
- 每个返回行含 `point_index`，与原始 `items[0].points` 序号一一对应；保留 `raw_sha256`、响应原始证券标识、请求复权、响应复权回显和异常名称原值。采集时间由绑定原始字节哈希的 capture receipt 提供，不由解析器伪造。
- 双项目标识、错误 host/fullCode、重复 JSON 键、非法数值、乱序/重复/窗口外日期、交易日与 timestampUtc 不一致均拒绝。缺失/额外 expected 日期完整报告，不能通过 coverage。指数成交额缺失时保留 None；股票成交额缺失拒绝。

## 指数身份与名称

证券规范明确区分项目 canonical、服务响应 fullCode 与宿主 hostFullCode。原生指数必须显式传入映射证据说明；解析器只核验响应是否与该规范一致，不证明映射证据充分性。

| 项目 canonical | 本次原始响应 fullCode | 本次原始响应 hostFullCode |
| --- | --- | --- |
| SH000300 | 399300.SZ | USZI399300 |
| SH000001 | 10001.SH | USHI1A0001 |

SH000001 的来源格式是资格采集 job 2 实际观测，不是按规则删除字母 A。生产代码没有通用删字母转换。只有显式给定 `response_full_code="10001.SH"` 的规范能接受该响应；以 `1A0001.SH` 为预期的规范拒绝同一响应。host 或 canonical 不被覆盖。项目与宿主指数的语义映射仍由单独的来源证据审查负责。

全部 8 个响应的 7,824 个 point 名称都是异常私用区字符；解析结果将可展示的 `source_name` 设为 None，并保留 `raw_security_name` 和逐点 `invalid_source_name`。没有拿 manifest 名称替换为所谓供应商原始名称。

## 验证

2026-09-10 本地执行：

```powershell
.\backend\.venv\Scripts\python.exe -B backend/tests/test_tonghuasun_history.py
.\backend\.venv\Scripts\python.exe -B 'claude methods/_m2_codex_implementation_20260910/verify_provider_capture.py'
git diff --check -- backend/app/data/tonghuasun_provider.py backend/app/data/tonghuasun_history.py backend/tests/test_tonghuasun_history.py
```

最终版本合成测试 **20/20 PASS**，unittest 执行时间 0.346 秒，命令退出 0。测试直接执行纯模块，日常兼容性测试仅提取受改动方法并注入合成 transport/frame，避免 pytest conftest 初始化生产应用。没有修改已有 dirty `test_tonghuasun_provider.py`。

真实 raw 解析脚本退出 0：资格采集 job 1/2 两指数 none、job 3/4/5 SH600011 的 none/qfq/hfq、job 6/7/8 BJ920000 的 none/qfq/hfq 全部逐字节哈希匹配 capture receipt，全部严格解析通过。每份 978 行，含 728 研究日与 250 warmup 日，窗口 2022-08-24 至 2026-09-04，无缺日、额外日或缺失 amount。没有把合成测试当作数据源验收。

固定 calendar SHA256 为 `f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656`。日历原文是 YYYYMMDD，离线脚本仅规范格式为 ISO 日期后作固定区间比较。原始日历未改动。

详细结果与各输入/代码哈希在 `provider_raw_parse_summary.json`。该文件只证明纯解析集成；`vendor_basis`、`volume_unit`、`amount_unit` 仍为 unverified，`mapping_verified` / `eligible` / `source_qualified` / `M2_complete` 均为 false。请求枚举或回显不会直接改为资格通过。

`verify_provider_capture.py` 默认以 x 模式创建结果，重跑需传入新的结果路径，避免覆盖旧验证证据。

## 独立审查边界及回退

本说明是实现者自测记录，不冒称独立审查。另对 root 的 `collect_remaining.py` / `test_collect_remaining.py` 做只读静态复核：固定 48 剩余股票原始隔离采集范围内未发现阻断项；意外非对象 JSON 可能遗漏统一 summary 的问题已反馈给 root，该情况不会触发追加请求或落库。

回退仅撤销上述 provider 的两处行为修改，并移除本阶段新纯模块/新测试；保留原始 capture、原始审计、既有 dirty 测试及其他用户更改。没有生产数据需要回退。

## Root 后续集成复核

2026-09-10 上午，root 另对现有 `test_tonghuasun_provider.py` 做最小配套修改：请求应只有 `fullCode`，因此把旧 `codes` 数组断言改为不存在，并删除 `security.code` 的旧期待。与 baseline 原始 dirty 测试逐内容比较，仅这两处变化；既有用户修改保留。前文“未修改已有 dirty 测试”描述的是解析实现者当时的交付，此处记录后续集成变化。

通过 `run_provider_regression.py` 执行现有完整 provider 测试，**34/34 PASS，21.36 秒**，退出 0；另有一条现存 Starlette/httpx 弃用提示。测试守卫限制 SQLite 只能访问本次临时目录，拒绝实际网络连接，仅允许 Windows asyncio 的标准库内部 socket pair。结果记录 7 次隔离 SQLite 连接、0 次外部数据库尝试、0 次真实网络尝试，`live_trading_enabled=false`。原始测试收据位于 `test_runtime/provider_20260910T010627948466Z/result.json`。
