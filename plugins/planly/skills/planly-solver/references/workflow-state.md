# 工作流状态与失效规则

## 状态用途

在当前会话中维护一份统一状态，防止混用不同 ImageVersion、Schema、草稿、确认或任务。该状态只是 Agent 的临时工作上下文，不是 Gateway 领域对象、持久化记录或平台审计日志。

按以下概念维护状态；不要求向用户输出完整结构：

```yaml
access:
  installation_mode: unknown
  trusted_connection: null
  runtime_tool_names: {}
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
ui:
  host_support: unknown
  map_display_tool_name: null
  gantt_display_tool_name: null
  display_job_id: null
  render_status: unverified
intent: connect | create | integrate | query | explain | change | display
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
location_encoding:
  mode: null # centralized_refs | inline_objects
  source: null # schema_preferred | existing_valid_payload
location_validation:
  checked_revision: null
  status: pending # pending | passed | failed
draft:
  revision: 0
  value: null
confirmation:
  confirmed_revision: null
job:
  job_id: null
  status: null
job_contexts: {} # 按 job_id 绑定已确认输入来源及 revision；不读取历史 payload
change_request:
  baseline_job_id: null
  resource_id: null
  date: null
  protected_assignments: []
  adjustable_ticket_ids: []
  open_questions: []
evidence:
  facts: []
  inferences: []
  insufficient: []
```

## 状态不变量

- `access.connection_status` 只能在 Gateway 只读 tool 成功返回后记为 `connected`；仅发现客户端配置不等于连接成功。
- `installation_mode` 取 plugin/standalone/unknown，依据宿主安装信息而非工具缺失推断。plugin/unknown 不运行用户级配置脚本；可信连接失效或来源不明时停止，不静默切换账号/端点。
- `gateway.*` 是逻辑名称；每次工具发现都查询 `ALL_TOOLS` 或实际宿主目录，核对连接归属后记录实际工具名。不得硬编码插件完整命名空间、仅凭后缀信任来源，或用 `startsWith("gateway.")` 判断不可见。仅独立 Skill 的既有连接可按 `mcp__gateway__` 查询。完成查询后才设置 `deferred_catalog_checked` 并增加 `tool_discovery_attempts`。
- 默认 `auth_mode=oauth`；配置脚本的 `config_status=configured` 不证明登录成功，OAuth 登录成功也不证明本轮已有 tools。只在客户端明确返回授权成功后记录 `oauth_login_status=authorized`，只读 tool 成功后才记录连接成功。
- 独立 Skill 自动配置只添加缺失的固定端点用户级配置，或补齐同一端点的公开 Client ID、callback、resource 和 scope；写入前确认宿主支持预注册客户端；冲突、显式禁用、项目覆盖或解析失败时停止，不静默覆盖。默认不读取 `.env`、PAT 或 OAuth 凭证存储。
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
- `location_encoding.mode` 只能根据当前实时 `request_schema` 允许的地点结构、其中明确给出的首选方式及已有草稿的实际合法结构确定，不按镜像名称、版本号或历史引擎经验推断。新草稿采用 Schema 明确首选的模式；全部地点已经以合法内嵌对象存在时可记录 `inline_objects / existing_valid_payload`。
- `centralized_refs` 表示业务对象地点全部使用字符串 ID，并由 Schema 定义的集中地点集合提供目标；`inline_objects` 表示业务对象地点全部使用完整内嵌对象且没有字符串地点引用。两种形式同时出现属于混合草稿，不能设置为已通过。
- Schema 允许集中结构时，混合草稿必须先规范化并记录为 `centralized_refs / schema_preferred`：保留已有 ID，为确实缺失且 Schema 要求 ID 的地点只生成一次稳定 ID，替换内嵌地点引用。该转换属于草稿变化，必须增加 revision、清空创建确认并重新校验；无法无损转换时保持 `failed`，不得静默合并同名地点。
- 每次检查当前草稿后，把 `location_validation.checked_revision` 设为被检查的 revision；只有地点模式、位置完整性、ID 唯一性、引用和坐标均通过时才设置 `status=passed`，否则设置 `status=failed` 并保留阻断问题。
- 只有 `schema.composite_validation_view_ready` 为 `true` 且约束相关场景事实充分时，才能设置 `constraint_selection.recommended_preset_id` 或 `selected_preset_id`。
- 任一创建字段变化都必须增加 `draft.revision`，把 `confirmation.confirmed_revision` 和 `location_validation.checked_revision` 清空，并把 `location_validation.status` 重置为 `pending`；即使地点字段未变，也必须对新 revision 重新执行地点检查。
- `draft.revision` 和 `confirmation.confirmed_revision` 只用于 Agent 内部绑定确认，不向业务用户展示，也不要求用户复述 revision 编号。
- 地址解析候选不是最终事实；只有用户确认的 POI 或坐标才能进入字段映射和草稿。
- 网点、仓库或站点位置适用同一规则；存在网点引用但没有已确认有效位置时必须保持为阻断缺口。
- 只有未决必填问题已解决、关键映射已确认、明显非法值已清除，并且 `location_validation.status == passed` 与 `location_validation.checked_revision == draft.revision` 同时成立时，才能展示创建摘要并进入确认阶段。
- 只有上述地点校验门仍成立且 `confirmation.confirmed_revision == draft.revision` 时才能调用创建 tool。
- `job.job_id` 只记录 Gateway 明确返回或近期任务查询能够确认的任务标识。
- 创建 tool 明确返回后，把该 `job_id` 与本次已确认的输入 revision、场景事实和调整边界绑定到 `job_contexts`；输入证据仅来自会话已确认草稿或用户明确提供并确认属于该任务的资料。只读查询不能把当前草稿自动绑定为历史任务输入，缺失时记为不可用而非由结果猜测还原。
- `change_request.baseline_job_id` 指向用户正在讨论且有权限访问的基线任务。变更新任务创建后保留基线和新任务的关系，不能覆盖掉逐单对比所需的基线输入及结果证据；这些仅是当前会话上下文，不是 Gateway 保存的原始请求。
- `ui.map_display_tool_name` / `ui.gantt_display_tool_name` 只来自该任务的 Gateway 展示提示，并分别与当前可信工具目录核对；换任务、换连接、错误版本、权限失效或目录刷新后重新发现，不复用旧映射，也不从其中一个名称推导另一个。
- `ui.host_support` 只有宿主明确完成 MCP Apps 协商才记 supported；没有图形宿主实际证据时 `render_status` 仍为 unverified。只读工具调用成功不证明 HTML 已渲染或地图已联网。无 UI 时按 [展示参考](mcp-apps-ui.md) 降级，不调用写工具修复展示。

