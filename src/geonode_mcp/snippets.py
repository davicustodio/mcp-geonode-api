"""Generation of MCP configuration snippets for supported clients."""

from __future__ import annotations

import json
import shlex
from typing import Any

from .models.resources import MCPClientTarget


def build_mcp_config_snippet(
    client: MCPClientTarget,
    server_name: str,
    python_command: str,
    env: dict[str, str],
) -> dict[str, Any]:
    builders = {
        MCPClientTarget.CODEX: _build_codex_snippet,
        MCPClientTarget.CURSOR: _build_cursor_snippet,
        MCPClientTarget.OPENCODE: _build_opencode_snippet,
        MCPClientTarget.CLAUDE_CODE: _build_claude_code_snippet,
    }
    return builders[client](server_name, python_command, env)


def _build_codex_snippet(
    server_name: str,
    python_command: str,
    env: dict[str, str],
) -> dict[str, Any]:
    env_lines = "\n".join([f'{key} = "{value}"' for key, value in env.items()])
    snippet = (
        f"[mcp_servers.{server_name}]\n"
        f'command = "{python_command}"\n'
        'args = ["-m", "geonode_mcp"]\n\n'
        f"[mcp_servers.{server_name}.env]\n"
        f"{env_lines}\n"
    )
    return {
        "client": "codex",
        "config_path": "~/.codex/config.toml",
        "format": "toml",
        "snippet": snippet,
    }


def _build_cursor_snippet(
    server_name: str,
    python_command: str,
    env: dict[str, str],
) -> dict[str, Any]:
    snippet = json.dumps(
        {
            "mcpServers": {
                server_name: {
                    "command": python_command,
                    "args": ["-m", "geonode_mcp"],
                    "env": env,
                }
            }
        },
        indent=2,
        ensure_ascii=False,
    )
    return {
        "client": "cursor",
        "config_path": ".cursor/mcp.json",
        "format": "json",
        "snippet": snippet,
    }


def _build_opencode_snippet(
    server_name: str,
    python_command: str,
    env: dict[str, str],
) -> dict[str, Any]:
    snippet = json.dumps(
        {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                server_name: {
                    "type": "local",
                    "command": [python_command, "-m", "geonode_mcp"],
                    "enabled": True,
                    "environment": env,
                }
            },
        },
        indent=2,
        ensure_ascii=False,
    )
    return {
        "client": "opencode",
        "config_path": "opencode.json",
        "format": "json",
        "snippet": snippet,
    }


def _build_claude_code_snippet(
    server_name: str,
    python_command: str,
    env: dict[str, str],
) -> dict[str, Any]:
    env_flags = " ".join([
        f"--env {shlex.quote(f'{key}={value}')}" for key, value in env.items()
    ])
    cli_command = (
        f"claude mcp add --transport stdio {shlex.quote(server_name)} "
        f"{env_flags} -- {shlex.quote(python_command)} -m geonode_mcp"
    )
    json_snippet = json.dumps(
        {
            "mcpServers": {
                server_name: {
                    "command": python_command,
                    "args": ["-m", "geonode_mcp"],
                    "env": env,
                }
            }
        },
        indent=2,
        ensure_ascii=False,
    )
    return {
        "client": "claude_code",
        "config_path": ".mcp.json",
        "format": "mixed",
        "snippet": json_snippet,
        "cli_command": cli_command,
    }
