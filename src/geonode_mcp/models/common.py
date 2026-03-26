"""Pydantic models shared across all tools."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class PaginationInput(BaseModel):
    """Reusable pagination parameters."""

    model_config = ConfigDict(str_strip_whitespace=True)

    limit: int = Field(default=20, description="Maximum results (1-100)", ge=1, le=100)
    offset: int = Field(default=0, description="Skip the first N results", ge=0)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' (readable) or 'json' (structured)",
    )


def build_pagination_params(limit: int, offset: int) -> dict[str, object]:
    """Converts limit/offset into GeoNode page/page_size parameters."""
    page_size = min(limit, 100)
    page = (offset // page_size) + 1
    return {"page_size": page_size, "page": page}


def format_pagination_footer(total: int, count: int, offset: int, limit: int) -> str:
    has_more = total > offset + count
    return (
        f"\n---\nTotal: {total} | Shown: {count} | Offset: {offset}"
        + (f" | Next offset: {offset + count}" if has_more else "")
    )
