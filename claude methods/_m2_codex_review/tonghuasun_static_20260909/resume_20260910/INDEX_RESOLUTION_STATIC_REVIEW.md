# 指数请求身份分叉：独立静态复核

日期：2026-09-10，Asia/Taipei。执行者：Codex 子代理；无网络请求、配置令牌读取、目标 DLL 加载或目标方法执行。仅在本次 `resume_20260910` 新增本报告及静态 IL 证据，未改冻结的旧 42 项。

## 结论

原 job 5 同时提交 `security.fullCode=000300.SH`、`security.code=000300` 与 `codes=[000300.SH]`。插件会把这些字段合并为多个待解析字符串，**显式交易所不会覆盖或约束另一个裸码字段**。因此出现 `USHA000300` 与 `USZA000300` 两个证券有明确的静态实现解释，不是服务器已经返回一份可接受的 SH000300 指数数据。

**仅删除裸码或去重仍不够。** 当前插件将 `.SH` 固定解析到 `USHA`；本机默认指数配置使用的是 `USHI` / `USZI`。停止后的原 job 6 仍未发送，本报告不修改请求计划或授权额外请求。

## 与实测对应的解析链

1. `HevoQuoteSeriesSupport.ResolveSecurities`（token `0x06000265`）依次加入非空的 `HostFullCode`、`FullCode`、`Code`，再加入 `codes`。本次传入 `ResolveMany` 的标识相当于 `[000300.SH, 000300, 000300.SH]`。该路径没有使用单独的 `HostMarketCode` 字段去约束裸码。证据：[IL 第 516 行](</D:/codex-A股交易/claude methods/_m2_codex_review/tonghuasun_static_20260909/resume_20260910/index_resolution_static_il.txt:516>)；原冻结 `ths_il_evidence.txt` 第 2971–3029 行也已有此方法。
2. `ResolveMany`（`0x060002AB`）逐项调用 `TryResolveSingle`，最后按解析所得 `Security.ToString()` 分组取首项，重复的 SH 身份会合并，不同的 SH/SZ 身份不会。证据：新 IL 第 574 行起；分组委托 token `0x060005E4` / `0x060005E5`。
3. `TryParseWithExchange`（`0x060002B1`）将 `SH` 固定映射 `USHA`，将 `SZ` 映射 `USZA`，将 `BJ` 映射 `USTM`。它没有根据 `000300` 识别指数并选择指数市场。证据：新 IL 第 787 行起，`IL_0089..00A0`。
4. 裸码经 `NormalizeFullCode` → `BuildStrictMainlandCandidates`（`0x060002BB`）；`0/2/3` 开头分支先产生 `USZA+code`，再产生 `code+.SZ`。这解释裸码 `000300` 的深圳身份。证据：新 IL 第 1081 行起，`IL_00F5..0141`。

实测 `capture/response_5.bin` 返回 `ok=true`，但 items 是 `000300.SH / USHA / USHA000300` 与 `000300.SZ / USZA / USZA000300` 两项，各自 `points=[]`。严格单证券门禁因此停止。HTTP 200 或两个空 points 数组不能证明沪深300的正确本机标识没有历史数据。

固定 Python SDK `distribution/sdk/python/src/tonghuasun_codex/client.py:557–561` 的 `_security` 也同时构造裸 `code` 和 `fullCode`。这个字段组合来自已有接口用法，但它在本插件解析实现中存在上述指数歧义。未修改 SDK 或生产适配器。

## 已有指数标识证据与支持边界

本机非用户目录的静态配置直接列出：

| 文件 | 位置 | 静态记录 |
|---|---|---|
| `D:\同花顺软件\同花顺远航版\bin\data\public\NewIndexConfig.xml` | 11 | `Name="沪深300" Code="399300" Market="USZI"` |
| `D:\同花顺软件\同花顺远航版\bin\modules\Tools\LocalSecuritiesConfig.xml` | 8 | `market="USZI" code="399300"` |
| 同一 `NewIndexConfig.xml` | 4、12 | 沪指 `USHI / 1A0001`、上证50 `USHI / 1B0016`，说明不能假定指数 host code 恒为六位数字 |

这证明安装配置存在原生指数市场和编码，不证明 `SH000300` 合同键可不经核实直接替换为 `USZI399300`，也没有证明该标识的可用历史、价格口径或全区间身份。

插件 `NormalizeExchange`（`0x060000CF`，新 IL 第 91 行起）明确识别 `USHI→SH` 与 `USZI→SZ`；`TryExtractHostMarketCode` / `LooksLikeHostSecurityCode` 可识别原生前缀。`MainlandPrefixes` 的快捷构造表只有 6 项，确实未列 USHI/USZI，但这不是整个解析器的拒绝清单：`TryParseFullCode` 后备路径会调用客户端 `Security.FromString(string)`。

静态继续追到 `Hevo.Core.DataModel.dll`：`Security.FromString`（`0x06000130`）经 `A.b` 解析器注册表进入 `A.f::A`（`0x060001D3`，新 IL 第 1652 行），后者对 U/u 开头字符串按前 4 字符建立 Market，其余建立 Code。因此 USHI/USZI 原生拼接格式存在实际语法解析路径。**语法可解析不等于某个代码有行情，也不等于其与项目基准身份对应关系已验收。**

后续隔离修正应避免把裸 code、通用 fullCode 与不同语义的 hostFullCode 一起累加；不能只给现有 payload 加一个 `hostMarketCode` 字段就声称已修正。具体指数身份与请求方案应先独立核实并保持原始 job 5 失败证据；本轮未设计或发送替代行情请求。

## 固定来源

沿用原冻结 `inspect_ths_il.ps1`，SHA-256 `87b64fc70739bd07c1d4515f3988b4cf1d73495c2bac83d03d894b261ffb4930`。它使用 PEReader / ECMA-335 读取文件，不执行目标程序集；IL 中出现的反射 Invoke 是被审代码内容，不是审查器执行了该调用。

- 新 `index_resolution_static_il.txt`：1679 行；SHA-256 `cbd044b914906079c31e40fe7b871c2595b16df2c681c00d37505f911a83c61d`。
- `ThsPlugin.Adapters.Hevo.dll`：SHA-256 `19fbd89528ebe933cee267de34d63171afd47aef230132bd3574a3b81883469b`，MVID `a1601fcd-097a-49b3-9a0a-cdabfd43b0e5`。
- `Hevo.Core.DataModel.dll`：SHA-256 `5c64b1444f379c54067d0dc37c36cf019ed389b958e75665ae802b657ba17167`，MVID `5039f7eb-3e87-4879-a9c5-b9467745e9c0`。
- `NewIndexConfig.xml`：SHA-256 `daf3167c5d33acb41a325deee2b5c28232920bfd02c594b6d1e6cdb9b0207da1`。
- `LocalSecuritiesConfig.xml`：SHA-256 `f5c3754407259e3203ce0bec26a411350e4d369f871a75305fe7fc82ad0b41c6`。

原授权累计已发送 5 次，其中旧 1 次为认证失败、本次 4 次；原 job 6 未发。正向股票覆盖观测与指数解析失败应分开保留；本报告没有将 M2、价格口径或 eligibility 标记为通过。
