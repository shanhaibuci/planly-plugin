---
name: planly-solver
description: Use Planly Gateway to configure solver access, turn routing, dispatch, scheduling, or resource-planning requirements into a validated solve request, submit and track the job, explain the result, and generate local data-integration tools. Use for Planly planning scenarios and existing solver jobs; do not use for implementing solver algorithms.
metadata:
  version: "1.3.2"
---

# Planly Solver

使用一个 Agent 完成场景分析、参数构建、Gateway 求解任务执行和结果解释。把这些能力作为同一求解闭环的内部阶段，不把它们当成独立 Skill 或未来专业 Agent。

把 Gateway 视为认证、鉴权、积分、Schema 权威校验、任务状态、调度、归档和审计的唯一可信边界。只负责用户引导、会话草稿、辅助检查、任务操作和公开结果解释。

## 全局规则

- 跟随用户语言；API 字段、错误码、枚举和 tool name 保持原值。
- 优先使用 Planly Plugin 自带的 MCP 连接和宿主 OAuth；只有明确的独立 Skill 安装才自动配置用户级 Gateway MCP。用户只完成登录授权，不要求准备 PAT、编辑配置或运行配置命令。遵守宿主权限确认，不代替用户同意 OAuth。只有用户明确选择独立接入的 PAT 兼容模式时才使用独立参考；OAuth 失败不得自动降级为 PAT，不读取或输出任何 Token、授权码、密码或凭证缓存。
- 优先收集脱敏结构和小样本，不要求上传完整生产数据。
- 不访问管理员接口、Registry、Git、Gateway 数据库、对象存储内部地址、引擎实例、最终引擎请求归档或完整结果文件。
- 不保存或声称 Gateway 保存了 `request_payload` 原文。只在当前会话或用户明确指定的本地文件中维护草稿。
- 不实现模型、算法或求解器工程，不自动组合实验、调参或反事实任务。求解能力由选定 ImageVersion 对应的引擎实现。
- 不直接调用规划引擎；所有求解任务必须通过 Gateway 创建。

## 使用时自动配置 Gateway MCP

任一需要 Gateway 的路线先检查一次，已连接时直接继续原任务。先按宿主安装信息区分 `plugin`、`standalone` 或 `unknown`，不依据工具缺失猜测安装方式：

1. 读取 `config/system-endpoint.json`，其 `origin` 和 `mcp_path` 是唯一地址事实源；不得从 `.env`、会话输入或命令行 URL 覆盖。客户端选择按实际宿主，不根据用户业务数据猜测。
2. 先发现并只读验证：`gateway.*` 是逻辑名称。从宿主目录（Codex 的 `ALL_TOOLS` 包括延迟 tools）发现 `gateway.image_versions.list_available` 对应的实际名称，并核对 Planly 插件归属与受信连接。不得硬编码插件运行时前缀，不得仅凭后缀或描述认定来源；不得用 `startsWith("gateway.")` 判断 tools 不可见。多个候选或来源不明时停止并澄清连接，不混用账号/端点。独立 Skill 的旧用户级连接可以使用 `mcp__gateway__`；插件模式不得因此排除其他合法命名空间。成功后静默继续。
3. tools 确实不可见时读取 [Gateway 自动接入](references/gateway-access.md)。`plugin` 模式只检查插件安装、启用、宿主 OAuth 和工具加载，禁止执行用户级 `apply` 创建第二条连接；`unknown` 模式先确认安装来源。只有明确的 `standalone` 模式才由 Agent 运行 `scripts/configure_codex_gateway_mcp.py status --project-root <project-root>`。先按脚本的 `codex_oauth_support` 确认宿主具备预注册 OAuth 能力；缺失配置或仅缺少公开 OAuth 字段时，简短告知并执行同一脚本的 `apply`，默认 OAuth，不要求 PAT 或用户执行终端命令。从 `config/oauth-client.json` 读取公开 Client ID、回调和 scope；只添加固定 HTTPS 端点的用户级缺失配置或补齐公开字段，保留原工具策略；已有配置、显式禁用或项目覆盖发生冲突时停止，取得用户定向修复决定，不静默覆盖。
4. 新配置或宿主明确要求登录时由 Agent 发起原生 OAuth；插件模式使用当前插件 MCP 的 Authenticate 入口，不能拿独立连接的登录命令代替。明确的独立 Skill 且有 CLI 时使用 `codex mcp login gateway --scopes gateway:mcp,offline_access`，否则使用宿主认证入口。只让用户完成浏览器登录授权；不读取 `.env` 或 OAuth 凭证缓存，不让用户粘贴 Token。
5. 首次按实际连接查询仍不可见不等于认证失败；独立 Skill 首次按 `mcp__gateway__` 查询仍不可见也适用。按接入参考检查认证状态、刷新或在原聊天重试一次；不得反复登录。配置/授权刚更新后使用可用重载能力；确需重启时 IDE 提示 **Restart extension**，CLI 续接原会话，不要求重新描述需求。
6. 配置写入和 OAuth 登录成功都不代表工具已载入。必须重新发现并通过只读 tool 验证后才记录已连接；成功后静默继续原始意图，不输出接入报告，不得把“工具已就绪”描述为“已重连”。取消、超时、网络、scope、注册或配置冲突按真实原因停止，不重复写配置或自动降级。

