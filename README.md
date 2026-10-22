# Planly Plugin

Planly 智能规划助理：Skill + 插件自带 Gateway MCP + 宿主 OAuth；在支持 MCP Apps 的宿主中请求只读可视化。不再引用历史远端 App。

| 项目 | 当前值 |
| --- | --- |
| Plugin 标识 | `planly` |
| Skill 标识 | `planly-solver` |
| 插件内 MCP 名 | `planly`（业务工具仍为 `gateway.*`） |
| 展示名称 | Planly 智能规划助理 |
| Plugin / Skill 版本 | **1.3.11**（发布标签 `v1.3.11`） |

**名称调整与本地标签重打：** 插件和内置 Skill 的展示名称及默认提示统一使用「Planly 智能规划助理」，技术标识和版本不变。按用户要求提交更名，并将本地 `v1.3.11` 重打到本次提交；尚未推送，远端同名标签仍指向原发布内容，本地重打不表示客户端已更新。

**v1.3.11：同步当前 Planly 品牌。** 小图标及深浅色横排 Logo 更新为已确认的「01 冰蓝浅底」时空折叠与路径方案，并同步 Quicksand 字标许可和品牌测试基线；不改变 Skill 行为或 MCP / OAuth 配置。见 [版本说明](docs/releases/v1.3.11.md)。

**接入与验收：** 双组选项需要配套 Gateway 更新；约束模式映射当前 ImageVersion 的真实公开方案，缺少对应模式时展示实际可用方案，不修改引擎权重。既有自动化与本地模拟宿主验证不代替真实 GPT Desktop 验收，本次品牌同步未重测真实客户端。详见 [验收清单](docs/acceptance.md)。

**保留的续期修复：** 服务器级 OAuth scopes 固定为 `gateway:mcp` 与 `offline_access`。前者是唯一 Gateway 业务权限，后者只请求 OAuth 离线续期，不授予资料、组织或管理权限。v1.3.1 及更早版本即使服务端允许 refresh token，也会因未请求 `offline_access` 而只拿到 access token；客户端不会自动获得本次包更新。详见 [scope 规范与验证边界](docs/oauth-scopes.md)。

## 安装与使用

安装发布版本 `1.3.11` 时使用标签 `v1.3.11`；固定旧标签的安装不会取得本次品牌更新：

```bash
codex plugin marketplace add shanhaibuci/planly-plugin --ref v1.3.11
```

在支持 Plugins Directory 的桌面客户端找到 **Planly** 插件并安装，启用插件内 `planly` MCP，在宿主 Authenticate 入口完成 OAuth，然后开启新会话：

```text
$planly-solver 查看我最近成功的任务，并展示地图和 Gantt
```

固定旧 tag 的 marketplace 不会因刷新自动切到新 tag；需先更新 Git ref，再更新插件。已有用户级 Gateway 连接和历史插件不自动删除；如出现两套工具，应确认当前插件连接及账号后选择，不混用或静默切换。插件 OAuth 不继承旧远端 App 的授权，可能需要重新登录。

本地开发可在独立测试客户端从本仓库目录添加 marketplace；不要通过修改用户现有配置替代插件安装。CLI/IDE 的纯文本界面不等于支持可视化宿主。

### 客户端范围

