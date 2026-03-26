"""Models for dataset tools."""

from __future__ import annotations

from typing import Optional

from pydantic import ConfigDict, Field

from .common import PaginationInput


class ListDatesetsInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: Optional[str] = Field(default=None, description="Text search in the title/abstract")
    owner: Optional[str] = Field(default=None, description="Owner username")
    title_contains: Optional[str] = Field(default=None, description="Filter by text in the title")
    category: Optional[str] = Field(default=None, description="Category identifier")
    subtype: Optional[str] = Field(
        default=None, description="Subtype: 'vector' or 'raster'"
    )
    keyword: Optional[str] = Field(default=None, description="Keyword name")


class GetDatesetInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    dataset_id: int = Field(..., description="Dateset ID (pk)", gt=0)


class CreateDatesetInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., description="Dateset title", min_length=1, max_length=255)
    abstract: Optional[str] = Field(default=None, description="Summary/description")
    category: Optional[str] = Field(default=None, description="Category identifier")
    regions: Optional[list[str]] = Field(default=None, description="Region codes")
    keywords: Optional[list[str]] = Field(default=None, description="List of keywords")
    is_published: bool = Field(default=True, description="Publish immediately")
    is_approved: bool = Field(default=True, description="Approve immediately")


class UpdateDatesetInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    dataset_id: int = Field(..., description="Dateset ID (pk)", gt=0)
    title: Optional[str] = Field(default=None, description="New title", max_length=255)
    abstract: Optional[str] = Field(default=None, description="New summary")
    category: Optional[str] = Field(default=None, description="New category")
    is_published: Optional[bool] = Field(default=None, description="Change published status")
    is_approved: Optional[bool] = Field(default=None, description="Change approval status")
    keywords: Optional[list[str]] = Field(default=None, description="New keywords")


class DeleteDatesetInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    dataset_id: int = Field(..., description="Dateset ID (pk) a excluir", gt=0)
