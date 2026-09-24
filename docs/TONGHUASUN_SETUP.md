# 同花顺 skill 安装与数据源接入记录

检查日期：2026-09-03（北京时间）

## 当前结论

**本机同花顺行情只读链路已接通，并已按用户授权固定到项目启动配置。** `scripts/tonghuasun_readonly.psd1` 是唯一非秘密配置入口，后续正常项目启动将给子进程传入 `D:\TonghuasunCodex`，无需再为 provider 手填路径；未重启现有旧后端或切换默认源。三股×120根的对照显示，相对现行失败回退链取数更快、成交额字段更完整，但部分历史前复权价格不一致，单位仍未正式确认。详见 [启动固化与比较验收](TONGHUASUN_COMPARISON.md)。不写行情库、不启用实盘。旧 `%LOCALAPPDATA%` 配置保留原样，先前 `NAME NOT FOUND` 的底层原因仍未解释。

| 层级 | 本次状态 | 证据 |
| --- | --- | --- |
| 核心 skill 文件 | 已安装 | GitHub 固定提交下载成功，Git blob 与源文件相同 |
| 同花顺客户端 | 已安装，两个日线样本读取通过 | 官方远航版 12.1.1.6，`happ.exe`，签名有效，`Hevo.App`；不代表所有行情功能均兼容 |
| 客户端插件部署 | 实体复制，独立目录试验已配置 | `deploymentMode=copy`，6/6 文件哈希一致，旧配置未变，6 个相同内容备份可恢复 |
| 本机服务 | 独立目录已纳入项目启动，仅本机监听 | `127.0.0.1:17180`；不设置全局变量；现有旧后端在下次正常启动时继承新配置 |
| 行情实测 | 新目录登录后成功读取 | `600519.SH`、`000001.SZ`；修复后各 5 根日线，日期 2026-08-28 至 2026-09-03；量额单位、实际复权未完成验收 |
| 项目适配器 | 真实只读样本通过，条数契约已修复 | 先校验所有返回行，再按日期取最近请求条数；25 项适配器测试、73 项相关回归通过 |
| 默认数据源 | 未切换 | 保留 `akshare_first`；实盘开关保持关闭 |

## 用户同意后的安装结果

用户确认保留经典版并另装远航版后，完成以下操作：

