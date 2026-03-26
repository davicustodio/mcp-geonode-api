"""MCP server configuration via environment variables."""

import os


GEONODE_URL = os.environ.get("GEONODE_URL", "https://geoinfo.dados.embrapa.br")
GEONODE_USER = os.environ.get("GEONODE_USER", "admin")
GEONODE_PASSWORD = os.environ.get("GEONODE_PASSWORD", "")
API_BASE = f"{GEONODE_URL.rstrip('/')}/api/v2"

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
REQUEST_TIMEOUT = 30.0
