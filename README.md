# GeoNode MCP

MCP server for GeoNode `4.x` and `5.x`, with API compatibility resolved through configuration.

The server currently targets the GeoNode REST API exposed under `/api/v2`, which is still the documented API base for GeoNode 4.x and 5.x. The MCP configuration separates:

- `GEONODE_VERSION`: the GeoNode product version (`4` or `5`)
- `GEONODE_API_VERSION`: the REST API version to use (currently `v2`)

This keeps the MCP ready for future API changes without spreading version checks across every tool.

## Features

- Search and inspect GeoNode resources
- Detect the most likely GeoNode/API compatibility settings from a URL
- Generate ready-to-paste MCP client configuration snippets from a URL
- Write the generated MCP client configuration directly into a local config file
- Verify that a written MCP config file is structurally correct and usable
- Bootstrap a complete MCP client setup in one call
- List and manage datasets, documents, maps, users, and groups
- List categories, keywords, regions, and owners
- Centralized compatibility layer for GeoNode/API version mapping
- Local stdio execution for MCP clients such as Codex, Cursor, OpenCode, and Claude Code

## Compatibility

Supported today:

- GeoNode `4.x` with API `v2`
- GeoNode `5.x` with API `v2`

Default runtime values:

- `GEONODE_VERSION=5`
- `GEONODE_API_VERSION=v2`

## Local Installation

### Requirements

- Python `3.10+`
- Access to a GeoNode instance
- GeoNode credentials if you need authenticated operations

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd mcp-geoinfo-api
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the package locally

For normal usage:

```bash
pip install -e .
```

For development, including linting and tests:

```bash
pip install -e ".[dev]"
```

### 4. Set environment variables

```bash
export GEONODE_URL="https://your-geonode.example.com"
export GEONODE_USER="admin"
export GEONODE_PASSWORD="your-password"
export GEONODE_VERSION="5"
export GEONODE_API_VERSION="v2"
```

Optional override:

```bash
export GEONODE_API_BASE_PATH="/api/v2"
```

Use `GEONODE_API_BASE_PATH` only if your deployment exposes the API under a custom path.

### 5. Run the server locally

```bash
python -m geonode_mcp
```

This starts the MCP server over `stdio`, which is what local MCP clients expect.

## Configuration Reference

### Environment variables

- `GEONODE_URL`: GeoNode base URL, without a trailing slash preferred
- `GEONODE_USER`: username for Basic Auth
- `GEONODE_PASSWORD`: password for Basic Auth
- `GEONODE_VERSION`: GeoNode major version, currently `4` or `5`
- `GEONODE_API_VERSION`: API version, currently `v2`
- `GEONODE_API_BASE_PATH`: optional explicit API path override

### Recommended values

For most GeoNode 5 deployments:

```bash
GEONODE_VERSION=5
GEONODE_API_VERSION=v2
```

For most GeoNode 4 deployments:

```bash
GEONODE_VERSION=4
GEONODE_API_VERSION=v2
```

## Detecting the Correct Version Settings

The MCP includes a discovery tool named `geonode_detect_instance`.

Its purpose is to inspect a GeoNode instance URL and suggest which values should be used for:

- `GEONODE_URL`
- `GEONODE_VERSION`
- `GEONODE_API_VERSION`

This is a best-effort detection flow. In practice:

- API version detection is usually reliable when `/api/v2/resources/` is reachable
- exact GeoNode major version detection depends on whether the instance exposes version hints in HTML, headers, or static files

### Tool name

```text
geonode_detect_instance
```

### Input parameters

- `url`: base URL of the GeoNode instance, or even a known API URL
- `username`: optional Basic Auth username for probing protected instances
- `password`: optional Basic Auth password for probing protected instances
- `timeout`: optional timeout in seconds
- `response_format`: `json` or `markdown`

### Example call

```json
{
  "url": "https://your-geonode.example.com",
  "response_format": "json"
}
```

You can also pass an API URL directly:

```json
{
  "url": "https://your-geonode.example.com/api/v2/resources/",
  "response_format": "json"
}
```

### Example response

```json
{
  "normalized_base_url": "https://your-geonode.example.com",
  "detected_api_base_path": "/api/v2",
  "recommended_settings": {
    "GEONODE_URL": "https://your-geonode.example.com",
    "GEONODE_VERSION": "5",
    "GEONODE_API_VERSION": "v2"
  },
  "confidence": {
    "geonode_version": "medium",
    "api_version": "high"
  }
}
```

