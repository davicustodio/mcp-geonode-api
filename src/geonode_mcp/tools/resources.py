"""Tools for generic resource search."""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast

import httpx

from ..client import api, handle_api_error
from ..config_verifier import verify_mcp_config
from ..config_writer import write_mcp_config
from ..detection import detect_geonode_instance
from ..models.common import (
    ResponseFormat,
    build_pagination_params,
    format_pagination_footer,
)
from ..models.resources import (
    BootstrapMCPConfigInput,
    DetectGeoNodeInstanceInput,
    GenerateMCPConfigInput,
    GetResourceInput,
    MetadataSearchField,
    MetadataSearchMode,
    MetadataSearchResourceType,
    SearchMetadataTextInput,
    SearchResourcesInput,
    VerifyMCPConfigInput,
    WriteMCPConfigInput,
)
from ..snippets import build_mcp_config_snippet

_DEFAULT_METADATA_TYPES = [
    MetadataSearchResourceType.DATASET,
    MetadataSearchResourceType.DOCUMENT,
    MetadataSearchResourceType.MAP,
]
_FIELD_PRIORITY = {
    MetadataSearchField.TITLE: 0,
    MetadataSearchField.KEYWORDS: 1,
    MetadataSearchField.ABSTRACT: 2,
    MetadataSearchField.EXTRA_METADATA: 3,
}
_ITEMS_BY_ROUTE = {
    "datasets": "datasets",
    "documents": "documents",
    "maps": "maps",
    "resources": "resources",
}


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


def _unique_in_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _normalize_resource_types(
    resource_types: list[MetadataSearchResourceType] | None,
) -> list[MetadataSearchResourceType]:
    return list(resource_types or _DEFAULT_METADATA_TYPES)


def _expand_search_fields(
    search_in: list[MetadataSearchField],
) -> list[MetadataSearchField]:
    if not search_in or MetadataSearchField.ANY_METADATA in search_in:
        return [
            MetadataSearchField.TITLE,
            MetadataSearchField.ABSTRACT,
            MetadataSearchField.KEYWORDS,
            MetadataSearchField.EXTRA_METADATA,
        ]

    ordered = [field.value for field in search_in]
    return [MetadataSearchField(value) for value in _unique_in_order(ordered)]


def _resource_key(item: dict[str, Any]) -> str:
    resource_type = item.get("resource_type", "resource")
    return f"{resource_type}:{item.get('pk', '')}"


def _get_route_name(resource_type: MetadataSearchResourceType, field: MetadataSearchField) -> str:
    if (
        field == MetadataSearchField.EXTRA_METADATA
        or resource_type == MetadataSearchResourceType.GEOAPP
    ):
        return "resources"

    return {
        MetadataSearchResourceType.DATASET: "datasets",
        MetadataSearchResourceType.DOCUMENT: "documents",
        MetadataSearchResourceType.MAP: "maps",
        MetadataSearchResourceType.GEOAPP: "resources",
    }[resource_type]


def _build_field_params(
    resource_type: MetadataSearchResourceType,
    field: MetadataSearchField,
    text: str,
) -> dict[str, object]:
    params: dict[str, object] = {}

    if field == MetadataSearchField.TITLE:
        params["filter{title.icontains}"] = text
    elif field == MetadataSearchField.ABSTRACT:
        params["filter{abstract.icontains}"] = text
    elif field == MetadataSearchField.KEYWORDS:
        params["filter{keywords.name.icontains}"] = text
    elif field == MetadataSearchField.EXTRA_METADATA:
        params["filter{metadata.metadata.icontains}"] = text

    if (
        resource_type == MetadataSearchResourceType.GEOAPP
        or field == MetadataSearchField.EXTRA_METADATA
    ):
        params["filter{resource_type}"] = resource_type.value
    elif _get_route_name(resource_type, field) == "resources":
        params["filter{resource_type}"] = resource_type.value

    return params


def _build_subqueries(params: SearchMetadataTextInput) -> list[dict[str, object]]:
    subqueries: list[dict[str, object]] = []
    fields = _expand_search_fields(params.search_in)

    for resource_type in _normalize_resource_types(params.resource_types):
        for field in fields:
            subqueries.append({
                "resource_type": resource_type.value,
                "field": field.value,
                "route_name": _get_route_name(resource_type, field),
                "query_params": _build_field_params(resource_type, field, params.text),
            })

    return subqueries


