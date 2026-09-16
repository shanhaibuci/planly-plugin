# Gateway MCP 自动配置与 OAuth 接入

## 固定目标与宿主边界

先读取 `../config/system-endpoint.json`；MCP URL 只由 `origin + mcp_path` 派生，Server 名为 `gateway`，OAuth scope 为 `gateway:mcp`。公开 Client ID 和回调从 `../config/oauth-client.json` 读取，Token/Secret 不得进入该文件；OAuth resource 与上述 MCP URL 相同。自动配置要求 HTTPS，不接受调用方覆盖 URL，不从 `.env`、命令行 URL 或会话输入派生目标。

- **Codex CLI/IDE**：Agent 使用下述内置脚本自动添加缺失的用户级 MCP 配置，再通过客户端原生 OAuth 登录。默认不读取 `.env`、PAT 或 OAuth 凭证缓存，不配置静态 Authorization。
- **ChatGPT Plugin**：使用当前 Plugin 绑定的远程 MCP 连接和宿主 OAuth。缺少授权时引导连接当前 Plugin；不要运行本地 Codex 脚本，也不要假设宿主工具名以 `mcp__gateway__` 开头。
- **其他客户端**：只有确认当前宿主提供 MCP 注册和 OAuth 入口后才使用其原生方式。没有可用配置能力时准确说明限制，不虚构“已配置”、不要求 PAT 作为替代。

## 1. 先发现延迟 tools

`gateway.*` 是逻辑名称。Codex 中先检查实际延迟目录，不能用首轮静态列表判断缺失：

```javascript
const gatewayTools = ALL_TOOLS.filter(
  ({ name }) => name.startsWith("mcp__gateway__"),
);
if (gatewayTools.some(
  ({ name }) => name === "mcp__gateway__gateway_image_versions_list_available",
)) {
  await tools.mcp__gateway__gateway_image_versions_list_available({});
}
```

只读调用成功就静默继续原任务，不再次配置或登录。认证 challenge 才进入 OAuth；网络、权限或服务端错误应按实际原因处理，不能一律重写配置。ChatGPT 从 Plugin 绑定连接的实际目录发现相应只读能力。

## 2. tools 确实不可见：自动配置

下面命令由 Agent 执行，不交给用户执行。`<skill-dir>` 为当前 Skill 的真实路径，`<project-root>` 为当前用户工程根目录。

```bash
python3 <skill-dir>/scripts/configure_codex_gateway_mcp.py status --project-root <project-root>
```

默认 `--auth oauth`，只检查配置，不验证登录。先检查 `codex_oauth_support`：只有 `supported` 才由脚本写入预注册配置；`unsupported` 说明当前 CLI 需更新至支持预注册 Client ID 和 resource 的版本，不自动升级全局客户端。`cli_unavailable` 或 `unknown` 时改用经确认支持预注册客户端的宿主原生配置/认证入口；没有可用能力就报告限制，不让用户编辑凭证或降级 PAT。依据 `config_status`：

- `missing`：简短告知“我会自动添加 Gateway MCP，并按需打开登录授权。”然后执行下列 `apply`，不再要求用户填写 URL、创建 PAT 或编辑配置；遵守宿主原生文件/命令授权策略，不绕过确认。
- `oauth_client_missing`：地址和已有字段无冲突，但缺少公开 OAuth 元数据时，Agent 执行 `apply` 补齐 Client ID、callback、resource 和 scope，不移除已有工具策略。
- `configured`：不重复写入，保留已有 OAuth 客户端参数、工具权限和其他设置，继续检查宿主连接/认证状态。
- `url_conflict`、`auth_conflict`、`transport_conflict`、`disabled`、`project_override`、`oauth_client_conflict`、`oauth_resource_conflict`、`oauth_scope_conflict`：停止自动配置。只说明冲突类别，询问用户是否需要定向修复；不打印旧凭证、不删除其他连接或放开禁用/工具权限策略。当前自动脚本不覆盖这些配置。
- 解析、权限或安全检查失败：停止并说明原因，不尝试手工读取完整配置、凭证缓存或换一个文件覆盖。

```bash
python3 <skill-dir>/scripts/configure_codex_gateway_mcp.py apply --project-root <project-root>
```

