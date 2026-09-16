# 工作流状态与失效规则

## 状态用途

在当前会话中维护一份统一状态，防止混用不同 ImageVersion、Schema、草稿、确认或任务。该状态只是 Agent 的临时工作上下文，不是 Gateway 领域对象、持久化记录或平台审计日志。

按以下概念维护状态；不要求向用户输出完整结构：

```yaml
access:
  tools_discovered: false
  tool_discovery_attempts: 0
  deferred_catalog_checked: false
  startup_retry_requested: false
  config_changed_in_session: false
  config_status: unknown
  auth_mode: oauth
  oauth_login_status: unknown
  oauth_login_attempted: false
  connection_status: unverified
intent: connect | create | integrate | query | explain
phase: access | analyze | build | confirm | submit | monitor | explain
scenario:
  objects: []
  resources: []
  rules: []
  objectives: []
  scale: {}
  data_sources: []
  expected_outputs: []
  open_questions: []
image_version:
  id: null
  resolved: false
  selection_source: null
  base_credit_cost: null
  duration_credit_per_10s: null
map_selection:
  value: null
  source: null
constraint_selection:
  available_presets: []
  recommended_preset_id: null
  selected_preset_id: null
  rationale: null
  custom_overrides: {}
schema:
  loaded_for_image_version_id: null
  composite_validation_view_ready: false
mapping:
  confirmed: []
  pending: []
  missing: []
  risks: []
location_resolution:
  candidates: []
  confirmed: []
draft:
  revision: 0
  value: null
confirmation:
  confirmed_revision: null
job:
  job_id: null
  status: null
evidence:
  facts: []
  inferences: []
  insufficient: []
```

## 状态不变量

- `access.connection_status` 只能在 Gateway 只读 tool 成功返回后记为 `connected`；仅发现客户端配置不等于连接成功。
- `gateway.*` 是逻辑名称；Codex 延迟目录的运行时名称以 `mcp__gateway__` 开头。每次工具发现尝试都必须按该前缀查询 `ALL_TOOLS`，不得用 `startsWith("gateway.")` 或首轮静态工具列表判断不可见。完成查询后才把 `deferred_catalog_checked` 设为 `true` 并增加 `tool_discovery_attempts`。
- 默认 `auth_mode=oauth`；配置脚本的 `config_status=configured` 不证明登录成功，OAuth 登录成功也不证明本轮已有 tools。只在客户端明确返回授权成功后记录 `oauth_login_status=authorized`，只读 tool 成功后才记录连接成功。
- 自动配置只添加缺失的固定端点用户级配置，或补齐同一端点的公开 Client ID、callback、resource 和 scope；写入前确认宿主支持预注册客户端；冲突、显式禁用、项目覆盖或解析失败时停止，不静默覆盖。默认不读取 `.env`、PAT 或 OAuth 凭证存储。
- 新配置或宿主明确要求认证时发起一次 OAuth，并设置 `oauth_login_attempted=true`。取消、超时或失败后停止，只有用户新动作才重试；认证/网络/权限错误不能统一解释为工具冷启动。
- 既有配置未改动且首次延迟发现为空时，优先检查宿主认证状态/刷新，必要时设置 `startup_retry_requested=true` 并只在原聊天重试一次；不能因此推断需要重复登录。
- 用户重试后必须重新查询延迟目录，增加 `tool_discovery_attempts`；成功后清除 `startup_retry_requested` 并静默继续，不使用“已重连”。第二次仍不可见时提示宿主重载/Restart extension 或 CLI 续接，不循环重试。
- 只有 `apply` 返回 `changed=true` 才设置 `config_changed_in_session=true`；新配置不能误判为冷启动竞态。优先宿主可用重载，缺少热加载能力时如实提示必要的重启。
- 仅用户明确选择 PAT 时切换兼容路线，只记录其归一化状态，不记录 PAT、OAuth Token、授权码、认证头、原始响应或凭证缓存。
- 当前会话已验证连接后不重复执行接入引导；只读 tool 后续返回认证或网络错误时使连接状态失效。
- 只把用户明确提供或 Gateway 实时返回的信息记为已确认事实。
- ImageVersion 必须经当前用户可用列表和详情验证。用户明确选择，或唯一可用版本与已知场景适配且无影响适用性的未决问题时，才记为 `resolved=true`；`selection_source` 分别记为 `user_explicit` 或 `sole_compatible`。默认选定不得伪装为用户确认，多个未指定候选仍需选择，不适配时不得继续。
- 图商验证支持后，`map_selection.source` 按用户明确指定或地区默认分别记为 `user_explicit`、`regional_default`，`value` 写入草稿顶层 `map_provider`。地区默认无需单独确认，用户明确指定优先；未解决的地点或能力冲突不能标为已确定。最终创建确认仍覆盖实际镜像和图商。
- 约束方案名称、说明和分值只来自当前 ImageVersion 详情；`selected_preset_id` 仅用于会话解释，不得作为创建字段提交。
- `schema.loaded_for_image_version_id` 必须等于当前 `image_version.id`，否则不得构建或提交草稿。
- 只有 `schema.composite_validation_view_ready` 为 `true` 且约束相关场景事实充分时，才能设置 `constraint_selection.recommended_preset_id` 或 `selected_preset_id`。
- 任一创建字段变化都必须增加 `draft.revision` 并把 `confirmation.confirmed_revision` 清空。
- `draft.revision` 和 `confirmation.confirmed_revision` 只用于 Agent 内部绑定确认，不向业务用户展示，也不要求用户复述 revision 编号。
- 地址解析候选不是最终事实；只有用户确认的 POI 或坐标才能进入字段映射和草稿。
- 网点、仓库或站点位置适用同一规则；存在网点引用但没有已确认有效位置时必须保持为阻断缺口。
- 只有未决必填问题已解决、关键映射已确认且明显非法值已清除时，才能进入确认阶段。
- 只有 `confirmation.confirmed_revision == draft.revision` 时才能调用创建 tool。
- `job.job_id` 只记录 Gateway 明确返回或近期任务查询能够确认的任务标识。