def _build_subquery_batches(params: SearchMetadataTextInput) -> list[list[dict[str, object]]]:
    if params.search_mode == MetadataSearchMode.EXHAUSTIVE:
        return [_build_subqueries(params)]

    resource_types = _normalize_resource_types(params.resource_types)
    requested_fields = _expand_search_fields(params.search_in)
    stage_fields: list[list[MetadataSearchField]] = []

    high_priority_fields = [
        field
        for field in (MetadataSearchField.TITLE, MetadataSearchField.KEYWORDS)
        if field in requested_fields
    ]
    if high_priority_fields:
        stage_fields.append(high_priority_fields)

    for field in (MetadataSearchField.ABSTRACT, MetadataSearchField.EXTRA_METADATA):
        if field in requested_fields:
            stage_fields.append([field])

    batches: list[list[dict[str, object]]] = []
    for fields in stage_fields:
        batch: list[dict[str, object]] = []
        for resource_type in resource_types:
            for field in fields:
                batch.append({
                    "resource_type": resource_type.value,
                    "field": field.value,
                    "route_name": _get_route_name(resource_type, field),
                    "query_params": _build_field_params(resource_type, field, params.text),
                })
        if batch:
            batches.append(batch)

    return batches


def _extract_matching_keywords(item: dict[str, Any], text: str) -> str:
    needle = text.casefold()
    names = [k.get("name", "") for k in item.get("keywords", [])]
    matches = [name for name in names if needle in name.casefold()]
    return ", ".join(matches[:3])


def _build_excerpt(item: dict[str, Any], field: MetadataSearchField, text: str) -> str:
    if field == MetadataSearchField.TITLE:
        return item.get("title", "Untitled")

    if field == MetadataSearchField.KEYWORDS:
        keyword_excerpt = _extract_matching_keywords(item, text)
        return keyword_excerpt or "Matched in keywords."

    if field == MetadataSearchField.EXTRA_METADATA:
        return "Matched in extra metadata."

    abstract = item.get("raw_abstract", "") or item.get("abstract", "")
    if not abstract:
        return "No summary available."

    haystack = " ".join(str(abstract).split())
    lower = haystack.casefold()
    needle = text.casefold()
    index = lower.find(needle)
    if index < 0:
        return haystack[:160] + ("..." if len(haystack) > 160 else "")

    start = max(index - 60, 0)
    end = min(index + len(text) + 100, len(haystack))
    excerpt = haystack[start:end]
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(haystack) else ""
    return f"{prefix}{excerpt}{suffix}"


def _match_keyword_locally(item: dict[str, Any], text: str) -> bool:
    needle = text.casefold()
    for keyword in item.get("keywords", []):
        if needle in keyword.get("name", "").casefold():
            return True
    return False


async def _run_subquery(
    subquery: dict[str, object],
    limit: int,
    offset: int,
    text: str,
) -> dict[str, object]:
    route_name = cast(str, subquery["route_name"])
    route = api.route(route_name)
    query_params = dict(cast(dict[str, object], subquery["query_params"]))
    query_params.update(build_pagination_params(limit + offset, 0))

    try:
        data = await api.get(route, params=query_params)
    except httpx.HTTPStatusError as exc:
        field = cast(str, subquery["field"])
        if field != MetadataSearchField.KEYWORDS.value or exc.response.status_code != 400:
            raise

        fallback_params = dict(build_pagination_params(limit + offset, 0))
        fallback_params["search"] = text
        if route_name == "resources":
            fallback_params["filter{resource_type}"] = cast(str, subquery["resource_type"])
        data = await api.get(route, params=fallback_params)

    items_key = _ITEMS_BY_ROUTE[route_name]
    items = cast(list[dict[str, Any]], data.get(items_key, []))
    if cast(str, subquery["field"]) == MetadataSearchField.KEYWORDS.value:
        items = [item for item in items if _match_keyword_locally(item, text)]

    return {
        "items": items,
        "total": data.get("total", len(items)),
        "field": subquery["field"],
        "resource_type": subquery["resource_type"],
        "route_name": route_name,
    }


