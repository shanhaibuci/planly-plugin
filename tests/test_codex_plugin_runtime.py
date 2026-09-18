"""Opt-in real Codex parser/OAuth/protocol smoke tests, with loopback fakes only.

PLANLY_CODEX_BIN=/path/to/codex python3 -m unittest discover -s tests \
    -p 'test_codex_plugin_runtime.py' -v

No real login, Gateway, model turn, user config, token store or graphical UI is
used. Passing these tests does NOT establish target desktop UI compatibility.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CODEX = os.environ.get("PLANLY_CODEX_BIN")
URI = "ui://planly-test/result.html"
MIME = "text/html;profile=mcp-app"
HTML = "<!doctype html><html><body>synthetic UI transport fixture</body></html>"
TOOL = "gateway.ui.result_" + "1" * 32


@unittest.skipUnless(CODEX, "Set PLANLY_CODEX_BIN for isolated native-client smoke tests")
class CodexPluginRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="planly-plugin-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.codex_home = self.root / "codex"
        self.home.mkdir()
        self.codex_home.mkdir()
        self.auth_required = False
        self.requests = []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, value=None, headers=None):
                self.send_response(status)
                for key, val in (headers or {}).items():
                    self.send_header(key, val)
                if value is not None:
                    self.send_header("Content-Type", "application/json")
                self.end_headers()
                if value is not None:
                    self.wfile.write(json.dumps(value).encode())

            def challenge(self):
                self.reply(401, headers={"WWW-Authenticate":
                    f'Bearer resource_metadata="{fixture.base}/.well-known/oauth-protected-resource/mcp"'})

            def do_GET(self):
                fixture.requests.append(("GET", self.path))
                if self.path.startswith("/.well-known/oauth-protected-resource"):
                    self.reply(200, {
                        "resource": fixture.base + "/mcp", "authorization_servers": [fixture.base],
                        "scopes_supported": ["gateway:mcp"],
                    })
                elif self.path in ("/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"):
                    self.reply(200, {
                        "issuer": fixture.base, "authorization_endpoint": fixture.base + "/authorize",
                        "token_endpoint": fixture.base + "/token", "response_types_supported": ["code"],
                        "grant_types_supported": ["authorization_code"],
                        "code_challenge_methods_supported": ["S256"],
                        "token_endpoint_auth_methods_supported": ["none"],
                        "scopes_supported": ["gateway:mcp"],
                        "authorization_response_iss_parameter_supported": True,
                    })
                elif fixture.auth_required:
                    self.challenge()
                else:
                    self.reply(405)

            def do_POST(self):
                message = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                fixture.requests.append(("POST", self.path, message.get("method")))
                if fixture.auth_required:
                    self.challenge()
                    return
                if "id" not in message:
                    self.reply(202)
                    return
                method = message.get("method")
                if method == "initialize":
                    result = {
                        "protocolVersion": message["params"]["protocolVersion"],
                        "capabilities": {"tools": {}, "resources": {}},
                        "serverInfo": {"name": "planly-test-fixture", "version": "1.0"},
                    }
                elif method == "tools/list":
                    result = {"tools": [{
                        "name": TOOL, "description": "Synthetic read-only UI test",
                        "inputSchema": {"type": "object", "properties": {}},
                        "annotations": {"readOnlyHint": True}, "_meta": {"ui": {"resourceUri": URI}},
                    }]}
                elif method == "resources/list":
                    result = {"resources": [{"uri": URI, "name": "Test UI", "mimeType": MIME}]}
                elif method == "resources/templates/list":
                    result = {"resourceTemplates": []}
                elif method == "resources/read" and message["params"]["uri"] == URI:
                    result = {"contents": [{"uri": URI, "mimeType": MIME, "text": HTML}]}
                else:
                    self.reply(200, {"jsonrpc": "2.0", "id": message["id"],
                        "error": {"code": -32601, "message": "Not implemented in fixture"}})
                    return
                self.reply(200, {"jsonrpc": "2.0", "id": message["id"], "result": result})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.addCleanup(self.stop_server)
        repo = self.root / "repo"
        shutil.copytree(ROOT / ".agents", repo / ".agents")
        shutil.copytree(ROOT / "plugins", repo / "plugins", ignore=shutil.ignore_patterns("__pycache__"))
        config = repo / "plugins/planly/.mcp.json"
        value = json.loads(config.read_text())
        # Only the isolated test copy points at a local fake. Shipped config is HTTPS.
        value["mcpServers"]["planly"]["url"] = self.base + "/mcp"
        config.write_text(json.dumps(value))
        self.marketplace = str(repo / ".agents/plugins/marketplace.json")
        self.err = (self.root / "stderr.log").open("w")
        self.addCleanup(self.err.close)
        self.process = subprocess.Popen(
            [CODEX, "app-server"], cwd=self.root,
            env={"PATH": os.environ["PATH"], "HOME": str(self.home), "CODEX_HOME": str(self.codex_home)},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err, text=True,
        )
        self.addCleanup(self.stop_process)
        self.messages = queue.Queue()
        self.reader = threading.Thread(target=self.read_messages, daemon=True)
        self.reader.start()
        self.next_id = 0
        self.rpc("initialize", {"clientInfo": {"name": "planly-smoke", "version": "1.0"},
            "capabilities": {"experimentalApi": True}})
        self.process.stdin.write('{"method":"initialized"}\n')
        self.process.stdin.flush()

    def stop_process(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)
        self.process.stdin.close()
        self.reader.join(timeout=5)
        self.process.stdout.close()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=5)

    def read_messages(self):
        for line in self.process.stdout:
            self.messages.put(json.loads(line))

    def rpc(self, method, params):
        self.next_id += 1
        request_id = self.next_id
        self.process.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            message = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
            if message.get("id") == request_id:
                self.assertNotIn("error", message, f"RPC failed: {method}")
                return message["result"]
        self.fail(f"RPC timed out: {method}")

    def install(self):
        params = {"marketplacePath": self.marketplace, "pluginName": "planly"}
        self.assertEqual([], self.rpc("plugin/install", params)["appsNeedingAuth"])
        plugin = self.rpc("plugin/read", params)["plugin"]
        self.assertEqual([], plugin["apps"])
        self.assertEqual(["planly"], plugin["mcpServers"])
        self.assertEqual("Planly 场景求解", plugin["summary"]["interface"]["displayName"])
        status = self.rpc("mcpServerStatus/list", {})["data"]
        self.assertEqual(1, len(status))
        self.assertEqual("planly@personal", status[0]["pluginId"])
        return status[0]

    def test_native_plugin_preserves_ui_metadata_and_resource_html(self):
        status = self.install()
        self.assertIsNone(status["toolsError"])
        descriptor = next(t for t in status["tools"].values() if t["name"] == TOOL)
        self.assertEqual(URI, descriptor["_meta"]["ui"]["resourceUri"])
        resource = self.rpc("mcpServer/resource/read", {"server": status["name"], "uri": URI})
        self.assertEqual({"uri": URI, "mimeType": MIME, "text": HTML}, resource["contents"][0])

    def test_native_plugin_oauth_uses_registered_client_and_discovered_scope_resource(self):
        self.auth_required = True
        status = self.install()
        self.assertEqual("notLoggedIn", status["authStatus"])
        login = self.rpc("mcpServer/oauth/login", {"name": status["name"], "timeoutSecs": 20})
        query = parse_qs(urlsplit(login["authorizationUrl"]).query)
        public = json.loads((ROOT / "plugins/planly/skills/planly-solver/config/oauth-client.json").read_text())
        self.assertEqual([public["client_id"]], query["client_id"])
        self.assertEqual(["code"], query["response_type"])
        self.assertEqual(["S256"], query["code_challenge_method"])
        self.assertEqual(public["scopes"], query["scope"])
        self.assertEqual([self.base + "/mcp"], query["resource"])
        callback = urlsplit(query["redirect_uri"][0])
        self.assertEqual("127.0.0.1", callback.hostname)
        self.assertEqual("/callback", callback.path)
        self.assertGreater(callback.port, 0)
        self.assertTrue(query["state"])
        self.assertTrue(query["code_challenge"])
        self.assertFalse(any("register" in entry[1] for entry in self.requests))
        # Stop before consent/code exchange; no real browser or account is used.


if __name__ == "__main__":
    unittest.main()
