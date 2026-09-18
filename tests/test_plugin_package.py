from __future__ import annotations

import hashlib
import json
import re
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
        self.assertEqual("./.app.json", manifest["apps"])
        self.assertNotIn("mcpServers", manifest)

    def test_installation_instructions_use_current_release(self):
        version = (ROOT / "VERSION").read_text().strip()
        readme = (ROOT / "README.md").read_text()
        self.assertIn(f"| Plugin / Skill 版本 | **{version}** |", readme)
        self.assertEqual([f"v{version}"], re.findall(r"--ref (\S+)", readme))
        self.assertIn(f"## {version} 变更", readme)

    def test_app_alias_is_planly_and_registered_identity_is_unchanged(self):
        app = json.loads((PLUGIN / ".app.json").read_text())
        self.assertEqual({
            "apps": {
                "planly": {
                    "id": "asdk_app_6a9a8567d2dc819190f6338b44a06c29",
                    "category": "Productivity",
                },
            },
        }, app)

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
        self.assertIn("SIL OPEN FONT LICENSE", (PLUGIN / "assets/OFL-DMSerifDisplay.txt").read_text())

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

    def test_public_connections_match_approved_baseline(self):
        # Public routing/OAuth bytes stay fixed; the App alias changes in v1.2.2.
        # Registered App identity is also asserted separately, not only by hash.
        baseline = json.loads((ROOT / "tests/public-config-baseline.json").read_text())
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