def _sort_hits(hits: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_hits = list(hits.values())
    sorted_hits.sort(key=lambda item: item.get("date", ""), reverse=True)
    sorted_hits.sort(
        key=lambda item: min(
            _FIELD_PRIORITY[MetadataSearchField(field)]
            for field in cast(list[str], item["matched_fields"])
        ),
    )
    return sorted_hits


def _format_metadata_search_result(
    hits: list[dict[str, Any]],
    requested_offset: int,
    requested_limit: int,
    total: int,
    total_is_exact: bool,
    execution_mode: str,
    executed_subqueries: int,
    planned_subqueries: int,
) -> str:
    if not hits:
        return "No resources found with the applied metadata filters. Total: 0"

    label = "exact" if total_is_exact else "partial"
    lines = [f"# Metadata Search Results ({total} {label} matches)\n"]
    for item in hits:
        lines.append(f"## {item.get('title', 'Untitled')} (ID: {item.get('id', 'N/A')})")
        lines.append(f"- **Type**: {item.get('resource_type', 'N/A')}")
        lines.append(f"- **Matched fields**: {', '.join(item.get('matched_fields', []))}")
        lines.append(f"- **Owner**: {item.get('owner', 'N/A')}")
        lines.append(f"- **Date**: {item.get('date', 'N/A')}")
        lines.append(f"- **Excerpt**: {item.get('excerpt', 'N/A')}")
        lines.append(f"- **Link**: {item.get('detail_url', '')}")
        lines.append("")

    lines.append(format_pagination_footer(total, len(hits), requested_offset, requested_limit))
    if not total_is_exact:
        lines.append("\nNote: total is partial because this search merges multiple field queries.")
    if execution_mode == MetadataSearchMode.FAST.value and executed_subqueries < planned_subqueries:
        lines.append(
            "\nNote: fast mode stopped early after higher-priority matches "
            "filled the requested page."
        )
    return "\n".join(lines)


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


async def geonode_search_metadata_text(params: SearchMetadataTextInput) -> str:
    """Searches GeoNode metadata fields using the most selective API filters available.

    Supports title, abstract, keywords, and extra metadata across datasets,
    documents, maps, and geoapps.

    Returns:
        List of matching resources with matched fields and excerpts.
    """
    try:
        subquery_batches = _build_subquery_batches(params)
        planned_subqueries = sum(len(batch) for batch in subquery_batches)
        executed_subqueries = 0
        merged_hits: dict[str, dict[str, Any]] = {}
        required_hits = params.offset + params.limit
        last_query_results: list[dict[str, object]] = []

        for batch_index, batch in enumerate(subquery_batches):
            query_results = await asyncio.gather(*[
                _run_subquery(subquery, params.limit, params.offset, params.text)
                for subquery in batch
            ])
            last_query_results = query_results
            executed_subqueries += len(batch)

            for result in query_results:
                field = MetadataSearchField(cast(str, result["field"]))

                for item in cast(list[dict[str, Any]], result["items"]):
                    key = _resource_key(item)
                    owner = item.get("owner", {})
                    owner_name = (
                        f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
                    )
                    entry = merged_hits.setdefault(key, {
                        "id": item.get("pk"),
                        "resource_type": item.get(
                            "resource_type",
                            cast(str, result["resource_type"]),
                        ),
                        "title": item.get("title", "Untitled"),
                        "detail_url": item.get("detail_url", ""),
                        "owner": f"{owner_name} ({owner.get('username', '')})".strip(),
                        "date": item.get("date", "N/A"),
                        "matched_fields": [],
                        "excerpt": _build_excerpt(item, field, params.text),
                    })
                    if field.value not in cast(list[str], entry["matched_fields"]):
                        cast(list[str], entry["matched_fields"]).append(field.value)
                        cast(list[str], entry["matched_fields"]).sort(
                            key=lambda value: _FIELD_PRIORITY[MetadataSearchField(value)]
                        )
                    if field == MetadataSearchField.TITLE:
                        entry["excerpt"] = _build_excerpt(item, field, params.text)

            if (
                params.search_mode == MetadataSearchMode.FAST
                and batch_index < len(subquery_batches) - 1
                and len(_sort_hits(merged_hits)) >= required_hits
            ):
                break

        sorted_hits = _sort_hits(merged_hits)
        paged_hits = sorted_hits[params.offset: params.offset + params.limit]
        total_is_exact = executed_subqueries == 1
        total = (
            len(sorted_hits)
            if not total_is_exact
            else cast(int, last_query_results[0]["total"])
        )

        payload = {
            "total": total,
            "total_is_exact": total_is_exact,
            "count": len(paged_hits),
            "offset": params.offset,
            "search_mode": params.search_mode.value,
            "query_plan": _build_subqueries(params),
            "query_plan_executed": executed_subqueries,
            "query_plan_total": planned_subqueries,
            "results": paged_hits,
        }
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(payload, indent=2, ensure_ascii=False)

        return _format_metadata_search_result(
            paged_hits,
            params.offset,
            params.limit,
            total,
            total_is_exact,
            params.search_mode.value,
            executed_subqueries,
            planned_subqueries,
        )

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_search_resources(params: SearchResourcesInput) -> str:
    """Searches GeoNode resources with filters.

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