### Recommended usage

1. Run `geonode_detect_instance` against the target URL.
2. Copy the returned recommended settings into your MCP client configuration.
3. If `GEONODE_VERSION` is returned as `undetermined` or `null`, keep the detected `GEONODE_API_VERSION` and confirm the GeoNode major version manually.

## Generating Ready-to-Use MCP Client Config

The MCP also includes a helper tool named `geonode_generate_mcp_config`.

This tool combines:

- instance detection from the provided URL
- recommended `GEONODE_*` settings
- a ready-to-paste MCP snippet for one target client

### Tool name

```text
geonode_generate_mcp_config
```

### Input parameters

- `client`: one of `codex`, `cursor`, `opencode`, `claude_code`
- `url`: base URL of the GeoNode instance, or a known API URL
- `username`: optional Basic Auth username
- `password`: optional Basic Auth password
- `geonode_version`: optional manual override
- `api_version`: optional manual override
- `server_name`: optional MCP server name, default `geonode`
- `python_command`: Python executable path used to start `python -m geonode_mcp`
- `response_format`: `markdown` or `json`

### Example call

```json
{
  "client": "cursor",
  "url": "https://your-geonode.example.com",
  "username": "admin",
  "password": "your-password",
  "python_command": "/path/to/mcp-geoinfo-api/.venv/bin/python",
  "response_format": "markdown"
}
```

### Example usage flow

1. Run `geonode_generate_mcp_config`.
2. Copy the generated snippet into the config file suggested by the response.
3. If needed, replace `GEONODE_PASSWORD` with your preferred secret-management pattern.

### When to use each tool

- Use `geonode_detect_instance` if you only want to inspect a GeoNode URL and understand the inferred compatibility.
- Use `geonode_generate_mcp_config` if you want the final client snippet immediately.
- Use `geonode_write_mcp_config` if you want the MCP to update the target config file for you.
- Use `geonode_verify_mcp_config` after writing to confirm the file and command are valid.
- Use `geonode_bootstrap_mcp_config` if you want the full flow in one step.

## One-Step Bootstrap

The MCP also provides `geonode_bootstrap_mcp_config`.

This is the highest-level helper. It:

- detects the target GeoNode instance
- resolves the recommended `GEONODE_*` settings
- writes the client config file
- optionally verifies the final result

### Tool name

```text
geonode_bootstrap_mcp_config
```

### Input parameters

- `client`: one of `codex`, `cursor`, `opencode`, `claude_code`
- `url`: base URL of the GeoNode instance, or a known API URL
- `config_path`: file to create or update
- `username`: optional Basic Auth username
- `password`: optional Basic Auth password
- `geonode_version`: optional manual override
- `api_version`: optional manual override
- `server_name`: optional MCP server name, default `geonode`
- `python_command`: Python executable path used to start `python -m geonode_mcp`
- `create_parent_dirs`: create missing parent directories automatically
- `verify_after_write`: validate the file after writing, default `true`
- `response_format`: `markdown` or `json`

### Example call

```json
{
  "client": "cursor",
  "url": "https://your-geonode.example.com",
  "config_path": "/Users/you/.cursor/mcp.json",
  "username": "admin",
  "password": "your-password",
  "python_command": "/path/to/mcp-geoinfo-api/.venv/bin/python",
  "verify_after_write": true,
  "response_format": "json"
}
```

### Recommended default workflow

For most users, `geonode_bootstrap_mcp_config` should be the default choice.

### Why the lower-level tools still exist

The other tools are still useful and should remain:

- `geonode_detect_instance`: best for diagnosis and understanding what the server exposes
- `geonode_generate_mcp_config`: best when you want to review the snippet before touching files
- `geonode_write_mcp_config`: best when writing should happen without verification, or when verification must be separated
- `geonode_verify_mcp_config`: best for CI, troubleshooting, or validating an already existing config file

So after bootstrap exists, the lower-level tools are still justified. They are not redundant; they support review, debugging, and partial workflows.

## Writing MCP Client Config Files Automatically

The MCP also provides `geonode_write_mcp_config`.

This tool:

- detects the instance settings from the URL
- generates the correct client configuration
- writes or updates the target local config file

### Tool name

```text
geonode_write_mcp_config
```

### Input parameters

