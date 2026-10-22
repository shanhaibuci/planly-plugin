from __future__ import annotations

import hashlib
import json
import re
import struct
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/planly"
SKILL = PLUGIN / "skills/planly-solver"
PARAMETERS = SKILL / "references/parameter-building.md"
WORKFLOW = SKILL / "references/workflow-state.md"
EXECUTION = SKILL / "references/job-execution.md"


class PluginPackageTest(unittest.TestCase):
    def test_constraint_mode_names_are_four_characters_and_keep_real_preset_bindings(self):
        # This is a display/instruction contract, not an engine-weight change.
        section = PARAMETERS.read_text(encoding="utf-8").split("## 约束方案推荐与个别调整\n", 1)[1].split("\n## ", 1)[0]
        rows = [
            [cell.strip() for cell in line.strip("|").split("|")]
            for line in section.splitlines() if line.startswith("|")
        ][2:]
        self.assertEqual(["全面兼顾", "均衡优先", "效率优先"], [row[0] for row in rows])
        self.assertTrue(all(len(row) == 2 and len(row[0]) == 4 and row[1] for row in rows))
        self.assertIn("工作时长", rows[1][1])
        self.assertIn("工单数量", rows[1][1])
        self.assertIn("行驶距离", rows[2][1])
        self.assertIn("在途用时", rows[2][1])
        for invariant in ("未指定倾向且无继承设置时初始选中“全面兼顾”", "自定义覆盖也保留",
                          "真实方案 ID 与分值", "不按标题相似或列表顺序套用", "不为凑齐三项编造罚分"):
            self.assertIn(invariant, section)
        self.assertIn("parameter-building.md#约束方案推荐与个别调整", EXECUTION.read_text(encoding="utf-8"))
        self.assertNotRegex(section, r"[0-9]+hard/[0-9]+medium/[0-9]+soft")

    def test_group_confirmation_binds_defaults_candidate_mapping_and_revalidated_revision(self):
        execution = EXECUTION.read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        parameters = PARAMETERS.read_text(encoding="utf-8")
        for marker in ("selected_option_ids=[当前值ID]", "confirm_label=确认求解", "resource_spec", "constraint_mode",
                       "当前设置（已调整）", "choice_bindings", "完整 `selected_groups`", "各组恰好出现一次",
                       "按 ID 而非 label", "重新通过 Schema 和地点校验", "候选映射", "仅支持 `presentation=buttons`"):
            self.assertIn(marker, execution)
        self.assertIn("choice_bindings: null", workflow)
        self.assertIn("不复用旧 revision 的检查结果", workflow)
        self.assertIn("默认采用标准 `medium`", parameters)
        self.assertIn("不单独询问", parameters)
        self.assertNotIn("仅一个 confirm_solve 选项完成确认", workflow)

    def test_resource_tier_mapping_has_three_names_without_hardware_columns(self):
        section = PARAMETERS.read_text().split("## 求解资源规格\n", 1)[1].split("\n## ", 1)[0]
        rows = [
            [cell.strip().strip("`") for cell in line.strip("|").split("|")]
            for line in section.splitlines()
            if line.startswith("|") and "`" in line
        ]
        self.assertEqual(3, len(rows))
        self.assertTrue(all(len(row) == 2 for row in rows))
        self.assertEqual({
            "small": "轻量",
            "medium": "标准",
            "large": "增强",
        }, {code: label for label, code in rows})

    def test_manifest_skill_and_release_versions_agree(self):
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        version = (ROOT / "VERSION").read_text().strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual("1.3.11", version)
        self.assertEqual(version, manifest["version"])
        self.assertEqual(version, (SKILL / "VERSION").read_text().strip())
        frontmatter = (SKILL / "SKILL.md").read_text().split("---", 2)[1]
        self.assertRegex(frontmatter, r"(?m)^name: planly-solver$")
        self.assertIn(f'version: "{version}"', frontmatter)
        self.assertEqual(PLUGIN.name, manifest["name"])
        self.assertEqual("Planly 智能规划助理", manifest["interface"]["displayName"])
        self.assertIn("$planly-solver", (SKILL / "agents/openai.yaml").read_text())
        self.assertEqual("./skills/", manifest["skills"])
        self.assertEqual("./.mcp.json", manifest["mcpServers"])
        self.assertNotIn("apps", manifest)

    def test_plugin_and_skill_display_names_agree_without_renaming_technical_ids(self):
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        market = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        skill_ui = (SKILL / "agents/openai.yaml").read_text(encoding="utf-8")
        display_name = manifest["interface"]["displayName"]
        self.assertIn(f'  display_name: "{display_name}"\n', skill_ui)
        for prompt in manifest["interface"]["defaultPrompt"]:
            self.assertIn(display_name, prompt)
        self.assertIn(display_name, skill_ui.split('  default_prompt: ', 1)[1])
        self.assertIn("$planly-solver", skill_ui)
        self.assertEqual("planly", manifest["name"])
        self.assertEqual("planly", market["plugins"][0]["name"])
        self.assertEqual("personal", market["name"])
        self.assertIn(f"| 展示名称 | {display_name} |", (ROOT / "README.md").read_text())
        self.assertNotIn("Planly 场景求解", json.dumps(manifest, ensure_ascii=False) + skill_ui)

    def test_installation_instructions_use_current_release(self):
        version = (ROOT / "VERSION").read_text().strip()
        readme = (ROOT / "README.md").read_text()
        self.assertIn(f"| Plugin / Skill 版本 | **{version}**", readme)
        self.assertEqual([f"v{version}"], re.findall(r"--ref (\S+)", readme))
        self.assertIn(f"## {version} 变更", readme)
        release = ROOT / "docs/releases" / f"v{version}.md"
        self.assertTrue(release.is_file(), "Current release notes must exist")
        self.assertIn(f"# Planly Plugin v{version}", release.read_text())

    def test_direct_mcp_has_no_legacy_app_dependency_or_embedded_ui(self):
        self.assertFalse((PLUGIN / ".app.json").exists())
        self.assertFalse((PLUGIN / "mcp.json").exists(), "Avoid two transport declarations")
        for path in PLUGIN.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            self.assertNotEqual(".html", path.suffix)
            if path.suffix in {".json", ".md", ".yaml", ".py"}:
                self.assertNotIn("asdk_app_", path.read_text())

    def test_published_names_and_text_do_not_reintroduce_legacy_brand(self):
        paths = [ROOT / "README.md", ROOT / ".agents/plugins/marketplace.json"]
        paths.extend(PLUGIN.rglob("*"))
        for path in paths:
            if "__pycache__" in path.parts:
                continue
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn("dfst", str(path.relative_to(ROOT)).lower())
                if path.is_file():
                    try:
                        content = path.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        continue  # Binary brand assets have separate format checks.
                    self.assertNotIn("dfst", content.lower())

    def test_marketplace_resolves_real_plugin_and_explicit_policies(self):
        market = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        self.assertRegex(market["name"], r"^[A-Za-z0-9_-]+$")
        self.assertEqual("Planly Plugins", market["interface"]["displayName"])
        self.assertEqual(1, len(market["plugins"]))
        entry = market["plugins"][0]
        self.assertEqual("planly", entry["name"])
        self.assertEqual("local", entry["source"]["source"])
        self.assertEqual(PLUGIN.resolve(), (ROOT / entry["source"]["path"]).resolve())
        self.assertEqual({"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, entry["policy"])
        self.assertEqual("Productivity", entry["category"])

    def test_referenced_assets_exist_and_pngs_are_valid(self):
        interface = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())["interface"]
        for key in ("composerIcon", "logo", "logoDark"):
            with self.subTest(asset=key):
                path = (PLUGIN / interface[key]).resolve()
                self.assertTrue(path.is_relative_to(PLUGIN.resolve()))
                self.assertTrue(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        license_path = PLUGIN / "assets/OFL-Quicksand.txt"
        license_text = license_path.read_text(encoding="utf-8")
        self.assertIn("SIL OPEN FONT LICENSE", license_text)
        self.assertIn("The Quicksand Project Authors", license_text)
        self.assertEqual(
            "b4578833b5c1ce3a9a811df806760ba4e98566c3b52689808fa1290f946450fc",
            hashlib.sha256(license_path.read_bytes()).hexdigest(),
            "Ship the complete, unchanged Quicksand license",
        )
        self.assertFalse((PLUGIN / "assets/OFL-Outfit.txt").exists())
        self.assertFalse((PLUGIN / "assets/OFL-DMSerifDisplay.txt").exists())

    def test_brand_assets_match_approved_ice_blue_baseline(self):
        baseline = json.loads((ROOT / "tests/brand-assets-baseline.json").read_text())
        interface = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())["interface"]
        approved_sources = {
            "composerIcon": ("docs/brand-assets/planly/favicon/favicon.png", [256, 256]),
            "logo": ("docs/brand-assets/planly/screen/logo-horizontal.png", [1480, 440]),
            "logoDark": ("docs/brand-assets/planly/screen/logo-horizontal-dark.png", [1480, 440]),
        }
        self.assertEqual(set(approved_sources), set(baseline))
        for key, expected in baseline.items():
            with self.subTest(asset=key):
                self.assertEqual(approved_sources[key], (expected["source"], expected["size"]))
                self.assertEqual(expected["path"], interface[key])
                data = (PLUGIN / interface[key]).read_bytes()
                self.assertEqual(expected["sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(b"IHDR", data[12:16])
                self.assertEqual(expected["size"], list(struct.unpack(">II", data[16:24])))
                self.assertEqual(6, data[25], "Brand PNG must retain its RGBA channel")

    def test_skill_local_reference_links_resolve_inside_bundle(self):
        for source in SKILL.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", source.read_text()):
                if urlparse(target).scheme or target.startswith("#"):
                    continue
                target = target.split("#", 1)[0]
                path = (source.parent / target).resolve()
                with self.subTest(source=source.name, target=target):
                    self.assertTrue(path.is_relative_to(PLUGIN.resolve()))
                    self.assertTrue(path.exists(), target)

    def test_skill_prioritizes_plugin_connection_without_duplicate_configuration(self):
        skill = (SKILL / "SKILL.md").read_text()
        access = (SKILL / "references/gateway-access.md").read_text()
        pat = (SKILL / "references/gateway-access-pat.md").read_text()
        self.assertIn("`plugin`、`standalone` 或 `unknown`", skill)
        self.assertIn("禁止执行用户级 `apply` 创建第二条连接", skill)
        self.assertIn("不得硬编码插件运行时前缀", skill)
        self.assertIn("不得仅凭后缀或描述认定来源", skill)
        self.assertIn("无法确认归属时停止并澄清", access)
        self.assertIn("独立 Skill 用户级连接", access)
        self.assertIn("安装来源未知", access)
        self.assertIn("插件模式不执行本文脚本", pat)
        self.assertIn("Desktop only", access)
        self.assertNotIn(".app.json", skill + access + pat)

    def test_skill_exposes_readonly_ui_and_preserves_task_confirmation(self):
        skill = (SKILL / "SKILL.md").read_text()
        ui = (SKILL / "references/mcp-apps-ui.md").read_text()
        for marker in (
            "map_display_tool_name", "gantt_display_tool_name", "display_tools_by_job_id", "JSON TextContent",
            "_meta.ui.resourceUri", "resources/read", "text/html;profile=mcp-app",
            "当前可信目录", "不根据 image_version_id 拼接工具名",
            "不传 `view`", "长工程师 ID 不截断", "默认不轮询",
            "只回传意图，不创建/修改任务", "detail_page_url",
            "权限错误", "不能代替图形宿主验收",
        ):
            self.assertIn(marker, ui)
        self.assertIn("gateway.ui.show_choices", skill)
        self.assertIn("Agent 仍执行原有创建校验", skill)
        self.assertIn("普通选择不等于创建授权", skill)
        self.assertIn("不声称已显示", skill)

    def test_map_and_gantt_have_separate_tools_and_state(self):
        skill = (SKILL / "SKILL.md").read_text()
        ui = (SKILL / "references/mcp-apps-ui.md").read_text()
        workflow = (SKILL / "references/workflow-state.md").read_text()
        for name in ("map_display_tool_name", "gantt_display_tool_name"):
            self.assertIn(name, skill)
            self.assertIn(name, ui)
            self.assertIn(f"  {name}: null", workflow)
        self.assertNotIn("  display_tool_name: null", workflow)
        self.assertNotIn("view=map|gantt", ui)
        self.assertIn("Gantt 工具只传 `job_id`", ui)
        self.assertIn("地图失败不表示 Gantt 失败", ui)
        self.assertIn("在下一条消息调用它", ui)

    def test_result_explanation_uses_model_visible_summary_not_ui_metadata(self):
        explanation = (SKILL / "references/result-explanation.md").read_text()
        self.assertIn("不返回 `result_summary`、`engine_view` 或 `pending_engine_view`", explanation)
        self.assertIn("gateway.solver_jobs.get_summary", explanation)
        self.assertIn("_meta.gateway_ui.engine_view", explanation)
        self.assertIn("不视为 Agent 已获得的分析证据", explanation)

    def test_result_answers_stay_on_question_and_do_not_invent_objectives_or_apologies(self):
        explanation = (SKILL / "references/result-explanation.md").read_text()
        for marker in (
            "问题范围守恒与目标守恒", "不转而批评同址拆分", "不自行制定目标",
            "没有可核对的先前错误，不生成认错叙事",
            "未被询问且不影响结论的证明问题留在内部核查",
            "不自动转入调参或替代方案建议",
            "不能擅自改成“同址集中优先于均衡”等优先级",
        ):
            self.assertIn(marker, explanation)

    def test_existing_workload_requires_input_result_binding_and_not_equal_totals(self):
        explanation = (SKILL / "references/result-explanation.md").read_text()
        workflow = WORKFLOW.read_text()
        for marker in (
            "明确绑定该任务", "已有、新派和全天合计", "按业务 ID 对照公开结果",
            "单量相同或安排可行，都不能单独证明已有工单已传入",
            "输入中有而结果缺失时如实报告", "单量核对不能证明旧单时间未变",
        ):
            self.assertIn(marker, explanation)
        self.assertIn("job_contexts:", workflow)
        self.assertIn("当前草稿自动绑定为历史任务输入", workflow)

    def test_same_location_cap_is_not_a_proof_of_actual_split_or_optimality(self):
        explanation = (SKILL / "references/result-explanation.md").read_text()
        for marker in (
            "独立计数", "单人当日上限", "已有占用",
            "超硬上限时直接回答不能全部同人",
            "再结合本次目标优先级和全天指标解释当前分法",
            "用户要求证明或比较替代方案时，如实说明证据覆盖范围",
            "局部单移假定其他分配不变，不等于全局重新求解",
            "无需为这一算术事实创建对照任务", "是权重 50 的软约束，不保证同人",
        ):
            self.assertIn(marker, explanation)
        self.assertIn("结论强度与证据相称", (SKILL / "SKILL.md").read_text())

    def test_comparing_workers_requires_both_schedules_and_no_automatic_paid_counterfactual(self):
        explanation = (SKILL / "references/result-explanation.md").read_text()
        for marker in (
            "核对目标工单实际归属", "用户点名的两个候选", "不只看日初出发点",
            "涉及时间先按当前摘要 Schema 核实", "数字必须现场计算", "其他工单不动",
            "配置说明优化方向，不充当决策记录",
            "局部单移假定其他分配不变，不等于全局重新求解",
            "规则调整与对照求解须由用户决定",
            "单项资格或当前安排的局部冲突均不足以判定替代排程整体可行性",
        ):
            self.assertIn(marker, explanation)
        self.assertIn("不自动组合实验、调参或反事实任务", (SKILL / "SKILL.md").read_text())

    def test_explanation_uses_actual_objectives_and_scores_without_inventing_components(self):
        explanation = (SKILL / "references/result-explanation.md").read_text()
        for marker in (
            "本次生效的硬约束、相关目标优先级和实际指标解释取舍",
            "得分有助于回答时可展示原值，并解释层级和业务含义",
            "仅有总分不能反推分项贡献",
            "不得将 soft 数值直接写成秒或分钟",
        ):
            self.assertIn(marker, explanation)
        self.assertIn("得分按解释价值展示", (SKILL / "SKILL.md").read_text())

    def test_current_draft_button_confirmation_is_single_use_and_falls_back(self):
        execution = (SKILL / "references/job-execution.md").read_text()
        workflow = WORKFLOW.read_text()
        for marker in ("presentation=buttons", "confirm_solve", "edit_parameters", "question_id", "consumed", "不再要求打字", "旧卡", "计费条件"):
            self.assertIn(marker, execution)
        self.assertIn("invalidated", workflow)
        self.assertIn("无卡片时允许当前摘要后的明确文字确认", workflow)

    def test_absence_inherits_confirmed_scope_but_preserves_create_gates_and_diff(self):
        skill = (SKILL / "SKILL.md").read_text()
        workflow = WORKFLOW.read_text()
        explanation = (SKILL / "references/result-explanation.md").read_text()
        parameters = PARAMETERS.read_text()
        for marker in (
            "业务变更：某人某日请假", "也不要求用户重复已知规则",
            "不构成改变目标或重新选择约束方案的理由",
            "不得把“尚未开始”自行解释为可以重排",
            "取得本次明确创建确认后才提交新任务",
            "仍保留基线任务，不修改或删除它",
        ):
            self.assertIn(marker, workflow)
        self.assertIn("继承不免除实时 Schema", parameters)
        self.assertIn("其他工单的连带换人", explanation)
        self.assertIn("核实服务开始和结束的语义后比较变化", explanation)
        self.assertIn("变更结果问答须先读取 [结果解释](references/result-explanation.md)", skill)
        self.assertIn("即使用户已提供全部数据文件也不能跳过", skill)
        self.assertIn("人员、顺序与时间分别比较", explanation)
        self.assertIn("顺序依据实际 `sequence` 或摘要 Schema 定义的有序列表", explanation)
        self.assertIn("不因插入新单或时间后移推断其他工单顺序改变", explanation)
        self.assertIn("字段缺失时不猜测", explanation)

    def test_service_time_requires_schema_semantics_not_departure_minus_duration(self):
        explanation = (SKILL / "references/result-explanation.md").read_text()
        for marker in (
            "### 时间字段语义", "语义、单位和时区",
            "`arrival_time` / `departure_time` 不因字段名而自动等于服务开始 / 结束",
            "不得仅凭 `duration` 自行用离开减时长推定服务开始",
            "不能将推算值冒充直接返回值", "具体哪些时段未能核对",
            "不能把计划要求当成结果证明", "冻结要求不等于结果已保持",
            "窗口相同不能证明服务起止相同",
            "不能笼统称“原预约未变”或“原工单完全未变”",
        ):
            self.assertIn(marker, explanation)

    def test_display_buttons_are_readonly_and_real_anomalies_cannot_be_hidden(self):
        ui = (SKILL / "references/mcp-apps-ui.md").read_text()
        explanation = (SKILL / "references/result-explanation.md").read_text()
        self.assertIn("不要求用户再输入展示提示词", ui)
        self.assertIn("不要查询积分、准备变更草稿或创建新任务来完成展示", ui)
        self.assertIn("简短不等于隐瞒异常", explanation)
        self.assertIn("地图线路与排程时间不一致", explanation)
        self.assertIn("不能声称 Skill 修改修复了引擎时间差", explanation)

    def test_parameter_guidance_distinguishes_omitted_null_and_empty_without_inference(self):
        parameters = PARAMETERS.read_text()
        for marker in (
            "字段省略、显式 `null` 和空数组", "`required`", "`minItems`", "示例不",
            "隐含必填", "保留用户已有指派及顺序", "不假设引擎会自动补齐",
            "不猜测字段修补后自动重提收费任务",
        ):
            self.assertIn(marker, parameters)
        self.assertNotIn("agents[].tickets", parameters)

    def test_location_encoding_contract_is_explicit_and_uses_live_schema(self):
        skill = (SKILL / "SKILL.md").read_text()
        parameters = PARAMETERS.read_text()
        workflow = WORKFLOW.read_text()
        execution = EXECUTION.read_text()

        self.assertRegex(
            workflow,
            r"location_encoding:\n"
            r"  mode: null # centralized_refs \| inline_objects\n"
            r"  source: null # schema_preferred \| existing_valid_payload\n"
            r"location_validation:\n"
            r"  checked_revision: null\n"
            r"  status: pending # pending \| passed \| failed",
        )
        self.assertLess(
            parameters.index("读取并解析当前 ImageVersion 的 `request_schema`"),
            parameters.index("location_encoding:"),
        )
        for text in (skill, parameters, workflow):
            self.assertRegex(text, r"不(?:得)?按镜像名称")
        for forbidden in ("x-force/vrp-0", "1.1.1-alpha-SNAPSHOT"):
            self.assertNotIn(forbidden, parameters + workflow + execution)

        for marker in (
            "centralized_refs / schema_preferred",
            "inline_objects / existing_valid_payload",
            "集中地点集合必须存在且非空",
            "每个 POI ID 都非空且在集合内唯一",
            "referenceIds ⊆ poiIds",
            "每个被引用 POI 都包含 Schema 要求的完整坐标",
            "任何业务对象地点都不得是字符串引用",
            "集中地点集合可以省略",
            "经度必须在 `[-180, 180]`、纬度必须在 `[-90, 90]`",
            "同时出现字符串地点引用和内嵌地点对象",
            "转换必须增加草稿 revision",
        ):
            self.assertIn(marker, parameters)

    def test_location_validation_blocks_confirmation_and_create_until_current_revision_passes(self):
        skill = (SKILL / "SKILL.md").read_text()
        parameters = PARAMETERS.read_text()
        workflow = WORKFLOW.read_text()
        execution = EXECUTION.read_text()

        self.assertIn("location_validation.status == passed", workflow)
        self.assertIn("location_validation.checked_revision == draft.revision", workflow)
        self.assertIn("重置为 `pending`", workflow)
        self.assertIn("即使地点字段未变，也必须对新 revision 重新执行地点检查", workflow)
        self.assertIn("不查询积分、不展示确认问题", execution)
        self.assertIn("任一条件不成立都不得调用", execution)
        self.assertIn("不得自动重提收费任务", execution)
        self.assertIn("不展示创建确认，也不调用 `gateway.solver_jobs.create`", parameters)
        self.assertIn("任何地点、ID、引用或坐标修复都形成新 revision", parameters)
        self.assertIn("当前 revision 的地点校验未通过时，不得进入创建确认", skill)

        self.assertLess(
            execution.index("location_validation.status=passed"),
            execution.index("### 确认卡与文字降级"),
        )
        self.assertLess(
            execution.index("调用 `gateway.solver_jobs.create` 前再次确认"),
            execution.index("调用时只传当前草稿中的合法字段"),
        )
        self.assertIn("客户端门禁", parameters)
        self.assertIn("不替代 Gateway Schema 校验", parameters)
        self.assertIn("不是引擎语义校验的服务端保证", parameters)

    def test_readme_discloses_host_scope_and_real_ui_acceptance(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("Desktop only", readme)
        self.assertIn("docs/acceptance.md", readme)
        self.assertIn("真实客户端验收", readme)
        self.assertIn("未验证", (ROOT / "docs/acceptance.md").read_text())

    def test_public_connections_match_approved_baseline(self):
        # Routing and public OAuth registration stay fixed. The old App binding
        # is intentionally removed; its absence has a separate regression test.
        baseline = json.loads((ROOT / "tests/public-config-baseline.json").read_text())
        self.assertEqual({
            "skills/planly-solver/config/system-endpoint.json",
            "skills/planly-solver/config/oauth-client.json",
        }, set(baseline))
        for relative, expected in baseline.items():
            with self.subTest(path=relative):
                actual = hashlib.sha256((PLUGIN / relative).read_bytes()).hexdigest()
                self.assertEqual(expected, actual)
        endpoint = json.loads((SKILL / "config/system-endpoint.json").read_text())
        self.assertEqual({"origin", "mcp_path"}, set(endpoint))
        self.assertEqual("https", urlparse(endpoint["origin"]).scheme)
        oauth = json.loads((SKILL / "config/oauth-client.json").read_text())
        self.assertEqual({"client_id", "callback_url", "scopes"}, set(oauth))
        self.assertEqual(["gateway:mcp", "offline_access"], oauth["scopes"])

    def test_release_excludes_environment_credentials_and_internal_resources(self):
        for path in PLUGIN.rglob("*"):
            self.assertFalse(path.is_symlink(), str(path))
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            self.assertFalse(path.name.startswith(".env"), str(path))
            self.assertNotIn(path.suffix, {".pem", ".key", ".p12"})
            self.assertNotEqual("gateway-embedded-agent.md", path.name)
            if path.suffix in {".json", ".yaml", ".md", ".py"}:
                text = path.read_text()
                self.assertNotRegex(text, r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


if __name__ == "__main__":
    unittest.main()
