# Planly 独立 MCP 与 MCP Apps 验收

版本：1.3.5。发布包内实现与真实宿主体验分开验收，未验证不算通过。

## 自动化范围

- Manifest 不再引用 App，恰好声明 Planly HTTP MCP；Logo 与 Skill 完整。
- 品牌采用已确认的线条骑士 A 版与 Outfit Bold 700 字标；小图标和两种 Logo 按基线校验 SHA-256、尺寸及 RGBA 通道，随包交付 Outfit 许可。
- `.mcp.json` 与公开源一致且可重复生成；端点和 OAuth 源文件指纹未变。
- 服务器级 `mcpServers.planly.scopes` 必须与公开源一致，严格为 `gateway:mcp`、`offline_access`；字段缺失、顺序变化、误放在 `oauth.scopes` 或增加资料权限均不能通过生成检查。原生测试必须覆盖授权服务器发现列表大于显式权限列表的情况。
- 不允许静态凭据、秘密字段、任意端点、非 HTTPS 地址或不支持的回调配置。
- Skill 区分插件与独立安装，不硬编码插件命名空间、不静默切换连接、不自动创建第二条用户级 MCP。
- UI 使用实际展示提示中的 `map_display_tool_name`、`gantt_display_tool_name` 和当前工具目录；地图与 Gantt 分别调用，不传 `view`。选择不创建任务，不拼工具/资源名；无 UI、错误版本、权限变化时安全降级。
- 结果解释只使用模型可见的摘要与 Schema；基础任务详情和 UI 专用 `_meta.gateway_ui.engine_view` 不作为完整结果分析证据。
- 参数构建说明区分省略、`null` 和空数组，不假设引擎自动补齐；合法草稿解析失败时不猜测修补后自动重提收费任务。
- 地点模式必须在读取当前 ImageVersion 的实时 `request_schema` 后确定，不按镜像名称或版本号启用；新草稿采用 Schema 明确首选的集中引用，已有合法内嵌草稿可保持内嵌。
- `location_encoding` 和 `location_validation` 状态必须显式存在。集中模式验证地点集合、POI ID 非空且唯一、`referenceIds ⊆ poiIds`、空地点与被引用 POI 坐标；内嵌模式不得含字符串地点引用，每个地点对象必须完整且坐标有效。
- 混合结构在确认前按 Schema 转为集中引用并产生新 revision。只有地点检查为 `passed` 且 `checked_revision` 等于当前 revision 时才可展示确认和调用创建 tool；失败或修复后不得沿用旧确认或自动重提。
- 地点门禁是 Skill 客户端辅助检查，不是 Gateway 或引擎运行时的服务端语义保证；未加载或绕过 Skill 的客户端不受保护。
- 这些是配置和 Skill 合约检查，不证明模型在每个真实会话中都已执行正确，更不等于图形宿主验收。

## v1.3.0 验证记录（2026-09-18）

| 验证 | 结果与边界 |
| --- | --- |
| Python 配置/包/Skill 合约测试 | 51 项通过；含新版 Logo 基线校验，不访问真实 Gateway |
| 品牌源与插件副本 | 3 张 PNG 及 Outfit 许可与 Gateway 已确认品牌源逐字节一致；品牌源只读测试 15 项通过；不代表客户端缓存已更新 |
| Plugin 与 Skill 结构校验 | 通过；端点/OAuth 源指纹保持不变，生成配置一致 |
| 原生客户端解析、安装和协议 | Codex 0.155.0，隔离 HOME/CODEX_HOME；插件独立 MCP 为 planly，apps 为空 |
| 原生 OAuth 授权请求 | 本地模拟授权服务器；预注册 Client ID、S256、发现的 gateway:mcp scope、resource 和 loopback callback 正确，未走 DCR；在用户同意和换码前停止 |
| 原生 MCP UI 资源传输 | 本地模拟 MCP；UI resourceUri 元数据保留、HTML 与 MIME 读取一致；不是 iframe 渲染验证 |
| 上述原生客户端回归 | 2 项通过；临时工具不替换用户的全局客户端 |
| Gateway 源 Skill 回归 | 54 项 Python 通过，打包及 MCP Apps 相关 JVM 26 项通过；未修改业务服务实现 |

重跑原生客户端隔离测试（必须指定待验证的客户端，不自动安装或升级）：

