"""MCP server entrypoint for the GeoNode API."""
# mypy: disable-error-code=arg-type

from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import api
from .tools.categories import (
    geonode_list_categories,
    geonode_list_keywords,
    geonode_list_owners,
    geonode_list_regions,
)
from .tools.datasets import (
    geonode_create_dataset,
    geonode_delete_dataset,
    geonode_get_dataset,
    geonode_list_datasets,
    geonode_update_dataset,
)
from .tools.documents import (
    geonode_create_document,
    geonode_delete_document,
    geonode_get_document,
    geonode_list_documents,
    geonode_update_document,
)
from .tools.maps import (
    geonode_create_map,
    geonode_delete_map,
    geonode_get_map,
    geonode_list_maps,
    geonode_update_map,
)
from .tools.resources import (
    geonode_bootstrap_mcp_config,
    geonode_detect_instance,
    geonode_generate_mcp_config,
    geonode_get_resource,
    geonode_search_resources,
    geonode_verify_mcp_config,
    geonode_write_mcp_config,
)
from .tools.users import (
    geonode_get_group,
    geonode_get_user,
    geonode_get_user_groups,
    geonode_list_groups,
    geonode_list_users,
    geonode_update_user,
)


@asynccontextmanager
async def lifespan(server: FastMCP):
    await api.start()
    try:
        yield {}
    finally:
        await api.stop()


mcp = FastMCP("geonode_mcp", lifespan=lifespan)

# ── Resources ────────────────────────────────────────────────────────────────

mcp.tool(
    name="geonode_detect_instance",
    annotations={
        "title": "Detect GeoNode Instance Compatibility",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_detect_instance)

mcp.tool(
    name="geonode_bootstrap_mcp_config",
    annotations={
        "title": "Full MCP Configuration Bootstrap",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_bootstrap_mcp_config)

mcp.tool(
    name="geonode_generate_mcp_config",
    annotations={
        "title": "Generate MCP Configuration for Client",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_generate_mcp_config)

mcp.tool(
    name="geonode_write_mcp_config",
    annotations={
        "title": "Write MCP Configuration to File",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_write_mcp_config)

mcp.tool(
    name="geonode_verify_mcp_config",
    annotations={
        "title": "Verify MCP Configuration File",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_verify_mcp_config)

mcp.tool(
    name="geonode_search_resources",
    annotations={
        "title": "Search GeoNode Resources",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_search_resources)

mcp.tool(
    name="geonode_get_resource",
    annotations={
        "title": "Resource Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_get_resource)

# ── Documents ────────────────────────────────────────────────────────────────

mcp.tool(
    name="geonode_list_documents",
    annotations={
        "title": "List Documents",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_list_documents)

mcp.tool(
    name="geonode_get_document",
    annotations={
        "title": "Document Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_get_document)

mcp.tool(
    name="geonode_create_document",
    annotations={
        "title": "Create Document",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)(geonode_create_document)

mcp.tool(
    name="geonode_update_document",
    annotations={
        "title": "Update Document",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_update_document)

mcp.tool(
    name="geonode_delete_document",
    annotations={
        "title": "Delete Document",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)(geonode_delete_document)

# ── Datesets ─────────────────────────────────────────────────────────────────

mcp.tool(
    name="geonode_list_datasets",
    annotations={
        "title": "List Datesets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_list_datasets)

mcp.tool(
    name="geonode_get_dataset",
    annotations={
        "title": "Dateset Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_get_dataset)

mcp.tool(
    name="geonode_create_dataset",
    annotations={
        "title": "Create Dateset",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)(geonode_create_dataset)

mcp.tool(
    name="geonode_update_dataset",
    annotations={
        "title": "Update Dateset",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_update_dataset)

mcp.tool(
    name="geonode_delete_dataset",
    annotations={
        "title": "Delete Dateset",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)(geonode_delete_dataset)

# ── Maps ─────────────────────────────────────────────────────────────────────

mcp.tool(
    name="geonode_list_maps",
    annotations={
        "title": "List Maps",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_list_maps)

mcp.tool(
    name="geonode_get_map",
    annotations={
        "title": "Map Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_get_map)

mcp.tool(
    name="geonode_create_map",
    annotations={
        "title": "Create Map",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)(geonode_create_map)

mcp.tool(
    name="geonode_update_map",
    annotations={
        "title": "Update Map",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_update_map)

mcp.tool(
    name="geonode_delete_map",
    annotations={
        "title": "Delete Map",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)(geonode_delete_map)

# ── Users & Groups ───────────────────────────────────────────────────────────

mcp.tool(
    name="geonode_list_users",
    annotations={
        "title": "List Users",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_list_users)

mcp.tool(
    name="geonode_get_user",
    annotations={
        "title": "User Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_get_user)

mcp.tool(
    name="geonode_get_user_groups",
    annotations={
        "title": "List User Groups",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_get_user_groups)

mcp.tool(
    name="geonode_update_user",
    annotations={
        "title": "Update User",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_update_user)

mcp.tool(
    name="geonode_list_groups",
    annotations={
        "title": "List Groups",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_list_groups)

mcp.tool(
    name="geonode_get_group",
    annotations={
        "title": "Group Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_get_group)

# ── Catalog ─────────────────────────────────────────────────────────────────

mcp.tool(
    name="geonode_list_categories",
    annotations={
        "title": "List Categories",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_list_categories)

mcp.tool(
    name="geonode_list_keywords",
    annotations={
        "title": "List Keywords",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_list_keywords)

mcp.tool(
    name="geonode_list_regions",
    annotations={
        "title": "List Regions",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_list_regions)

mcp.tool(
    name="geonode_list_owners",
    annotations={
        "title": "List Owners",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)(geonode_list_owners)


if __name__ == "__main__":
    mcp.run()
