# Gateway 求解任务执行

## 创建前检查与确认

只接受当前 ImageVersion、Schema 和参数构建阶段已经完成的草稿。展示创建摘要前，必须同时满足 `location_validation.status=passed` 和 `location_validation.checked_revision == draft.revision`；不满足时返回参数构建阶段修复或重新校验，不查询积分、不展示确认问题。门禁通过后调用 `gateway.credits.get_me`，以简洁业务摘要覆盖日期、城市/网点、工程师/车辆和工单数量、服务时间要求、关键规则、求解强度（档位名称）、求解约束模式（方案名称，有调整时标注）、求解时长及预计积分。已确认且未变的规则可一句概括，不强制重复六个分组或空的风险标题；真正的新取舍或异常必须说明。展示余额与可计算的预计剩余，但不为展示重复打开积分卡。

预计消耗使用当前 ImageVersion 详情中的 `base_credit_cost`、`duration_credit_per_10s` 和当前 `expected_solve_duration` 计算：

```text
base_credit_cost + ceil(求解秒数 / 10) × duration_credit_per_10s
```

计算保留 4 位小数，显示可去除尾零。用“预计消耗”表达创建前估算，创建后按 Gateway 返回的 credit_cost 报告实际冻结积分，不机械引用内部计费条款。不得硬编码单价或从其他 ImageVersion 沿用价格。历史 ImageVersion 没有公开价格时说明暂时无法预估，不自行猜测。

### 确认卡与文字降级

