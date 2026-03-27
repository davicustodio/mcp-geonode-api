"""Best-effort GeoNode compatibility discovery from a URL."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from . import config

GEONODE_VERSION_PATTERN = re.compile(
    r"geonode[^\d]{0,20}(?P<version>[45](?:\.\d+){0,2})",
    re.IGNORECASE,
)


def normalize_probe_target(url: str) -> tuple[str, list[str]]:
    """Extracts the instance base URL and candidate API base paths."""

    raw = url.strip().rstrip("/")
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("The URL must include a scheme and host, for example: https://example.com")

    path = parsed.path.rstrip("/")
    match = re.search(r"(?P<prefix>.*?)(?P<api>/api/v\d+)(?:/.*)?$", path)
    if match:
        root_path = match.group("prefix") or ""
        api_path = match.group("api")
        candidates = [api_path]
    else:
        root_path = path
        candidates = [f"{root_path}/api/v2" if root_path else "/api/v2"]

    base_url = urlunsplit((parsed.scheme, parsed.netloc, root_path or "", "", ""))
    return base_url.rstrip("/"), candidates


def extract_geonode_version(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        match = GEONODE_VERSION_PATTERN.search(text)
        if match:
            return match.group("version").split(".", 1)[0]
    return None


async def detect_geonode_instance(
    url: str,
    username: str | None = None,
    password: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Detects the compatible GeoNode instance version using heuristics."""

    base_url, api_candidates = normalize_probe_target(url)
    auth = _build_auth(username, password)
    request_timeout = timeout or config.REQUEST_TIMEOUT
    probes: list[dict[str, Any]] = []
    evidence: list[str] = []
    notes: list[str] = []

    async with httpx.AsyncClient(
        auth=auth,
        timeout=request_timeout,
        verify=config.VERIFY_SSL,
        follow_redirects=True,
    ) as client:
        root_probe = await _probe_text(client, f"{base_url}/")
        probes.append(root_probe)

        version_probe = await _probe_text(client, f"{base_url}/static/version.txt")
        probes.append(version_probe)

        detected_geonode_version = extract_geonode_version(
            root_probe.get("text"),
            version_probe.get("text"),
            str(root_probe.get("headers", {})),
            str(version_probe.get("headers", {})),
        )

        detected_api_version: str | None = None
        detected_api_path: str | None = None

        for api_path in api_candidates:
            resources_url = f"{base_url}{api_path}/resources/"
            resources_probe = await _probe_json(
                client,
                resources_url,
                params={"page": 1, "page_size": 1},
            )
            probes.append(resources_probe)

            if _looks_like_geonode_resources_response(resources_probe.get("json")):
                detected_api_path = api_path
                detected_api_version = api_path.rsplit("/", 1)[-1]
                evidence.append(
                    f"`GET {api_path}/resources/` returned a payload compatible with GeoNode."
                )
                break

        if detected_geonode_version:
            evidence.append(
                "GeoNode version detected from content/headers: "
                f"{detected_geonode_version}."
            )
        else:
            notes.append(
                "The exact GeoNode version could not be inferred with high "
                "confidence from the URL alone."
            )

        if detected_api_version is None:
            notes.append("Could not automatically confirm a supported API endpoint.")

    return {
        "input_url": url,
        "normalized_base_url": base_url,
        "detected_api_base_path": detected_api_path,
        "recommended_settings": {
            "GEONODE_URL": base_url,
            "GEONODE_VERSION": detected_geonode_version,
            "GEONODE_API_VERSION": detected_api_version,
        },
        "confidence": {
            "geonode_version": "medium" if detected_geonode_version else "low",
            "api_version": "high" if detected_api_version else "low",
        },
        "evidence": evidence,
        "notes": notes,
        "probes": probes,
    }


def _build_auth(username: str | None, password: str | None) -> tuple[str, str] | None:
    resolved_user = username or config.GEONODE_USER
    resolved_password = password if password is not None else config.GEONODE_PASSWORD

    if not resolved_password:
        return None
    return resolved_user, resolved_password


async def _probe_text(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    try:
        response = await client.get(url)
        return {
            "url": url,
            "status_code": response.status_code,
            "ok": response.is_success,
            "headers": dict(response.headers),
            "text": response.text[:1000],
        }
    except Exception as exc:
        return {"url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _probe_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, int] | None = None,
) -> dict[str, Any]:
    try:
        response = await client.get(url, params=params)
        payload: Any | None = None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        return {
            "url": url,
            "status_code": response.status_code,
            "ok": response.is_success,
            "json": payload,
            "text": None if payload is not None else response.text[:500],
        }
    except Exception as exc:
        return {"url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _looks_like_geonode_resources_response(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return "resources" in payload and any(key in payload for key in ("total", "page", "links"))
