from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError

from geonode_mcp.models.user_workflows import (
    AddUsersToGroupInput,
    BulkCreateUsersInput,
    CountUserOwnedResourcesInput,
    DeleteUsersSafelyInput,
    FindGroupUsersByResourceOwnershipInput,
    GeoNodeWorkflowUserInput,
)
from geonode_mcp.tools import user_workflows


def test_workflow_user_defaults_username_to_email() -> None:
    user = GeoNodeWorkflowUserInput(
        email="Ada.Lovelace@Example.org",
        first_name="Ada",
        last_name="Lovelace",
    )

    assert user.username_or_email == "Ada.Lovelace@Example.org"


def test_group_slug_rejects_path_separators() -> None:
    with pytest.raises(ValidationError):
        AddUsersToGroupInput(group_slug="../admin", user_ids=[1])

    with pytest.raises(ValidationError):
        FindGroupUsersByResourceOwnershipInput(group_slug="group/name")


def test_count_user_owned_resources_uses_owner_pk_filter(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        if route == "users/7":
            return {
                "user": {
                    "pk": 7,
                    "username": "ada@example.org",
                    "email": "ada@example.org",
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                }
            }
        assert params is not None
        calls.append((route, dict(params)))
        return {"total": 3}

    def fake_route(name: str, **kwargs) -> str:
        if name == "user_detail":
            return f"users/{kwargs['user_id']}"
        return name

    monkeypatch.setattr(user_workflows.api, "route", fake_route)
    monkeypatch.setattr(user_workflows.api, "get", fake_get)

    output = asyncio.run(
        user_workflows.geonode_count_user_owned_resources(
            CountUserOwnedResourcesInput(user_ids=[7])
        )
    )
    payload = json.loads(output)

    resource_calls = calls
    assert [call[0] for call in resource_calls] == ["datasets", "documents", "maps", "geoapps"]
    assert all(call[1]["filter{owner.pk}"] == 7 for call in resource_calls)
    assert all("owner" not in call[1] for call in resource_calls)
    assert all("owner__username" not in call[1] for call in resource_calls)
    assert payload["users"][0]["resources"]["total"] == 12


def test_count_user_owned_resources_fails_closed_without_total(monkeypatch) -> None:
    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        if route == "users/7":
            return {"user": {"pk": 7, "username": "ada@example.org", "email": "ada@example.org"}}
        return {}

    def fake_route(name: str, **kwargs) -> str:
        if name == "user_detail":
            return f"users/{kwargs['user_id']}"
        return name

    monkeypatch.setattr(user_workflows.api, "route", fake_route)
    monkeypatch.setattr(user_workflows.api, "get", fake_get)

    output = asyncio.run(
        user_workflows.geonode_count_user_owned_resources(
            CountUserOwnedResourcesInput(user_ids=[7])
        )
    )

    assert output.startswith("Error:")
    assert "did not include a total count" in output


def test_find_group_users_by_resource_ownership_splits_by_domain_and_counts(monkeypatch) -> None:
    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        if route == "groups":
            return {
                "total": 1,
                "groups": [{"pk": 60, "slug": "fapergs", "title": "fapergs"}],
            }
        if route == "users/1/groups":
            return {"groups": [{"pk": 60, "slug": "fapergs", "title": "fapergs"}]}
        if route == "users/2/groups":
            return {"groups": [{"pk": 60, "slug": "fapergs", "title": "fapergs"}]}
        if route == "users":
            return {
                "total": 3,
                "users": [
                    {"pk": 1, "username": "ada", "email": "ada@embrapa.br"},
                    {"pk": 2, "username": "grace", "email": "grace@embrapa.br"},
                    {"pk": 3, "username": "alan", "email": "alan@example.org"},
                ],
            }
        if route == "datasets" and params and params["filter{owner.pk}"] == 1:
            return {"total": 2}
        return {"total": 0}

    def fake_route(name: str, **kwargs) -> str:
        if name == "user_groups":
            return f"users/{kwargs['user_id']}/groups"
        return name

    monkeypatch.setattr(user_workflows.api, "route", fake_route)
    monkeypatch.setattr(user_workflows.api, "get", fake_get)

    output = asyncio.run(
        user_workflows.geonode_find_group_users_by_resource_ownership(
            FindGroupUsersByResourceOwnershipInput(
                group_slug="fapergs",
                email_domain="@embrapa.br",
            )
        )
    )
    payload = json.loads(output)

    assert payload["summary"] == {
        "group": "fapergs",
        "email_domain": "@embrapa.br",
        "total_users": 2,
        "with_resources": 1,
        "without_resources": 1,
    }
    assert payload["with_resources"][0]["email"] == "ada@embrapa.br"
    assert payload["without_resources"][0]["email"] == "grace@embrapa.br"


def test_bulk_create_users_requires_confirmation_for_password_and_redacts_it(monkeypatch) -> None:
    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        return {"total": 0, "users": []}

    async def fake_post(route: str, data: dict[str, object] | None = None) -> dict[str, object]:
        assert data is not None
        return {"user": {"pk": 10, **data}}

    async def fake_set_user_password(*, user_id: int, password: str) -> dict[str, object]:
        return {"user_id": user_id, "changed": True, "password": password}

    monkeypatch.setattr(user_workflows.api, "route", lambda name, **kwargs: {
        "users": "users",
    }[name])
    monkeypatch.setattr(user_workflows.api, "get", fake_get)
    monkeypatch.setattr(user_workflows.api, "post", fake_post)
    monkeypatch.setattr(user_workflows.api, "set_user_password", fake_set_user_password)

    blocked = asyncio.run(
        user_workflows.geonode_bulk_create_users(
            BulkCreateUsersInput(
                users=[GeoNodeWorkflowUserInput(email="ada@example.org")],
                password="secret-password",
            )
        )
    )
    assert blocked.startswith("Error:")

    output = asyncio.run(
        user_workflows.geonode_bulk_create_users(
            BulkCreateUsersInput(
                users=[GeoNodeWorkflowUserInput(email="ada@example.org")],
                password="secret-password",
                dry_run=False,
                confirm=True,
                expected_count=1,
            )
        )
    )

    assert "secret-password" not in output
    payload = json.loads(output)
    assert payload["password_updates"] == [{"user_id": 10, "changed": True}]


def test_add_users_to_group_uses_admin_membership_helper(monkeypatch) -> None:
    calls: list[tuple[str, str, list[int]]] = []
    added_user_ids: set[int] = set()

    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        if route == "groups":
            return {
                "total": 1,
                "groups": [{"pk": 60, "slug": "fapergs", "title": "fapergs"}],
            }
        if route == "users":
            return {
                "total": 1,
                "users": [{"pk": 10, "username": "ada", "email": "ada@example.org"}],
            }
        if route == "users/10/groups":
            if 10 in added_user_ids:
                return {"groups": [{"pk": 60, "slug": "fapergs", "title": "fapergs"}]}
            return {"groups": []}
        raise AssertionError(route)

    async def fake_add_group_members(*, group_slug: str, user_ids: list[int]) -> dict[str, object]:
        calls.append(("add_group_members", group_slug, user_ids))
        added_user_ids.update(user_ids)
        return {"added": user_ids}

    def fake_route(name: str, **kwargs) -> str:
        if name == "user_groups":
            return f"users/{kwargs['user_id']}/groups"
        return name

    monkeypatch.setattr(user_workflows.api, "route", fake_route)
    monkeypatch.setattr(user_workflows.api, "get", fake_get)
    monkeypatch.setattr(user_workflows.api, "add_group_members", fake_add_group_members)

    output = asyncio.run(
        user_workflows.geonode_add_users_to_group(
            AddUsersToGroupInput(group_slug="fapergs", emails=["ada@example.org"])
        )
    )
    payload = json.loads(output)

    assert calls == [("add_group_members", "fapergs", [10])]
    assert payload["added"] == [{"pk": 10, "username": "ada", "email": "ada@example.org"}]
    assert payload["failed"] == []


def test_add_users_to_group_reports_unconfirmed_membership(monkeypatch) -> None:
    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        if route == "groups":
            return {
                "total": 1,
                "groups": [{"pk": 60, "slug": "fapergs", "title": "fapergs"}],
            }
        if route == "users":
            return {
                "total": 1,
                "users": [{"pk": 10, "username": "ada", "email": "ada@example.org"}],
            }
        if route == "users/10/groups":
            return {"groups": []}
        raise AssertionError(route)

    async def fake_add_group_members(*, group_slug: str, user_ids: list[int]) -> dict[str, object]:
        return {"added": user_ids}

    def fake_route(name: str, **kwargs) -> str:
        if name == "user_groups":
            return f"users/{kwargs['user_id']}/groups"
        return name

    monkeypatch.setattr(user_workflows.api, "route", fake_route)
    monkeypatch.setattr(user_workflows.api, "get", fake_get)
    monkeypatch.setattr(user_workflows.api, "add_group_members", fake_add_group_members)

    output = asyncio.run(
        user_workflows.geonode_add_users_to_group(
            AddUsersToGroupInput(group_slug="fapergs", emails=["ada@example.org"])
        )
    )
    payload = json.loads(output)

    assert payload["added"] == []
    assert payload["failed"][0]["reason"] == "Membership was not confirmed after update."


def test_delete_users_safely_blocks_mismatched_expected_count(monkeypatch) -> None:
    deleted: list[str] = []

    async def fake_delete(route: str) -> dict[str, object]:
        deleted.append(route)
        return {}

    monkeypatch.setattr(user_workflows.api, "delete", fake_delete)

    output = asyncio.run(
        user_workflows.geonode_delete_users_safely(
            DeleteUsersSafelyInput(user_ids=[1, 2], dry_run=False, confirm=True, expected_count=1)
        )
    )

    assert output.startswith("Error:")
    assert deleted == []


def test_delete_users_safely_deletes_only_validated_users(monkeypatch) -> None:
    deleted: list[str] = []

    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        if route == "users/1":
            return {
                "user": {
                    "pk": 1,
                    "username": "ada",
                    "email": "ada@example.org",
                    "is_staff": False,
                    "is_superuser": False,
                }
            }
        if route == "users/2":
            return {
                "user": {
                    "pk": 2,
                    "username": "grace",
                    "email": "grace@example.org",
                    "is_staff": True,
                    "is_superuser": False,
                }
            }
        if route in {"datasets", "documents", "maps", "geoapps"}:
            return {"total": 0}
        raise AssertionError(route)

    async def fake_delete(route: str) -> dict[str, object]:
        deleted.append(route)
        return {}

    def fake_route(name: str, **kwargs) -> str:
        if name == "user_detail":
            return f"users/{kwargs['user_id']}"
        return name

    monkeypatch.setattr(user_workflows.api, "route", fake_route)
    monkeypatch.setattr(user_workflows.api, "get", fake_get)
    monkeypatch.setattr(user_workflows.api, "delete", fake_delete)

    output = asyncio.run(
        user_workflows.geonode_delete_users_safely(
            DeleteUsersSafelyInput(
                user_ids=[1, 2],
                dry_run=False,
                confirm=True,
                expected_count=2,
            )
        )
    )
    payload = json.loads(output)

    assert deleted == ["users/1"]
    assert payload["deleted"] == [{"pk": 1, "username": "ada", "email": "ada@example.org"}]
    assert payload["skipped"][0]["user"]["pk"] == 2
    assert payload["skipped"][0]["reason"] == (
        "User staff/superuser status is missing or privileged."
    )


def test_delete_users_safely_fails_closed_when_staff_fields_are_missing(monkeypatch) -> None:
    deleted: list[str] = []

    async def fake_get(route: str, params: dict[str, object] | None = None) -> dict[str, object]:
        if route == "users/1":
            return {"user": {"pk": 1, "username": "ada", "email": "ada@example.org"}}
        if route in {"datasets", "documents", "maps", "geoapps"}:
            return {"total": 0}
        raise AssertionError(route)

    async def fake_delete(route: str) -> dict[str, object]:
        deleted.append(route)
        return {}

    def fake_route(name: str, **kwargs) -> str:
        if name == "user_detail":
            return f"users/{kwargs['user_id']}"
        return name

    monkeypatch.setattr(user_workflows.api, "route", fake_route)
    monkeypatch.setattr(user_workflows.api, "get", fake_get)
    monkeypatch.setattr(user_workflows.api, "delete", fake_delete)

    output = asyncio.run(
        user_workflows.geonode_delete_users_safely(
            DeleteUsersSafelyInput(
                user_ids=[1],
                dry_run=False,
                confirm=True,
                expected_count=1,
            )
        )
    )
    payload = json.loads(output)

    assert deleted == []
    assert payload["skipped"][0]["reason"] == (
        "User staff/superuser status is missing or privileged."
    )