- 从[同花顺官方下载中心](https://download.10jqka.com.cn/free/)的远航版链接下载 `THS_hevo_gc_12.1.1.6.exe`。下载文件 183,954,152 字节；SHA-256 为 `e996f79110e99d116cd47d6420186180d2b73263ed0a1715eaff7f8a438d7245`。
- 外层安装包、其内置 `HevoInstall.exe` 和安装后的 `happ.exe` 均通过 Authenticode 验证；发布者为 `Hithink RoyalFlush Information Network Co.,Ltd.`。
- 使用官方安装器内置的 `--RunMode RunInstall --UserBinDir <独立目录> --SilentInstall true` 流程。安装目标为 `D:\同花顺软件\同花顺远航版\bin`，原经典版目录未覆盖、进程未关闭；没有导入经典版账户配置。
- 安装器已正常结束，创建桌面快捷方式 `C:\Users\Public\Desktop\同花顺远航版.lnk` 和卸载登记；安装日志确认 `AutoStartCheck.IsChecked=False`，没有启用开机自启动。
- 官方安装包与静态检查材料保存在 `C:\Users\Administrator\Downloads\Tonghuashun-Yuanhang-20260903`，不在项目 Git 中。

### 本机插件加固与部署

完整上游固定提交下载到持久目录 `C:\Users\Administrator\.codex\vendor\tonghuasun-agent-3c8fc58-loopback`，没有注册为 Codex/Claude 的完整 MCP。

对开源 `tooling/src/installer.ts` 做了本地最小加固：监听地址固定为 `127.0.0.1`，网络配置函数在任何系统调用前拒绝其他地址；启动说明明确运行时网络边界仍需验证。闭源 DLL 没有改动，6 个 payload 文件的大小和 SHA-256 均匹配上游 manifest。

配置器构建与测试：`npm test` 38 项通过，退出码 0。测试覆盖源码 CLI、发行 bundle 的 dry-run、仅 loopback URL ACL 规划、非本机地址拒绝及交易开关的 false 默认值；系统命令使用 mock，没有在测试中操作真实网络配置。

构建后的 `distribution/scripts/configure.mjs` SHA-256：`0bfef4526997981b255d1466307df0249e4f1b26e47793e5eda5957f50d9d696`。来源、补丁和验证记录见 vendor 根目录的 `LOCAL_HARDENING.md`。

正式部署前确认宿主已退出、17180 未占用、目标无冲突、原来不存在 loopback/wildcard URL ACL。部署时：

- 仅新增 `http://127.0.0.1:17180/` 的当前用户 URL ACL；没有新增 LAN 监听配置或防火墙放行规则，也未更改 HTTP.sys 全局 IP 监听设置。
- 通过加固配置器执行配置，显式传 `--enable-trade-tools false --enable-automated-trade-api false --keep-legacy-state --version 0.2.13`，不使用 `--force`。
- 首次部署时，6 个文件以受控 symlink 映射到 `D:\同花顺软件\同花顺远航版\bin\PluginSdks`，目标是 `%LOCALAPPDATA%\TonghuasunCodex\releases\0.2.13\ths-plugin`；后续已按下面的记录改为实体复制。
- 配置器管理本地 API 令牌和权限；令牌不进入项目或日志输出。两个交易开关均为 false，没有请求账户/资金接口。
- 最后只读检查：`configured=true`、`healthyMappings=6`、`totalMappings=6`，未找到名为“同花顺 Agent 局域网访问 (17180)”的防火墙规则。

这些检查只证明部署与配置。HTTP.sys 的 URL 前缀不能单独作为网络隔离保证；客户端启动后仍需检查实际端点、监听状态，以及不携带令牌的非 loopback 负向探测。上游只验证过更早的客户端版本，12.1.1.6 必须以真实样本验证兼容性。

后续若明确要求卸载，应先正常退出远航版、通过配置器 `uninstall --dry-run --keep-legacy-state` 核对映射，再执行受控卸载；本轮新建的 loopback URL ACL 不保证被上游自动回收，需要确认归属后单独移除。不要删除整个同花顺目录、vendor 根或用户数据。

### 首次登录检查与复制模式修复经过

用户报告已登录后，检查到远航版 `happ.exe` 正在运行且启动时间晚于插件部署。配置器仍报告 6/6 映射健康、两个交易开关为 false；配置监听地址为 `127.0.0.1`、端口 17180，令牌已配置且文件访问权限正常，没有路径覆盖环境变量。

但 `runtime/endpoint.json` 未生成，17180 没有监听；不携带令牌的本机 `/docs` 探测连接失败（HTTP 状态 000，curl exit 7）。没有请求到真实行情，更没有读取账户、执行交易或写入数据库。

进程模块列表中能看到 `PluginSdks/Hevo.Calculators.dll`，未看到 `ThsPlugin*.dll`。对上游插件的静态元数据读取成功，文件内容可读，不能把 symlink 属性显示的长度 0 当成 DLL 损坏。客户端加载器的静态代码使用 `Directory.GetFiles("*.dll")` 和 `Assembly.LoadFrom`，没有直接过滤符号链接、文件长度或程序集名称；因此不是已确认的“扫描器跳过 symlink”。

进一步沿客户端日志代码定位到 `%TEMP%\Hevo\HevoB2C\12.1.1.6\同花顺远航版_20260903.log`。只筛选 SDK 加载异常行后发现：12:36:27 的第 7–11 行分别对应 5 个 `ThsPlugin*.dll`，均报告 `PluginLoadersHelper.Load error`、`Could not load file or assembly` 和“系统找不到指定的路径”。这确定了失败发生在程序集加载阶段；符号链接部署在宿主中无法解析是优先排查方向，但尚未通过实体复制后的重启对照证明原因。没有读取该日志中的账户或其他无关内容。

用户随后确认已退出，进程检查也确认 `happ.exe` 已停止。通过同一加固配置器执行了 `--mode copy` 兼容性试验：

- 操作前核对配置器 SHA-256 与审计构建一致，重新 dry-run：6 项均为 `replace-managed`、无冲突、无退休映射、目标目录准确。
- 仅将 6 个托管 symlink 替换为实体文件；上游 releases 中的原始 DLL 保留，没有更改 DLL 内容。
- 操作后 6 项 `mode=copy`、不再是符号链接，文件长度正常，SHA-256 全部匹配。
- `Hevo.Calculators.dll` 操作前后哈希相同；访问令牌前后完全相同（仅输出布尔比较结果）；`legacyStatePreserved=true`。
- 监听配置仍仅 `127.0.0.1`，两个交易开关仍为 false，没有修改账户状态、数据库或历史行情缓存。

上述步骤完成时仍待重启；后续重启已证明本次复制模式可以成功加载插件，具体结果如下。不能据此断言所有客户端都不支持 symlink。

### 复制模式重启后的运行时验收（2026-09-03）

用户再次报告已登录后，确认 `happ.exe` 于北京时间 12:54:54 启动（PID 29860），5 个 `ThsPlugin*.dll` 均已从 `PluginSdks` 加载。配置器只读状态为：

```json
{
  "configured": true,
  "hostRunning": true,
  "endpointPublished": true,
  "deploymentMode": "copy",
  "healthyMappings": 6,
  "totalMappings": 6,
  "enableTradeTools": false,
  "enableAutomatedTradeApi": false,
  "baseUrl": "http://127.0.0.1:17180",
  "port": 17180
}
```

- 端点发布时间约 12:55:00；插件版本为 `0.2.13+e79abfd584683088e4df0a667318ff3d88c57711`。公开 `/health` 成功返回，`hasDataAccessor=true`、`version=0.2.13.0`，没有调用账户接口。
- 17180 仅见 `127.0.0.1` TCP 监听（PID 4 / HTTP.sys）；请求队列只关联远航版 PID 29860。没有通配或 LAN IP 监听。
- 未发现上游局域网规则或精确 LocalPort=17180 的防火墙规则。对两个本机非 loopback IPv4 地址的 2 秒 TCP 探测均未连通；没有向非 loopback 地址发送 HTTP 或令牌。这支持当前仅本机绑定，但不等于跨主机扫描，也不排除其他程序的转发。
- 本机 `/openapi/v2.json` 确认日线 `period=7`，复权 `0/1/2=不复权/前复权/后复权`；`values` 是原始字段字典，文档尚未明确量额单位，不能推定样本单位或实际复权已通过。
- 项目适配器对 `600519.SH`、`000001.SZ` 各请求 5 根前复权日线，均返回 `unauthorized`。另用无代理、保留原始头名称的 `http.client` 对同一行情端点复核，仍为 HTTP 401，排除单纯 Python 请求头大小写的问题。
- 只读确认请求令牌与正确产品目录下 `config.json` 完全一致（仅输出比较布尔值），且为 64 位十六进制。JSON 格式、精确字段名、文件权限和修改时间均正常；宿主属当前 Administrator、非 AppContainer、非受限 token。未在插件日志中发现 `plugin.runtime.config_error`。这些证据仍不足以断定宿主为何未接受令牌，不能冒称用户行情登录失败或确定的配置读取故障。

**当时阻点是本机插件的接口鉴权，不是服务未启动；状态为 `integration_pending`。** 曾考虑通过配置器轮换令牌，但当时独立只读复核未找到配置错误的证据，因此暂缓重配和无观察重启。用户授权的精确路径启动跟踪现已完成，记录为 `NAME NOT FOUND`；经过和后续计划见下节。没有据此关闭鉴权或盲目轮换令牌。

若跟踪证据表明需要重新配置，应按 `configure-ths` 要求先让用户正常退出远航版，再通过已审计配置器操作。不得直接编辑产品配置、关闭鉴权、放宽网络范围、在运行中替换 DLL 或强杀客户端。

本轮没有真实行情写入，没有访问账户/资金/委托、执行交易、注册完整 MCP 或修改默认源；现有 `ths_stock_brief` 等 MCP 工具仍不可调用。`POST /api/v2/quotes/candle` 的市场白名单仍是项目接入路径。

### 用户授权后的 Process Monitor 准备

- 从[微软官方页面](https://learn.microsoft.com/en-us/sysinternals/downloads/procmon)链接下载 `https://download.sysinternals.com/files/ProcessMonitor.zip`，解压到 `C:\Users\Administrator\Downloads\Tonghuashun-Diagnostics-20260903\ProcessMonitor`，不进入项目 Git。
- 版本 4.1；`Procmon64.exe` 的 Authenticode 状态为 `Valid`，签名者 `Microsoft Corporation`。ZIP SHA-256：`4ff309fe52c56599377896b7863cb77b6c601d9f2522e52da7a182eac593e8e1`；EXE SHA-256：`78d7148ef5e1472bbcec02cfd655f5aa789006b65d9990862dd8546ecf6c9af1`。
- 以 `/AcceptEula /NoConnect` 启动，未开始捕获。首次隐藏实例通过 `/Terminate` 正常结束；随后打开交互配置窗口（当时 PID 25288）。界面状态明确为 `No events (capture disabled)`、`Backed by virtual memory`。
- 最初配置窗口被 `ScreenSaverPlayer.exe` 的 `Chrome Legacy Window` 屏保覆盖；首次点击被工具拦截，重新激活并刷新后的一次重试仍被拦截。按 `computer-use` 的窗口校验与恢复规则暂停，没有绕过目标窗口保护，也没有关闭屏保进程或更改屏保/隐私设置。
- 用户报告“已恢复”后，发现旧诊断实例已关闭，重新核对签名和哈希后于 14:52:26 以 `/NoConnect` 打开交互实例（PID 30688）。通过 `computer-use` 的逐步观察、操作和刷新完成过滤配置，未开始捕获。
- 已设置两条启用的精确 Include：`Process Name is happ.exe`、`Path is C:\Users\Administrator\AppData\Local\TonghuasunCodex\config.json`；保留原有默认 Exclude，仅开启 File System 类别。已重新打开 Filter 菜单，目视确认 `Drop Filtered Events` 勾选，避免仅隐藏过滤外事件。
- 15:04:04 通过 File → Export Configuration 保存 `C:\Users\Administrator\Downloads\Tonghuashun-Diagnostics-20260903\ths-config-read-only.pmc`，2,989 字节，SHA-256：`343026403043da7dc3b61f186df9873fa9d6496783a5267b114ce2111e14911e`。这是诊断配置，不是事件记录，不包含插件访问令牌。
- Codex 独立只读复核确认 PMC 的 24 个配置记录完整覆盖 2,989 字节；`DestructiveFilter=1`、`Profiling=0`。29 条过滤规则中只有上述两条 Include，其他为 Exclude；Profiling、IPC、Registry、Network、Process 类别均排除，没有 File System 排除。私有格式数值语义通过本次 GUI 状态交叉确认，没有伪称上游公开格式规范或 Claude 审查。
- **准备阶段结束时，过滤配置已保存并复核，捕获关闭，尚无启动 trace。** 当时界面为 `No events (capture disabled)`，远航版仍为旧 PID 29860；随后请用户正常退出，在限定捕获开启后再启动。实际采集见下一节，不能用准备阶段的零事件断言启动时未读配置。
- 工具启动前后只读 `fltmc filters` 均未见 `PROCMON` 项；没有启用 Boot Logging、修改驱动或注册表安全策略。工具自行创建了其用户设置/EULA 记录；本轮未修改同花顺配置、令牌、DLL、账户、数据库或源策略。
- 若后续需要保留诊断结果，仅报告时间、PID、操作、精确路径和结果，不展开进程环境或上传原始 PML；原始诊断文件可能带有敏感元数据。捕获结束后复核驱动状态，不能把退出 Procmon 等同于驱动已卸载，也不擅自卸载驱动。

### 限定启动跟踪结果（15:13–15:16）

用户报告“已退出”后，进程检查确认 `happ.exe` 已停止。先通过 `/Terminate /Quiet` 正常关闭未采集的 Procmon 实例，核对原 PMC 哈希后，以 `/LoadConfig <已审核 PMC> /BackingFile <新 PML> /Runtime 180 /Quiet /Minimized` 启动限定采集；未使用 `/NoFilter`、Profiling 或 Boot Logging。`/Runtime` 的秒数和自动退出语义由本机微软签名 EXE 的帮助资源核对。

- 采集进程 PID 7112，15:13:40 启动，设置最多 180 秒。重新观察界面确认两条精确 Include 均已启用、只有 File System 类别开启，`DestructiveFilter=1`，状态为捕获中、写入指定本地 PML。
- 用户启动远航版：PID 18300，15:14:54 启动；端点文件在 15:14:55 更新。用户报告已登录后，于 15:16:31 发出 `/Terminate /Quiet`，15:16:33 确认采集进程已退出，提前于设置的自动停止时间。没有再次启动采集。
- 本地 PML：`C:\Users\Administrator\Downloads\Tonghuashun-Diagnostics-20260903\ths-config-startup-151340.pml`，关闭后 2,694,387 字节；SHA-256：`9b7d5f5dea8225e6cec70503fd3cbb522959b06f906589955aa0ad65a482eab1`。运行时文件的 128 MiB 预分配长度不代表事件数据量。
- 通过 `/OpenLog ... /SaveAs ... /NoConnect /Quiet` 仅导出已有记录，退出码 0；CSV 共 1 条事件、214 字节。仅对这一事件核对了调用栈中的模块路径，未展开进程环境，也未上传原始诊断文件。PML、CSV 和本地 XML 均在诊断目录，不加入 Git。

| 时间（北京时间） | 进程 / PID | 操作 | 路径 | 结果 |
| --- | --- | --- | --- | --- |
| 15:14:55.0389267 | `happ.exe` / 18300 | `QueryOpen` | `C:\Users\Administrator\AppData\Local\TonghuasunCodex\config.json` | `NAME NOT FOUND` |

该路径与实际配置路径逐字符相同。配置文件长 3,282 字节，创建于 12:31:55、修改于 12:52:59，早于此次宿主启动；普通 32 位和 64 位 PowerShell 进程均报告 `File.Exists=true`、目录存在和相同长度。父目录没有 reparse/link，产品目录未启用大小写敏感。调用栈包含 WOW64 和客户端自带 `SystemCore5.0/System.IO.FileSystem.dll`，但不能仅凭这些模块断言 WOW64、杀毒软件、权限或某个驱动是根因。

再次静态核对插件 IL：`PluginRuntimeSettings.Load` 先执行 `File.Exists(configPath)`，false 时跳过 `ReadAllText` 和 `localAccessToken` 读取；默认令牌为空，且不是这一路径上的异常，因此没有 `config_error` 日志并不能证明配置成功加载。`IsRequestAuthorized` 在没有安全令牌时直接返回 false。单条失败探测、缺少配置读取事件和上述代码共同支持“本次启动未加载配置令牌”的判断；宿主为何收到找不到文件仍未解释。

重启后只读状态仍为 `configured=true`、`hostRunning=true`、`endpointPublished=true`、映射 6/6 健康；产品配置中的两个交易开关仍为 false，仅 `127.0.0.1:17180` 监听。通过项目适配器仅复测 `600519.SH` 的 5 根前复权日线，仍返回 `unauthorized`，没有获得行情或写入数据库。

采集结束及本地导出完成后，Procmon 进程均已退出；`fltmc filters` 仍显示 `PROCMON25`，实例数为 0。没有手工卸载驱动、添加安全排除或改变系统安全策略。

当时提出独立目录对照并等待授权；用户随后回复“ok”，实际实施见下一节。上游配置器与插件均支持 `TONGHUASUN_AGENT_HOME`；对照限定到本次启动的进程和显式指定目录的适配器，未先修改全局环境、默认数据源或普通启动快捷方式。

### 用户同意后的独立目录对照（15:47–15:51）

开始时确认 `happ.exe` 已退出、17180 没有监听、`D:\TonghuasunCodex` 不存在。按照 `configure-ths` 先执行只读 status 和新目录 dry-run。新目录没有原配置的映射记录，预检将 6 个同名文件判为冲突；没有直接忽略这一结果。

对这 6 个目标逐一核对：文件名集合与旧配置完全一致；准确位于远航版 `bin\PluginSdks`；均为实体 copy、没有 reparse；每个文件的 SHA-256 同时匹配原映射记录和固定发行包，且没有待删除映射。向用户说明备份后复制范围后，通过已审计配置器的 `--force --mode copy --version 0.2.13 --keep-legacy-state --enable-trade-tools false --enable-automated-trade-api false` 完成同版本复制，只允许这些已验证的目标。

验证脚本为 `C:\Users\Administrator\Downloads\Tonghuashun-Diagnostics-20260903\configure-home-trial.ps1`（SHA-256 `dd78776678b4fff4d085f6ec8ac17640652bdb9a43ecb52fff12cb3e86978033`），位于 Git 外，执行前 PowerShell 语法检查通过。脚本仅向配置器子进程传 `TONGHUASUN_AGENT_HOME=D:\TonghuasunCodex`；新目录先设置当前用户、SYSTEM、Administrators 的受保护权限，再由配置器生成配置，不直接编辑产品 JSON。

配置后检查通过：

- 6 个部署文件和 6 个可恢复备份均与固定 payload 哈希一致；旧 `config.json` 内容哈希完全未变，`Hevo.Calculators.dll` 完全未变。
- 新配置由配置器生成独立令牌；旧配置和旧令牌未改，没有输出令牌。新目录与配置文件的 ACL 均禁止继承，两个交易开关为 false，监听地址仅 `127.0.0.1`。
- 15:50:19 通过仅本次启动生效的环境变量打开官方签名的远航版（PID 18772）。没有修改用户/系统环境变量、默认数据源、普通快捷方式或账户配置；登录由用户操作。
- 15:50:20 新目录 `runtime\endpoint.json` 已发布，地址 `http://127.0.0.1:17180`；新目录没有生成配置缺失时的 `device.id` 回退文件。
- 项目适配器以 `product_home=D:\TonghuasunCodex` 显式连接，针对 `600519.SH` 请求 5 根前复权日线。15:50:40 和 15:51:09 两次请求均已越过鉴权，返回 HTTP 500 / `internal_error`，不再是 401。
- 只筛选对应 `plugin.http.failure` 的脱敏异常：`System.NullReferenceException`，发生在 `Hevo.Core.DataCenterExtension.RequestCandleV2` 调用链，经 `HevoQuoteCandleService.LoadFallbackAsync` 上抛。未读取账户数据，未生成行情 DataFrame，也未写入数据库。

**该阶段结论：** 新目录对照已解决本次进程的配置/令牌可用性，但当时尚未完成行情接入。新进程的行情登录状态仍待用户确认；空引用也可能与 SDK 初始化或兼容性有关，当时未下根因结论。此轮没有再启用 Procmon，也没有更改系统安全策略。

随后用户确认本次登录完成，成功读取结果见下一节。回退时应先正常退出远航版，再用原快捷方式启动，即回到未覆盖的原目录配置；这也可能恢复原先的 401 状态。新目录和备份先保留，不擅自删除。普通项目默认发现仍指向旧目录，不能把默认 status 的 `configured` 当成新目录已启用。

### 登录后的真实行情验收（16:18–16:25）

用户报告“已登录”后，继续使用同一临时进程与 `product_home=D:\TonghuasunCodex`，没有再次重启、重新配置或轮换令牌。`600519.SH` 的前复权请求首先成功；随后沪、深两个不复权样本均成功。这说明当前实例的日线读取可用，不能将先前的空引用直接推广为客户端版本不兼容。登录确认与成功发生的先后顺序支持初始化/登录就绪相关性，但没有证明 SDK 内部的确切根因。

- 初次请求 `days=5` 时，上游为两只证券各返回 6 个 points，日期 2026-08-27 至 2026-09-03。返回证券标识与请求完全对应；必需字段无缺失，日期无重复，OHLC 关系及非负量额校验通过。
- 修复 `TonghuasunMarketDataProvider.get_daily_bars`：先验证全部响应行，再对已按日期排序的结果执行 `tail(limit).reset_index(drop=True)`，保留 source、请求复权模式与 `volume_unit=unknown` 属性。不能先裁剪再验证，从而掩盖窗口外的非法数据。
- 新增 4 组参数化回归，覆盖少于/多于请求条数、乱序响应、输出索引与属性，以及即使最终窗口不包含非法旧行也必须拒绝。适配器测试 25 项、相关回归测试 73 项全部通过。
- 16:24:54 再次只读调用修复后的适配器，实机验收如下；请求均为日线、不复权、5 条，日期以北京时间解释。

| 证券 | 上游原始 points | 输出行数 | 输出日期范围 | 缺失单元格 / 重复日期 / 未来日期 | OHLC 与非负量额 |
| --- | --- | --- | --- | --- | --- |
| `600519.SH` | 6 | 5 | 2026-08-28 至 2026-09-03 | 0 / 0 / 0 | 通过 |
| `000001.SZ` | 6 | 5 | 2026-08-28 至 2026-09-03 | 0 / 0 / 0 | 通过 |

量额和复权的限制仍然重要：响应 data 只有 `items`，没有复权回显或量额单位元数据。不复权样本的 `amount / volume` 全部处于当日 low/high 内，这仅支持量额比例的内部一致性，不能独立证明“股/元”单位。近期短样本未覆盖已知除权事件；`adjustment_mode` 只记录请求模式，不是上游认证。未验证全市场、北交所、停牌、长历史、交易日历完整性或实时延迟。因此只完成行情连接和短样本结构验收，不放行量额敏感执行、自动灌库或默认源切换。

数据质量检查的可复现代码保存在 Git 外：`C:\Users\Administrator\Downloads\Tonghuashun-Diagnostics-20260903\market-read-acceptance.ipynb`。本机两个现有 Python 环境均没有 nbformat/nbclient/ipykernel，没有安装新依赖；通过 PowerShell 解析 notebook，按顺序将代码单元交给项目 backend Python 执行，退出码 0。没有声称完成 Jupyter 内核执行。Notebook 不保存原始行情或令牌，以上表格保留审核后的检查摘要。

只读复核：17180 仍仅监听 `127.0.0.1`；两个插件交易开关均为 false；用户/系统 `TONGHUASUN_AGENT_HOME` 均未设置；项目实际加载配置仍为 `daily_bar_source_policy=akshare_first`、`enable_live_trading=false`。本轮未访问账户、未写行情库、未修改客户端配置或普通快捷方式。

该阶段之后，用户已明确授权固化只读连接并比较效率/可信度，实施结果见 [后续验收记录](TONGHUASUN_COMPARISON.md)。连接配置已经固定，但没有设置同花顺优先；两者是不同变更。

## 下载来源与安装范围

- 仓库：[zhuyifang/tonghuasun-agent](https://github.com/zhuyifang/tonghuasun-agent)。注意上游拼写为 `tonghuasun`，不是 `tonghuashun`。
- 2026-09-03 核对 GitHub HEAD：`3c8fc58150102bd9095e5d268e6fa35ca398b2bc`。
- 本次固定下载同一 commit，不跟随浮动分支自动升级。
- 源路径：`tonghuasun-mcp/distribution/skills/tonghuasun-agent/SKILL.md`。
- 安装目录：`C:\Users\Administrator\.codex\skills\tonghuasun-agent`。
- 原始文件 SHA-256：`1b53571db2e6253aeeeb0ad12ed9d8907593c334158baed411a9c3221b8970bf`。
- 安装文件的 Git blob：`988212b8e5db4aef068338bbaa15f01fa3a3b4e6`，与该提交的源文件一致。旧审计 checkout 使用 CRLF，所以不能直接用它的文件 SHA-256 与 GitHub ZIP 中的 LF 文件比较。
- skill 保留上游内容，未篡改或伪装成官方插件；项目的账户/交易禁用规则始终有效。

通过系统 `skill-installer` 提供的脚本安装，仅复制 skill 文件，没有执行上游安装器的部署动作。可复现命令如下（从项目根目录运行；目标目录已存在时安装器会拒绝覆盖）：

```powershell
& '.\backend\.venv\Scripts\python.exe' 'C:\Users\Administrator\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py' --repo zhuyifang/tonghuasun-agent --path tonghuasun-mcp/distribution/skills/tonghuasun-agent --ref 3c8fc58150102bd9095e5d268e6fa35ca398b2bc --method download
```

新 skill 可在下一轮加载；如果界面没有更新，再刷新/重新打开任务。**能加载指令不等于已有可调用 MCP 工具。** 当前没有注册同花顺 MCP，不能声称 `ths_stock_brief` 等工具已经可用。

没有单独安装 `configure-ths`：该 skill 依赖完整发行包中的 `scripts/configure.mjs`、payload 等目录，直接复制到普通 skills 目录会破坏它的相对路径。后续部署必须使用审计过的完整发行包，不能只复制两个 `SKILL.md`。

## 首次检查记录（安装前）

本次找到并确认正在运行的客户端：

```text
D:\同花顺软件\同花顺\hexin.exe
产品：同花顺用户端主程序
版本：9,60,20,88
```

C/D/E 盘可读取路径的文件名搜索未找到 `happ.exe`。上游安装器只接受远航版宿主，不支持把经典版路径作为替代。

在上游审计副本上执行了只读 `status --json`，结果为 `configured=false`、`hostRunning=false`、`endpointPublished=false`。其中 `hostRunning` 只检测远航版 `happ.exe`，不表示经典版未运行。

对已确认的经典版路径执行 `configure --ths-path "D:\同花顺软件\同花顺" --dry-run --enable-trade-tools false --enable-automated-trade-api false --json`，配置器返回：

```json
{"ok": false, "error": {"code": "client_not_found", "message": "没有找到同花顺 happ.exe。请使用 --ths-path 指定同花顺安装目录。"}}
```

没有正式运行 `configure`，没有向经典版复制 DLL，没有关闭或重启客户端，没有修改防火墙/URL ACL，没有建立令牌或账户连接。

## 上游安全边界（升级时仍需复核）

审计固定提交后确认：

1. 上游完整包会将闭源 DLL 加载到远航版宿主；本次检查的 DLL 没有 Authenticode 签名。安装 skill 文本不代表已经验证这些二进制的安全性。
2. 原版配置器会自动配置私有局域网监听、URL ACL 和 Private/Domain LocalSubnet 入站规则，没有 loopback-only CLI 开关。本轮使用上述本地加固版本；后续不能直接运行原版 configure 覆盖本轮限制。
3. `enableTradeTools=false` 和 `enableAutomatedTradeApi=false` 不等于禁止账户读取。上游 MCP 桥透明转发工具列表和调用，没有市场行情白名单。
4. 本项目继续走现有市场数据 REST 白名单，不注册未经限制的完整 MCP，不调用账户、资金、委托或交易接口。需要在 Codex 中直接调用行情工具时，应另外实现并测试严格的工具白名单入口。
5. 不直接编辑上游产品 `config.json`，不输出访问令牌；配置变更走审计过的配置器。上游卸载逻辑未见自动清理网络规则，部署前还需记录这些变更的恢复方案。

对应源码：[宿主识别与安装器](https://github.com/zhuyifang/tonghuasun-agent/blob/3c8fc58150102bd9095e5d268e6fa35ca398b2bc/tonghuasun-mcp/tooling/src/installer.ts)、[MCP 转发桥](https://github.com/zhuyifang/tonghuasun-agent/blob/3c8fc58150102bd9095e5d268e6fa35ca398b2bc/tonghuasun-mcp/tooling/src/mcpProxy.ts)。

## 后续实机验收

1. 只读连接已固定到项目 profile，短样本和120根对照均已执行。使用 `scripts/start_tonghuasun_readonly.ps1` 显式启动客户端；常规 run_stack/ensure_stack 只加载固定配置，不操作行情/券商登录，也不因为目录差异盲目重启。
2. 复查 `endpointPublished=true`、文件映射健康、两个交易开关仍为 false，并复核已通过的实际端点及运行时网络边界。
3. 证券标识、短窗口日期、必需字段、OHLC、非负量额和输出条数已验证；仍需通过可靠契约或客户端对照核对量额单位，以及覆盖除权事件的复权样本。扩展历史/市场覆盖前保持只读、不写数据库。
4. 剩余数据验收通过后再请求启用项目 `tonghuasun_first`，不因连接成功自动切换。成交额、复权或单位无法确认时，继续只读复核，不自动灌库或放行模拟执行。

项目现有入口：

- `backend/app/data/tonghuasun_provider.py`：仅 `POST /api/v2/quotes/candle`；numeric loopback、令牌隐藏、拒绝重定向、响应大小和行情字段校验。
- `GET /api/data/tonghuasun/status`：不读取账户、不探测行情；`configured` 仅说明配置被发现，不等于连通。
- `DAILY_BAR_SOURCE_POLICY`：当前不改；可用策略及历史补数规则见 `docs/MARKET_HISTORY.md`。

## 本次验证

从 `backend` 执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_tonghuasun_provider.py tests/test_market_history_refresh_loop.py tests/test_universe_backfill.py
```

结果：`73 passed`，退出码 0；一个现有 Starlette/httpx 弃用提示。其中适配器测试单独执行为 `25 passed`。代码回归使用模拟响应；另外完成的真实远航版短样本验收见上表，两者不混为一项证据。

以上 73 项是登录短样本阶段的测试结果。后续启动固化阶段新增了启动预检、纯内存源比较和边界测试，并加固了代理绕行与证券标识校验；最新验证见 [后续验收记录](TONGHUASUN_COMPARISON.md)。默认源保持 `akshare_first`、实盘关闭；未修改客户端配置、行情数据库、历史缓存、全局环境、普通快捷方式或系统安全策略。剩余工作是历史复权差异、单位与更广覆盖的验收，而非重复登录或临时目录接入。