## 失效与回退

### ImageVersion 改变

清空：

- 已加载 Schema；
- 内部组合校验视图及其完成状态；
- 当前 ImageVersion 的约束方案、推荐和选择；
- 字段映射、缺口和基于旧版本得出的风险；
- 地址解析候选及已确认位置映射；
- 创建草稿及其 revision 对应的确认；
- 未提交草稿关联的任务状态。

重置版本的 resolved 与 selection_source，并重新验证新版本的适配性和图商支持；用户已经明确指定的图商要求作为业务事实保留，不能被地区默认覆盖。保留业务场景事实，重新选定并验证后读取新版本 Schema。已创建的历史 `job_id` 只能作为只读历史任务保留，不能与新草稿混用。

### 草稿改变

`image_version_id`、`map_provider`、`expected_solve_duration`、`request_payload` 或 `constraint_overrides` 任一字段变化都视为新 revision。更换约束方案或调整个别罚分后必须重新计算 `constraint_overrides`；只要最终覆盖项发生变化，就重新执行辅助检查、积分查询、摘要展示和用户确认。

`map_provider` 改变时同步更新 map_selection 的值与来源，清空地址解析候选和已确认位置映射，并使用新图商重新解析。

### 结果需要调整

- 业务对象、资源、规则或目标需要改变时，回到场景分析。
- 仅 Schema 字段、数据映射、时长、图商或合法覆盖项需要改变时，回到参数构建。
- 不在结果解释阶段直接修改旧任务或自动创建对照任务。

## 快捷路线

- 已有 `job_id` 的查询不要求创建场景状态，但必须先验证当前用户可访问该任务。
- 历史任务解释不得假设当前会话草稿就是该任务的原始输入。
- 日常数据接入沿用已确认场景、已选定验证的 ImageVersion、Schema 和字段映射；任一上游内容变化时重新确认映射。
