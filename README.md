# Planly Plugin

Planly 场景求解插件：Skill + 插件自带 Gateway MCP + 宿主 OAuth；在支持 MCP Apps 的宿主中请求只读可视化。不再引用历史远端 App。

| 项目 | 当前值 |
| --- | --- |
| Plugin 标识 | `planly` |
| Skill 标识 | `planly-solver` |
| 插件内 MCP 名 | `planly`（业务工具仍为 `gateway.*`） |
| 展示名称 | Planly 场景求解 |
| Plugin / Skill 版本 | **1.3.1** |

**v1.3.1：OAuth 最小 scope 修复。** 保留独立 MCP 接入与新版 Planly Logo，变更及升级说明见 [发布说明](docs/releases/v1.3.1.md)。自动化检查与真实客户端验收分别记录在 [验收清单](docs/acceptance.md)，不能把安装成功或工具可调用当成 UI 已就绪。

**本版修复：** 显式配置服务器级 OAuth scopes，避免宿主采用 Logto 的完整发现列表并遗漏 `gateway:mcp`。旧 `v1.3.0` tag 不含此修复；不会自动替用户更新客户端。详见 [scope 规范与验证边界](docs/oauth-scopes.md)。

## 安装与使用

使用 `v1.3.1` tag 安装；不要用旧 tag 验证本轮修复：

```bash
codex plugin marketplace add shanhaibuci/planly-plugin --ref v1.3.1
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
- `skills/planly-solver/config/oauth-client.json`：原有公开 Client ID、回调和最小 scope，不含秘密。
- `scripts/build_mcp_config.py`：确定性生成 `.mcp.json`，`--check` 检查同步而不写文件。

使用 `type=http`、`url`、`oauth.clientId`、`oauth.callbackUrl`，并由同一公开源生成 **`mcpServers.planly.scopes=["gateway:mcp"]`**（与 `oauth` 同级，不是 `oauth.scopes`）。服务器级 scopes 已通过 Codex 0.155.0 原生授权请求的隔离验证；目标桌面版本仍须实测。resource 继续来自 Gateway Protected Resource Metadata，不伪造第二套资源身份；不能再假定发现文档会自动选择最小业务权限。[插件 OAuth](https://learn.chatgpt.com/docs/extend/mcp#plugin-provided-mcp-servers)

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

公共卡片由 Gateway 提供；地图、Gantt、单工程师路线和规划回放页面由引擎随 ImageVersion 交付，再由 Gateway 校验、导入和分发。Plugin 不捆绑这些 HTML，不直接访问引擎、业务 REST 或完整结果归档。

Skill 从 Gateway 的任务展示提示获取 `display_tool_name`，与当前可信工具目录核对后请求只读展示，不拼版本工具名。无 UI、版本未就绪或权限失效时明确说明，提供可用摘要与真实网页入口；不会创建新任务或换版本“修复”展示。选择卡只回传意图，创建任务仍需当前草稿的明确确认。协议机制见 [官方 MCP Apps UI 文档](https://developers.openai.com/plugins/build/chatgpt-ui)。

## 本地验证

```bash
python3 scripts/build_mcp_config.py --check
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

公开配置更新后执行 `python3 scripts/build_mcp_config.py`。自动化测试使用临时目录和模拟数据，不连接真实账号、不创建任务、不写用户 Codex 配置。真实宿主 OAuth、MCP Apps、地图网络与展示效果按验收清单独立记录。

设置 `PLANLY_CODEX_BIN` 可额外运行真实 Codex 二进制的隔离协议测试，详见验收清单；默认不自动安装客户端。原生 MCP/OAuth 请求与资源读取通过仍不代表实际桌面 UI 已渲染。

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
