from __future__ import annotations

import asyncio

import httpx
import pytest

from geonode_mcp.client import GeoNodeClient, _ensure_login_success, _extract_csrf_token


def test_extract_csrf_token_reads_cookie_first() -> None:
    cookies = httpx.Cookies()
    cookies.set("csrftoken", "cookie-token")

    assert _extract_csrf_token("", cookies) == "cookie-token"


def test_extract_csrf_token_reads_hidden_input() -> None:
    html = '<input type="hidden" name="csrfmiddlewaretoken" value="form-token">'

    assert _extract_csrf_token(html, httpx.Cookies()) == "form-token"


def test_ensure_login_success_rejects_failed_ajax_response() -> None:
    response = httpx.Response(200, json={"success": False})

    with pytest.raises(RuntimeError):
        _ensure_login_success(response)


def test_set_user_password_rejects_non_redirect_form_response(monkeypatch) -> None:
    class FakeWebClient:
        cookies = httpx.Cookies()

        async def get(self, path: str) -> httpx.Response:
            request = httpx.Request("GET", f"https://example.test{path}")
            return httpx.Response(
                200,
                request=request,
                text='<input type="hidden" name="csrfmiddlewaretoken" value="form-token">',
            )

        async def post(self, url: str, **kwargs: object) -> httpx.Response:
            request = httpx.Request("POST", url)
            return httpx.Response(200, request=request, text="password form error")

        async def aclose(self) -> None:
            return None

    client = GeoNodeClient()

    async def fake_start_web_session() -> FakeWebClient:
        return FakeWebClient()

    monkeypatch.setattr(client, "_start_web_session", fake_start_web_session)

    with pytest.raises(RuntimeError):
        asyncio.run(client.set_user_password(user_id=7, password="secret-password"))