## 先路由意图

识别当前意图并只进入需要的路线：

1. **首次接入或接入修复**：读取[Gateway 自动接入](references/gateway-access.md)。自动配置 MCP，按需发起 OAuth，并在工具载入后执行只读连接验证。连接成功前不收集生产业务数据。
2. **新建场景求解**：依次执行场景分析、参数构建、任务执行和结果解释。
3. **日常数据接入**：先完成场景分析和参数映射，再读取 [日常数据接入](references/data-integration.md) 在用户工程生成转换工具。
4. **已有任务查询**：取得 `job_id` 后直接读取 [任务执行](references/job-execution.md) 查询；成功任务再进入结果解释。
5. **已有结果解释**：先验证任务访问和状态，再读取 [结果解释](references/result-explanation.md)。

Gateway tools 不可用或只读调用认证失败时，停止其他路线并切换到接入检查与修复。

## 维护统一会话状态

开始任何路线前读取 [工作流状态](references/workflow-state.md)，只维护一份当前事实。严格执行以下失效规则：

- ImageVersion 改变时，清空旧 Schema、字段映射、参数草稿和创建确认。
- 任一求解字段改变时，提升内部草稿 revision，并立即清空此前确认；revision 不向业务用户展示。
- Schema 必须来自当前已选定并验证的 ImageVersion 的实时查询结果；默认选定不等于用户已授权创建。
- 只有当前草稿 revision 与用户确认 revision 一致时才能创建任务。
- 创建成功后保留 `job_id`；调用结果不明确时不得自动重复创建。

## 新建场景求解主流程

### 1. 场景分析与 ImageVersion 选择

读取 [场景分析](references/scenario-analysis.md)。梳理业务场景，实时查询当前用户可用 ImageVersion 及详情。只有一个可用且适配的版本时默认采用并进入参数构建，不单独询问是否使用；明显不适配时停止，适用性不明时只澄清必要业务问题。用户已明确指定版本时验证后采用；多个版本且未指定时再推荐并让用户选择。

用户未指定图商且地点明确时，在所选 ImageVersion 支持的前提下默认采用中国境内 `AMAP`、境外 `HERE`；用户明确指定受支持图商时优先遵照。将使用的镜像、图商及简短推荐依据合并到后续业务回复，不单独要求图商确认、不展示“镜像 + 图商”的组合选择卡。能力冲突、跨境或地点不明时才澄清必要问题；地址解析结果确认和最终创建确认仍保留。本阶段不得推荐约束方案或设置罚分。

### 2. 场景参数构建

读取 [参数构建](references/parameter-building.md)。严格按以下顺序执行：获取当前 ImageVersion 的 `request_schema` → 与创建顶层字段及约束覆盖 Schema 组成内部校验视图 → 按 Schema 理解并收集场景参数 → 在目标、硬规则和可接受取舍足以判断后推荐约束方案及罚分。必要时通过 Gateway 把用户提供的地址解析为候选 POI 并确认，按 Schema 决定地点结构、枚举机器值和可覆盖字段，不硬编码 `plan.pois`、枚举语义、约束方案或 Gateway 技术默认值。使用网点、仓库或站点时必须按 Schema 提供已确认的有效位置并验证引用；业务不需要且 Schema 不要求时不得构造空位置的占位对象。用户询问其他方案时介绍当前 ImageVersion 返回的全部方案，允许在选定方案基础上按用户要求调整个别开放罚分。完成数据准备、内部字段映射、缺口和风险识别，生成带内部 revision 的创建草稿。必填缺口、未确认关键映射或明显非法值存在时不得进入创建确认。

