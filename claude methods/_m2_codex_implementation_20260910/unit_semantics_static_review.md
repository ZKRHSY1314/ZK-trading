# 同花顺量额单位的本地静态证据

2026-09-10，Codex 限域只读检查。结论：已找到插件字段到宿主字段及 K 线展示换算的明确链，支持本次沪深京股票 `transaction_volume` 是基础股数，展示时除以每手 100 股。`transaction_amount` 是宿主成交额字段且插件不作量额缩放；本次静态资料没有直接给出“人民币元”标签，金额的绝对币种/单位仍需官方成交记录锚点。未因量额同倍率可以保持价格包络而判单位 PASS。

## 已核实的链

| 环节 | 静态原文 / 行号 |
| --- | --- |
| 插件成交量请求别名 | `unit_semantics_static_plugin_il.txt:163`，`transaction_volume` 映射到 `Hevo.DataModel.Business.QuoteFields.get_transaction_volume`；对应 token `0x0600022D` 的静态字典 |
| 插件成交额请求别名 | 同文件 `:147`，`transaction_amount` 映射到 `get_transaction_amount` |
| 原始数值映射 | 同文件 `:197` 起 `Normalize` → `NormalizePrimitive`；有限 Double/Single/Decimal/整数直接返回原值，仅空值、NaN、Infinity 和 sentinel 变 null，代码/证券标识字符串另有处理。无成交量/成交额除 100 或乘除 10000 的逻辑 |
| 宿主字段编号 | `unit_semantics_static_fields_il.txt:98`，volume=`GetQuoteField(13,1)`；`:132`，amount=`GetQuoteField(19,1)` |
| 字段说明 | DLL 内嵌 `QuoteFieldData.xml:329` 为 13 / 总量 / Volume，`:344` 为 19 / 成交额 / Turnover，均 `data_type=5`。同 XML 的这两项没有 unit 或 currency 属性 |
| 每手基础股数 | DLL 内嵌 `MarketData.xml` 中 USHA（沪市A股，`:7`）、USZA（深市A股，`:43`）、USTM（北京A股，`:275`）、USHI（沪市指数，`:3`）、USZI（深市指数，`:39`）均 `ShareCountPerUnit="100"` |
| 元数据实际读取 | `unit_semantics_static_constants_il.txt:466` 起，`DataModelConstants.c` 从 `Data.MarketData.xml` 取 `ShareCountPerUnit`，转换 UInt32 后设置 `MarketInfo.ShareCountPerUnit`，不是仅存在未使用的 XML 标签 |
| 股票 K 线成交量柱 | `unit_semantics_static_candle_data_il.txt:630` 读取同一 `transaction_volume` FieldValue；`:658` 附近将其除以当前 `Market.Info.ShareCountPerUnit` 后构建 ColumnPoint。无中间 10000 倍变换 |
| 成交量标题 | 同文件 `:883` 读取 volume 并不缩放地存入 value1（`:965`）；`unit_semantics_static_candle_title_il.txt:736` 取该值调用 `MakeVolumeUnit` |
| 成交量标题换算 | `unit_semantics_static_candle_indicator_il.txt:83`，`MakeVolumeUnit` 默认 divisor=100，存在市场 Info 时改用 ShareCountPerUnit，除完才作万/亿显示缩写 |
| 成交额展示 | `unit_semantics_static_candle_data_il.txt:294` 直接读取 amount，`:314` 附近把原值传入 ColumnPoint；`unit_semantics_static_candle_title_il.txt:448` 的 `GetAmountStr` 仅按 1e4 / 1e8 / 1e12 分别显示万 / 亿 / 万亿，未直接标明人民币元 |

`QuoteFields.transaction_volume_shou` 是另一个展示名称为“总手”的 QuoteField，但编号仍为 13（`unit_semantics_static_fields_il.txt:102`）。这表明字段名或中文标题本身不能单独用来判量纲；上述判定使用的是实际读取/除数链。

插件 `CreatePoint` 的原始调用链已存在于旧只读证据 `../_m2_codex_review/tonghuasun_static_20260909/ths_il_evidence.txt:1671`：`TryReadQuoteFieldValue` → `HevoQuoteValueNormalizer.Normalize` → response values。该旧文件未改动。

## 固定二进制与资源验证

- 插件 `ThsPlugin.Adapters.Hevo.dll`：`19fbd89528ebe933cee267de34d63171afd47aef230132bd3574a3b81883469b`。
- `Hevo.DataModel.Business.dll`：`6cbcc287f5e11abf860f912da7a923b6141e0759416593fc5664576169d56db7`。
- `Hevo.Core.DataModel.dll`：`5c64b1444f379c54067d0dc37c36cf019ed389b958e75665ae802b657ba17167`。
- `Hevo.DataVisualization.dll`：`5f844304512b56969feb31081b992b67db2121251c113bce145edc61a04a8df9`。
- 提取的 MarketData.xml：39,299 字节，`f8e251d1e74bef48d5d7ede03fc6e32e8ea288c218098515e0bf46b6bcffc2a6`。
- 提取的 QuoteFieldData.xml：351,647 字节，`7380b29bb34d3d7f1ea7a31f88527ea2db04b88b17eb3e3b11ec9be427d97ce8`。

采用已冻结 `inspect_ths_il.ps1`（SHA `87b64fc70739bd07c1d4515f3988b4cf1d73495c2bac83d03d894b261ffb4930`）及本阶段 `unit_semantics_static_resources.ps1`，只读取 PE / ECMA-335 元数据和内嵌资源字节，不 Load/Invoke 目标 DLL。新的 Python `verify_unit_semantics_static.py` 独立读取 PE section table，把资源 RVA 25564 映射到原始文件位置，核对长度与提取 XML 字节全等，并检查上述五市场/两个字段，退出 0。

核对结果在 `unit_semantics_static_verification.json`。所有输出哈希及 DLL 来源由文件头/该 JSON 记录。提取工具起初将 UInt64 resource offset 传给有 int/string 重载的 GetSectionData，PowerShell 选择了错误重载而返回空 block；改为显式 `[int]` 后成功。失败尝试没有提取出错误 XML，也没有运行目标代码；两份只有头部的失败输出保留，正式结果为 `unit_semantics_static_resources_extracted.txt`。

## 判定边界

该证据闭合当前安装版本、当前三个股票 host market 的 volume 字段和每手换算语义；同时给官方同日绝对量额比对提供明确字段对应。它不单独证明历史服务每一日都正确执行该契约，不证明供应商复权、不证明 BJ 历史主体连续性，也不把指数成交量变成可交易股数。完整数据资格仍要结合实际原始响应与独立官方锚点。

本次对 MarketData、DataModel.Business、DataVisualization、Core.Common、DataVisualization.Component、DataVisualization.Interface、Core、Core.DataModel 和插件做了目标类型名/方法名检索及必要 IL 深入。没有匹配的有限类型名检索只代表该范围未命中，不代表客户端不存在其他单位证据。没有读 users/config 凭据、HTTP、账户数据或数据库，未改 provider/parser/test 三文件及任何旧采集。
