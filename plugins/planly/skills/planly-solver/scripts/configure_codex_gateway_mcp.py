#!/usr/bin/env python3

"""Configure Gateway MCP for Codex using OAuth by default, without credentials.

OAuth status/apply only inspect configuration and add a missing trusted HTTPS
server. They never read .env or OAuth credential storage. Login is delegated to
the host's OAuth UI or
`codex mcp login gateway --scopes gateway:mcp,offline_access`.

Only with explicit --auth pat, the PAT is read from <project-root>/.env and
the apply action writes a
static Authorization header to the user-level Codex config because an already
running IDE extension cannot inherit variables from the project's .env file.
The verify action sends a business-data-free MCP initialize request only to the
trusted endpoint derived from config/system-endpoint.json. No credential value
or raw server response is written to stdout, stderr, or command-line arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


VARIABLE = "GATEWAY_MCP_PAT"
SERVER_NAME = "gateway"
SYSTEM_ENDPOINT_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "system-endpoint.json"
)
OAUTH_CLIENT_PATH = SYSTEM_ENDPOINT_PATH.parent / "oauth-client.json"
MCP_PROTOCOL_VERSION = "2025-11-25"
VERIFY_TIMEOUT_SECONDS = 5
MAX_VERIFY_RESPONSE_BYTES = 64 * 1024
TABLE_HEADER_RE = re.compile(r"^\s*\[([^\[\]]+)]\s*(?:#.*)?$")


class ConfigurationError(Exception):
    """A safe, non-secret configuration error."""


def load_system_endpoint(path: Path = SYSTEM_ENDPOINT_PATH) -> dict[str, str]:
    if path.is_symlink():
        raise ConfigurationError("Skill system-endpoint.json 不能是符号链接")
    if not path.is_file():
        raise ConfigurationError("Skill 缺少 config/system-endpoint.json")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(
            "Skill config/system-endpoint.json 无法安全解析"
        ) from exc

    if not isinstance(payload, dict) or set(payload) != {"origin", "mcp_path"}:
        raise ConfigurationError(
            "Skill system-endpoint.json 只能声明 origin 和 mcp_path"
        )

    origin = payload.get("origin")
    mcp_path = payload.get("mcp_path")
    if not isinstance(origin, str) or not origin or origin != origin.strip():
        raise ConfigurationError("Skill system-endpoint.json 的 origin 无效")
    if not isinstance(mcp_path, str) or not mcp_path or mcp_path != mcp_path.strip():
        raise ConfigurationError("Skill system-endpoint.json 的 mcp_path 无效")

    if any(character in origin for character in ("\r", "\n", "\x00")):
        raise ConfigurationError("Skill system-endpoint.json 的 origin 无效")
    try:
        parsed_origin = urllib.parse.urlsplit(origin)
        parsed_origin.port
    except ValueError as exc:
        raise ConfigurationError("Skill system-endpoint.json 的 origin 无效") from exc
    if (
        parsed_origin.scheme not in {"http", "https"}
        or not parsed_origin.hostname
        or parsed_origin.username is not None
        or parsed_origin.password is not None
        or parsed_origin.path
        or parsed_origin.query
        or parsed_origin.fragment
    ):
        raise ConfigurationError(
            "Skill system-endpoint.json 的 origin 必须是不含路径的 HTTP(S) origin"
        )

    if any(character in mcp_path for character in ("\r", "\n", "\x00")):
        raise ConfigurationError("Skill system-endpoint.json 的 mcp_path 无效")
    parsed_mcp_path = urllib.parse.urlsplit(mcp_path)
    if (
        not mcp_path.startswith("/")
        or mcp_path.startswith("//")
        or parsed_mcp_path.scheme
        or parsed_mcp_path.netloc
        or parsed_mcp_path.query
        or parsed_mcp_path.fragment
    ):
        raise ConfigurationError(
            "Skill system-endpoint.json 的 mcp_path 必须是不含查询或片段的站内绝对路径"
        )

    return {
        "origin": origin,
        "mcp_path": mcp_path,
    }


def system_mcp_url(system_endpoint: dict[str, str]) -> str:
    return system_endpoint["origin"] + system_endpoint["mcp_path"]


def load_oauth_client(path: Path = OAUTH_CLIENT_PATH) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ConfigurationError("Skill 缺少安全的 config/oauth-client.json")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError("Skill OAuth 客户端公开配置无法安全解析") from exc
    if (not isinstance(value, dict)
            or set(value) != {"client_id", "callback_url", "scopes"}
            or not isinstance(value.get("client_id"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value["client_id"])
            or value.get("callback_url") != "http://127.0.0.1/callback"
            or value.get("scopes") != ["gateway:mcp", "offline_access"]):
        raise ConfigurationError(
            "OAuth 配置只能包含公开 Client ID、受支持回调、MCP 权限与离线续期 scope"
        )
    return value


def codex_oauth_support() -> str:
    """Check capabilities, not a guessed version number; never print CLI output."""
    try:
        result = subprocess.run(
            ["codex", "mcp", "add", "--help"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5,
        )
    except FileNotFoundError:
        return "cli_unavailable"
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if result.returncode:
        return "unknown"
    return "supported" if all(
        flag in result.stdout for flag in ("--oauth-client-id", "--oauth-resource")
    ) else "unsupported"


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent forwarding the PAT if the trusted endpoint redirects elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def emit(payload: dict[str, Any], *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), file=stream)


def fail(code: str, message: str) -> "NoReturn":
    emit({"ok": False, "code": code, "message": message}, error=True)
    raise SystemExit(2)


def codex_config_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME", "").strip()
    base = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return base / "config.toml"


def dotenv_path(project_root: Path) -> Path:
    path = project_root / ".env"
    if path.is_symlink():
        raise ConfigurationError("项目 .env 不能是符号链接")
    return path


def parse_dotenv_value(project_root: Path) -> str | None:
    path = dotenv_path(project_root)
    if not path.is_file():
        return None

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError("无法安全读取项目 .env") from exc

    found: str | None = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == VARIABLE:
            if found is not None:
                raise ConfigurationError(f"项目 .env 重复声明 {VARIABLE}")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            found = value

    if found is None or not found:
        return None
    if any(character in found for character in ("\r", "\n", "\x00")):
        raise ConfigurationError("项目 .env 中的 Gateway PAT 格式无效")
    return found


def load_config(path: Path) -> tuple[str, dict[str, Any]]:
    if path.is_symlink():
        raise ConfigurationError("用户级 Codex config.toml 不能是符号链接")
    if not path.exists():
        return "", {}
    if not path.is_file():
        raise ConfigurationError("用户级 Codex config.toml 不是普通文件")
    try:
        text = path.read_text(encoding="utf-8")
        data = tomllib.loads(text)
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError("用户级 Codex config.toml 无法安全解析") from exc
    return text, data


def gateway_config(data: dict[str, Any]) -> dict[str, Any] | None:
    servers = data.get("mcp_servers")
    if not isinstance(servers, dict):
        return None
    gateway = servers.get(SERVER_NAME)
    return gateway if isinstance(gateway, dict) else None


def auth_mode(config: dict[str, Any] | None) -> str:
    if not config:
        return "missing"
    headers = config.get("http_headers")
    if isinstance(headers, dict):
        authorization = headers.get("Authorization")
        if isinstance(authorization, str) and authorization.startswith("Bearer "):
            return "static_header"
    if config.get("bearer_token_env_var") == VARIABLE:
        return "environment"
    return "missing"


def parse_verify_response(body: bytes) -> dict[str, Any] | None:
    if not body:
        return None
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def verify_error_code(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    data = error.get("data")
    if not isinstance(data, dict):
        return None
    code = data.get("code")
    return code if isinstance(code, str) and code else None


def verification_result(
    auth_status: str,
    http_status: int | None,
    error_code: str | None,
) -> dict[str, Any]:
    return {
        "auth_status": auth_status,
        "http_status": http_status,
        "error_code": error_code,
    }


def classify_verify_response(status: int, body: bytes) -> dict[str, Any]:
    payload = parse_verify_response(body)
    error_code = verify_error_code(payload)

    if error_code in {"INVALID_PAT", "UNAUTHORIZED"}:
        return verification_result("invalid_pat", status, error_code)
    if status == 200:
        result = payload.get("result") if payload else None
        if isinstance(result, dict) and isinstance(result.get("protocolVersion"), str):
            return verification_result("authenticated", status, None)
        return verification_result("unexpected_response", status, error_code)
    if status == 401:
        return verification_result("invalid_pat", status, error_code or "INVALID_PAT")
    if status == 403:
        return verification_result("forbidden", status, error_code)
    if status == 404:
        return verification_result("mcp_unavailable", status, error_code)
    if status == 400:
        return verification_result("protocol_error", status, error_code)
    if status >= 500:
        return verification_result("server_error", status, error_code)
    return verification_result("unexpected_response", status, error_code)


def verify_pat(pat: str, system_endpoint: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "gateway-pat-check",
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "gateway-skill-auth-check",
                    "version": "1.0",
                },
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        system_mcp_url(system_endpoint),
        data=body,
        headers={
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + pat,
            "Content-Type": "application/json",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        },
        method="POST",
    )
    opener = urllib.request.build_opener(NoRedirectHandler())
    try:
        with opener.open(request, timeout=VERIFY_TIMEOUT_SECONDS) as response:
            status = response.status
            response_body = response.read(MAX_VERIFY_RESPONSE_BYTES)
    except urllib.error.HTTPError as exc:
        status = exc.code
        response_body = exc.read(MAX_VERIFY_RESPONSE_BYTES)
    except (urllib.error.URLError, TimeoutError, OSError):
        return verification_result("unreachable", None, "MCP_UNREACHABLE")
    return classify_verify_response(status, response_body)


def normalize_table_name(raw_name: str) -> str:
    normalized = re.sub(r"\s+", "", raw_name)
    normalized = normalized.replace('"gateway"', "gateway").replace("'gateway'", "gateway")
    return normalized


def gateway_table_range(text: str, config: dict[str, Any] | None) -> tuple[int, int] | None:
    lines = text.splitlines(keepends=True)
    start: int | None = None
    end = len(lines)

    for index, line in enumerate(lines):
        match = TABLE_HEADER_RE.match(line.rstrip("\r\n"))
        if not match:
            continue
        table_name = normalize_table_name(match.group(1))
        is_gateway = table_name == "mcp_servers.gateway"
        is_gateway_child = table_name.startswith("mcp_servers.gateway.")

        if start is None and is_gateway:
            start = index
            continue
        if start is not None and not is_gateway_child:
            end = index
            break

    if start is None:
        if config is not None:
            raise ConfigurationError(
                "已有 gateway MCP 使用了不受支持的 TOML 写法，未修改配置"
            )
        return None
    return start, end


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_config(
    original: str,
    data: dict[str, Any],
    pat: str,
    system_endpoint: dict[str, str],
) -> str:
    current_gateway = gateway_config(data)
    table_range = gateway_table_range(original, current_gateway)
    mcp_url = system_mcp_url(system_endpoint)
    block = (
        f"[mcp_servers.{SERVER_NAME}]\n"
        f"url = {toml_string(mcp_url)}\n"
        "http_headers = { Authorization = "
        f"{toml_string('Bearer ' + pat)} }}\n"
    )

    if table_range is None:
        prefix = original
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        if prefix and not prefix.endswith("\n\n"):
            prefix += "\n"
        result = prefix + block
    else:
        lines = original.splitlines(keepends=True)
        start, end = table_range
        result = "".join(lines[:start]) + block
        suffix = "".join(lines[end:])
        if suffix and not suffix.startswith("\n"):
            result += "\n"
        result += suffix

    try:
        parsed = tomllib.loads(result)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError("生成的 Codex 配置未通过 TOML 校验，未修改配置") from exc

    generated = gateway_config(parsed)
    expected_authorization = "Bearer " + pat
    if (
        not generated
        or generated.get("url") != mcp_url
        or generated.get("http_headers", {}).get("Authorization") != expected_authorization
    ):
        raise ConfigurationError("生成的 Gateway MCP 配置校验失败，未修改配置")
    return result


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".config.toml.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary, path)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    finally:
        if temporary.exists():
            temporary.unlink()


def oauth_config_status(
    data: dict[str, Any], system_endpoint: dict[str, str], oauth_client: dict[str, Any]
) -> str:
    """Describe configuration, never infer that OAuth login has completed."""
    if not system_mcp_url(system_endpoint).startswith("https://"):
        raise ConfigurationError("OAuth 自动配置要求 Skill 使用 HTTPS 端点")
    servers = data.get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise ConfigurationError("MCP 配置结构无效，未修改配置")
    if SERVER_NAME not in servers:
        return "missing"
    config = servers[SERVER_NAME]
    if not isinstance(config, dict):
        raise ConfigurationError("Gateway MCP 配置结构无效，未修改配置")
    if config.get("enabled", True) is not True:
        return "disabled"
    if config.get("url") != system_mcp_url(system_endpoint):
        return "url_conflict"
    if any(key in config for key in ("command", "args", "env", "env_vars")):
        return "transport_conflict"
    if config.get("auth", "oauth") != "oauth" or any(
        key in config for key in ("bearer_token_env_var", "http_headers_helper")
    ):
        return "auth_conflict"
    for key in ("http_headers", "env_http_headers"):
        headers = config.get(key, {})
        if not isinstance(headers, dict):
            raise ConfigurationError("Gateway MCP header 配置结构无效，未修改配置")
        if any(name.lower() == "authorization" for name in headers):
            return "auth_conflict"
    oauth = config.get("oauth", {})
    if not isinstance(oauth, dict):
        raise ConfigurationError("已有 OAuth 客户端配置无效，未修改配置")
    for key in ("client_id", "callback_url"):
        if key in oauth and oauth[key] != oauth_client[key]:
            return "oauth_client_conflict"
    if "oauth_resource" in config and config["oauth_resource"] != system_mcp_url(system_endpoint):
        return "oauth_resource_conflict"
    if "scopes" in config and config["scopes"] != oauth_client["scopes"]:
        return "oauth_scope_conflict"
    if any(key not in oauth for key in ("client_id", "callback_url")) or any(
        key not in config for key in ("oauth_resource", "scopes")
    ):
        return "oauth_client_missing"
    return "configured"


def merge_oauth_config(
    original: str, data: dict[str, Any], endpoint: dict[str, str], client: dict[str, Any]
) -> str:
    """Add missing public settings only, preserving policies and other servers."""
    current = gateway_config(data) or {}
    oauth = current.get("oauth", {})
    required = {"url": system_mcp_url(endpoint), "oauth_resource": system_mcp_url(endpoint), "scopes": client["scopes"]}
    oauth_required = {key: client[key] for key in ("client_id", "callback_url")}
    result = original
    for table, existing, additions in (
        ("mcp_servers.gateway", current, required),
        ("mcp_servers.gateway.oauth", oauth, oauth_required),
    ):
        missing = {k: v for k, v in additions.items() if k not in existing}
        if not missing:
            continue
        assignments = "".join(f"{key} = {json.dumps(value, ensure_ascii=False)}\n" for key, value in missing.items())
        lines = result.splitlines(keepends=True)
        index = next((i for i, line in enumerate(lines)
                      if (match := TABLE_HEADER_RE.match(line.rstrip("\r\n")))
                      and normalize_table_name(match.group(1)) == table), None)
        if index is None:
            result = result.rstrip("\n") + ("\n\n" if result else "") + f"[{table}]\n" + assignments
        else:
            # The header may be the final line without a newline.
            lines[index] = lines[index].rstrip("\r\n") + "\n"
            lines.insert(index + 1, assignments)
            result = "".join(lines)
    expected_gateway = {**current, **required, "oauth": {**oauth, **oauth_required}}
    expected = {**data, "mcp_servers": {**data.get("mcp_servers", {}), SERVER_NAME: expected_gateway}}
    try:
        parsed = tomllib.loads(result)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError("生成的 OAuth 配置无法安全合并，未修改配置") from exc
    if parsed != expected:
        raise ConfigurationError("生成的 OAuth 配置改变了其他设置，未修改配置")
    return result


def project_overrides_gateway(project_root: Path, config_path: Path) -> bool:
    """Don't silently add user config shadowed by a project/ancestor config."""
    for directory in (project_root, *project_root.parents):
        candidate = directory / ".codex" / "config.toml"
        if candidate == config_path:
            continue
        if candidate.parent.is_symlink():
            raise ConfigurationError("项目 .codex 不能是符号链接，未修改配置")
        _, data = load_config(candidate)
        servers = data.get("mcp_servers", {})
        if not isinstance(servers, dict):
            raise ConfigurationError("项目 MCP 配置结构无效，未修改配置")
        if SERVER_NAME in servers:
            return True
    return False