- `client`: one of `codex`, `cursor`, `opencode`, `claude_code`
- `url`: base URL of the GeoNode instance, or a known API URL
- `config_path`: file to create or update
- `username`: optional Basic Auth username
- `password`: optional Basic Auth password
- `geonode_version`: optional manual override
- `api_version`: optional manual override
- `server_name`: optional MCP server name, default `geonode`
- `python_command`: Python executable path used to start `python -m geonode_mcp`
- `create_parent_dirs`: create missing parent directories automatically
- `response_format`: `markdown` or `json`

### Example call

```json
{
  "client": "cursor",
  "url": "https://your-geonode.example.com",
  "config_path": "/Users/you/.cursor/mcp.json",
  "username": "admin",
  "password": "your-password",
  "python_command": "/path/to/mcp-geoinfo-api/.venv/bin/python",
  "response_format": "markdown"
}
```

### What it updates

- For `cursor` and `claude_code`, it updates the `mcpServers` entry for the selected server name.
- For `opencode`, it updates the `mcp` entry for the selected server name.
- For `codex`, it updates the matching `[mcp_servers.<name>]` and `[mcp_servers.<name>.env]` TOML blocks.

### Recommended usage

1. For the fastest setup, use `geonode_bootstrap_mcp_config`.
2. If you want a staged flow, use `geonode_generate_mcp_config`, then `geonode_write_mcp_config`, then `geonode_verify_mcp_config`.
3. Re-run the relevant tool whenever the GeoNode URL, credentials, or Python path changes.

## Verifying a Written MCP Config File

The MCP also provides `geonode_verify_mcp_config`.

This tool validates:

- that the target file exists
- that the expected server entry is present
- that the file shape matches the selected client
- that the configured executable exists
- that `python -m geonode_mcp` can at least import the package when the command matches that pattern

### Tool name

```text
geonode_verify_mcp_config
```

### Input parameters

- `client`: one of `codex`, `cursor`, `opencode`, `claude_code`
- `config_path`: file to validate
- `server_name`: MCP server name to inspect, default `geonode`
- `response_format`: `markdown` or `json`

### Example call

```json
{
  "client": "cursor",
  "config_path": "/Users/you/.cursor/mcp.json",
  "server_name": "geonode",
  "response_format": "json"
}
```

### Recommended usage flow

1. Run `geonode_write_mcp_config`.
2. Run `geonode_verify_mcp_config`.
3. If verification fails, inspect the returned checks and correct the command path, environment, or file location.

## MCP Client Setup

The examples below assume:

- the repository lives at `/path/to/mcp-geoinfo-api`
- the virtual environment lives at `/path/to/mcp-geoinfo-api/.venv`

Adjust those paths to your machine.

### Codex

If you want the MCP to generate this automatically, call `geonode_generate_mcp_config` with `"client": "codex"`.
If you want it to write the file directly, use `geonode_write_mcp_config` with `config_path="~/.codex/config.toml"`.

OpenAI documents MCP configuration in `~/.codex/config.toml`. The `mcp_servers` table is documented for Codex; the local stdio example below follows that same structure for this server.

File: `~/.codex/config.toml`

```toml
[mcp_servers.geonode]
command = "/path/to/mcp-geoinfo-api/.venv/bin/python"
args = ["-m", "geonode_mcp"]

[mcp_servers.geonode.env]
GEONODE_URL = "https://your-geonode.example.com"
GEONODE_USER = "admin"
GEONODE_PASSWORD = "your-password"
GEONODE_VERSION = "5"
GEONODE_API_VERSION = "v2"
```

If you prefer a project-specific setup, keep the same command and environment values in the Codex configuration you use for that workspace.

### Cursor

If you want the MCP to generate this automatically, call `geonode_generate_mcp_config` with `"client": "cursor"`.
If you want it to write the file directly, use `geonode_write_mcp_config` with `config_path="~/.cursor/mcp.json"` or a project `.cursor/mcp.json`.

Cursor supports MCP via `mcp.json`. You can configure it globally in `~/.cursor/mcp.json` or per project in `.cursor/mcp.json`.

File: `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "geonode": {
      "command": "/path/to/mcp-geoinfo-api/.venv/bin/python",
      "args": ["-m", "geonode_mcp"],
      "env": {
        "GEONODE_URL": "https://your-geonode.example.com",
        "GEONODE_USER": "admin",
        "GEONODE_PASSWORD": "your-password",
        "GEONODE_VERSION": "5",
        "GEONODE_API_VERSION": "v2"
      }
    }
  }
}
```

You can also use Cursor variable interpolation if needed, for example `${workspaceFolder}` or `${env:GEONODE_PASSWORD}`.