```bash
PLANLY_CODEX_BIN=/path/to/codex python3 -m unittest discover -s tests -p 'test_codex_plugin_runtime.py' -v
```

未设置环境变量时常规测试跳过原生客户端测试。它们仅将临时复制的插件连接到本机假服务，正式 `.mcp.json` 仍为原 HTTPS 端点。桌面 GUI、真实 OAuth 登录与地图数据均未验证。

## v1.3.1 scope 修复验证（2026-09-20）

此前最小发现列表测试不能证明真实 Logto 式宽列表安全，具体配置与边界见 [scope 规范](oauth-scopes.md)。本轮不修改 Logto 应用权限、不修改 Gateway/引擎、不创建任务或读取用户 Token。

| 验证 | 结果与边界 |
| --- | --- |
| 自动化总体验证 | 56 项测试全部通过（含 4 项原生测试，无跳过）；生成配置一致性、Plugin/Skill 校验及 `git diff --check` 通过 |
| Codex 0.155.0 隔离 A/B | 服务器级 `scopes` 能约束实际授权请求；嵌套 `oauth.scopes` 不能替代 |
| 原生回归 | 4 项通过：最小发现、13 项 Logto 式发现、未声明 scopes、既有 MCP UI 资源读取；登录 RPC 不传 scopes，以检验插件配置 |
| 真实公网授权前置检查 | 隔离原生客户端使用修复后的插件获取真实发现信息；授权 URL 恰好包含 `gateway:mcp`，Client ID/resource/S256/loopback callback 正确；真实 Logto 返回 303 进入登录交互，没有 `invalid_scope` |
| 前置检查停止点 | 未登录、未替用户同意、未换 Token；不是完整 OAuth 或 GPT Desktop 验收 |
| 发布与桌面更新 | 修复纳入 v1.3.1；未替用户更新桌面插件，v1.3.0 及更早 tag 不包含修复 |

## v1.3.2 自动续期修复（2026-09-20）

真实 GPT Desktop 使用 v1.3.1 重新登录后，Logto 交互日志显示 `ExchangeTokenBy.AuthorizationCode` 成功，但请求 scope 只有 `gateway:mcp`，`tokenTypes=["AccessToken"]`，没有 RefreshToken grant。实际使用的是公开 **DFST Agent MCP** 客户端；其服务端已启用 refresh token 签发与轮换，因此根因是插件未请求 `offline_access`，不是安装详情页缺少可编辑开关。

v1.3.2 将公开配置和生成的 `.mcp.json` 精确更新为 `gateway:mcp offline_access`，并保持其他身份、资料、组织与管理 scope 被拒绝。包内自动化验证完成后仍不能声称真实续期通过；必须发布并更新 GPT Desktop 插件、重新授权，再按下表检查 Logto。

| 验证 | 结果与边界 |
| --- | --- |
| 包内自动化 | 56 项通过（常规运行中 4 项原生测试按设计跳过）；生成配置一致性与 `git diff --check` 通过 |
| Codex 0.155.0 原生隔离回归 | 4 项通过；授权 URL 的 scope 精确为 `gateway:mcp offline_access`，同时覆盖最小发现、Logto 式宽发现、缺失 scope 发现和 MCP UI 资源读取 |
| 真实 GPT Desktop | 尚未安装 v1.3.2；AuthorizationCode 换码返回 RefreshToken、到期 RefreshToken grant 与轮换仍待验证 |

## v1.3.3 Skill 同步与发布校验（2026-09-28）

- 同步来源为 Gateway `8a34acd8`，Plugin 与内置 Skill 统一升级到 `1.3.3`；除版本声明外，公开 Skill 文件与来源一致。
- 地图 / Gantt 双工具映射、参数边界和模型可见摘要规则纳入包合约测试；公开端点、OAuth 配置、生成的 `.mcp.json` 和品牌素材不变。
- 58 项测试中 54 项通过，4 项可选原生客户端测试因未指定 `PLANLY_CODEX_BIN` 跳过；Skill / Plugin 结构校验、MCP 配置一致性及差异检查通过。
- 没有重测真实 OAuth、地图网络或图形 UI；双工具契约冻结不代表 Gateway / 引擎迁移完成。

## v1.3.4 参数构建说明同步校验（2026-09-29）

