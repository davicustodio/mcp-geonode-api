"""CRUD tools for datasets."""

from __future__ import annotations

import json

from ..client import api, handle_api_error
from ..models.common import ResponseFormat, build_pagination_params, format_pagination_footer
from ..models.datasets import (
    CreateDatesetInput,
    DeleteDatesetInput,
    GetDatesetInput,
    ListDatesetsInput,
    UpdateDatesetInput,
)


def _format_dataset(d: dict) -> str:
    owner = d.get("owner", {})
    owner_name = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
    keywords = ", ".join(k.get("name", "") for k in d.get("keywords", []))
    return "\n".join([
        f"## {d.get('title', 'Untitled')} (ID: {d['pk']})",
        f"- **Subtype**: {d.get('subtype', 'N/A')} | **Name**: {d.get('name', 'N/A')}",
        f"- **Owner**: {owner_name} ({owner.get('username', '')})",
        f"- **Category**: {(d.get('category') or {}).get('identifier', 'N/A')}",
        f"- **Date**: {d.get('date', 'N/A')}",
        f"- **Published**: {d.get('is_published')} | **Approved**: {d.get('is_approved')}",
        f"- **Keywords**: {keywords or 'None'}",
        f"- **Download**: {d.get('download_url', 'N/A')}",
        "",
    ])


async def geonode_list_datasets(params: ListDatesetsInput) -> str:
    """Lists GeoNode datasets (geospatial layers) with filters.

    Returns:
        Paginated list of datasets with primary metadata.
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
        if params.subtype:
            qp["filter{subtype}"] = params.subtype
        if params.keyword:
            qp["filter{keywords.name}"] = params.keyword

        data = await api.get("/datasets/", params=qp)
        items = data.get("datasets", [])
        total = data.get("total", 0)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {"total": total, "count": len(items), "offset": params.offset,
                 "datasets": items}, indent=2, ensure_ascii=False,
            )

        if not items:
            return f"No datasets found. Total: {total}"

        lines = [f"# Datesets ({total} found)\n"]
        for d in items:
            lines.append(_format_dataset(d))
        lines.append(format_pagination_footer(total, len(items), params.offset, params.limit))
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_get_dataset(params: GetDatesetInput) -> str:
    """Returns full details for a specific dataset by ID.

    Returns:
        Full metadata including abstract, extent, styles, and links.
    """
    try:
        data = await api.get(f"/datasets/{params.dataset_id}/")
        d = data.get("dataset", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"dataset": d}, indent=2, ensure_ascii=False)

        owner = d.get("owner", {})
        owner_name = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
        keywords = ", ".join(k.get("name", "") for k in d.get("keywords", []))
        regions = ", ".join(r.get("name", "") for r in d.get("regions", []))
        extent = d.get("extent", {}).get("coords", [])

        lines = [
            f"# {d.get('title', 'Untitled')} (ID: {d.get('pk', params.dataset_id)})",
            "",
            f"**Technical name**: {d.get('alternate', d.get('name', 'N/A'))}",
            f"**Subtype**: {d.get('subtype', 'N/A')} | **SRS**: {d.get('srid', 'N/A')}",
            f"**Owner**: {owner_name} ({owner.get('username', '')})",
            f"**Category**: {(d.get('category') or {}).get('gn_description', 'N/A')}",
            f"**Date**: {d.get('date', 'N/A')} ({d.get('date_type', '')})",
            f"**Published**: {d.get('is_published')} | **Approved**: {d.get('is_approved')}",
            "",
            "## Summary",
            d.get("raw_abstract", "No summary"),
            "",
            f"**Keywords**: {keywords or 'None'}",
            f"**Regions**: {regions or 'None'}",
            f"**Extent**: {extent}",
            "",
            f"**Download**: {d.get('download_url', 'N/A')}",
            f"**Embed**: {d.get('embed_url', 'N/A')}",
            f"**Detail**: {d.get('detail_url', 'N/A')}",
        ]
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_create_dataset(params: CreateDatesetInput) -> str:
    """Creates metadata for a new dataset in GeoNode.

    For actual geospatial data uploads (Shapefile, GeoPackage, etc.),
    use the web upload endpoint.

    Returns:
        Created dataset data.
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

        data = await api.post("/datasets/", data=payload)
        ds = data.get("dataset", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"dataset": ds}, indent=2, ensure_ascii=False)

        return (
            f"Dateset criado com sucesso!\n\n"
            f"- **ID**: {ds.get('pk', 'N/A')}\n"
            f"- **Title**: {ds.get('title', params.title)}\n"
            f"- **Link**: {ds.get('detail_url', 'N/A')}\n"
        )

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_update_dataset(params: UpdateDatesetInput) -> str:
    """Updates metadata for an existing dataset.

    Returns:
        Updated dataset data.
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
            return "Error: Nenhum campo para atualizar foi informado."

        data = await api.patch(f"/datasets/{params.dataset_id}/", data=payload)
        ds = data.get("dataset", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"dataset": ds}, indent=2, ensure_ascii=False)

        return (
            f"Dateset atualizado com sucesso!\n\n"
            f"- **ID**: {ds.get('pk', params.dataset_id)}\n"
            f"- **Title**: {ds.get('title', 'N/A')}\n"
        )

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_delete_dataset(params: DeleteDatesetInput) -> str:
    """Permanently deletes a dataset from GeoNode.

    WARNING: This action is irreversible and also removes the data from GeoServer.

    Returns:
        Deletion confirmation.
    """
    try:
        await api.delete(f"/datasets/{params.dataset_id}/")
        return f"Dateset ID {params.dataset_id} deleted successfully."
    except Exception as exc:
        return handle_api_error(exc)