### OpenCode

If you want the MCP to generate this automatically, call `geonode_generate_mcp_config` with `"client": "opencode"`.
If you want it to write the file directly, use `geonode_write_mcp_config` with `config_path="~/.config/opencode/opencode.json"` or a project `opencode.json`.

OpenCode loads config from `~/.config/opencode/opencode.json` globally or `opencode.json` in the project root.

File: `opencode.json`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "geonode": {
      "type": "local",
      "command": [
        "/path/to/mcp-geoinfo-api/.venv/bin/python",
        "-m",
        "geonode_mcp"
      ],
      "enabled": true,
      "environment": {
        "GEONODE_URL": "https://your-geonode.example.com",
        "GEONODE_USER": "admin",
        "GEONODE_PASSWORD": "your-password",
        "GEONODE_VERSION": "5",
        "GEONODE_API_VERSION": "v2"
      }
    }
  }
}
```

### Claude Code

If you want the MCP to generate this automatically, call `geonode_generate_mcp_config` with `"client": "claude_code"`.
If you want it to write the file directly, use `geonode_write_mcp_config` with `config_path=".mcp.json"` or another Claude Code MCP file path.

Claude Code supports local stdio MCP servers directly from the CLI and can also store project-scoped configuration in `.mcp.json`.

#### Option 1: add it with the CLI

```bash
claude mcp add --transport stdio geonode \
  --env GEONODE_URL=https://your-geonode.example.com \
  --env GEONODE_USER=admin \
  --env GEONODE_PASSWORD=your-password \
  --env GEONODE_VERSION=5 \
  --env GEONODE_API_VERSION=v2 \
  -- /path/to/mcp-geoinfo-api/.venv/bin/python -m geonode_mcp
```

For a shared project configuration:

```bash
claude mcp add --transport stdio --scope project geonode \
  --env GEONODE_URL=https://your-geonode.example.com \
  --env GEONODE_USER=admin \
  --env GEONODE_PASSWORD=your-password \
  --env GEONODE_VERSION=5 \
  --env GEONODE_API_VERSION=v2 \
  -- /path/to/mcp-geoinfo-api/.venv/bin/python -m geonode_mcp
```

#### Option 2: configure `.mcp.json` manually

File: `.mcp.json`

```json
{
  "mcpServers": {
    "geonode": {
      "command": "/path/to/mcp-geoinfo-api/.venv/bin/python",
      "args": ["-m", "geonode_mcp"],
      "env": {
        "GEONODE_URL": "https://your-geonode.example.com",
        "GEONODE_USER": "admin",
        "GEONODE_PASSWORD": "your-password",
        "GEONODE_VERSION": "5",
        "GEONODE_API_VERSION": "v2"
      }
    }
  }
}
```

## Recommended Setup Strategy

Use this layout if you want stable local development:

1. Install the package in a project-local virtual environment.
2. Point your MCP client to that virtualenv Python executable.
3. Keep secrets in environment variables or client-side secret storage where possible.
4. Set `GEONODE_VERSION` explicitly even when using defaults.
5. Only override `GEONODE_API_BASE_PATH` if your deployment is non-standard.

## Development

Run checks:

```bash
ruff check .
python3 -m mypy src
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` is recommended if your machine has unrelated global pytest plugins installed.

## Why Versioning Is Implemented This Way

GeoNode 4.x and 5.x still document the primary REST API under `/api/v2`. Because of that, this project does not map GeoNode product versions directly to a new REST prefix. Instead, it:

- reads the GeoNode version from configuration
- reads the API version from configuration
- resolves the actual route set through a compatibility layer

That design keeps the tool surface stable and makes future version support much easier to add.

## Sources

- OpenAI Codex MCP docs: [developers.openai.com/learn/docs-mcp](https://developers.openai.com/learn/docs-mcp)
- Cursor MCP docs: [docs.cursor.com/advanced/model-context-protocol](https://docs.cursor.com/advanced/model-context-protocol)
- Claude Code MCP docs: [code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp)
- OpenCode MCP docs: [opencode.ai/docs/mcp-servers](https://opencode.ai/docs/mcp-servers/)
- OpenCode config locations: [opencode.ai/docs/config](https://opencode.ai/docs/config/)
- GeoNode developer API docs: [docs.geonode.org/en/5.0.x/devel/api/usage/index.html](https://docs.geonode.org/en/5.0.x/devel/api/usage/index.html)