Skill 求解默认开启路线绘制：在当前 Schema 允许且用户未指定时，于确认前显式写入 `request_payload.options.draw_route=true`；保留用户明确提供的合法值。该 Skill 默认行为不改变 Gateway 默认值，完整处理规则见参数构建参考。

### 3. Gateway 求解任务执行

读取 [任务执行](references/job-execution.md)。查询积分，按固定业务分组展示当前草稿、预计积分消耗和可计算时的预计剩余，再询问“是否按以上参数创建求解任务”。把用户确认绑定到当前内部 revision，然后调用 `gateway.solver_jobs.create`。只有明确返回 `job_id` 和状态才称为任务创建成功；只有状态为 `succeeded` 才称为求解成功。期望求解时长不超过 `PT30S` 时有限等待终态，超过 `PT30S` 时创建后立即返回；均不得紧密轮询。

### 4. 求解结果分析

只有任务成功终态才读取结果摘要、摘要 Schema 和结果入口。读取 [结果解释](references/result-explanation.md)，默认按整体可行性、派单成功与未派数量、公开未派原因、总里程、总时间、非零吨公里费用、工程师派单顺序和详情入口展示。结合得分摘要判断和解释，但默认不展示原始 hard/soft score。把结论分为可确认事实、合理推断和证据不足；不得伪装成引擎真实决策链。

用户查看任务、地图、Gantt 或工程师路线时，按 [MCP Apps 展示](references/mcp-apps-ui.md) 使用已授权只读 UI。成功结果概览可附会话内卡片；针对性问题先回答，不强制额外卡片。使用 Gateway 返回的 `display_tool_name`，不拼版本工具名；无 UI 时保留摘要和网页入口，不声称已显示。

结果不可解或质量不满足用户目标时，只提出业务数据或合法参数调整建议。用户决定调整后返回场景分析或参数构建，生成新 revision，并重新经过积分提示和人工确认。

## Gateway tool 边界

使用以下用户级业务 tools：

- `gateway.image_versions.list_available`
- `gateway.image_versions.get_detail`
- `gateway.image_versions.get_request_schema`
- `gateway.image_versions.get_result_summary_schema`
- `gateway.map.geocode`
- `gateway.credits.get_me`
- `gateway.solver_jobs.create`
- `gateway.solver_jobs.list`
- `gateway.solver_jobs.get_detail`
- `gateway.solver_jobs.get_summary`
- `gateway.solver_jobs.get_result_access`

额外允许当前可信 Gateway 目录中的只读 UI tools：`gateway.ui.show_choices`，以及 Gateway 按任务返回的 `display_tool_name` 所指向的版本化结果工具。必须与当前目录交叉核对，只给 schema 允许的 `job_id`、`view`、可选 `engineer_id`；不自行拼接 `gateway.ui.result_...`。选择卡只传意图，不等于创建授权，创建确认门不变。工具禁用、版本不匹配或权限失效时停止并按展示参考降级，不探测其他版本或账号。

先用只读 tool 获取事实，再推荐、构建或解释。不要把历史经验当作当前用户的镜像、权限、Schema、积分或任务状态。生成到用户工程的日常脚本优先调用 Gateway REST API，不要求运行环境加载 Skill 或 MCP 客户端。

## 阶段输出

每完成一个业务阶段，使用用户容易理解的业务语言说明：已确认事实、当前产物、仍需用户提供的内容和下一步。不把“字段映射”、revision、原始字段路径或机器枚举作为普通用户阶段标题或确认用语。接入成功时不单独输出接入报告；接入失败时只输出缺失或错误与修复动作。只有用户要求查询已有任务或 Gateway 已创建任务时才提及 `job_id`。求解完成后提供业务摘要和“点击查看派单路线与排程详情”入口。
