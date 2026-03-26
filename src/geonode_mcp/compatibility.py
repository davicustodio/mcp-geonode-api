"""Compatibility layer between GeoNode and REST API versions."""

from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_GEONODE_VERSIONS = {"4", "5"}
SUPPORTED_API_VERSIONS = {"v2"}


@dataclass(frozen=True)
class GeoNodeCompatibility:
    """Defines base path, routes, and capabilities for each supported combination."""

    geonode_version: str
    api_version: str
    api_base_path: str
    routes: dict[str, str]

    def route(self, name: str, **params: object) -> str:
        try:
            template = self.routes[name]
        except KeyError as exc:
            raise KeyError(f"Unknown MCP route: {name}") from exc
        return template.format(**params)


def _build_v2_routes() -> dict[str, str]:
    return {
        "resources": "/resources/",
        "resource_detail": "/resources/{resource_id}/",
        "datasets": "/datasets/",
        "dataset_detail": "/datasets/{dataset_id}/",
        "documents": "/documents/",
        "document_detail": "/documents/{document_id}/",
        "maps": "/maps/",
        "map_detail": "/maps/{map_id}/",
        "users": "/users/",
        "user_detail": "/users/{user_id}/",
        "groups": "/groups/",
        "group_detail": "/groups/{group_id}/",
        "categories": "/categories/",
        "keywords": "/keywords/",
        "regions": "/regions/",
        "owners": "/owners/",
    }


def resolve_compatibility(
    geonode_version: str,
    api_version: str | None = None,
    api_base_path: str | None = None,
) -> GeoNodeCompatibility:
    """Resolves the compatibility matrix supported by the MCP.

    GeoNode 4.x and 5.x still document the main REST API at ``/api/v2``.
    The MCP exposes the GeoNode version and API version as configuration values to
    support future variations without spreading conditionals across the tools.
    """

    normalized_geonode = normalize_geonode_version(geonode_version)
    normalized_api = normalize_api_version(api_version or "v2")

    if normalized_geonode not in SUPPORTED_GEONODE_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_GEONODE_VERSIONS))
        raise ValueError(
            f"Unsupported GeoNode version: {geonode_version!r}. Use one of: {supported}."
        )

    if normalized_api not in SUPPORTED_API_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_API_VERSIONS))
        raise ValueError(
            f"Unsupported API version for GeoNode {normalized_geonode}: "
            f"{api_version!r}. Use one of: {supported}."
        )

    base_path = (api_base_path or f"/api/{normalized_api}").rstrip("/")
    return GeoNodeCompatibility(
        geonode_version=normalized_geonode,
        api_version=normalized_api,
        api_base_path=base_path,
        routes=_build_v2_routes(),
    )


def normalize_geonode_version(version: str) -> str:
    value = version.strip().lower()
    if value.startswith("v"):
        value = value[1:]
    return value.split(".", 1)[0]


def normalize_api_version(version: str) -> str:
    value = version.strip().lower()
    if not value.startswith("v"):
        value = f"v{value}"
    return value