def configure_oauth(
    action: str,
    project_root: Path,
    config_path: Path,
    system_endpoint: dict[str, str],
) -> None:
    if action == "verify":
        raise ConfigurationError(
            "OAuth 请通过客户端登录并调用只读 Gateway tool 验证；不读取 Token 或 PAT"
        )
    original, data = load_config(config_path)
    oauth_client = load_oauth_client()
    state = oauth_config_status(data, system_endpoint, oauth_client)
    if project_overrides_gateway(project_root, config_path):
        state = "project_override"
    payload = {
        "ok": True,
        "config_status": state,
        "mcp_auth": "oauth",
        "oauth_login_status": "unknown",
        "connection_status": "unverified",
        "config_scope": "user",
        "config_path": str(config_path),
        "codex_oauth_support": codex_oauth_support(),
    }
    if action == "status":
        emit(payload)
        return
    if state not in {"missing", "oauth_client_missing", "configured"}:
        emit(
            {**payload, "ok": False, "code": "MCP_CONFIG_CONFLICT"}, error=True
        )
        raise SystemExit(3)
    if payload["codex_oauth_support"] != "supported":
        emit({**payload, "ok": False, "code": "CODEX_OAUTH_CAPABILITY_REQUIRED"}, error=True)
        raise SystemExit(3)

    changed = state in {"missing", "oauth_client_missing"}
    if changed:
        updated = merge_oauth_config(original, data, system_endpoint, oauth_client)
        atomic_write(config_path, updated)
    emit({
        **payload,
        "config_status": "configured",
        "configured": True,
        "changed": changed,
        "reload_required": changed,
    })


