"""Tools for generic resource search."""

from __future__ import annotations

import json
from typing import Any, cast

from ..client import api, handle_api_error
from ..config_verifier import verify_mcp_config
from ..config_writer import write_mcp_config
from ..detection import detect_geonode_instance
from ..models.common import ResponseFormat, build_pagination_params, format_pagination_footer
from ..models.resources import (
    BootstrapMCPConfigInput,
    DetectGeoNodeInstanceInput,
    GenerateMCPConfigInput,
    GetResourceInput,
    SearchResourcesInput,
    VerifyMCPConfigInput,
    WriteMCPConfigInput,
)
from ..snippets import build_mcp_config_snippet


async def _resolve_client_config_context(
    url: str,
    username: str | None,
    password: str | None,
    geonode_version: str | None = None,
    api_version: str | None = None,
) -> tuple[dict[str, object], dict[str, str]]:
    detection = await detect_geonode_instance(
        url=url,
        username=username,
        password=password,
    )

    recommended = detection["recommended_settings"]
    resolved_geonode_version = geonode_version or recommended.get("GEONODE_VERSION") or "5"
    resolved_api_version = api_version or recommended.get("GEONODE_API_VERSION") or "v2"
    geonode_url = recommended.get("GEONODE_URL") or detection["normalized_base_url"]

    env = {
        "GEONODE_URL": str(geonode_url),
        "GEONODE_USER": username or "admin",
        "GEONODE_PASSWORD": password or "",
        "GEONODE_VERSION": str(resolved_geonode_version),
        "GEONODE_API_VERSION": str(resolved_api_version),
    }
    return detection, env


