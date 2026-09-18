#!/usr/bin/env python3
"""Generate the plugin HTTP MCP declaration from its public Skill config only.

No network, environment credentials, user Codex config or OAuth login is used.
The generated file contains no tokens. Actual OAuth/UI compatibility is a
separate host acceptance gate, not established by this build-time check.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/planly"
SKILL = PLUGIN / "skills/planly-solver"
spec = importlib.util.spec_from_file_location(
    "planly_public_config", SKILL / "scripts/configure_codex_gateway_mcp.py"
)
public_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public_config)


def render_mcp_config(plugin: Path = PLUGIN) -> bytes:
    config = plugin / "skills/planly-solver/config"
    endpoint = public_config.load_system_endpoint(config / "system-endpoint.json")
    client = public_config.load_oauth_client(config / "oauth-client.json")
    url = public_config.system_mcp_url(endpoint)
    if not url.startswith("https://"):
        raise public_config.ConfigurationError("Plugin MCP requires HTTPS")
    # Use documented plugin camelCase OAuth fields, not config.toml snake_case.
    # The host obtains gateway:mcp scope and resource from protected-resource
    # discovery. Do not invent unsupported plugin fields or static auth headers.
    payload = {
        "mcpServers": {
            "planly": {
                "type": "http",
                "url": url,
                "oauth": {
                    "clientId": client["client_id"],
                    "callbackUrl": client["callback_url"],
                },
            },
        },
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check without writing files")
    args = parser.parse_args()
    output = PLUGIN / ".mcp.json"
    try:
        if output.is_symlink():
            raise public_config.ConfigurationError("Plugin MCP output must not be a symlink")
        expected = render_mcp_config()
        actual = output.read_bytes() if output.is_file() else None
        if args.check:
            if actual != expected:
                print("Plugin MCP config is missing or stale; run scripts/build_mcp_config.py")
                return 1
        elif actual != expected:
            output.write_bytes(expected)
    except (OSError, public_config.ConfigurationError):
        print("Cannot generate Plugin MCP config: invalid public inputs or unsafe output")
        return 1
    print("Plugin MCP config matches public source files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
