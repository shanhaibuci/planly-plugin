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


class PluginPackageTest(unittest.TestCase):
    def test_manifest_skill_and_release_versions_agree(self):
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        version = (ROOT / "VERSION").read_text().strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual(version, manifest["version"])
        self.assertEqual(version, (SKILL / "VERSION").read_text().strip())
        frontmatter = (SKILL / "SKILL.md").read_text().split("---", 2)[1]
        self.assertRegex(frontmatter, r"(?m)^name: planly-solver$")
        self.assertIn(f'version: "{version}"', frontmatter)
        self.assertEqual(PLUGIN.name, manifest["name"])
        self.assertEqual("Planly 场景求解", manifest["interface"]["displayName"])
        self.assertIn("$planly-solver", (SKILL / "agents/openai.yaml").read_text())
        self.assertEqual("./skills/", manifest["skills"])
        self.assertEqual("./.mcp.json", manifest["mcpServers"])
        self.assertNotIn("apps", manifest)

    def test_installation_instructions_use_current_release(self):
        version = (ROOT / "VERSION").read_text().strip()
        readme = (ROOT / "README.md").read_text()
        self.assertIn(f"| Plugin / Skill 版本 | **{version}** |", readme)
        self.assertEqual([f"v{version}"], re.findall(r"--ref (\S+)", readme))
        self.assertIn(f"## {version} 变更", readme)

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
        license_text = (PLUGIN / "assets/OFL-Outfit.txt").read_text()
        self.assertIn("SIL OPEN FONT LICENSE", license_text)
        self.assertIn("The Outfit Project Authors", license_text)
        self.assertFalse((PLUGIN / "assets/OFL-DMSerifDisplay.txt").exists())

    def test_brand_assets_match_approved_knight_a_baseline(self):
        baseline = json.loads((ROOT / "tests/brand-assets-baseline.json").read_text())
        interface = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())["interface"]
        self.assertEqual({"composerIcon", "logo", "logoDark"}, set(baseline))
        for key, expected in baseline.items():
            with self.subTest(asset=key):
                self.assertEqual(expected["path"], interface[key])
                data = (PLUGIN / interface[key]).read_bytes()
                self.assertEqual(expected["sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(b"IHDR", data[12:16])
                self.assertEqual(expected["size"], list(struct.unpack(">II", data[16:24])))
                self.assertEqual(6, data[25], "Brand PNG must retain its RGBA channel")
                self.assertTrue(expected["source"].startswith("docs/brand-assets/planly/"))

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
            "display_tool_name", "display_tools_by_job_id", "JSON TextContent",
            "_meta.ui.resourceUri", "resources/read", "text/html;profile=mcp-app",
            "当前可信目录", "不根据 image_version_id 拼接工具名",
            "view=map|gantt", "长工程师 ID 不截断", "默认不轮询",
            "只回传意图，不创建/修改任务", "detail_page_url",
            "权限错误", "不能代替图形宿主验收",
        ):
            self.assertIn(marker, ui)
        self.assertIn("gateway.ui.show_choices", skill)
        self.assertIn("创建确认门不变", skill)
        self.assertIn("不声称已显示", skill)

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
        self.assertEqual(["gateway:mcp"], oauth["scopes"])

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
