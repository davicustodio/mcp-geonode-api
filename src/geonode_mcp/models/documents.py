"""Models for document tools."""

from __future__ import annotations

from typing import Optional

from pydantic import ConfigDict, Field

from .common import PaginationInput


class ListDocumentsInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: Optional[str] = Field(default=None, description="Text search in the title/abstract")
    owner: Optional[str] = Field(default=None, description="Owner username")
    title_contains: Optional[str] = Field(default=None, description="Filter by text in the title")
    category: Optional[str] = Field(default=None, description="Category identifier")
    subtype: Optional[str] = Field(
        default=None, description="Document subtype (e.g. 'image', 'document')"
    )


class GetDocumentInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    document_id: int = Field(..., description="Document ID (pk)", gt=0)


class CreateDocumentInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., description="Document title", min_length=1, max_length=255)
    abstract: Optional[str] = Field(default=None, description="Summary/description do documento")
    doc_url: Optional[str] = Field(default=None, description="External document URL")
    category: Optional[str] = Field(default=None, description="Category identifier")
    regions: Optional[list[str]] = Field(default=None, description="Region codes (ex: ['BRA'])")
    keywords: Optional[list[str]] = Field(default=None, description="List of keywords")
    is_published: bool = Field(default=True, description="Publish immediately")
    is_approved: bool = Field(default=True, description="Approve immediately")


class UpdateDocumentInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    document_id: int = Field(..., description="Document ID (pk)", gt=0)
    title: Optional[str] = Field(default=None, description="New title", max_length=255)
    abstract: Optional[str] = Field(default=None, description="New summary")
    category: Optional[str] = Field(default=None, description="New category")
    is_published: Optional[bool] = Field(default=None, description="Change published status")
    is_approved: Optional[bool] = Field(default=None, description="Change approval status")
    keywords: Optional[list[str]] = Field(default=None, description="New keywords")


class DeleteDocumentInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    document_id: int = Field(..., description="Document ID (pk) a excluir", gt=0)
