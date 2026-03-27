"""CRUD tools for documents."""

from __future__ import annotations

import json

from ..client import api, handle_api_error
from ..models.common import ResponseFormat, build_pagination_params, format_pagination_footer
from ..models.documents import (
    CreateDocumentInput,
    DeleteDocumentInput,
    GetDocumentInput,
    ListDocumentsInput,
    UpdateDocumentInput,
)


def _format_document(d: dict) -> str:
    owner = d.get("owner", {})
    owner_name = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
    keywords = ", ".join(k.get("name", "") for k in d.get("keywords", []))
    return "\n".join([
        f"## {d.get('title', 'Untitled')} (ID: {d['pk']})",
        f"- **Subtype**: {d.get('subtype', 'N/A')} | **Extension**: {d.get('extension', 'N/A')}",
        f"- **Owner**: {owner_name} ({owner.get('username', '')})",
        f"- **Category**: {(d.get('category') or {}).get('identifier', 'N/A')}",
        f"- **Date**: {d.get('date', 'N/A')}",
        f"- **Published**: {d.get('is_published')} | **Approved**: {d.get('is_approved')}",
        f"- **Keywords**: {keywords or 'None'}",
        f"- **Download**: {d.get('download_url', 'N/A')}",
        "",
    ])


async def geonode_list_documents(params: ListDocumentsInput) -> str:
    """Lists GeoNode documents with filters for owner, title, category, and subtype.

    Returns:
        Paginated list of documents with primary metadata.
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

        data = await api.get(api.route("documents"), params=qp)
        docs = data.get("documents", [])
        total = data.get("total", 0)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {"total": total, "count": len(docs), "offset": params.offset,
                 "documents": docs}, indent=2, ensure_ascii=False,
            )

        if not docs:
            return f"No documents found. Total: {total}"

        lines = [f"# Documents ({total} found)\n"]
        for d in docs:
            lines.append(_format_document(d))
        lines.append(format_pagination_footer(total, len(docs), params.offset, params.limit))
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_get_document(params: GetDocumentInput) -> str:
    """Returns full details for a specific document by ID.

    Returns:
        Full document metadata including abstract, links, and permissions.
    """
    try:
        data = await api.get(api.route("document_detail", document_id=params.document_id))
        d = data.get("document", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"document": d}, indent=2, ensure_ascii=False)

        owner = d.get("owner", {})
        owner_name = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip()
        keywords = ", ".join(k.get("name", "") for k in d.get("keywords", []))
        regions = ", ".join(r.get("name", "") for r in d.get("regions", []))

        lines = [
            f"# {d.get('title', 'Untitled')} (ID: {d.get('pk', params.document_id)})",
            "",
            f"**Subtype**: {d.get('subtype', 'N/A')} | **MIME**: {d.get('mime_type', 'N/A')}",
            f"**Owner**: {owner_name} ({owner.get('username', '')})",
            f"**Group**: {(d.get('group') or {}).get('name', 'N/A')}",
            f"**Category**: {(d.get('category') or {}).get('gn_description', 'N/A')}",
            f"**Date**: {d.get('date', 'N/A')} ({d.get('date_type', '')})",
            f"**Published**: {d.get('is_published')} | **Approved**: {d.get('is_approved')}",
            "",
            "## Summary",
            d.get("raw_abstract", "No summary"),
            "",
            f"**Keywords**: {keywords or 'None'}",
            f"**Regions**: {regions or 'None'}",
            "",
            f"**Download**: {d.get('download_url', 'N/A')}",
            f"**Link**: {d.get('href', d.get('detail_url', 'N/A'))}",
            f"**Thumbnail**: {d.get('thumbnail_url', 'N/A')}",
        ]
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_create_document(params: CreateDocumentInput) -> str:
    """Creates a new document in GeoNode via an external link.

    For file uploads, use the web endpoint directly.

    Returns:
        Created document data.
    """
    try:
        payload: dict = {
            "title": params.title,
            "is_published": params.is_published,
            "is_approved": params.is_approved,
        }
        if params.abstract:
            payload["abstract"] = params.abstract
        if params.doc_url:
            payload["doc_url"] = params.doc_url
        if params.category:
            payload["category"] = {"identifier": params.category}
        if params.regions:
            payload["regions"] = [{"code": c} for c in params.regions]
        if params.keywords:
            payload["keywords"] = [{"name": k} for k in params.keywords]

        data = await api.post(api.route("documents"), data=payload)
        doc = data.get("document", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"document": doc}, indent=2, ensure_ascii=False)

        return (
            f"Document created successfully!\n\n"
            f"- **ID**: {doc.get('pk', 'N/A')}\n"
            f"- **Title**: {doc.get('title', params.title)}\n"
            f"- **Link**: {doc.get('detail_url', 'N/A')}\n"
        )

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_update_document(params: UpdateDocumentInput) -> str:
    """Updates metadata for an existing document.

    Returns:
        Updated document data.
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

        data = await api.patch(
            api.route("document_detail", document_id=params.document_id),
            data=payload,
        )
        doc = data.get("document", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"document": doc}, indent=2, ensure_ascii=False)

        return (
            f"Document updated successfully!\n\n"
            f"- **ID**: {doc.get('pk', params.document_id)}\n"
            f"- **Title**: {doc.get('title', 'N/A')}\n"
        )

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_delete_document(params: DeleteDocumentInput) -> str:
    """Permanently deletes a document from GeoNode.

    WARNING: This action is irreversible.

    Returns:
        Deletion confirmation.
    """
    try:
        await api.delete(api.route("document_detail", document_id=params.document_id))
        return f"Document ID {params.document_id} deleted successfully."
    except Exception as exc:
        return handle_api_error(exc)
