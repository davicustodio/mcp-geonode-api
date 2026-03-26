"""Models for resource tools."""

from __future__ import annotations

from typing import Optional

from pydantic import ConfigDict, Field

from .common import PaginationInput


class SearchResourcesInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: Optional[str] = Field(default=None, description="Free-text search query")
    resource_type: Optional[str] = Field(
        default=None,
        description="Type: 'dataset', 'document', 'map', 'geoapp'",
    )
    owner: Optional[str] = Field(default=None, description="Owner username")
    category: Optional[str] = Field(
        default=None, description="Category identifier (ex: 'biota', 'environment')"
    )
    keyword: Optional[str] = Field(default=None, description="Keyword name")
    region: Optional[str] = Field(default=None, description="Region code (e.g. 'BRA')")
    is_published: Optional[bool] = Field(default=None, description="Filter by published status")
    is_approved: Optional[bool] = Field(default=None, description="Filter by approved status")
    featured: Optional[bool] = Field(default=None, description="Filter by featured status")


class GetResourceInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    resource_id: int = Field(..., description="Resource ID (pk)", gt=0)
