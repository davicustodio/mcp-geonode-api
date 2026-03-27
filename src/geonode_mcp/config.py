"""MCP server configuration via environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .compatibility import GeoNodeCompatibility, resolve_compatibility


@dataclass(frozen=True)
class Settings:
    geonode_url: str
    geonode_user: str
    geonode_password: str
    geonode_version: str
    api_version: str
    api_base: str
    verify_ssl: bool
    compatibility: GeoNodeCompatibility


def load_settings() -> Settings:
    geonode_url = os.environ.get("GEONODE_URL", "https://demo.geonode.org").rstrip("/")
    geonode_user = os.environ.get("GEONODE_USER", "admin")
    geonode_password = os.environ.get("GEONODE_PASSWORD", "")
    geonode_version = os.environ.get("GEONODE_VERSION", "5")
    api_version = os.environ.get("GEONODE_API_VERSION", "v2")
    api_base_path = os.environ.get("GEONODE_API_BASE_PATH")
    geonode_verify_ssl = os.environ.get("GEONODE_VERIFY_SSL", "true").strip().lower()

    compatibility = resolve_compatibility(
        geonode_version=geonode_version,
        api_version=api_version,
        api_base_path=api_base_path,
    )

    return Settings(
        geonode_url=geonode_url,
        geonode_user=geonode_user,
        geonode_password=geonode_password,
        geonode_version=compatibility.geonode_version,
        api_version=compatibility.api_version,
        api_base=f"{geonode_url}{compatibility.api_base_path}",
        verify_ssl=geonode_verify_ssl not in {"0", "false", "no", "off"},
        compatibility=compatibility,
    )


settings = load_settings()

GEONODE_URL = settings.geonode_url
GEONODE_USER = settings.geonode_user
GEONODE_PASSWORD = settings.geonode_password
GEONODE_VERSION = settings.geonode_version
GEONODE_API_VERSION = settings.api_version
API_BASE = settings.api_base
VERIFY_SSL = settings.verify_ssl
COMPATIBILITY = settings.compatibility

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
REQUEST_TIMEOUT = 30.0