1. 当前工具 Schema 支持 `groups`、`selected_option_ids` 和 `confirm_label` 时，用一张 `gateway.ui.show_choices` 卡展示两组单选：`resource_spec`（求解强度）使用三个档位，`constraint_mode`（求解约束）按[约束模式](parameter-building.md#约束方案推荐与个别调整)映射当前 ImageVersion 的合法方案，使用对应四字名称与当前选中值。每组传 `id`、`label`、`selection_mode=single`、`options` 和 `selected_option_ids=[当前值ID]`，`confirm_label=确认求解`；默认值由 Skill 决定，用户不必重新选择。当前约束已调整时用“当前设置（已调整）”保留真实覆盖项，不用预设覆盖。候选说明展示业务差异，只纳入符合已确认硬规则和取舍的方案；无法如实表示当前值或候选不符合工具限制时沿用单组确认。
2. 多组位于 `prompt` 参数摘要前；摘要包含上述业务信息、求解时长及预计积分，不重复会随切换变化的旧档位/方案值。其他参数可通过文字提出修改。仅支持 `presentation=buttons` 时沿用 `selection_mode=single`、选项 `confirm_solve` / `edit_parameters`（“确认求解”/“修改参数”）；无可用 UI 时在摘要后文字询问“确认开始吗？”。不要重复提问或引用 Skill 路径、条款和 revision。
3. 每次展示生成唯一 `question_id`，在会话 `confirmation` 中绑定当前 revision、账号/可信连接、镜像、计费快照 `quote`，状态为 `pending`；多组另存 `choice_bindings`（各组候选 ID 到实际参数的固定映射）。只有匹配当前问题的完整 `selected_groups` 才是对该组合的确认：各组恰好出现一次、各有一个合法 ID，无额外组或字段；按 ID 而非 label 映射规格及约束差异，未选择部分保持不变。变更生成新 revision，重新通过 Schema 和地点校验后记录 `confirmed_revision`；不再要求打字或再点一次。单组仍只接受 `confirm_solve`；`edit_parameters` 使确认失效并返回修改，普通选择和地图/Gantt意图不授权创建。
4. 预选和切换不等于确认，只有显式提交或当前摘要后的明确文字肯定有效。发送失败可复制选择结果，或用文字明确所选组合后确认；用户同时更改其他参数须更新摘要。除本次多组回传中已绑定的候选组合外，任何创建字段、账号/连接、镜像、候选映射或计费条件变化均使旧确认失效，按新 revision 重新校验和确认。丢失绑定状态时重新展示，不能复用旧卡或此前“可以”“继续”。
5. 创建前再次调用 `gateway.image_versions.get_detail` 和 `gateway.credits.get_me`，复核候选映射仍有效、当前单价、求解时长和积分；与已展示费用不一致须重新确认，余额不足停止。地点校验的 `checked_revision` 和 `confirmed_revision` 必须同时等于当前 revision。创建尝试前置 `confirmation.status=consumed`；重复消息只返回已知任务状态。发送成功不代表创建成功，创建结果未知时按下一节核对，不自动重提。

## 创建任务

调用 `gateway.solver_jobs.create` 前再次确认地点校验仍为 `passed`、其 `checked_revision` 与当前草稿 revision 相等，且 `confirmed_revision` 也等于当前草稿 revision；任一条件不成立都不得调用。调用时只传当前草稿中的合法字段。只有 tool 明确返回非空 `job_id` 和任务状态时，才能判定求解任务创建成功并保存：

- `job_id`；
- Gateway 返回的初始状态；
- Gateway 返回的积分费用或冻结信息；
- 推荐的下一次查询时机。

创建成功不等于方案生成成功：

- `created`、`queued`、`preparing_engine`、`engine_starting`、`running`、`pending_confirmation`：只说明任务已创建或正在处理；
- `succeeded`：才能说明求解成功并进入结果解释；
- `failed`、`canceled`、`timed_out`、`archive_failed`：说明任务曾创建成功，但本次求解或归档没有成功。

Gateway 返回字段或业务错误时，保留 `code`、`message` 和 `details` 事实，给出对应修正建议。修改草稿后必须生成新 revision、重新执行地点校验并重新确认；不得自动重提收费任务。

## 结果不明确时

创建调用超时、断连或返回结果不明确时不得自动再次创建：

1. 调用 `gateway.solver_jobs.list` 检查近期同一 ImageVersion 的任务；
2. 只有能够确认对应任务时才记录其 `job_id`；
3. 仍无法确认时要求用户人工核对；
4. 不创建“替代任务”。

调度或归档阶段失败可能已经生成任务记录。有 `job_id` 时查询该任务，不重新创建。

## 查询状态

已有 `job_id` 时先调用 `gateway.solver_jobs.get_detail` 验证访问和状态。只在用户需要持续等待时有限轮询，避免紧密循环；长任务返回 `job_id` 并建议稍后继续查询。

新建任务按 `expected_solve_duration` 分流：

- 不超过 `PT30S`：在当前交互中有限等待并查询终态；达到短任务等待边界仍未完成时，说明任务仍在运行，返回 `job_id` 和后续入口后停止轮询；
- 超过 `PT30S`：创建成功后立即返回任务信息，不在当前交互中等待终态；
- 任一路线都不得通过高频查询模拟等待，也不得因为状态查询失败创建替代任务。

- `created`、`queued`、`preparing_engine`、`engine_starting`、`running`：解释当前阶段，不声称已有结果。
- `pending_confirmation`：说明平台仍在确认，不把待定结果当成成功。
- `succeeded`：进入结果解释，调用结果摘要、摘要 Schema 和结果入口。
- `failed`、`canceled`、`timed_out`、`archive_failed`：只解释公开安全错误和下一步，不推测内部堆栈。

调用 `gateway.solver_jobs.get_result_access` 后只使用 `detail_page_url`。绝对 URL 原样返回；相对 URL 只与 `../config/system-endpoint.json` 中的 `origin` 合并。用户可见链接文案统一为“点击查看派单路线与排程详情”。不得构造下载或对象存储地址。

在支持 MCP Apps 的宿主中，任务查询及结果查看按 [只读展示](mcp-apps-ui.md) 使用公共卡片和 Gateway 返回的实际展示工具；保留上述网页入口作为降级。展示失败不创建替代任务、不重跑求解、不绕过权限，也不等同于求解失败。
