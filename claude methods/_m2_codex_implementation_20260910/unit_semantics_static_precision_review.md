# 同花顺 M2 本地数值精度静态复核（限域补充）

结论：本地接口并没有被证明使用 Single。已证明客户端存在 **27 位十进制尾数 HxLong → Double** 与 **GMS JSON → Double** 两条 candle 解码路径。保留的两日 SH600011 官方绝对锚点、四个量/额字段都精确符合本地 HxLong 格式的最小十进制网格；这为单位对照提供固定、非拟合的分辨率检查，不能改写为实际传输分支、服务端舍入算法或全部数据误差界已经得到证明。

本报告只补充 `unit_semantics_static_review.md` 的单位链。读取本地程序 PE/ECMA-335 元数据、IL 和常量，没有加载或运行目标 DLL、调用 HTTP、打开数据库、读取账户/用户配置。既有 provider/parser/test 三文件、旧阶段和原始响应不变。

## 字段和运行时数值类型

- 嵌入 QuoteFieldData.xml 中字段 13（总量）和 19（成交额）的 `data_type=5` 是 `FieldDataType.Money`，不是 CLR `Single`；见 `unit_types_datamodel.txt` 第 133 行。业务别名到 13/19 的链见原单位报告。
- 插件 `HevoQuoteValueNormalizer.NormalizePrimitive` token `0x06000282` 对有限 `Double` 和 `Single` 均返回原 `value`；还支持多种整数和 Decimal。`unit_semantics_static_plugin_il.txt` 第 252–361 行显示这条逻辑。它不会把任意数字强制转换成 Single，也不能单凭名字推定底层类型。
- 正式 candle reply 的 `TimeToDictionary` 存放 `object` 数值。`a.u.Parse`（`0x06000778`）处理 GMS response，字段解析 `B.F.A`（`0x06000B67`）进入 `A.q.B`（`0x0600035F`）；数字分支明确调用 `JsonElement.GetDouble` 并装箱 `System.Double`。对应文件为 `unit_semantics_static_typed_candle_parsers_il.txt`、`unit_semantics_static_gms_field_parser_il.txt` 和 `unit_semantics_static_json_number_il.txt` 第 5–35 行。
- V2 candle parser `b.f.Parse`（`0x06000DFA`）进入 `DataResponseV2.GetListDictionary` / `AsListDictionary`，最终由 `C.j` 根据响应中的列类型选择解码。列描述 `C.L` 的字段 ID（`0x04002053`, UInt32）和 wire type（`0x04002054`, Byte）是不同字段；`C.j.E`（`0x06001A67`）从响应 bytes 用 `BytesToMultipleStructSpan<C.L>` 读取。因此 XML Money=5 不能等同于 wire type=5，静态 XML 也不能证明某一次响应的列类型。

## 已证明的 HxLong 格式

`Hevo.Api.Quotes.dll` SHA256：`33a69a8c37779f1db3602c6ccd49c9be5e7c4d49cc87c61f7db1278ca7954625`。

`C.j` 的列解码分支 wire type=2 调用 `Hevo.Core.Protocols.HxLong.A`（token `0x06001A93`），然后明确装箱 Double；wire type=3 直接读取 64 位 Double。见 `unit_semantics_static_binary_fields_il.txt` 第 464–566 行。`HxLong.value` 字段签名为 `0609`（UInt32）；解码方法签名为 `20010D1193E0`，返回签名 `0D` 为 Double。相应元数据保留于 `unit_semantics_static_precision_metadata_success.txt`。

去掉协议哨兵分支后，`HxLong.A` 使用：

```text
mantissa = bits & 0x07ffffff             # 最大 134217727
negative = (bits & 0x08000000) >> 27
exponent = (bits & 0x70000000) >> 28
divide   = (bits & 0x80000000) >> 31
factor   = [1,10,100,1000,10000,100000,1000000,10000000][exponent]
value    = divide ? mantissa/factor : mantissa*factor
result   = negative ? -value : value     # Double
```

掩码和操作见 `unit_semantics_static_hxlong_il.txt` 第 202–327 行。倍率常量来自 FieldRVA token `0x04002255`、RVA `605907`，由纯 PE 元数据读取，再由独立 Python PE section 映射复核 32 个原始字节。其十六进制为 `010000000A00000064000000E803000010270000A086010040420F0080969800`。

当前保留的是插件整理后的 HTTP JSON，并没有原始 GMS/Hx wire header 或实际 dispatcher 选择证据。因此这里只证明本地存在并实现了该格式。没有发现/证明服务端 encoder 的选择指数、截断/最近舍入/中点舍入算法，也未将有限搜索扩张为“不存在 Single 路径”。

## 固定格式分辨率对照

采用公开写明的对照规则：M=134217727；在本地常量表中选最小 q=10^e 使 `abs(官方值) <= M*q`；要求 THS 数值在 q 的整数网格上且 `abs(THS-官方值) <= q/2`。这是一条源格式支持的**对照政策**，不是对当前服务端 encoder 的断言。它没有从这四个差值拟合百分比或绝对阈值；恰在中点的舍入方向不作断言。

| 日期 | 字段 | 上交所原值 | THS 原值 | q | 实际差 | 半格限值 |
|---|---|---:|---:|---:|---:|---:|
| 2022-11-29 | volume | 131565868 | 131565868 | 1 | 0 | 0.5 |
| 2022-11-29 | amount | 1030152542.00 | 1030152540 | 10 | -2 | 5 |
| 2026-05-29 | volume | 455150398 | 455150400 | 10 | 2 | 5 |
| 2026-05-29 | amount | 3878787080.00 | 3878787100 | 100 | 20 | 50 |

四项均通过，也均排除把当前 THS 原值再乘 0.01、100、10000、100000000 的单位假设。结合前一报告已证明的 A 股 volume÷100 显示为手、amount 不做基准缩放，以及上交所原始字段/展示脚本的万股、万元标题与÷10000，可支持这两个绝对锚点的股/人民币元解释。指数口径、全标的质量、覆盖率、调整语义和后续 staging 验收仍由 M2 的各自门禁负责。

`131565868` 本身不是精确 binary32 数值，转换后是 `131565872`。两个不同十进制数转换到 binary32 相等，只说明它们落入同一量化区间；不证明真实源 dtype。因此旧 `unit_anchor_evidence.json` 的 binary32 对照只保留为描述事实，不用来论证 Single 来源。

复算程序 `verify_unit_semantics_static_precision.py` 固定校验 DLL、`unit_anchor_evidence.json`（`fc812f6664a7eb3b2646e20454102cf13f27fc0769d21bfe6107191c1d777fda`）及其每个输入 pin，直接重读 THS raw decimal，并独立核实倍率原始 bytes。默认新建 `unit_semantics_static_precision_verification.json`；输出已存在会拒绝覆盖。PowerShell 最初的 `_precision_metadata.txt` 仅为失败尝试的头部输出（ImmutableArray 扩展方法绑定问题）；成功证据以 `_precision_metadata_success.txt` 为准，失败输出保留但不作成功证据。

本次结论不授予任何 symbol eligibility，不修改原始数字，不声称已证明一般来源误差界。
