"""Persistence for MCP configuration in local files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models.resources import MCPClientTarget


def write_mcp_config(
    client: MCPClientTarget,
    config_path: str,
    server_name: str,
    python_command: str,
    env: dict[str, str],
    create_parent_dirs: bool = True,
) -> dict[str, Any]:
    path = Path(config_path).expanduser()
    if create_parent_dirs:
        path.parent.mkdir(parents=True, exist_ok=True)

    if client == MCPClientTarget.CODEX:
        content = _write_codex_toml(path, server_name, python_command, env)
    elif client in {MCPClientTarget.CURSOR, MCPClientTarget.CLAUDE_CODE}:
        content = _write_json_mcp_servers(path, server_name, python_command, env)
    elif client == MCPClientTarget.OPENCODE:
        content = _write_opencode_json(path, server_name, python_command, env)
    else:
        raise ValueError(f"Unsupported MCP client for automatic writing: {client}")

    return {
        "config_path": str(path),
        "bytes_written": len(content.encode("utf-8")),
    }


def _write_codex_toml(
    path: Path,
    server_name: str,
    python_command: str,
    env: dict[str, str],
) -> str:
    snippet = _build_codex_block(server_name, python_command, env)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    cleaned = _remove_codex_server(existing, server_name).strip()
    final = f"{cleaned}\n\n{snippet}".strip() + "\n"
    path.write_text(final, encoding="utf-8")
    return final


def _write_json_mcp_servers(
    path: Path,
    server_name: str,
    python_command: str,
    env: dict[str, str],
) -> str:
    data = _read_json_object(path)
    mcp_servers = data.setdefault("mcpServers", {})
    mcp_servers[server_name] = {
        "command": python_command,
        "args": ["-m", "geonode_mcp"],
        "env": env,
    }
    final = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(final, encoding="utf-8")
    return final


def _write_opencode_json(
    path: Path,
    server_name: str,
    python_command: str,
    env: dict[str, str],
) -> str:
    data = _read_json_object(path)
    data.setdefault("$schema", "https://opencode.ai/config.json")
    mcp = data.setdefault("mcp", {})
    mcp[server_name] = {
        "type": "local",
        "command": [python_command, "-m", "geonode_mcp"],
        "enabled": True,
        "environment": env,
    }
    final = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(final, encoding="utf-8")
    return final


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return {}
    loaded = json.loads(content)
    if not isinstance(loaded, dict):
        raise ValueError(f"The file {path} must contain a root JSON object.")
    return loaded


def _build_codex_block(server_name: str, python_command: str, env: dict[str, str]) -> str:
    env_lines = "\n".join([f'{key} = "{value}"' for key, value in env.items()])
    return (
        f"[mcp_servers.{server_name}]\n"
        f'command = "{python_command}"\n'
        'args = ["-m", "geonode_mcp"]\n\n'
        f"[mcp_servers.{server_name}.env]\n"
        f"{env_lines}"
    )


def _remove_codex_server(content: str, server_name: str) -> str:
    if not content.strip():
        return ""

    pattern = re.compile(
        rf"(?ms)^\[mcp_servers\.{re.escape(server_name)}(?:\.env)?\]\n.*?(?=^\[|\Z)"
    )
    previous = None
    updated = content
    while previous != updated:
        previous = updated
        updated = pattern.sub("", updated)
    return updated.strip()