## 失效与回退

### ImageVersion 改变

清空：

- 已加载 Schema；
- 内部组合校验视图及其完成状态；
- 当前 ImageVersion 的约束方案、推荐和选择；
- 字段映射、缺口和基于旧版本得出的风险；
- 地址解析候选及已确认位置映射；
- 地点编码模式及其来源；
- 地点校验状态及其绑定的 revision；
- 创建草稿及其 revision 对应的确认；
- 未提交草稿关联的任务状态。

重置版本的 resolved 与 selection_source，并重新验证新版本的适配性和图商支持；用户已经明确指定的图商要求作为业务事实保留，不能被地区默认覆盖。保留业务场景事实，重新选定并验证后读取新版本 Schema。已创建的历史 `job_id` 只能作为只读历史任务保留，不能与新草稿混用。

### 草稿改变

`image_version_id`、`map_provider`、`expected_solve_duration`、`request_payload` 或 `constraint_overrides` 任一字段变化都视为新 revision。新 revision 必须把地点校验重置为 `pending` 并重新检查，地点修复和混合结构规范化也不例外。更换约束方案或调整个别罚分后必须重新计算 `constraint_overrides`；只要最终覆盖项发生变化，就重新执行辅助检查、积分查询、摘要展示和用户确认。

`map_provider` 改变时同步更新 map_selection 的值与来源，清空地址解析候选和已确认位置映射，并使用新图商重新解析。

### 结果需要调整

- 业务对象、资源、规则或目标需要改变时，回到场景分析。
- 仅 Schema 字段、数据映射、时长、图商或合法覆盖项需要改变时，回到参数构建。
- 不在结果解释阶段直接修改旧任务或自动创建对照任务。

### 业务变更：某人某日请假

1. 定位基线任务及其已确认输入来源。按业务名称解析对应资源 ID 和用户指定的日期；姓名重复、日期缺失或存在多份候选方案时，只澄清无法唯一识别的部分，不猜测。
2. 继承该基线已确认的 ImageVersion、图商、业务规则、目标、合法覆盖项，以及预约冻结和可调整范围。人员请假不构成改变目标或重新选择约束方案的理由，也不要求用户重复已知规则。不得把“尚未开始”自行解释为可以重排，或一律冻结所有结果工单。
3. 根据当前实时 Schema 表达该资源在指定日期不可用，只改变用户明确提出的事项。原已确认预约与请假冲突、冻结范围未确认或当前能力不能表达时，补问决定方案的必要问题；不能擅自取消预约、扩大可调整范围或假设某个固定字段会自动锁定服务时间。
4. 结合原输入与最新结果准备新草稿。必须保护的工单保留已确认人员和服务开始 / 结束；允许调整的预排按已确认边界处理。不在历史输入缺失时由结果重建并宣称还原了原始参数，不直接沿用与基线不对应的旧重排文件。
5. 新草稿增加 revision、清空旧确认，并重新进行 Schema、地点、引用和业务边界检查。再查询积分、展示变更范围与预计消耗，取得本次明确创建确认后才提交新任务；“帮我重新规划”不替代该创建门。仍保留基线任务，不修改或删除它。
6. 成功后按相同业务 ID 对比，分别核对请假人员转出的工单、其他工单的连带换人、服务时间变化和保留项；对缺失字段明确无法核对。参见 [结果解释](result-explanation.md)。

## 快捷路线

- 已有 `job_id` 的查询不要求创建场景状态，但必须先验证当前用户可访问该任务。
- 历史任务解释不得假设当前会话草稿就是该任务的原始输入。
- 日常数据接入沿用已确认场景、已选定验证的 ImageVersion、Schema 和字段映射；任一上游内容变化时重新确认映射。
