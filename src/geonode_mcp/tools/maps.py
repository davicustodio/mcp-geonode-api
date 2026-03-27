"""CRUD tools for maps."""

from __future__ import annotations

import json

from ..client import api, handle_api_error
from ..models.common import ResponseFormat, build_pagination_params, format_pagination_footer
from ..models.maps import (
    CreateMapInput,
    DeleteMapInput,
    GetMapInput,
    ListMapsInput,
    UpdateMapInput,
)


def _format_map(m: dict) -> str:
    owner = m.get("owner", {})
    owner_name = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
    keywords = ", ".join(k.get("name", "") for k in m.get("keywords", []))
    layers = len(m.get("maplayers", []))
    return "\n".join([
        f"## {m.get('title', 'Untitled')} (ID: {m['pk']})",
        f"- **Owner**: {owner_name} ({owner.get('username', '')})",
        f"- **Category**: {(m.get('category') or {}).get('identifier', 'N/A')}",
        f"- **Layers**: {layers}",
        f"- **Date**: {m.get('date', 'N/A')}",
        f"- **Published**: {m.get('is_published')} | **Approved**: {m.get('is_approved')}",
        f"- **Keywords**: {keywords or 'None'}",
        "",
    ])


async def geonode_list_maps(params: ListMapsInput) -> str:
    """Lists GeoNode maps with filters for owner, title, category, and keyword.

    Returns:
        Paginated list of maps with primary metadata.
    """
    try:
        qp = build_pagination_params(params.limit, params.offset)
        if params.search:
            qp["search"] = params.search
        if params.owner:
            qp["filter{owner.username}"] = params.owner
        if params.title_contains:
            qp["filter{title.icontains}"] = params.title_contains
        if params.category:
            qp["filter{category.identifier}"] = params.category
        if params.keyword:
            qp["filter{keywords.name}"] = params.keyword

        data = await api.get(api.route("maps"), params=qp)
        items = data.get("maps", [])
        total = data.get("total", 0)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {"total": total, "count": len(items), "offset": params.offset,
                 "maps": items}, indent=2, ensure_ascii=False,
            )

        if not items:
            return f"No maps found. Total: {total}"

        lines = [f"# Maps ({total} found)\n"]
        for m in items:
            lines.append(_format_map(m))
        lines.append(format_pagination_footer(total, len(items), params.offset, params.limit))
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_get_map(params: GetMapInput) -> str:
    """Returns full details for a specific map by ID.

    Returns:
        Full metadata including abstract, layers (maplayers), and links.
    """
    try:
        data = await api.get(api.route("map_detail", map_id=params.map_id))
        m = data.get("map", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"map": m}, indent=2, ensure_ascii=False)

        owner = m.get("owner", {})
        owner_name = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
        keywords = ", ".join(k.get("name", "") for k in m.get("keywords", []))
        regions = ", ".join(r.get("name", "") for r in m.get("regions", []))

        lines = [
            f"# {m.get('title', 'Untitled')} (ID: {m.get('pk', params.map_id)})",
            "",
            f"**Owner**: {owner_name} ({owner.get('username', '')})",
            f"**Category**: {(m.get('category') or {}).get('gn_description', 'N/A')}",
            f"**Date**: {m.get('date', 'N/A')} ({m.get('date_type', '')})",
            f"**Published**: {m.get('is_published')} | **Approved**: {m.get('is_approved')}",
            "",
            "## Summary",
            m.get("raw_abstract", "No summary"),
            "",
            f"**Keywords**: {keywords or 'None'}",
            f"**Regions**: {regions or 'None'}",
        ]

        maplayers = m.get("maplayers", [])
        if maplayers:
            lines.append(f"\n## Layers ({len(maplayers)})")
            for layer in maplayers:
                lines.append(f"- {layer.get('name', 'N/A')} (visible: {layer.get('visibility')})")

        lines.extend([
            "",
            f"**Embed**: {m.get('embed_url', 'N/A')}",
            f"**Detail**: {m.get('detail_url', 'N/A')}",
        ])
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_create_map(params: CreateMapInput) -> str:
    """Creates a new map in GeoNode.

    Returns:
        Created map data.
    """
    try:
        payload: dict = {
            "title": params.title,
            "is_published": params.is_published,
            "is_approved": params.is_approved,
        }
        if params.abstract:
            payload["abstract"] = params.abstract
        if params.category:
            payload["category"] = {"identifier": params.category}
        if params.regions:
            payload["regions"] = [{"code": c} for c in params.regions]
        if params.keywords:
            payload["keywords"] = [{"name": k} for k in params.keywords]

        data = await api.post(api.route("maps"), data=payload)
        m = data.get("map", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"map": m}, indent=2, ensure_ascii=False)

        return (
            f"Map created successfully!\n\n"
            f"- **ID**: {m.get('pk', 'N/A')}\n"
            f"- **Title**: {m.get('title', params.title)}\n"
            f"- **Link**: {m.get('detail_url', 'N/A')}\n"
        )

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_update_map(params: UpdateMapInput) -> str:
    """Updates metadata for an existing map.

    Returns:
        Updated map data.
    """
    try:
        payload: dict = {}
        if params.title is not None:
            payload["title"] = params.title
        if params.abstract is not None:
            payload["abstract"] = params.abstract
        if params.category is not None:
            payload["category"] = {"identifier": params.category}
        if params.is_published is not None:
            payload["is_published"] = params.is_published
        if params.is_approved is not None:
            payload["is_approved"] = params.is_approved
        if params.keywords is not None:
            payload["keywords"] = [{"name": k} for k in params.keywords]

        if not payload:
            return "Error: No fields to update were provided."

        data = await api.patch(api.route("map_detail", map_id=params.map_id), data=payload)
        m = data.get("map", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"map": m}, indent=2, ensure_ascii=False)

        return (
            f"Map updated successfully!\n\n"
            f"- **ID**: {m.get('pk', params.map_id)}\n"
            f"- **Title**: {m.get('title', 'N/A')}\n"
        )

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_delete_map(params: DeleteMapInput) -> str:
    """Permanently deletes a map from GeoNode.

    WARNING: This action is irreversible.

    Returns:
        Deletion confirmation.
    """
    try:
        await api.delete(api.route("map_detail", map_id=params.map_id))
        return f"Map ID {params.map_id} deleted successfully."
    except Exception as exc:
        return handle_api_error(exc)