- 采用受支持的 `.codex-plugin/plugin.json` + `.mcp.json` 兼容布局，面向支持插件 HTTP MCP/OAuth 的桌面端/Codex。
- 直接声明 MCP 的 GitHub 插件按当前平台规则为 **Desktop only**，不声称在 ChatGPT 网页端可通过同一方式使用；网页端 App 接入另行处理。[官方范围](https://learn.chatgpt.com/docs/enterprise/plugin-management#desktop-only-plugins)
- MCP Apps 是否渲染、全屏是否可用，必须在实际目标客户端验证；没有 `supports_ui=true` 之类包内开关能替代宿主能力。

## MCP 和 OAuth

`.codex-plugin/plugin.json` 引用 `.mcp.json`，不再包含 `apps`，也不发布 `.app.json`。MCP 连接配置由公开源文件生成：

- `skills/planly-solver/config/system-endpoint.json`：唯一端点来源。
- `skills/planly-solver/config/oauth-client.json`：原有公开 Client ID、回调、最小业务 scope 与续期 scope，不含秘密。
- `scripts/build_mcp_config.py`：确定性生成 `.mcp.json`，`--check` 检查同步而不写文件。

使用 `type=http`、`url`、`oauth.clientId`、`oauth.callbackUrl`，并由同一公开源生成 **`mcpServers.planly.scopes=["gateway:mcp","offline_access"]`**（与 `oauth` 同级，不是 `oauth.scopes`）。`offline_access` 只用于让授权服务器签发 refresh token，Token 存储、刷新与轮换仍由宿主管理；它不扩大 Gateway API 权限。服务器级 scopes 已通过原生授权请求的隔离验证；目标桌面版本的完整换码与续期仍须实测。resource 继续来自 Gateway Protected Resource Metadata，不伪造第二套资源身份；不能再假定发现文档会自动选择正确权限。[插件 OAuth](https://learn.chatgpt.com/docs/extend/mcp#plugin-provided-mcp-servers)

已有公开 OAuth Client ID、回调、端点未改，不重新注册或放宽服务端认证。宿主若忽略公开客户端配置、使用不匹配回调、请求错误 scope/resource 或要求 DCR，应停止并检查兼容性；不要降级 PAT、放宽安全校验或添加第二条用户级 MCP。OAuth 服务端的品牌展示仍由管理员单独维护，删除旧 App 引用不等于修改认证服务名称。

用户自行完成登录和同意授权；Token 交换、存储及刷新归宿主管理。包内不含 PAT、Token、Client Secret、业务数据或环境文件，不读取用户 OAuth 凭证缓存。独立 Skill 的用户级自动配置脚本仅用于明确的独立安装，不用于修复插件未加载。

## MCP Apps UI

```text
Planly Plugin 自带 MCP → Gateway /mcp
                          ├─ 业务工具与只读展示工具
                          ├─ 安全展示数据
                          └─ resources/read 返回 HTML
                                      ↓
                           客户端沙箱：会话内 / 全屏
```

公共卡片由 Gateway 提供；引擎随 ImageVersion 分别交付地图和 Gantt 两份资源，再由 Gateway 校验、导入和分发。全部 / 单工程师路线属于地图状态，规划回放属于地图大屏，不新增第三份资源。Plugin 不捆绑这些 HTML，不直接访问引擎、业务 REST 或完整结果归档。

Skill 从 Gateway 的任务展示提示分别获取 `map_display_tool_name`、`gantt_display_tool_name`，与当前可信工具目录核对后按意图请求只读展示，不拼版本工具名。地图工具只传 `job_id` 和可选 `engineer_id`，Gantt 工具只传 `job_id`，不传 `view` 切换页面。地图下方 Gantt 入口只发送意图，Skill 在下一条消息重新核对并调用 Gantt 工具。无 UI、版本未就绪或权限失效时明确说明，提供可用摘要与真实网页入口；不会创建新任务或换版本“修复”展示。选择卡只回传意图，创建任务仍需当前草稿的明确确认。协议机制见 [官方 MCP Apps UI 文档](https://developers.openai.com/plugins/build/chatgpt-ui)。

上述双工具 / 双资源为已冻结的接入契约，不代表 Gateway、引擎或真实宿主已完成迁移。提示缺失或目录未就绪时降级为摘要和网页入口，不回退旧单工具契约，也不把只读调用成功当作 UI 已渲染。

`v1.3.11` 首次发布的 Skill 沿用 2026-10-19 从 Gateway 同步的 `1.3.10` 内容，仅将两处 Skill 版本声明与 Plugin 一并升级为 `1.3.11`。本次另提交内置 Skill 的展示名称及默认提示调整，不改变求解流程或反向修改 Gateway。来源与验证边界见 [同步记录](docs/gateway-skill-sync.md)。仅按用户要求重打本地 `v1.3.11`，其他标签不变；未推送、更新用户安装或部署上游服务。

## 本地验证

包内自动化检查与真实客户端验收分别记录在 [验收清单](docs/acceptance.md)，不能互相替代。

```bash
python3 scripts/build_mcp_config.py --check
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

公开配置更新后执行 `python3 scripts/build_mcp_config.py`。自动化测试使用临时目录和模拟数据，不连接真实账号、不创建任务、不写用户 Codex 配置。真实宿主 OAuth、MCP Apps、地图网络与展示效果按验收清单独立记录。

设置 `PLANLY_CODEX_BIN` 可额外运行真实 Codex 二进制的隔离协议测试，详见验收清单；默认不自动安装客户端。原生 MCP/OAuth 请求与资源读取通过仍不代表实际桌面 UI 已渲染。

## 1.3.11 变更

- 从 Gateway 正式品牌包逐字节同步 256 × 256 图标和两种 1480 × 440 横排 Logo，保持透明背景和原清单路径。
- 替换为完整 Quicksand 许可，移除未使用的 Outfit 许可；同步品牌源路径、尺寸与 SHA-256 基线及回归测试。
- 根版本、Plugin 清单和内置 Skill 版本统一为 `1.3.11`；不修改 Skill 行为、公开端点、OAuth 或 MCP 配置。
- 插件与内置 Skill 的展示名称及默认提示统一为「Planly 智能规划助理」，保留 `planly` 和 `planly-solver` 技术标识。
- 初次发布后，按用户后续要求提交更名并本地重打 `v1.3.11`；尚未推送本次提交或标签，其他标签不变，不部署服务或更新用户安装。

## 1.3.10 变更

- 在求解参数摘要前展示强度与约束两组选项，由 Skill 预选当前值；可独立切换，统一“确认求解”，无需额外文字确认。
- 求解强度为轻量、标准、增强；未指定时采用标准档，保留用户选择或继承设置，日常仅展示档位名称。
- 约束模式为全面兼顾、均衡优先、效率优先；无指定或继承设置时初选全面兼顾，按当前公开方案绑定真实参数并保留自定义覆盖。
- 旧服务或无 UI 宿主沿用按钮或文字确认；保留草稿、候选映射、费用复核及重复提交门禁。公开连接、OAuth、MCP 配置和品牌不变。

## 1.3.9 变更

- 结合本次硬约束、目标优先级和结果指标解释业务取舍；得分有助于回答时展示并解释，不从总分反推分项或时长。
- 删除强制收尾、仅追问才展开等重复限制，合并证据边界；不改变目标、收费确认、任务绑定或真实异常披露规则。
- 仅同步 Skill、版本、文档与包契约测试；公开连接、OAuth、MCP 配置及品牌不变。验证范围与已知限制见 [发布说明](docs/releases/v1.3.9.md)。

## 1.3.8 变更

- 求解确认优先使用 buttons 单选卡片；问题绑定当前草稿、连接、镜像及预计积分，点击确认后不重复提问。
- 修改参数或计费变化使旧确认失效，创建前消费确认，未知结果或重复消息不重提；普通选择与地图仍不授权创建。
- 解释先主动核查同任务场景、摘要及 Schema，按业务语言给结论与依据，支持明确限定其他工单不变的局部比较。
- 不引用内部 Skill 路径，不机械追加免责声明，不伪造另一人不能接或唯一最优；服务时间仍须公开 Schema 支持。
- 通过新标签 `v1.3.8` 发布，不移动旧 tag。公开连接、OAuth、品牌及创建 API 不变；需要配套 Gateway 按钮展示能力。问答稳定性和真实宿主验收仍未通过，不部署服务或更新用户安装。

## 1.3.7 变更

- 新增只读 `gateway.solver_jobs.get_scenario` 接入，仅传 `job_id`；工具由 Gateway 动态发布，不在 Plugin 中复制工具实现或硬编码目录。
- 日期／城市到来源任务 ID 的映射放在演示专有配置；不猜 ID、不自动选最近任务，固定来源、本轮初排与重排分别记录。
- 场景是 Gateway 派生的求解前输入，不是原始上传 JSON 或已求解结果。保留已有安排、图商和显式矩阵／路线选项，不把新派工单自动冻结。
- `can_create=false` 时只读；重新求解仍须实时 Schema、地点与覆盖校验、积分提示和当前草稿确认。工具缺失或失败不绕过权限访问 REST 回放、管理员或归档接口。
- 结果解释可用同任务的历史输入核对已有单量和安排；读取失败不猜测，不用其他任务的数据替代。保留 v1.3.6 的业务问答、异常披露与只读展示边界。
- Plugin、Skill 和根版本统一为 `1.3.7`；公开端点、OAuth、`.mcp.json` 与品牌不变。本版通过新标签 `v1.3.7` 发布，不声明真实客户端已更新或新流程已完成端到端验收。

## 1.3.6 变更

- 结果解释直接回答当前业务疑问，核对与任务明确绑定的已确认输入和模型可见结果；已有 / 新派 / 全天合计按工单 ID 对照，不能凭均匀结果证明输入正确。
- 不将正常同址拆分称为故障，不擅设“同址优先于均衡”，不生成无依据认错；超单人硬上限只证明不能全部同人，不证明当前人数最优。
- 比较“为什么派给甲而不是乙”时核对实际候选和双方相关安排；没有轨迹或对照不宣称唯一归因或全局最优，不自动创建收费对照任务。
- 某人某日请假时继承基线已确认规则、目标和冻结 / 可调整范围，只澄清缺失或冲突；新草稿仍走 Schema / 地点校验、积分提示和创建确认。
- 重排摘要说明请假人员工单去向、其他连带换人、服务时间变化和逐项核对的保留项，不只重列全部编号。地图 / Gantt 按钮只读，不查询积分或触发重新求解。
- Skill 规范不能掩盖漏单、超上限、预约变化、地图与排程时间不一致，也不修复引擎。仅同步 Skill 副本、版本元数据、文档和测试；`v1.3.6` 发布不会自动更新客户端或部署上游服务。

## 1.3.5 变更

- 从当前 ImageVersion 的实时 `request_schema` 选择 `centralized_refs` 或 `inline_objects`，不按镜像名称或版本号分支；新草稿采用 Schema 明确首选的集中引用，已有合法内嵌草稿可以保持内嵌。
- 显式维护 `location_encoding` 与 `location_validation`；集中模式检查地点集合、POI ID 唯一性、`referenceIds ⊆ poiIds` 和被引用 POI 坐标，内嵌模式禁止字符串引用并要求完整有效地点对象。
- 混合地点在确认前按 Schema 转为集中引用；转换或任何草稿变化都产生新 revision，使旧地点检查和创建确认失效。
- 只有地点检查为 `passed` 且 `checked_revision` 等于当前 revision 时才展示确认并调用创建 tool；失败时禁止创建，修复后重新检查和确认，不自动重提收费任务。
- Plugin 与内置 Skill 统一为 `1.3.5`。本轮同步 Skill 指导和客户端门禁，并配套引擎 OpenAPI/Schema 契约说明；不修改 Gateway 或引擎运行时、公开端点、OAuth、`.mcp.json` 或品牌素材，也不声称已有服务端语义兜底。

## 1.3.4 变更

- 明确字段省略、`null` 和空数组的区别；示例不代表必填或默认值，不把可选字段改成通用隐含必填。
- 按当前字段说明准备关联数据，保留已有指派与顺序，不假设引擎自动补齐；契约通过但解析失败时不自动重提收费任务。
- Plugin 与内置 Skill 统一为 `1.3.4`；仅同步指导说明，不改变 Gateway / 引擎业务行为、MCP / OAuth 配置或品牌素材。

## 1.3.3 变更

- 同步 Gateway Skill 的地图 / Gantt 双工具、双资源契约；动态发现两个展示工具，不再传 `view` 切换页面。
- 分别维护任务展示映射，地图下方 Gantt 入口只发送意图；目录或版本未就绪时安全降级，不回退旧契约。
- 结果解释只使用模型可见摘要和 Schema，不把基础任务详情或 UI 专用元数据当作已获得的分析证据。
- Plugin 与内置 Skill 统一升级为 `1.3.3`；公开端点、OAuth 配置与品牌素材保持不变，真实宿主和上游迁移仍待验收。

## 1.3.2 变更

- 将显式 OAuth scopes 从 `gateway:mcp` 更新为 `gateway:mcp` 与 `offline_access`，修复重新登录仍只签发 access token、到期后必须再次授权的问题。
- 保持公开 Client ID、回调、Gateway 业务权限与 refresh token 轮换策略不变；不加入 `openid`、`profile`、组织或管理权限。
- 新增授权 URL 对两个 scope 的精确回归校验；真实 GPT Desktop 仍需安装本版本后观察首次换码是否返回 RefreshToken，以及一小时后是否发生 RefreshToken grant。

## 1.3.1 变更

- 从既有公开 OAuth 源生成 `mcpServers.planly.scopes=["gateway:mcp"]`，与 `oauth` 同级；不扩大 Logto 应用权限。
- 增加宽发现列表、缺失 scopes、字段误放及额外权限的回归检查，覆盖此次 `invalid_scope` 的触发条件。
- 56 项测试通过（含 4 项原生隔离测试）；真实公网授权前置检查进入登录流程，完整桌面登录与 UI 仍需独立验收。
- 保持 Gateway 地址、公开 Client ID、回调、Logo 和既有 MCP Apps 功能不变。

## 1.3.0 变更

- 将历史 App 引用替换为插件自带 MCP，沿用 Gateway 和公开 OAuth 注册信息。
- Skill 按插件/独立安装分流，按实际宿主命名空间发现工具，避免重复连接。
- 增加只读 MCP Apps 工具发现、动态版本工具调用及无 UI 降级指导。
- 增加配置生成、身份安全、来源一致性和展示边界回归测试；真实客户端验证单独记录。
- 同步新版 Planly 线条骑士 A 版：小图标、浅色/深色横排 Logo 和 Outfit 字体许可。

## 历史版本

- **1.2.2**：统一包内 App 别名和文案，当时仍引用已有远端 App。
- **1.2.1**：建立 Planly 独立 Plugin 仓库，统一品牌、Skill 标识与版本。

## 品牌与许可

`plugins/planly/assets/` 采用 2026-10-13 确认的 Planly「01 冰蓝浅底」时空折叠与路径图标，以及 Quicksand Medium 500 字标。资源从 Gateway 的 `docs/brand-assets/planly/` 逐字节同步，不另行绘制或缩放；保留真实透明 alpha 与原清单路径：

| 插件资源 | 已确认品牌源文件 | 用途 |
| --- | --- | --- |
| `icon.png` | `favicon/favicon.png` | 纯图标，256 × 256 |
| `logo.png` | `screen/logo-horizontal.png` | 浅色背景用深海军蓝字标横排，1480 × 440 |
| `logo-dark.png` | `screen/logo-horizontal-dark.png` | 深色背景用白色字标横排，1480 × 440 |

`tests/brand-assets-baseline.json` 记录源路径、尺寸与 SHA-256，独立仓库测试无需访问 Gateway。横排字标已经转为图形，不加载运行时字体；完整许可从 `source/wordmark/fonts/OFL-Quicksand.txt` 同步到 `assets/OFL-Quicksand.txt`，不再交付未使用的 Outfit 许可，不代表软件或商标采用相同许可。

市场技术标识保留 `personal`，展示名为 `Planly Plugins`，不重建市场身份。品牌资产已随 `v1.3.11` 首次发布，本次更名与本地标签重打不改变品牌文件；不会修改远端 App 或 OAuth 登录页的 Logo，客户端需安装包含这些资产的版本。
