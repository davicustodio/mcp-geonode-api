from __future__ import annotations

import sys

from geonode_mcp.config_verifier import _run_server_checks
from geonode_mcp.snippets import _build_claude_code_snippet


def test_run_server_checks_resolves_python_from_path() -> None:
    checks = _run_server_checks({
        "command": "python3",
        "args": ["-m", "geonode_mcp"],
        "env": {},
    })

    by_name = {item["name"]: item for item in checks}
    assert by_name["command_exists"]["ok"] is True
    assert by_name["python_can_import_geonode_mcp"]["ok"] is True


def test_build_claude_code_snippet_quotes_shell_sensitive_values() -> None:
    snippet = _build_claude_code_snippet(
        server_name="geo node",
        python_command=sys.executable,
        env={
            "GEONODE_PASSWORD": "abc 123$danger",
            "GEONODE_URL": "https://example.com/path?a=1&b=2",
        },
    )

    cli_command = snippet["cli_command"]
    assert "--env 'GEONODE_PASSWORD=abc 123$danger'" in cli_command
    assert "--env 'GEONODE_URL=https://example.com/path?a=1&b=2'" in cli_command
    assert "stdio 'geo node' --env" in cli_command
