"""Verification for locally written MCP configuration files."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .models.resources import MCPClientTarget


def verify_mcp_config(
    client: MCPClientTarget,
    config_path: str,
    server_name: str,
) -> dict[str, Any]:
    path = Path(config_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    if client == MCPClientTarget.CODEX:
        server = _read_codex_server(path, server_name)
    elif client in {MCPClientTarget.CURSOR, MCPClientTarget.CLAUDE_CODE}:
        server = _read_json_server(path, "mcpServers", server_name)
    elif client == MCPClientTarget.OPENCODE:
        server = _read_json_server(path, "mcp", server_name)
    else:
        raise ValueError(f"Unsupported MCP client for verification: {client}")

    checks = _run_server_checks(server)
    return {
        "config_path": str(path),
        "client": client.value,
        "server_name": server_name,
        "server_config": server,
        "checks": checks,
        "valid": all(item["ok"] for item in checks),
    }


def _read_json_server(path: Path, top_key: str, server_name: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"The file {path} must contain a root JSON object.")

    container = data.get(top_key)
    if not isinstance(container, dict):
        raise ValueError(f"The file {path} does not contain the key `{top_key}` in the expected format.")

    server = container.get(server_name)
    if not isinstance(server, dict):
        raise ValueError(f"The server `{server_name}` was not found under `{top_key}`.")
    return server


def _read_codex_server(path: Path, server_name: str) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    command_match = re.search(
        rf"(?ms)^\[mcp_servers\.{re.escape(server_name)}\]\n(.*?)(?=^\[|\Z)",
        content,
    )
    env_match = re.search(
        rf"(?ms)^\[mcp_servers\.{re.escape(server_name)}\.env\]\n(.*?)(?=^\[|\Z)",
        content,
    )
    if not command_match:
        raise ValueError(f"The server `{server_name}` was not found in the Codex TOML.")

    command_block = command_match.group(1)
    command = _extract_toml_string(command_block, "command")
    args = _extract_toml_array(command_block, "args")
    env = _extract_toml_env(env_match.group(1) if env_match else "")
    return {"command": command, "args": args, "env": env}


def _extract_toml_string(block: str, key: str) -> str:
    match = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([^"]*)"', block, re.MULTILINE)
    if not match:
        raise ValueError(f"Required TOML key is missing: {key}")
    return match.group(1)


def _extract_toml_array(block: str, key: str) -> list[str]:
    match = re.search(rf'^\s*{re.escape(key)}\s*=\s*\[(.*?)\]', block, re.MULTILINE)
    if not match:
        return []
    values = re.findall(r'"([^"]*)"', match.group(1))
    return values


def _extract_toml_env(block: str) -> dict[str, str]:
    entries = re.findall(r'^\s*([A-Z0-9_]+)\s*=\s*"([^"]*)"', block, re.MULTILINE)
    return {key: value for key, value in entries}


def _run_server_checks(server: dict[str, Any]) -> list[dict[str, Any]]:
    command_value = server.get("command")
    args_value = server.get("args", [])

    if isinstance(command_value, list):
        command_parts = [str(item) for item in command_value]
        executable = command_parts[0] if command_parts else ""
        args = command_parts[1:]
    else:
        executable = str(command_value or "")
        args = [str(item) for item in args_value] if isinstance(args_value, list) else []

    env_value = server.get("env", server.get("environment", {}))
    has_env = isinstance(env_value, dict)
    checks: list[dict[str, Any]] = [
        {"name": "server_has_command", "ok": bool(executable), "detail": executable or None},
        {"name": "server_has_env_mapping", "ok": has_env, "detail": None},
        {
            "name": "command_exists",
            "ok": Path(executable).expanduser().exists(),
            "detail": executable,
        },
    ]

    if executable and Path(executable).expanduser().exists() and _looks_like_python_geonode_command(
        executable, args
    ):
        checks.append(_check_python_import(executable))

    return checks


def _looks_like_python_geonode_command(executable: str, args: list[str]) -> bool:
    name = Path(executable).name.lower()
    return "python" in name and args[:2] == ["-m", "geonode_mcp"]


def _check_python_import(executable: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [executable, "-c", "import geonode_mcp"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return {
            "name": "python_can_import_geonode_mcp",
            "ok": result.returncode == 0,
            "detail": result.stderr.strip() or result.stdout.strip() or None,
        }
    except Exception as exc:
        return {
            "name": "python_can_import_geonode_mcp",
            "ok": False,
            "detail": f"{type(exc).__name__}: {exc}",
        }