def status(
    project_root: Path,
    config_path: Path,
    system_endpoint: dict[str, str],
) -> None:
    pat = parse_dotenv_value(project_root)
    _, data = load_config(config_path)
    config = gateway_config(data)
    headers = config.get("http_headers") if config else None
    authorization = headers.get("Authorization") if isinstance(headers, dict) else None
    emit(
        {
            "ok": True,
            "pat_source": "project_dotenv" if pat else "missing",
            "mcp_configured": config is not None,
            "mcp_url_matches": bool(
                config and config.get("url") == system_mcp_url(system_endpoint)
            ),
            "mcp_auth": auth_mode(config),
            "mcp_pat_config_matches_dotenv": bool(pat and authorization == "Bearer " + pat),
            "config_scope": "user",
            "config_path": str(config_path),
        }
    )


def verify(project_root: Path, system_endpoint: dict[str, str]) -> None:
    pat = parse_dotenv_value(project_root)
    if not pat:
        raise ConfigurationError(f"当前项目 .env 未声明非空 {VARIABLE}")
    emit({"ok": True, **verify_pat(pat, system_endpoint)})


def apply(
    project_root: Path,
    config_path: Path,
    system_endpoint: dict[str, str],
) -> None:
    pat = parse_dotenv_value(project_root)
    if not pat:
        raise ConfigurationError(f"当前项目 .env 未声明非空 {VARIABLE}")

    verification = verify_pat(pat, system_endpoint)
    if verification["auth_status"] != "authenticated":
        emit(
            {
                "ok": False,
                "code": "PAT_VERIFICATION_FAILED",
                **verification,
            },
            error=True,
        )
        raise SystemExit(3)

    original, data = load_config(config_path)
    updated = render_config(original, data, pat, system_endpoint)
    changed = updated != original
    if changed:
        atomic_write(config_path, updated)
    elif config_path.exists():
        os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)

    emit(
        {
            "ok": True,
            "configured": True,
            "changed": changed,
            "mcp_auth": "static_header",
            "pat_verified": True,
            "config_scope": "user",
            "config_path": str(config_path),
            "restart_required": True,
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configure Codex Gateway MCP with OAuth; PAT requires explicit --auth pat."
    )
    parser.add_argument("action", choices=("status", "verify", "apply"))
    parser.add_argument("--auth", choices=("oauth", "pat"), default="oauth")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root for override detection; only --auth pat reads its .env.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    config_path = codex_config_path()
    try:
        system_endpoint = load_system_endpoint()
        if args.auth == "oauth":
            configure_oauth(args.action, project_root, config_path, system_endpoint)
        elif args.action == "status":
            status(project_root, config_path, system_endpoint)
        elif args.action == "verify":
            verify(project_root, system_endpoint)
        else:
            apply(project_root, config_path, system_endpoint)
    except ConfigurationError as exc:
        fail("CONFIGURATION_ERROR", str(exc))
    except OSError:
        fail("IO_ERROR", "Codex Gateway MCP 配置写入失败，未输出凭证")


if __name__ == "__main__":
    main()