- 同步来源为 Gateway `6157c24d`，16 个公开 Skill 文件逐字节一致，Plugin 与 Skill 均为 `1.3.4`。
- Gateway Skill 契约测试 18 项通过；插件常规测试共 59 项，55 项通过，4 项可选原生客户端测试因未指定 `PLANLY_CODEX_BIN` 按设计跳过。
- Skill / Plugin 结构校验、MCP 配置一致性、公开配置与品牌基线、差异检查通过；参数说明文字纳入包合约测试。
- 仅更新说明和版本，不改变自动补齐、空值校验或求解逻辑；未重测真实客户端，未部署服务或重提收费任务。

## v1.3.5 地点编码门禁同步校验（2026-09-30）

- 同步来源为 Gateway 本次实现工作区；16 个公开 Skill 文件逐字节一致，Plugin 与 Skill 均为 `1.3.5`。不记录未提交工作区的虚假提交 hash。
- 包合约覆盖实时 Schema、两种地点编码、混合结构转换、ID 唯一性、`referenceIds ⊆ poiIds`、坐标与空地点，以及地点检查绑定当前 revision 后才能确认和创建。
- 常规测试共 61 项，57 项通过，4 项可选原生客户端测试因未指定 `PLANLY_CODEX_BIN` 按设计跳过；Skill 结构校验、MCP 配置一致性、公开配置与品牌基线、逐字节同步及 `git diff --check` 通过。
- 本轮只同步 Skill 指导和客户端门禁，并与引擎 OpenAPI/Schema 契约说明配套；没有修改 Gateway 或引擎运行时、公开端点、OAuth、`.mcp.json` 或品牌。已创建新 tag `v1.3.5`，但未部署服务、更新用户安装或执行真实任务，也不声称已有服务端语义兜底。

## 真实目标客户端验收（全部待验证）

| 项目 | 操作及通过条件 | 当前状态 |
| --- | --- | --- |
| 安装与品牌 | 从本版本安装，显示 Planly 名称和图标；无历史远端 App 依赖 | 未验证 |
| 独立连接 | 插件提供一条 Planly MCP；无重复用户级连接或错误账号切换 | 未验证 |
| OAuth 授权请求 | 使用既有公开 client_id、S256、登记回调、正确 resource 与恰好 `gateway:mcp offline_access`；不误走 DCR、不照搬 OIDC 宽列表 | v1.3.1 实测只有 `gateway:mcp`；当前版本更新、重新授权后待重测 |
| OAuth 完整流程 | AuthorizationCode 换码返回 AccessToken 与 RefreshToken；access token 到期后出现 RefreshToken grant 并完成轮换；只读工具调用与撤销正常，无凭据泄漏 | 未验证 |
| UI 能力协商 | 宿主 initialize 声明正确的 UI 扩展/MIME，Gateway 返回协商能力 | 未验证 |
| 公共 UI | 真实镜像、积分或任务卡能从 resources/read 获取 HTML 并完成桥接渲染 | 未验证 |
| 版本化结果 | 真实成功任务与生效 ImageVersion 匹配；分别使用地图 / Gantt 展示工具和对应资源，单工程师路线属于地图状态；不传 `view` | 未验证 |
| 全屏/刷新 | inline 精简、全屏请求及拒绝处理、只读刷新、选择和游标保持 | 未验证 |
| 地图/规划回放 | 真实 CSP、图商 browser key/网络通过，规划回放不伪装实时位置 | 未验证 |
| 降级与隔离 | 无 UI、失效版本、认证/权限失效、多卡隔离及迟到响应正确 | 未验证 |

使用用户有权访问的已有任务，不为验收额外创建求解任务。先确认 Gateway 中该 ImageVersion 的 UI 可用；插件无法修复上游 CSP 未审批或引擎产物缺失。

## 边界

- 插件无 App 依赖不代表 OAuth 不需要用户同意。
- 桌面端/Codex 的 MCP 工具可调用，不代表 CLI、IDE 和桌面 GUI 都具备相同 UI 能力。
- 导入直接声明 MCP 的 GitHub 插件当前为 Desktop only；ChatGPT 网页端接入不在本包验收声明中。
- 不为兼容测试修改 Logto 注册、Gateway 权限或 CSP；遇到不兼容应记录真实错误并停止。
