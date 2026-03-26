"""Tools for generic resource search."""

from __future__ import annotations

import json

from ..client import api, handle_api_error
from ..models.common import ResponseFormat, build_pagination_params, format_pagination_footer
from ..models.resources import GetResourceInput, SearchResourcesInput


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

        data = await api.get("/resources/", params=qp)
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
            lines.append(f"- **Published**: {r.get('is_published')} | Approved: {r.get('is_approved')}")
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
        data = await api.get(f"/resources/{params.resource_id}/")

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
