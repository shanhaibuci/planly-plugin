from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1] / "plugins/planly"
SCRIPT = ROOT / "skills/planly-solver/scripts/configure_codex_gateway_mcp.py"
SYSTEM_ENDPOINT = (
    ROOT / "skills/planly-solver/config/system-endpoint.json"
)
PAT = "gwpat_xxx"

SPEC = importlib.util.spec_from_file_location("configure_codex_gateway_mcp", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConfigureCodexGatewayMcpTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project = self.root / "project"
        self.codex_home = self.root / "codex-home"
        self.project.mkdir()
        self.codex_home.mkdir()
        self.oauth_client = {
            "client_id": "public-test-client",
            "callback_url": "http://127.0.0.1/callback",
            "scopes": ["gateway:mcp"],
        }

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def run_script(
        self,
        action: str,
        *,
        verification: dict[str, object] | None = None,
        auth: str | None = "pat",
        support: str = "supported",
    ) -> SimpleNamespace:
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(self.codex_home)
        environment.pop("GATEWAY_MCP_PAT", None)
        stdout = io.StringIO()
        stderr = io.StringIO()
        verification_result = verification or {
            "auth_status": "authenticated",
            "http_status": 200,
            "error_code": None,
        }
        argv = [
            str(SCRIPT),
            action,
            "--project-root",
            str(self.project),
        ]
        if auth is not None:
            argv.extend(["--auth", auth])
        returncode = 0
        with (
            mock.patch.dict(os.environ, environment, clear=True),
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(MODULE, "verify_pat", return_value=verification_result),
            mock.patch.object(MODULE, "codex_oauth_support", return_value=support),
            mock.patch.object(MODULE, "load_oauth_client", return_value=self.oauth_client),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            try:
                MODULE.main()
            except SystemExit as exc:
                returncode = int(exc.code or 0)
        return SimpleNamespace(
            returncode=returncode,
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
        )

    def assert_secret_not_output(self, result: SimpleNamespace) -> None:
        self.assertNotIn(PAT, result.stdout)
        self.assertNotIn(PAT, result.stderr)

    def test_status_reports_presence_without_exposing_pat(self) -> None:
        (self.project / ".env").write_text(
            f"GATEWAY_MCP_PAT={PAT}\n", encoding="utf-8"
        )

        result = self.run_script("status")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_secret_not_output(result)
        payload = json.loads(result.stdout)
        self.assertEqual("project_dotenv", payload["pat_source"])
        self.assertFalse(payload["mcp_configured"])
        self.assertFalse(payload["mcp_pat_config_matches_dotenv"])
        self.assertEqual("user", payload["config_scope"])

    def test_apply_replaces_only_gateway_section_and_is_idempotent(self) -> None:
        (self.project / ".env").write_text(
            f"export GATEWAY_MCP_PAT='{PAT}'\n", encoding="utf-8"
        )
        config_path = self.codex_home / "config.toml"
        config_path.write_text(
            "model = \"gpt-example\"\n\n"
            "[mcp_servers.gateway]\n"
            "url = \"http://old.example/mcp\"\n"
            "bearer_token_env_var = \"OLD_TOKEN\"\n\n"
            "[mcp_servers.other]\n"
            "url = \"https://other.example/mcp\"\n",
            encoding="utf-8",
        )

        first = self.run_script("apply")

        self.assertEqual(0, first.returncode, first.stderr)
        self.assert_secret_not_output(first)
        self.assertTrue(json.loads(first.stdout)["changed"])
        self.assertTrue(json.loads(first.stdout)["pat_verified"])

        content = config_path.read_text(encoding="utf-8")
        parsed = tomllib.loads(content)
        self.assertEqual("gpt-example", parsed["model"])
        self.assertEqual(
            "https://other.example/mcp",
            parsed["mcp_servers"]["other"]["url"],
        )
        gateway = parsed["mcp_servers"]["gateway"]
        self.assertEqual(
            MODULE.system_mcp_url(MODULE.load_system_endpoint()),
            gateway["url"],
        )
        self.assertEqual(f"Bearer {PAT}", gateway["http_headers"]["Authorization"])
        self.assertNotIn("bearer_token_env_var", gateway)
        self.assertEqual(0o600, stat.S_IMODE(config_path.stat().st_mode))

        second = self.run_script("apply")

        self.assertEqual(0, second.returncode, second.stderr)
        self.assert_secret_not_output(second)
        self.assertFalse(json.loads(second.stdout)["changed"])

        status_result = self.run_script("status")
        self.assertEqual(0, status_result.returncode, status_result.stderr)
        self.assert_secret_not_output(status_result)
        self.assertTrue(
            json.loads(status_result.stdout)["mcp_pat_config_matches_dotenv"]
        )

    def test_verify_reports_invalid_pat_without_exposing_pat(self) -> None:
        (self.project / ".env").write_text(
            f"GATEWAY_MCP_PAT={PAT}\n", encoding="utf-8"
        )

        result = self.run_script(
            "verify",
            verification={
                "auth_status": "invalid_pat",
                "http_status": 401,
                "error_code": "INVALID_PAT",
            },
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_secret_not_output(result)
        payload = json.loads(result.stdout)
        self.assertEqual("invalid_pat", payload["auth_status"])
        self.assertEqual(401, payload["http_status"])
        self.assertEqual("INVALID_PAT", payload["error_code"])

    def test_apply_refuses_invalid_pat_without_modifying_config(self) -> None:
        (self.project / ".env").write_text(
            f"GATEWAY_MCP_PAT={PAT}\n", encoding="utf-8"
        )
        config_path = self.codex_home / "config.toml"
        original = '[mcp_servers.gateway]\nurl = "http://old.example/mcp"\n'
        config_path.write_text(original, encoding="utf-8")

        result = self.run_script(
            "apply",
            verification={
                "auth_status": "invalid_pat",
                "http_status": 401,
                "error_code": "INVALID_PAT",
            },
        )

        self.assertEqual(3, result.returncode)
        self.assert_secret_not_output(result)
        self.assertEqual("", result.stdout)
        payload = json.loads(result.stderr)
        self.assertEqual("PAT_VERIFICATION_FAILED", payload["code"])
        self.assertEqual("invalid_pat", payload["auth_status"])
        self.assertEqual(original, config_path.read_text(encoding="utf-8"))

    def test_verify_response_classification_is_normalized(self) -> None:
        authenticated = MODULE.classify_verify_response(
            200,
            b'{"jsonrpc":"2.0","id":"gateway-pat-check",'
            b'"result":{"protocolVersion":"2025-11-25"}}',
        )
        invalid = MODULE.classify_verify_response(
            401,
            b'{"jsonrpc":"2.0","error":{"data":{"code":"INVALID_PAT"}}}',
        )
        server_error = MODULE.classify_verify_response(500, b"internal detail")

        self.assertEqual("authenticated", authenticated["auth_status"])
        self.assertEqual("invalid_pat", invalid["auth_status"])
        self.assertEqual("server_error", server_error["auth_status"])
        self.assertNotIn("internal detail", json.dumps(server_error))

    def test_verify_pat_uses_only_fixed_endpoint_and_disables_redirects(self) -> None:
        response = mock.MagicMock()
        response.status = 200
        response.read.return_value = (
            b'{"jsonrpc":"2.0","id":"gateway-pat-check",'
            b'"result":{"protocolVersion":"2025-11-25"}}'
        )
        response_context = mock.MagicMock()
        response_context.__enter__.return_value = response
        opener = mock.MagicMock()
        opener.open.return_value = response_context

        with mock.patch.object(
            MODULE.urllib.request,
            "build_opener",
            return_value=opener,
        ) as build_opener:
            system_endpoint = MODULE.load_system_endpoint()
            result = MODULE.verify_pat(PAT, system_endpoint)

        request = opener.open.call_args.args[0]
        self.assertEqual(MODULE.system_mcp_url(system_endpoint), request.full_url)
        self.assertEqual(f"Bearer {PAT}", request.get_header("Authorization"))
        self.assertEqual("authenticated", result["auth_status"])
        self.assertIsInstance(
            build_opener.call_args.args[0],
            MODULE.NoRedirectHandler,
        )

    def test_system_endpoint_is_loaded_from_skill_config(self) -> None:
        configured = json.loads(SYSTEM_ENDPOINT.read_text(encoding="utf-8"))
        endpoint = MODULE.load_system_endpoint()

        self.assertEqual(configured, endpoint)
        self.assertEqual(
            configured["origin"] + configured["mcp_path"],
            MODULE.system_mcp_url(endpoint),
        )

    def test_changed_system_origin_drives_generated_mcp_config(self) -> None:
        endpoint_path = self.root / "system-endpoint.json"
        endpoint_path.write_text(
            json.dumps(
                {
                    "origin": "https://new-environment.example",
                    "mcp_path": "/mcp",
                }
            ),
            encoding="utf-8",
        )
        endpoint = MODULE.load_system_endpoint(endpoint_path)

        rendered = MODULE.render_config("", {}, PAT, endpoint)
        generated = tomllib.loads(rendered)["mcp_servers"]["gateway"]

        self.assertEqual(
            "https://new-environment.example/mcp",
            generated["url"],
        )

    def test_system_endpoint_rejects_paths_credentials_and_unknown_fields(self) -> None:
        invalid_payloads = (
            {"origin": "https://example.com/base", "mcp_path": "/mcp"},
            {"origin": "https://example.com/", "mcp_path": "/mcp"},
            {"origin": "https://user@example.com", "mcp_path": "/mcp"},
            {"origin": "https://example.com:bad", "mcp_path": "/mcp"},
            {"origin": "https://example.com", "mcp_path": "//other.example/mcp"},
            {
                "origin": "https://example.com",
                "mcp_path": "/mcp",
                "override": "https://other.example",
            },
        )

        for index, payload in enumerate(invalid_payloads):
            with self.subTest(index=index):
                path = self.root / f"invalid-system-endpoint-{index}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(MODULE.ConfigurationError):
                    MODULE.load_system_endpoint(path)

    def test_apply_without_pat_does_not_create_config(self) -> None:
        result = self.run_script("apply")

        self.assertNotEqual(0, result.returncode)
        self.assert_secret_not_output(result)
        self.assertFalse((self.codex_home / "config.toml").exists())
        payload = json.loads(result.stderr)
        self.assertEqual("CONFIGURATION_ERROR", payload["code"])

    def test_unsupported_inline_gateway_config_is_not_modified(self) -> None:
        (self.project / ".env").write_text(
            f"GATEWAY_MCP_PAT={PAT}\n", encoding="utf-8"
        )
        config_path = self.codex_home / "config.toml"
        original = (
            "mcp_servers = { gateway = { url = \"http://old.example/mcp\" } }\n"
        )
        config_path.write_text(original, encoding="utf-8")

        result = self.run_script("apply")

        self.assertNotEqual(0, result.returncode)
        self.assert_secret_not_output(result)
        self.assertEqual(original, config_path.read_text(encoding="utf-8"))

    def test_default_oauth_configures_without_reading_pat_or_contacting_gateway(self) -> None:
        (self.project / ".env").symlink_to(self.root / "unreadable-secret")
        with mock.patch.object(
            MODULE, "parse_dotenv_value", side_effect=AssertionError("must not read PAT")
        ), mock.patch.object(
            MODULE.urllib.request, "build_opener", side_effect=AssertionError("no HTTP")
        ):
            before = self.run_script("status", auth=None)
            result = self.run_script("apply", auth=None)
        self.assertEqual("missing", json.loads(before.stdout)["config_status"])
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["changed"])
        self.assertEqual("configured", payload["config_status"])
        self.assertEqual("oauth", payload["mcp_auth"])
        self.assertEqual("unknown", payload["oauth_login_status"])
        self.assertEqual("unverified", payload["connection_status"])
        path = self.codex_home / "config.toml"
        self.assertEqual({"mcp_servers": {"gateway": {
            "url": MODULE.system_mcp_url(MODULE.load_system_endpoint()),
            "oauth_resource": MODULE.system_mcp_url(MODULE.load_system_endpoint()),
            "scopes": ["gateway:mcp"],
            "oauth": {k: self.oauth_client[k] for k in ("client_id", "callback_url")},
        }}}, tomllib.loads(path.read_text()))
        self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
        self.assertFalse((self.project / ".codex").exists())

    def test_oauth_append_preserves_other_configuration_and_repeated_apply_does_not_write(self) -> None:
        path = self.codex_home / "config.toml"
        original = ('# 用户配置\nmodel = "existing"\n'
                    '[mcp_servers.other]\nurl = "https://other.example/mcp"\n'
                    'disabled_tools = ["write"]\n')
        path.write_text(original)
        first = self.run_script("apply", auth=None)
        self.assertEqual(0, first.returncode, first.stderr)
        written = path.read_text()
        self.assertTrue(written.startswith(original))
        with mock.patch.object(MODULE, "atomic_write") as write:
            second = self.run_script("apply", auth=None)
            write.assert_not_called()
        self.assertFalse(json.loads(second.stdout)["changed"])
        self.assertEqual(written, path.read_text())

    def test_oauth_matching_config_preserves_policies_and_registered_client(self) -> None:
        path = self.codex_home / "config.toml"
        url = MODULE.system_mcp_url(MODULE.load_system_endpoint())
        original = (f'[mcp_servers.gateway]\nurl = "{url}"\n'
                    f'oauth_resource = "{url}"\nscopes = ["gateway:mcp"]\n'
                    'tool_timeout_sec = 90\ndisabled_tools = ["write"]\n'
                    '[mcp_servers.gateway.oauth]\nclient_id = "public-test-client"\n'
                    'callback_url = "http://127.0.0.1/callback"\n'
                    '[mcp_servers.other]\nurl = "https://other.example/mcp"\n')
        path.write_text(original)
        result = self.run_script("apply", auth="oauth")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(json.loads(result.stdout)["changed"])
        self.assertEqual(original, path.read_text())

    def test_oauth_conflicts_are_not_replaced_or_exposed(self) -> None:
        path = self.codex_home / "config.toml"
        url = MODULE.system_mcp_url(MODULE.load_system_endpoint())
        cases = [
            ('url = "https://other.example/mcp"', "url_conflict"),
            (f'url = "{url}"\nenabled = false', "disabled"),
            (f'url = "{url}"\nbearer_token_env_var = "TOKEN"', "auth_conflict"),
            (f'url = "{url}"\nhttp_headers = {{ authorization = "{PAT}" }}', "auth_conflict"),
            (f'url = "{url}"\nenv_http_headers = {{ AUTHORIZATION = "TOKEN" }}', "auth_conflict"),
            (f'url = "{url}"\nhttp_headers_helper = "some-command"', "auth_conflict"),
            (f'url = "{url}"\nauth = "chatgpt"', "auth_conflict"),
            (f'url = "{url}"\ncommand = "some-command"', "transport_conflict"),
        ]
        for config, state in cases:
            with self.subTest(state=state, config=config):
                original = f'[mcp_servers.gateway]\n{config}\n'
                path.write_text(original)
                status = self.run_script("status", auth=None)
                self.assertEqual(state, json.loads(status.stdout)["config_status"])
                result = self.run_script("apply", auth=None)
                self.assertEqual(3, result.returncode)
                self.assertEqual("MCP_CONFIG_CONFLICT", json.loads(result.stderr)["code"])
                self.assertEqual(original, path.read_text())
                self.assert_secret_not_output(status)
                self.assert_secret_not_output(result)

    def test_oauth_stops_on_project_and_ancestor_overrides(self) -> None:
        for root in (self.project, self.root):
            with self.subTest(root=root):
                directory = root / ".codex"
                directory.mkdir()
                path = directory / "config.toml"
                original = '[mcp_servers.gateway]\nenabled = false\n'
                path.write_text(original)
                result = self.run_script("apply", auth=None)
                self.assertEqual(3, result.returncode)
                self.assertEqual("project_override", json.loads(result.stderr)["config_status"])
                self.assertFalse((self.codex_home / "config.toml").exists())
                self.assertEqual(original, path.read_text())
                path.unlink()
                directory.rmdir()

    def test_oauth_refuses_invalid_and_unsupported_config_without_modifying_it(self) -> None:
        path = self.codex_home / "config.toml"
        for original in ('[invalid', 'mcp_servers = 1\n', 'mcp_servers = {}\n',
                         '[mcp_servers]\ngateway = 1\n'):
            with self.subTest(original=original):
                path.write_text(original)
                result = self.run_script("apply", auth=None)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual(original, path.read_text())

    def test_oauth_does_not_follow_config_symlinks(self) -> None:
        secret = self.root / "secret.toml"
        original = f'other_secret = "{PAT}"\n'
        secret.write_text(original)
        path = self.codex_home / "config.toml"
        path.symlink_to(secret)
        result = self.run_script("apply", auth=None)
        self.assertNotEqual(0, result.returncode)
        self.assert_secret_not_output(result)
        self.assertEqual(original, secret.read_text())
        self.assertTrue(path.is_symlink())

    def test_oauth_malformed_or_symlinked_project_config_blocks_writes(self) -> None:
        directory = self.project / ".codex"
        directory.mkdir()
        path = directory / "config.toml"
        path.write_text('[invalid')
        invalid = self.run_script("apply", auth=None)
        self.assertNotEqual(0, invalid.returncode)
        self.assertEqual('[invalid', path.read_text())
        self.assertFalse((self.codex_home / "config.toml").exists())
        path.unlink()
        path.symlink_to(self.root / "absent-config")
        symlinked = self.run_script("apply", auth=None)
        self.assertNotEqual(0, symlinked.returncode)
        self.assertTrue(path.is_symlink())
        self.assertFalse((self.codex_home / "config.toml").exists())

    def test_oauth_other_project_server_does_not_block_gateway_addition(self) -> None:
        directory = self.project / ".codex"
        directory.mkdir()
        path = directory / "config.toml"
        original = '[mcp_servers.other]\nurl = "https://other.example/mcp"\n'
        path.write_text(original)
        result = self.run_script("apply", auth=None)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(original, path.read_text())
        self.assertTrue((self.codex_home / "config.toml").exists())

    def test_oauth_status_does_not_print_unrelated_secrets(self) -> None:
        path = self.codex_home / "config.toml"
        url = MODULE.system_mcp_url(MODULE.load_system_endpoint())
        original = (f'[mcp_servers.gateway]\nurl = "{url}"\n'
                    f'[mcp_servers.other]\nhttp_headers = {{ Authorization = "{PAT}" }}\n')
        path.write_text(original)
        result = self.run_script("status", auth=None)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_secret_not_output(result)
        self.assertEqual("oauth_client_missing", json.loads(result.stdout)["config_status"])
        self.assertEqual(original, path.read_text())

    def test_oauth_adds_missing_public_client_fields_without_changing_policies(self) -> None:
        path = self.codex_home / "config.toml"
        url = MODULE.system_mcp_url(MODULE.load_system_endpoint())
        original = (f'[mcp_servers.gateway]\nurl = "{url}"\n'
                    'disabled_tools = ["write"]\ntool_timeout_sec = 90\n'
                    '[mcp_servers.other]\nurl = "https://other.example/mcp"\n')
        path.write_text(original)
        before = self.run_script("status", auth=None)
        self.assertEqual("oauth_client_missing", json.loads(before.stdout)["config_status"])
        result = self.run_script("apply", auth=None)
        self.assertEqual(0, result.returncode, result.stderr)
        config = tomllib.loads(path.read_text())
        self.assertEqual(["write"], config["mcp_servers"]["gateway"]["disabled_tools"])
        self.assertEqual(90, config["mcp_servers"]["gateway"]["tool_timeout_sec"])
        self.assertEqual("public-test-client", config["mcp_servers"]["gateway"]["oauth"]["client_id"])
        self.assertEqual(url, config["mcp_servers"]["gateway"]["oauth_resource"])
        self.assertEqual("https://other.example/mcp", config["mcp_servers"]["other"]["url"])
        self.assertFalse(json.loads(self.run_script("apply", auth=None).stdout)["changed"])

    def test_oauth_conflicting_public_client_resource_and_scopes_are_preserved(self) -> None:
        path = self.codex_home / "config.toml"
        url = MODULE.system_mcp_url(MODULE.load_system_endpoint())
        for addition in ('oauth_resource = "https://other.example/mcp"\n',
                         'scopes = ["admin"]\n',
                         '[mcp_servers.gateway.oauth]\nclient_id = "someone-else"\n',
                         '[mcp_servers.gateway.oauth]\ncallback_url = "https://other.example/callback"\n'):
            original = f'[mcp_servers.gateway]\nurl = "{url}"\n' + addition
            path.write_text(original)
            result = self.run_script("apply", auth=None)
            self.assertEqual(3, result.returncode)
            self.assertEqual("MCP_CONFIG_CONFLICT", json.loads(result.stderr)["code"])
            self.assertEqual(original, path.read_text())

    def test_oauth_unsupported_cli_does_not_write_unknown_settings(self) -> None:
        for support in ("unsupported", "unknown", "cli_unavailable"):
            result = self.run_script("apply", auth=None, support=support)
            self.assertEqual(3, result.returncode)
            self.assertEqual("CODEX_OAUTH_CAPABILITY_REQUIRED", json.loads(result.stderr)["code"])
            self.assertFalse((self.codex_home / "config.toml").exists())

    def test_oauth_capability_check_uses_flags_not_version_guess(self) -> None:
        for output, expected in (("--oauth-client-id --oauth-resource", "supported"),
                                 ("--bearer-token-env-var", "unsupported")):
            with mock.patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=output)) as run:
                self.assertEqual(expected, MODULE.codex_oauth_support())
            self.assertEqual(["codex", "mcp", "add", "--help"], run.call_args.args[0])

    def test_public_oauth_file_rejects_secrets_and_unregistered_callbacks(self) -> None:
        path = self.root / "oauth-client.json"
        for value in ({**self.oauth_client, "client_secret": PAT},
                      {**self.oauth_client, "callback_url": "https://other.example/callback"},
                      {**self.oauth_client, "scopes": ["admin"]}):
            path.write_text(json.dumps(value))
            with self.assertRaises(MODULE.ConfigurationError):
                MODULE.load_oauth_client(path)

    def test_oauth_requires_https(self) -> None:
        with mock.patch.object(MODULE, "load_system_endpoint", return_value={
            "origin": "http://example.com", "mcp_path": "/mcp",
        }):
            result = self.run_script("apply", auth=None)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.codex_home / "config.toml").exists())

    def test_oauth_changed_endpoint_drives_new_config(self) -> None:
        with mock.patch.object(MODULE, "load_system_endpoint", return_value={
            "origin": "https://new-environment.example", "mcp_path": "/mcp",
        }):
            result = self.run_script("apply", auth=None)
        self.assertEqual(0, result.returncode, result.stderr)
        config = tomllib.loads((self.codex_home / "config.toml").read_text())
        self.assertEqual("https://new-environment.example/mcp", config["mcp_servers"]["gateway"]["url"])

    def test_oauth_atomic_write_failure_preserves_original(self) -> None:
        path = self.codex_home / "config.toml"
        original = 'model = "existing"\n'
        path.write_text(original)
        with mock.patch.object(MODULE.os, "replace", side_effect=OSError(PAT)):
            result = self.run_script("apply", auth=None)
        self.assertNotEqual(0, result.returncode)
        self.assert_secret_not_output(result)
        self.assertEqual(original, path.read_text())
        self.assertEqual([path], list(self.codex_home.iterdir()))

    def test_oauth_verify_never_uses_pat_as_a_fallback(self) -> None:
        with mock.patch.object(MODULE, "parse_dotenv_value") as read_pat:
            result = self.run_script("verify", auth=None)
            read_pat.assert_not_called()
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.codex_home / "config.toml").exists())


if __name__ == "__main__":
    unittest.main()
