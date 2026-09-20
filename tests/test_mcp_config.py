from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_mcp_config", ROOT / "scripts/build_mcp_config.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class McpConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.plugin = Path(self.temp.name) / "plugin"
        self.config = self.plugin / "skills/planly-solver/config"
        self.config.mkdir(parents=True)
        for name in ("system-endpoint.json", "oauth-client.json"):
            (self.config / name).write_bytes((builder.SKILL / "config" / name).read_bytes())

    def update(self, name, **fields):
        path = self.config / name
        value = json.loads(path.read_text())
        value.update(fields)
        path.write_text(json.dumps(value))

    def test_manifest_uses_tested_server_scopes_and_oauth_fields(self):
        rendered = builder.render_mcp_config()
        self.assertEqual(rendered, (builder.PLUGIN / ".mcp.json").read_bytes())
        self.assertEqual(rendered, builder.render_mcp_config())
        value = json.loads(rendered)
        endpoint = json.loads((self.config / "system-endpoint.json").read_text())
        client = json.loads((self.config / "oauth-client.json").read_text())
        self.assertEqual({"mcpServers": {"planly": {
            "type": "http",
            "url": endpoint["origin"] + endpoint["mcp_path"],
            "scopes": client["scopes"],
            "oauth": {"clientId": client["client_id"], "callbackUrl": client["callback_url"]},
        }}}, value)
        self.assertEqual(["gateway:mcp"], client["scopes"])

    def test_generation_uses_changed_public_sources_not_hardcoded_endpoint(self):
        self.update("system-endpoint.json", origin="https://gateway.example.test")
        self.update("oauth-client.json", client_id="public-test-client")
        connection = json.loads(builder.render_mcp_config(self.plugin))["mcpServers"]["planly"]
        self.assertEqual("https://gateway.example.test/mcp", connection["url"])
        self.assertEqual("public-test-client", connection["oauth"]["clientId"])

    def test_rejects_unsafe_endpoint_and_unknown_fields(self):
        for change in [
            {"origin": "http://gateway.example.test"},
            {"origin": "https://user:password@gateway.example.test"},
            {"origin": "https://gateway.example.test/path"},
            {"mcp_path": "//other.example.test/mcp"},
            {"origin": "https://gateway.example.test?token=secret"},
            {"extra": "unexpected"},
        ]:
            with self.subTest(change=change):
                path = self.config / "system-endpoint.json"
                path.write_bytes((builder.SKILL / "config/system-endpoint.json").read_bytes())
                self.update("system-endpoint.json", **change)
                with self.assertRaises(builder.public_config.ConfigurationError):
                    builder.render_mcp_config(self.plugin)

    def test_rejects_secrets_incompatible_callbacks_and_overbroad_scopes(self):
        for change in [
            {"client_secret": "not-a-real-secret"},
            {"token": "not-a-real-token"},
            {"client_id": ""},
            {"callback_url": "https://arbitrary.example.test/callback"},
            {"scopes": ["gateway:mcp", "admin"]},
            {"scopes": ["gateway:mcp", "profile"]},
            {"scopes": ["openid", "profile"]},
            {"scopes": []},
            {"scopes": "gateway:mcp"},
            {"scopes": ["gateway:mcp", "gateway:mcp"]},
        ]:
            with self.subTest(change=change):
                path = self.config / "oauth-client.json"
                path.write_bytes((builder.SKILL / "config/oauth-client.json").read_bytes())
                self.update("oauth-client.json", **change)
                with self.assertRaises(builder.public_config.ConfigurationError):
                    builder.render_mcp_config(self.plugin)

    def test_symlink_input_is_rejected(self):
        path = self.config / "oauth-client.json"
        original = path.with_suffix(".source")
        path.rename(original)
        path.symlink_to(original)
        with self.assertRaises(builder.public_config.ConfigurationError):
            builder.render_mcp_config(self.plugin)

    def run_main(self, check=False):
        stdout = io.StringIO()
        with mock.patch.object(builder, "PLUGIN", self.plugin), mock.patch.object(
            sys, "argv", ["build_mcp_config.py"] + (["--check"] if check else [])
        ), contextlib.redirect_stdout(stdout):
            return builder.main(), stdout.getvalue()

    def test_check_is_readonly_and_generation_is_idempotent(self):
        output = self.plugin / ".mcp.json"
        self.assertEqual(1, self.run_main(check=True)[0])
        self.assertFalse(output.exists())
        self.assertEqual(0, self.run_main()[0])
        old = (output.read_bytes(), output.stat().st_mtime_ns)
        self.assertEqual(0, self.run_main(check=True)[0])
        self.assertEqual(0, self.run_main()[0])
        self.assertEqual(old, (output.read_bytes(), output.stat().st_mtime_ns))
        output.write_text('{"stale": true}')
        self.assertEqual(1, self.run_main(check=True)[0])
        self.assertEqual('{"stale": true}', output.read_text())

    def test_symlink_output_is_never_overwritten(self):
        target = self.plugin / "unrelated.txt"
        target.write_text("keep")
        (self.plugin / ".mcp.json").symlink_to(target)
        self.assertEqual(1, self.run_main()[0])
        self.assertEqual("keep", target.read_text())

    def test_check_rejects_missing_nested_and_overbroad_generated_scopes(self):
        output = self.plugin / ".mcp.json"
        for variant in ("missing", "nested", "overbroad"):
            with self.subTest(variant=variant):
                value = json.loads(builder.render_mcp_config(self.plugin))
                server = value["mcpServers"]["planly"]
                if variant == "missing":
                    server.pop("scopes")
                elif variant == "nested":
                    server["oauth"]["scopes"] = server.pop("scopes")
                else:
                    server["scopes"].append("profile")
                output.write_text(json.dumps(value))
                before = output.read_bytes()
                self.assertEqual(1, self.run_main(check=True)[0])
                self.assertEqual(before, output.read_bytes())

    def test_cli_does_not_use_credentials_or_modify_user_config(self):
        home = Path(self.temp.name) / "home"
        home.mkdir()
        user_config = home / "config.toml"
        user_config.write_text("# preserve user config\n")
        fake = "sentinel-private-do-not-print"
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build_mcp_config.py"), "--check"],
            env={**os.environ, "HOME": str(home), "CODEX_HOME": str(home), "GATEWAY_MCP_PAT": fake},
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn(fake, result.stdout + result.stderr)
        self.assertEqual("# preserve user config\n", user_config.read_text())


if __name__ == "__main__":
    unittest.main()
