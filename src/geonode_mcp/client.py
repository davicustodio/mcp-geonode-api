"""Shared async HTTP client for the GeoNode API."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from . import config


class GeoNodeClient:
    """httpx wrapper with Basic authentication and error handling."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=config.API_BASE,
            auth=(config.GEONODE_USER, config.GEONODE_PASSWORD),
            timeout=config.REQUEST_TIMEOUT,
            verify=config.VERIFY_SSL,
        )

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client not initialized. Call start() first.")
        return self._client

    def route(self, name: str, **params: object) -> str:
        return config.COMPATIBILITY.route(name, **params)

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = await self.http.get(f"/{endpoint.lstrip('/')}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def post(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if files:
            kwargs["files"] = files
            if data:
                kwargs["data"] = data
        elif data:
            kwargs["json"] = data
        resp = await self.http.post(f"/{endpoint.lstrip('/')}", **kwargs)
        resp.raise_for_status()
        if resp.status_code == 204:
            return {}
        return resp.json()

    async def patch(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        resp = await self.http.patch(f"/{endpoint.lstrip('/')}", json=data)
        resp.raise_for_status()
        return resp.json()

    async def put(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        resp = await self.http.put(f"/{endpoint.lstrip('/')}", json=data)
        resp.raise_for_status()
        return resp.json()

    async def delete(self, endpoint: str) -> dict[str, Any]:
        resp = await self.http.delete(f"/{endpoint.lstrip('/')}")
        resp.raise_for_status()
        if resp.status_code == 204:
            return {}
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError):
            return {}

    async def _start_web_session(self) -> httpx.AsyncClient:
        client = httpx.AsyncClient(
            base_url=config.GEONODE_URL,
            timeout=config.REQUEST_TIMEOUT,
            verify=config.VERIFY_SSL,
            follow_redirects=True,
        )
        try:
            login_page = await client.get("/account/login/")
            login_page.raise_for_status()
            csrf_token = _extract_csrf_token(login_page.text, client.cookies)
            payload = {
                "username": config.GEONODE_USER,
                "password": config.GEONODE_PASSWORD,
                "csrfmiddlewaretoken": csrf_token,
                "next": "/",
            }
            response = await client.post(
                "/account/ajax_login",
                data=payload,
                headers={
                    "Referer": str(login_page.url),
                    "X-CSRFToken": csrf_token,
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            response.raise_for_status()
        except Exception:
            await client.aclose()
            raise
        return client

    async def add_group_members(self, *, group_slug: str, user_ids: list[int]) -> dict[str, Any]:
        if not user_ids:
            return {"added": []}

        client = await self._start_web_session()
        try:
            page = await client.get(f"/groups/group/{group_slug}/members/")
            page.raise_for_status()
            csrf_token = _extract_csrf_token(page.text, client.cookies)
            form_data = {
                "user_identifiers": [str(user_id) for user_id in user_ids],
                "csrfmiddlewaretoken": csrf_token,
            }
            response = await client.post(
                f"/groups/group/{group_slug}/members_add/",
                data=form_data,
                headers={"Referer": str(page.url), "X-CSRFToken": csrf_token},
            )
            response.raise_for_status()
        finally:
            await client.aclose()
        return {"added": user_ids}

    async def set_user_password(self, *, user_id: int, password: str) -> dict[str, Any]:
        client = await self._start_web_session()
        try:
            page = await client.get(f"/admin/people/profile/{user_id}/password/")
            page.raise_for_status()
            csrf_token = _extract_csrf_token(page.text, client.cookies)
            response = await client.post(
                str(page.url),
                data={
                    "csrfmiddlewaretoken": csrf_token,
                    "password1": password,
                    "password2": password,
                },
                headers={"Referer": str(page.url), "X-CSRFToken": csrf_token},
                follow_redirects=False,
            )
            if response.status_code not in {200, 302, 303}:
                response.raise_for_status()
        finally:
            await client.aclose()
        return {"user_id": user_id, "changed": True}


def _extract_csrf_token(html: str, cookies: httpx.Cookies) -> str:
    cookie_token = cookies.get("csrftoken")
    if cookie_token:
        return cookie_token

    match = re.search(r'name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)', html)
    if not match:
        match = re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']csrfmiddlewaretoken["\']', html)
    if not match:
        raise RuntimeError("Could not find CSRF token in GeoNode login/admin page.")
    return match.group(1)


def handle_api_error(exc: Exception) -> str:
    """Formats HTTP errors in a readable way."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        msgs = {
            400: "Invalid request. Check the parameters.",
            401: "Authentication failed. Check the credentials.",
            403: "Permission denied for this resource.",
            404: "Resource not found. Check the ID.",
            409: "Conflict. The resource may already exist.",
            429: "Rate limit exceeded. Wait and try again.",
            500: "GeoNode internal server error.",
        }
        detail = msgs.get(code, f"HTTP error {code}.")
        try:
            body = exc.response.json()
            if "message" in body:
                detail += f" Detail: {body['message']}"
            elif "detail" in body:
                detail += f" Detail: {body['detail']}"
        except (ValueError, KeyError):
            pass
        return f"Error: {detail}"
    if isinstance(exc, httpx.TimeoutException):
        return "Error: Request timeout. Try again."
    return f"Error: {type(exc).__name__} - {exc}"


# Global instance
api = GeoNodeClient()
