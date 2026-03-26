"""Catalog tools: categories, keywords, regions, and owners."""

from __future__ import annotations

import json

from ..client import api, handle_api_error
from ..models.common import ResponseFormat, build_pagination_params, format_pagination_footer
from ..models.users import ListCategoriesInput, ListKeywordsInput, ListOwnersInput, ListRegionsInput


async def geonode_list_categories(params: ListCategoriesInput) -> str:
    """Lists all available GeoNode categories (TopicCategory).

    Returns:
        List of categories with identifier, description, and resource count.
    """
    try:
        data = await api.get(api.route("categories"))
        items = data.get("TopicCategory", data.get("categories", []))
        total = len(items)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {"total": total, "categories": items}, indent=2, ensure_ascii=False,
            )

        if not items:
            return "No categories found."

        lines = [f"# Categories ({total})\n"]
        for c in items:
            lines.append(
                f"- **{c.get('gn_description', c.get('identifier', 'N/A'))}** "
                f"(`{c.get('identifier', '')}`) — {c.get('count', 0)} resources"
            )
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_list_keywords(params: ListKeywordsInput) -> str:
    """Lista keywords usadas nos resources do GeoNode.

    Returns:
        Paginated list of keywords with name and slug.
    """
    try:
        qp = build_pagination_params(params.limit, params.offset)
        if params.search:
            qp["search"] = params.search

        data = await api.get(api.route("keywords"), params=qp)
        items = data.get("keywords", data.get("HierarchicalKeyword", []))
        total = data.get("total", len(items))

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {"total": total, "count": len(items), "offset": params.offset,
                 "keywords": items}, indent=2, ensure_ascii=False,
            )

        if not items:
            return f"No keywords found. Total: {total}"

        lines = [f"# Keywords ({total})\n"]
        for k in items:
            lines.append(f"- **{k.get('name', 'N/A')}** (slug: `{k.get('slug', '')}`)")
        lines.append("")
        lines.append(format_pagination_footer(total, len(items), params.offset, params.limit))
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_list_regions(params: ListRegionsInput) -> str:
    """Lists geographic regions available in GeoNode.

    Returns:
        Paginated list of regions with code and name.
    """
    try:
        qp = build_pagination_params(params.limit, params.offset)
        if params.search:
            qp["search"] = params.search

        data = await api.get(api.route("regions"), params=qp)
        items = data.get("regions", [])
        total = data.get("total", len(items))

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {"total": total, "count": len(items), "offset": params.offset,
                 "regions": items}, indent=2, ensure_ascii=False,
            )

        if not items:
            return f"No regions found. Total: {total}"

        lines = [f"# Regions ({total})\n"]
        for r in items:
            lines.append(f"- **{r.get('name', 'N/A')}** (`{r.get('code', '')}`)")
        lines.append("")
        lines.append(format_pagination_footer(total, len(items), params.offset, params.limit))
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_list_owners(params: ListOwnersInput) -> str:
    """Lists GeoNode resource owners (users who have at least one resource).

    Returns:
        Paginated list of owners with name and username.
    """
    try:
        qp = build_pagination_params(params.limit, params.offset)
        if params.search:
            qp["search"] = params.search

        data = await api.get(api.route("owners"), params=qp)
        items = data.get("owners", [])
        total = data.get("total", len(items))

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {"total": total, "count": len(items), "offset": params.offset,
                 "owners": items}, indent=2, ensure_ascii=False,
            )

        if not items:
            return f"No owners found. Total: {total}"

        lines = [f"# Owners ({total})\n"]
        for o in items:
            name = f"{o.get('first_name', '')} {o.get('last_name', '')}".strip()
            lines.append(
                f"- **{name or 'Unnamed'}** (`{o.get('username', '')}`) — ID: {o.get('pk', 'N/A')}"
            )
        lines.append("")
        lines.append(format_pagination_footer(total, len(items), params.offset, params.limit))
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)