`apply` 仅添加固定端点的缺失用户级配置，或补齐同一端点缺失的公开 OAuth 字段；原子写入并设置文件权限 `0600`，保留其他配置。匹配时幂等不写入；发现当前项目或祖先目录的 `.codex/config.toml` 声明 Gateway 时报告覆盖，不写用户级配置。脚本输出的 `oauth_login_status=unknown`、`connection_status=unverified` 不能解释为登录成功。`reload_required` 只表示配置变更可能需要宿主重新加载，不证明工具可用。

## 3. 自动发起 OAuth，用户只完成登录授权

对于刚添加的配置或宿主明确报告需要认证的连接，优先使用当前宿主原生认证入口。有 Codex CLI 时，由 Agent 执行：

```bash
codex mcp login gateway --scopes gateway:mcp
```

执行前再次确认当前有效 Gateway 配置仍指向 Skill 端点且没有项目覆盖；在已配置的工程目录运行。该命令由客户端处理 OAuth Discovery、注册、浏览器授权和 Token 存储；不读取客户端凭证文件，不把 Token 提取出来自己调用 HTTP。运行时保持登录进程等待回调，用户在客户端提供的授权链接完成登录、同意授权和必要的 MFA。不要自动代替用户点击授权同意，不要求复制授权码或 Token 到聊天。

IDE 无 CLI 时，使用宿主的 Authenticate 入口；如果当前 Agent 无法触发该入口，只让用户点击 Authenticate，不要求安装 CLI 或编辑配置。远程开发环境的浏览器回调不可达时，准确报告回调问题，不能假设公网服务就意味着 localhost 回调可达。

OAuth 服务端前置条件：Gateway `/mcp/meta` 的 `oauth_enabled=true` 仍不足以证明客户端可接入。当前 Skill 随包携带维护者创建的既有 Agent MCP 公开客户端配置（服务端显示名仍为 `DFST Agent MCP`，本次品牌发布不修改该注册），直接使用预注册路线，不要求用户创建应用。Logto 必须支持当前客户端可用的注册/识别方式；在其他部署中未公布 DCR/CIMD 且没有对应预注册客户端配置时，报告需要平台维护者配置 OAuth 客户端，不让终端用户改填 PAT。预注册 Client ID 是公开标识，Client Secret 不得放进 Skill 或聊天。

取消/超时后停止当前登录；没有用户新动作不得反复启动登录。Discovery、客户端识别/注册或回调不兼容、网络错误、scope 不足分别说明，不降级为 PAT，不放宽 Gateway 的安全配置。OAuth 登录成功只记录授权完成，仍需后续只读 tool 验证。

## 4. 重新发现、验证并继续原任务

- `apply` 真正改变配置后，先完成必要的 OAuth，再使用宿主提供的重载/工具刷新能力并重新发现。不能声称配置文件写入会把 MCP 自动热加载进当前轮次。
- 配置正确、未改动且首次按 `mcp__gateway__` 查询仍不可见时，不据此推断 OAuth 失效；先检查宿主认证状态；宿主不提供状态入口时保留 `unknown`，不能据此假定需要重新登录。没有明确认证 challenge 时，使用可用刷新能力，或只请求用户在当前聊天发送一次“重试”。
- 用户发送“重试”后必须重新执行上述发现；第二次正确查询仍不可见时才提示 **Restart extension**（IDE）或续接 CLI 会话。不循环重试或凭空声称已授权；宿主报告需要认证时转到 OAuth。
- 本轮刚变更配置且宿主不能重载时，不进入冷启动重试分支：IDE 直接提示 **Restart extension** 并返回原聊天，CLI 通过 `codex resume` 续接原会话。不要求新建聊天或重新描述业务需求。
- 登录完成/重载后，调用只读 `gateway.image_versions.list_available`。只有成功才记录 `connected` 并继续原业务意图；不使用“已重连”。若认证失败，仅发起有界 OAuth 修复；网络、权限、scope 和服务错误保留真实原因，不重复写配置。

接入成功时不输出配置报告；失败时只输出必要错误和修复动作。未创建或查询已有任务时不提及 `job_id`。连接成功前不收集生产业务数据。

## 显式 PAT 兼容模式

只有用户明确选择 PAT 时才读取 [PAT 兼容接入](gateway-access-pat.md)，并显式传入 `--auth pat`。默认流程不得要求 PAT，也不得因 OAuth 失败自动进入兼容模式。Gateway 用户级 REST 数据集成工具的认证约定不因本次 MCP 接入调整而改变。