async def geonode_detect_instance(params: DetectGeoNodeInstanceInput) -> str:
    """Inspects a URL to suggest the correct GeoNode/API version configuration.

    Performs best-effort HTTP probes against the provided instance to detect which API is
    available and, when possible, infer the GeoNode major version.

    Returns:
        Recommendation for `GEONODE_URL`, `GEONODE_VERSION` e `GEONODE_API_VERSION`.
    """
    try:
        result = await detect_geonode_instance(
            url=params.url,
            username=params.username,
            password=params.password,
            timeout=params.timeout,
        )

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2, ensure_ascii=False)

        settings = result["recommended_settings"]
        confidence = result["confidence"]
        evidence = result["evidence"]
        notes = result["notes"]

        lines = [
            "# GeoNode Instance Detection",
            "",
            f"**Provided URL**: {result['input_url']}",
            f"**Normalized URL**: {result['normalized_base_url']}",
            f"**Detected API**: {result['detected_api_base_path'] or 'not detected'}",
            "",
            "## Recommended Settings",
            f"- `GEONODE_URL={settings['GEONODE_URL']}`",
            f"- `GEONODE_VERSION={settings['GEONODE_VERSION'] or 'undetermined'}`",
            f"- `GEONODE_API_VERSION={settings['GEONODE_API_VERSION'] or 'undetermined'}`",
            "",
            "## Confidence",
            f"- GeoNode version: {confidence['geonode_version']}",
            f"- API version: {confidence['api_version']}",
        ]

        if evidence:
            lines.extend(["", "## Evidence"])
            lines.extend([f"- {item}" for item in evidence])

        if notes:
            lines.extend(["", "## Notes"])
            lines.extend([f"- {item}" for item in notes])

        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_generate_mcp_config(params: GenerateMCPConfigInput) -> str:
    """Generates an MCP configuration snippet for a specific client.

    When `geonode_version` and `api_version` are not provided, the tool tries
    to detect them automatically from the URL.

    Returns:
        Ready-to-use snippet for Codex, Cursor, OpenCode, or Claude Code.
    """
    try:
        detection, env = await _resolve_client_config_context(
            url=params.url,
            username=params.username,
            password=params.password,
            geonode_version=params.geonode_version,
            api_version=params.api_version,
        )

        snippet = build_mcp_config_snippet(
            client=params.client,
            server_name=params.server_name,
            python_command=params.python_command,
            env=env,
        )

        payload = {
            "detection": {
                "normalized_base_url": detection["normalized_base_url"],
                "detected_api_base_path": detection["detected_api_base_path"],
                "confidence": detection["confidence"],
                "evidence": detection["evidence"],
                "notes": detection["notes"],
            },
            "recommended_settings": env,
            "client_config": snippet,
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(payload, indent=2, ensure_ascii=False)

        lines = [
            f"# MCP Config for {params.client.value}",
            "",
            f"**Suggested config path**: `{snippet['config_path']}`",
            "",
            "## Recommended Settings",
            f"- `GEONODE_URL={env['GEONODE_URL']}`",
            f"- `GEONODE_USER={env['GEONODE_USER']}`",
            f"- `GEONODE_PASSWORD={env['GEONODE_PASSWORD']}`",
            f"- `GEONODE_VERSION={env['GEONODE_VERSION']}`",
            f"- `GEONODE_API_VERSION={env['GEONODE_API_VERSION']}`",
            "",
            "## Snippet",
        ]

        fence = "toml" if snippet["format"] == "toml" else "json"
        lines.append(f"```{fence}")
        lines.append(snippet["snippet"])
        lines.append("```")

        if "cli_command" in snippet:
            lines.extend(["", "## CLI Command", "```bash", snippet["cli_command"], "```"])

        notes = cast(list[str], detection["notes"])
        if notes:
            lines.extend(["", "## Detection Notes"])
            lines.extend([f"- {note}" for note in notes])

        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_write_mcp_config(params: WriteMCPConfigInput) -> str:
    """Generates and writes the MCP configuration to the target file.

    The tool detects the recommended configuration from the URL and generates the snippet
    appropriate for the target client, then updates the provided file.

    Returns:
        Summary of the write operation and the settings that were applied.
    """
    try:
        detection, env = await _resolve_client_config_context(
            url=params.url,
            username=params.username,
            password=params.password,
            geonode_version=params.geonode_version,
            api_version=params.api_version,
        )

        snippet = build_mcp_config_snippet(
            client=params.client,
            server_name=params.server_name,
            python_command=params.python_command,
            env=env,
        )
        write_result = write_mcp_config(
            client=params.client,
            config_path=params.config_path,
            server_name=params.server_name,
            python_command=params.python_command,
            env=env,
            create_parent_dirs=params.create_parent_dirs,
        )

        payload = {
            "write_result": write_result,
            "recommended_settings": env,
            "client_config": snippet,
            "detection": {
                "normalized_base_url": detection["normalized_base_url"],
                "detected_api_base_path": detection["detected_api_base_path"],
                "confidence": detection["confidence"],
                "evidence": detection["evidence"],
                "notes": detection["notes"],
            },
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(payload, indent=2, ensure_ascii=False)

        lines = [
            f"# MCP Config Written for {params.client.value}",
            "",
            f"**Written file**: `{write_result['config_path']}`",
            f"**Bytes written**: {write_result['bytes_written']}",
            "",
            "## Applied Settings",
            f"- `GEONODE_URL={env['GEONODE_URL']}`",
            f"- `GEONODE_USER={env['GEONODE_USER']}`",
            f"- `GEONODE_PASSWORD={env['GEONODE_PASSWORD']}`",
            f"- `GEONODE_VERSION={env['GEONODE_VERSION']}`",
            f"- `GEONODE_API_VERSION={env['GEONODE_API_VERSION']}`",
        ]
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_verify_mcp_config(params: VerifyMCPConfigInput) -> str:
    """Verifies that a written MCP file is structurally correct and executable.

    Validates the presence of the target server in the file and checks the expected shape of the
    client, and when the configured command is Python + `-m geonode_mcp`,
    runs a lightweight import probe.

    Returns:
        Result of the file validation and configured command checks.
    """
    try:
        result = verify_mcp_config(
            client=params.client,
            config_path=params.config_path,
            server_name=params.server_name,
        )

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2, ensure_ascii=False)

        lines = [
            f"# MCP Config Verification for {params.client.value}",
            "",
            f"**Config file**: `{result['config_path']}`",
            f"**Server**: `{result['server_name']}`",
            f"**Valid**: {result['valid']}",
            "",
            "## Checks",
        ]
        for check in cast(list[dict[str, Any]], result["checks"]):
            detail = f" ({check['detail']})" if check.get("detail") else ""
            lines.append(f"- `{check['name']}`: {check['ok']}{detail}")
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_bootstrap_mcp_config(params: BootstrapMCPConfigInput) -> str:
    """Runs the full bootstrap flow for an MCP client.

    The flow includes: detecting the instance, generating the recommended configuration,
    writing to the target file and, optionally, verifying the final result.

    Returns:
        Consolidated result of the end-to-end MCP bootstrap.
    """
    try:
        detection, env = await _resolve_client_config_context(
            url=params.url,
            username=params.username,
            password=params.password,
            geonode_version=params.geonode_version,
            api_version=params.api_version,
        )

        snippet = build_mcp_config_snippet(
            client=params.client,
            server_name=params.server_name,
            python_command=params.python_command,
            env=env,
        )
        write_result = write_mcp_config(
            client=params.client,
            config_path=params.config_path,
            server_name=params.server_name,
            python_command=params.python_command,
            env=env,
            create_parent_dirs=params.create_parent_dirs,
        )

        verification: dict[str, object] | None = None
        if params.verify_after_write:
            verification = verify_mcp_config(
                client=params.client,
                config_path=params.config_path,
                server_name=params.server_name,
            )

        payload = {
            "detection": {
                "normalized_base_url": detection["normalized_base_url"],
                "detected_api_base_path": detection["detected_api_base_path"],
                "confidence": detection["confidence"],
                "evidence": detection["evidence"],
                "notes": detection["notes"],
            },
            "recommended_settings": env,
            "client_config": snippet,
            "write_result": write_result,
            "verification": verification,
            "bootstrap_ok": verification["valid"] if verification is not None else True,
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(payload, indent=2, ensure_ascii=False)

        lines = [
            f"# MCP Bootstrap for {params.client.value}",
            "",
            f"**Written file**: `{write_result['config_path']}`",
            f"**Bootstrap ok**: {payload['bootstrap_ok']}",
            "",
            "## Applied Settings",
            f"- `GEONODE_URL={env['GEONODE_URL']}`",
            f"- `GEONODE_USER={env['GEONODE_USER']}`",
            f"- `GEONODE_PASSWORD={env['GEONODE_PASSWORD']}`",
            f"- `GEONODE_VERSION={env['GEONODE_VERSION']}`",
            f"- `GEONODE_API_VERSION={env['GEONODE_API_VERSION']}`",
        ]
        if verification is not None:
            lines.extend(["", "## Verification"])
            for check in cast(list[dict[str, Any]], verification["checks"]):
                detail = f" ({check['detail']})" if check.get("detail") else ""
                lines.append(f"- `{check['name']}`: {check['ok']}{detail}")
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_search_resources(params: SearchResourcesInput) -> str:
    """Busca resources no GeoNode com filtros.

    Searches across all resource types (datasets, documents, maps, geoapps)
    with support for filters by type, owner, category, keyword, and region,
    published status and approval status.

    Returns:
        List of matching resources with title, type, owner, and date.
    """
    try:
        qp = build_pagination_params(params.limit, params.offset)
        if params.search:
            qp["search"] = params.search
        if params.resource_type:
            qp["filter{resource_type}"] = params.resource_type
        if params.owner:
            qp["filter{owner.username}"] = params.owner
        if params.category:
            qp["filter{category.identifier}"] = params.category
        if params.keyword:
            qp["filter{keywords.name}"] = params.keyword
        if params.region:
            qp["filter{regions.code}"] = params.region
        if params.is_published is not None:
            qp["filter{is_published}"] = str(params.is_published).lower()
        if params.is_approved is not None:
            qp["filter{is_approved}"] = str(params.is_approved).lower()
        if params.featured is not None:
            qp["filter{featured}"] = str(params.featured).lower()

        data = await api.get(api.route("resources"), params=qp)
        resources = data.get("resources", [])
        total = data.get("total", 0)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {"total": total, "count": len(resources), "offset": params.offset,
                 "resources": resources}, indent=2, ensure_ascii=False,
            )

        if not resources:
            return f"No resources found with the applied filters. Total: {total}"

        lines = [f"# Resources ({total} found)\n"]
        for r in resources:
            owner = r.get("owner", {})
            owner_name = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
            lines.append(f"## {r.get('title', 'Untitled')} (ID: {r['pk']})")
            lines.append(f"- **Type**: {r.get('resource_type', 'N/A')}")
            lines.append(f"- **Owner**: {owner_name} ({owner.get('username', '')})")
            lines.append(f"- **Category**: {(r.get('category') or {}).get('identifier', 'N/A')}")
            lines.append(f"- **Date**: {r.get('date', 'N/A')}")
            lines.append(
                f"- **Published**: {r.get('is_published')} | Approved: {r.get('is_approved')}"
            )
            lines.append(f"- **Link**: {r.get('detail_url', '')}")
            lines.append("")

        lines.append(format_pagination_footer(total, len(resources), params.offset, params.limit))
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_get_resource(params: GetResourceInput) -> str:
    """Returns full details for a specific resource by ID.

    Returns:
        All resource metadata including title, abstract, owner,
        category, keywords, regions, download links, and permissions.
    """
    try:
        data = await api.get(api.route("resource_detail", resource_id=params.resource_id))

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"resource": data}, indent=2, ensure_ascii=False)

        r = data.get("resource", data)
        owner = r.get("owner", {})
        owner_name = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
        keywords = ", ".join(k.get("name", "") for k in r.get("keywords", []))
        regions = ", ".join(reg.get("name", "") for reg in r.get("regions", []))

        lines = [
            f"# {r.get('title', 'Untitled')} (ID: {r.get('pk', params.resource_id)})",
            "",
            f"**Type**: {r.get('resource_type', 'N/A')} ({r.get('subtype', '')})",
            f"**Owner**: {owner_name} ({owner.get('username', '')})",
            f"**Category**: {(r.get('category') or {}).get('gn_description', 'N/A')}",
            f"**Date**: {r.get('date', 'N/A')} ({r.get('date_type', '')})",
            f"**Published**: {r.get('is_published')} | **Approved**: {r.get('is_approved')}",
            "",
            "## Summary",
            r.get("raw_abstract", "No summary"),
            "",
            f"**Keywords**: {keywords or 'None'}",
            f"**Regions**: {regions or 'None'}",
            f"**License**: {(r.get('license') or {}).get('identifier', 'N/A')}",
            "",
            f"**Download**: {r.get('download_url', 'N/A')}",
            f"**Detail**: {r.get('detail_url', 'N/A')}",
            f"**Thumbnail**: {r.get('thumbnail_url', 'N/A')}",
        ]
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)
