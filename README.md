# Planly Plugin

Planly 场景求解插件：Skill + 插件自带 Gateway MCP + 宿主 OAuth；在支持 MCP Apps 的宿主中请求只读可视化。不再引用历史远端 App。

| 项目 | 当前值 |
| --- | --- |
| Plugin 标识 | `planly` |
| Skill 标识 | `planly-solver` |
| 插件内 MCP 名 | `planly`（业务工具仍为 `gateway.*`） |
| 展示名称 | Planly 场景求解 |
| Plugin / Skill 版本 | **1.3.5** |

**v1.3.5：实时 Schema 驱动的地点编码与 revision 门禁。** 新草稿按当前 ImageVersion Schema 的明确偏好选择集中引用，已有合法内嵌草稿可保持内嵌，混合结构在确认前规范化；地点模式、ID、引用和坐标检查必须绑定当前草稿 revision，通过后才可确认和创建。变更及升级说明见 [发布说明](docs/releases/v1.3.5.md)。这是 Skill 客户端防错，不是 Gateway 或引擎运行时的服务端语义兜底；保留既有地图 / Gantt 双工具契约和 OAuth 离线续期配置。自动化检查与真实客户端验收分别记录在 [验收清单](docs/acceptance.md)。

**保留的续期修复：** 服务器级 OAuth scopes 固定为 `gateway:mcp` 与 `offline_access`。前者是唯一 Gateway 业务权限，后者只请求 OAuth 离线续期，不授予资料、组织或管理权限。v1.3.1 及更早版本即使服务端允许 refresh token，也会因未请求 `offline_access` 而只拿到 access token；客户端不会自动获得本次包更新。详见 [scope 规范与验证边界](docs/oauth-scopes.md)。

## 安装与使用

使用 `v1.3.5` tag 安装；不要用旧 tag 验证本轮 Skill 门禁：

```bash
codex plugin marketplace add shanhaibuci/planly-plugin --ref v1.3.5
```

在支持 Plugins Directory 的桌面客户端找到 **Planly 场景求解**并安装，启用插件内 `planly` MCP，在宿主 Authenticate 入口完成 OAuth，然后开启新会话：

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

2026-09-29 已从 Gateway 实现逐字节同步公开 Skill；发布版本为 `1.3.5`，新 tag `v1.3.5` 指向本次发布提交。范围和未验收边界见 [同步记录](docs/gateway-skill-sync.md)。所有既有 tag 保持不变；创建 tag 不表示已更新用户安装或部署上游服务。

## 本地验证

```bash
python3 scripts/build_mcp_config.py --check
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

公开配置更新后执行 `python3 scripts/build_mcp_config.py`。自动化测试使用临时目录和模拟数据，不连接真实账号、不创建任务、不写用户 Codex 配置。真实宿主 OAuth、MCP Apps、地图网络与展示效果按验收清单独立记录。

设置 `PLANLY_CODEX_BIN` 可额外运行真实 Codex 二进制的隔离协议测试，详见验收清单；默认不自动安装客户端。原生 MCP/OAuth 请求与资源读取通过仍不代表实际桌面 UI 已渲染。

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

`plugins/planly/assets/` 采用 2026-09-18 确认的 Planly 线条骑士 A 版与 Outfit Bold 700 字标。资源从 Gateway 的 `docs/brand-assets/planly/` 逐字节同步，不另行绘制；保留透明底与原清单路径：

| 插件资源 | 已确认品牌源文件 | 用途 |
| --- | --- | --- |
| `icon.png` | `screen/logo-256.png` | 数字优化小图标，256 × 256 |
| `logo.png` | `png/logo-horizontal-4096.png` | 浅色背景用炭黑横排，4096 × 1218 |
| `logo-dark.png` | `png/logo-horizontal-white-2048.png` | 深色背景用反白横排，2048 × 609 |

`tests/brand-assets-baseline.json` 记录源路径、尺寸与 SHA-256，独立仓库测试无需访问 Gateway。横排字标已经转为图形，不加载运行时字体；完整许可随 `assets/OFL-Outfit.txt` 交付，不代表软件或商标采用相同许可。

市场技术标识保留 `personal`，展示名为 `Planly Plugins`，不重建市场身份。包内资源更新不等于已发布，也不会修改远端 App 或 OAuth 登录页的 Logo；客户端需安装包含这些资产的新版本。
