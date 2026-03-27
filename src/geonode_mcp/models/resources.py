"""Models for resource tools."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import PaginationInput, ResponseFormat


class SearchResourcesInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: Optional[str] = Field(default=None, description="Free-text search query")
    resource_type: Optional[str] = Field(
        default=None,
        description="Type: 'dataset', 'document', 'map', 'geoapp'",
    )
    owner: Optional[str] = Field(default=None, description="Owner username")
    category: Optional[str] = Field(
        default=None, description="Category identifier (e.g. 'biota', 'environment')"
    )
    keyword: Optional[str] = Field(default=None, description="Keyword name")
    region: Optional[str] = Field(default=None, description="Region code (e.g. 'BRA')")
    is_published: Optional[bool] = Field(default=None, description="Filter by published status")
    is_approved: Optional[bool] = Field(default=None, description="Filter by approved status")
    featured: Optional[bool] = Field(default=None, description="Filter by featured status")


class MetadataSearchResourceType(str, Enum):
    DATASET = "dataset"
    DOCUMENT = "document"
    MAP = "map"
    GEOAPP = "geoapp"


class MetadataSearchField(str, Enum):
    TITLE = "title"
    ABSTRACT = "abstract"
    KEYWORDS = "keywords"
    EXTRA_METADATA = "extra_metadata"
    ANY_METADATA = "any_metadata"


class MetadataSearchMode(str, Enum):
    FAST = "fast"
    EXHAUSTIVE = "exhaustive"


class SearchMetadataTextInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(..., description="Text to search in metadata fields", min_length=1)
    resource_types: Optional[list[MetadataSearchResourceType]] = Field(
        default=None,
        description="Resource types to search. Empty means dataset, document, and map.",
    )
    search_in: list[MetadataSearchField] = Field(
        default_factory=lambda: [MetadataSearchField.ANY_METADATA],
        description=(
            "Metadata fields to search. Use 'any_metadata' to search title, abstract, "
            "keywords, and extra metadata."
        ),
    )
    search_mode: MetadataSearchMode = Field(
        default=MetadataSearchMode.FAST,
        description=(
            "Search execution mode. 'fast' stops after higher-priority fields if enough "
            "results were found for the requested page. 'exhaustive' executes all field plans."
        ),
    )


class GetResourceInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    resource_id: int = Field(..., description="Resource ID (pk)", gt=0)


class DetectGeoNodeInstanceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(..., description="Base URL of the GeoNode instance or an API endpoint")
    username: Optional[str] = Field(
        default=None,
        description="Optional username for Basic authentication during detection",
    )
    password: Optional[str] = Field(
        default=None,
        description="Optional password for Basic authentication during detection",
    )
    timeout: Optional[float] = Field(
        default=None,
        description="Optional timeout in seconds for HTTP probes",
        gt=0,
        le=120,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'json' for automation or 'markdown' for reading",
    )


class MCPClientTarget(str, Enum):
    CODEX = "codex"
    CURSOR = "cursor"
    OPENCODE = "opencode"
    CLAUDE_CODE = "claude_code"


class GenerateMCPConfigInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    client: MCPClientTarget = Field(..., description="Target MCP client")
    url: str = Field(..., description="Base URL of the GeoNode instance or an API endpoint")
    username: Optional[str] = Field(
        default=None,
        description="Basic authentication username and default value for GEONODE_USER",
    )
    password: Optional[str] = Field(
        default=None,
        description="Basic authentication password and default value for GEONODE_PASSWORD",
    )
    geonode_version: Optional[str] = Field(
        default=None,
        description="Overrides the GeoNode version if you already know the correct value",
    )
    api_version: Optional[str] = Field(
        default=None,
        description="Overrides the API version if you already know the correct value",
    )
    server_name: str = Field(default="geonode", description="MCP server name in the client")
    python_command: str = Field(
        default="/path/to/mcp-geonode-api/.venv/bin/python",
        description="Python executable that will start `python -m geonode_mcp`",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for copy-paste or 'json' for automation",
    )


class WriteMCPConfigInput(GenerateMCPConfigInput):
    config_path: str = Field(
        ...,
        description="Path of the MCP configuration file to create or update",
    )
    create_parent_dirs: bool = Field(
        default=True,
        description="Create parent directories automatically when needed",
    )


class VerifyMCPConfigInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    client: MCPClientTarget = Field(..., description="Target MCP client")
    config_path: str = Field(..., description="MCP configuration file to validate")
    server_name: str = Field(default="geonode", description="Expected MCP server name")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'json' for automation or 'markdown' for reading",
    )


class BootstrapMCPConfigInput(WriteMCPConfigInput):
    verify_after_write: bool = Field(
        default=True,
        description="Runs automatic file verification after writing",
    )
