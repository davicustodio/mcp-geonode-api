"""High-level workflow tools for GeoNode users and groups."""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..client import api, handle_api_error
from ..models.user_workflows import (
    AddUsersToGroupInput,
    BulkCreateUsersAndAddToGroupInput,
    BulkCreateUsersInput,
    CountUserOwnedResourcesInput,
    CreateGroupInput,
    DeleteUsersSafelyInput,
    FindGroupUsersByResourceOwnershipInput,
    GeoNodeWorkflowUserInput,
)

_RESOURCE_ROUTES = {
    "datasets": "datasets",
    "documents": "documents",
    "maps": "maps",
    "dashboards": "geoapps",
}


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _collection(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key, [])
    return value if isinstance(value, list) else []


def _user_summary(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "pk": user.get("pk"),
        "username": user.get("username"),
        "email": user.get("email"),
    }


def _group_summary(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "pk": group.get("pk"),
        "slug": group.get("slug") or group.get("name"),
        "title": group.get("title") or group.get("name"),
    }


def _group_matches(group: dict[str, Any], *, group_id: int | None, group_slug: str | None) -> bool:
    inner = group.get("group", {})
    if group_id is not None and group.get("pk") == group_id:
        return True
    if group_slug:
        values = {
            group.get("slug"),
            group.get("name"),
            group.get("title"),
            inner.get("name") if isinstance(inner, dict) else None,
        }
        return group_slug in values
    return False


def _password_update_allowed(
    *,
    target_count: int,
    password: str | None,
    dry_run: bool,
    confirm: bool,
    expected_count: int | None,
) -> str | None:
    if not password:
        return None
    if dry_run:
        return "Password updates require dry_run=false."
    if not confirm:
        return "Password updates require confirm=true."
    if expected_count != target_count:
        return f"Password updates require expected_count={target_count}."
    return None


async def _find_group_by_slug(slug: str) -> dict[str, Any] | None:
    data = await api.get(
        api.route("groups"),
        params={"filter{slug}": slug, "page": 1, "page_size": 10},
    )
    for group in _collection(data, "groups"):
        if _group_matches(group, group_id=None, group_slug=slug):
            return group

    data = await api.get(api.route("groups"), params={"search": slug, "page": 1, "page_size": 10})
    for group in _collection(data, "groups"):
        if _group_matches(group, group_id=None, group_slug=slug):
            return group
    return None


async def _resolve_group(
    *, group_id: int | None = None, group_slug: str | None = None
) -> dict[str, Any] | None:
    if group_id is not None:
        data = await api.get(api.route("group_detail", group_id=group_id))
        return data.get("group", data)
    if group_slug:
        return await _find_group_by_slug(group_slug)
    return None


async def _resolve_user_by_id(user_id: int) -> dict[str, Any] | None:
    try:
        data = await api.get(api.route("user_detail", user_id=user_id))
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise
    return data.get("user", data)


async def _resolve_user_by_filter(filter_name: str, value: str) -> dict[str, Any] | None:
    data = await api.get(
        api.route("users"),
        params={f"filter{{{filter_name}}}": value, "page": 1, "page_size": 10},
    )
    for user in _collection(data, "users"):
        if user.get(filter_name) == value:
            return user
    return None


async def _resolve_users(
    *,
    user_ids: list[int] | None = None,
    emails: list[str] | None = None,
    usernames: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    users: list[dict[str, Any]] = []
    not_found: list[dict[str, Any]] = []
    seen: set[int] = set()

    for user_id in user_ids or []:
        user = await _resolve_user_by_id(user_id)
        if user and user.get("pk") not in seen:
            seen.add(user["pk"])
            users.append(user)
        elif not user:
            not_found.append({"type": "user_id", "value": user_id})

    for email in emails or []:
        user = await _resolve_user_by_filter("email", email)
        if user and user.get("pk") not in seen:
            seen.add(user["pk"])
            users.append(user)
        elif not user:
            not_found.append({"type": "email", "value": email})

    for username in usernames or []:
        user = await _resolve_user_by_filter("username", username)
        if user and user.get("pk") not in seen:
            seen.add(user["pk"])
            users.append(user)
        elif not user:
            not_found.append({"type": "username", "value": username})

    return users, not_found


async def _user_groups(user_id: int) -> list[dict[str, Any]]:
    data = await api.get(api.route("user_groups", user_id=user_id))
    if isinstance(data, list):
        return data
    groups = data.get("groups", data.get("group_profiles", []))
    return groups if isinstance(groups, list) else []


async def _user_is_group_member(
    user_id: int,
    *,
    group_id: int | None,
    group_slug: str | None,
) -> bool:
    groups = await _user_groups(user_id)
    return any(_group_matches(group, group_id=group_id, group_slug=group_slug) for group in groups)


async def _all_group_users(
    *,
    group_id: int | None,
    group_slug: str | None,
) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = []
    page = 1
    page_size = 100

    while True:
        data = await api.get(api.route("users"), params={"page": page, "page_size": page_size})
        batch = _collection(data, "users")
        for user in batch:
            user_id = user.get("pk")
            if user_id is not None and await _user_is_group_member(
                user_id,
                group_id=group_id,
                group_slug=group_slug,
            ):
                users.append(user)

        total = int(data.get("total", len(batch)))
        if page * page_size >= total or not batch:
            break
        page += 1

    return users


async def _owned_resource_counts(user: dict[str, Any]) -> dict[str, int]:
    user_id = int(user["pk"])
    counts: dict[str, int] = {}
    total = 0
    for label, route_name in _RESOURCE_ROUTES.items():
        data = await api.get(
            api.route(route_name),
            params={"page": 1, "page_size": 1, "filter{owner.pk}": user_id},
        )
        count = int(data.get("total", 0))
        counts[label] = count
        total += count
    counts["total"] = total
    return counts


async def _get_or_create_group(params: CreateGroupInput) -> tuple[dict[str, Any], bool]:
    existing = await _find_group_by_slug(params.slug)
    if existing:
        return existing, False

    payload = {
        "slug": params.slug,
        "title": params.title or params.slug,
        "description": params.description or "",
        "access": params.access.value,
        "categories": params.categories,
        "group": 1,
    }
    data = await api.post(api.route("groups"), data=payload)
    return data.get("group", data), True


async def _get_or_create_user(params: GeoNodeWorkflowUserInput) -> tuple[dict[str, Any], bool]:
    existing = await _resolve_user_by_filter("username", params.username_or_email)
    if existing:
        return existing, False

    email_match = await _resolve_user_by_filter("email", params.email)
    if email_match:
        return email_match, False

    payload = {
        "username": params.username_or_email,
        "email": params.email,
        "first_name": params.first_name or "",
        "last_name": params.last_name or "",
    }
    data = await api.post(api.route("users"), data=payload)
    return data.get("user", data), True


async def geonode_create_group(params: CreateGroupInput) -> str:
    """Creates or reuses a GeoNode group by slug."""
    try:
        group, created = await _get_or_create_group(params)
        return _json({"created": created, "group": _group_summary(group)})
    except Exception as exc:
        return handle_api_error(exc)


async def geonode_bulk_create_users(params: BulkCreateUsersInput) -> str:
    """Creates or reuses users, optionally setting one password for all of them."""
    try:
        guard = _password_update_allowed(
            target_count=len(params.users),
            password=params.password,
            dry_run=params.dry_run,
            confirm=params.confirm,
            expected_count=params.expected_count,
        )
        if guard:
            return f"Error: {guard}"

        created: list[dict[str, Any]] = []
        reused: list[dict[str, Any]] = []
        password_updates: list[dict[str, Any]] = []
        for item in params.users:
            user, was_created = await _get_or_create_user(item)
            summary = _user_summary(user)
            if was_created:
                created.append(summary)
            else:
                reused.append(summary)

            if params.password:
                await api.set_user_password(user_id=int(user["pk"]), password=params.password)
                password_updates.append({"user_id": user["pk"], "changed": True})

        return _json({
            "created": created,
            "reused": reused,
            "password_updates": password_updates,
            "summary": {
                "created": len(created),
                "reused": len(reused),
                "password_updates": len(password_updates),
            },
        })
    except Exception as exc:
        return handle_api_error(exc)


async def geonode_add_users_to_group(params: AddUsersToGroupInput) -> str:
    """Adds existing users to a GeoNode group through the Django membership flow."""
    try:
        group = await _resolve_group(group_id=params.group_id, group_slug=params.group_slug)
        if not group:
            return "Error: Group not found."

        group_slug = group.get("slug") or params.group_slug or group.get("name")
        group_id = group.get("pk") or params.group_id
        if not group_slug:
            return "Error: Could not resolve group slug for membership update."

        users, not_found = await _resolve_users(
            user_ids=params.user_ids,
            emails=params.emails,
            usernames=params.usernames,
        )
        already_member: list[dict[str, Any]] = []
        to_add: list[dict[str, Any]] = []
        for user in users:
            if await _user_is_group_member(
                int(user["pk"]),
                group_id=group_id,
                group_slug=str(group_slug),
            ):
                already_member.append(_user_summary(user))
            else:
                to_add.append(user)

        if to_add:
            await api.add_group_members(
                group_slug=str(group_slug),
                user_ids=[int(user["pk"]) for user in to_add],
            )

        added = [_user_summary(user) for user in to_add]
        return _json({
            "group": _group_summary(group),
            "added": added,
            "already_member": already_member,
            "not_found": not_found,
            "failed": [],
            "summary": {
                "added": len(added),
                "already_member": len(already_member),
                "not_found": len(not_found),
                "failed": 0,
            },
        })
    except Exception as exc:
        return handle_api_error(exc)


async def geonode_bulk_create_users_and_add_to_group(
    params: BulkCreateUsersAndAddToGroupInput,
) -> str:
    """Creates or reuses users, creates or reuses a group, and adds users to that group."""
    try:
        guard = _password_update_allowed(
            target_count=len(params.users),
            password=params.password,
            dry_run=params.dry_run,
            confirm=params.confirm,
            expected_count=params.expected_count,
        )
        if guard:
            return f"Error: {guard}"

        group, group_created = await _get_or_create_group(params.group)
        created: list[dict[str, Any]] = []
        reused: list[dict[str, Any]] = []
        users: list[dict[str, Any]] = []
        password_updates: list[dict[str, Any]] = []
        for item in params.users:
            user, was_created = await _get_or_create_user(item)
            users.append(user)
            if was_created:
                created.append(_user_summary(user))
            else:
                reused.append(_user_summary(user))
            if params.password:
                await api.set_user_password(user_id=int(user["pk"]), password=params.password)
                password_updates.append({"user_id": user["pk"], "changed": True})

        group_slug = group.get("slug") or group.get("name") or params.group.slug
        already_member: list[dict[str, Any]] = []
        to_add: list[dict[str, Any]] = []
        for user in users:
            if await _user_is_group_member(
                int(user["pk"]),
                group_id=group.get("pk"),
                group_slug=str(group_slug),
            ):
                already_member.append(_user_summary(user))
            else:
                to_add.append(user)

        if to_add:
            await api.add_group_members(
                group_slug=str(group_slug),
                user_ids=[int(user["pk"]) for user in to_add],
            )

        added = [_user_summary(user) for user in to_add]
        return _json({
            "group": {"created": group_created, **_group_summary(group)},
            "created": created,
            "reused": reused,
            "added": added,
            "already_member": already_member,
            "password_updates": password_updates,
            "summary": {
                "created": len(created),
                "reused": len(reused),
                "added": len(added),
                "already_member": len(already_member),
                "password_updates": len(password_updates),
            },
        })
    except Exception as exc:
        return handle_api_error(exc)


async def geonode_count_user_owned_resources(params: CountUserOwnedResourcesInput) -> str:
    """Counts owned datasets, documents, maps, and dashboards for selected users."""
    try:
        users, not_found = await _resolve_users(
            user_ids=params.user_ids,
            emails=params.emails,
            usernames=params.usernames,
        )
        results: list[dict[str, Any]] = []
        totals = {"datasets": 0, "documents": 0, "maps": 0, "dashboards": 0, "total": 0}
        for user in users:
            counts = await _owned_resource_counts(user)
            for key in totals:
                totals[key] += counts[key]
            results.append({"user": _user_summary(user), "resources": counts})

        return _json({"users": results, "not_found": not_found, "totals": totals})
    except Exception as exc:
        return handle_api_error(exc)


async def geonode_find_group_users_by_resource_ownership(
    params: FindGroupUsersByResourceOwnershipInput,
) -> str:
    """Splits group users into users with and without owned resources."""
    try:
        group = await _resolve_group(group_id=params.group_id, group_slug=params.group_slug)
        if not group:
            return "Error: Group not found."

        group_slug = group.get("slug") or params.group_slug or group.get("name")
        users = await _all_group_users(group_id=group.get("pk"), group_slug=str(group_slug))
        if params.email_domain:
            domain = params.email_domain.casefold()
            users = [
                user
                for user in users
                if str(user.get("email", "")).casefold().endswith(domain)
            ]

        with_resources: list[dict[str, Any]] = []
        without_resources: list[dict[str, Any]] = []
        for user in users:
            counts = await _owned_resource_counts(user)
            entry = {**_user_summary(user), "resources": counts}
            if counts["total"] > 0:
                with_resources.append(entry)
            else:
                without_resources.append(entry)

        return _json({
            "summary": {
                "group": group_slug,
                "email_domain": params.email_domain,
                "total_users": len(users),
                "with_resources": len(with_resources),
                "without_resources": len(without_resources),
            },
            "with_resources": with_resources,
            "without_resources": without_resources,
        })
    except Exception as exc:
        return handle_api_error(exc)


async def geonode_delete_users_safely(params: DeleteUsersSafelyInput) -> str:
    """Deletes only explicitly listed users after safety validation."""
    try:
        requested_count = len(params.user_ids) + len(params.emails) + len(params.usernames)
        if not params.dry_run:
            if not params.confirm:
                return "Error: User deletion requires confirm=true."
            if params.expected_count != requested_count:
                return f"Error: User deletion requires expected_count={requested_count}."

        users, not_found = await _resolve_users(
            user_ids=params.user_ids,
            emails=params.emails,
            usernames=params.usernames,
        )
        if not params.dry_run and params.expected_count != len(users):
            return (
                "Error: Resolved user count changed; "
                f"expected {params.expected_count}, got {len(users)}."
            )

        deletable: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for user in users:
            reason = None
            if params.require_not_staff and (
                bool(user.get("is_staff")) or bool(user.get("is_superuser"))
            ):
                reason = "User is staff or superuser."

            if (
                reason is None
                and (params.required_group_id is not None or params.required_group_slug)
                and not await _user_is_group_member(
                    int(user["pk"]),
                    group_id=params.required_group_id,
                    group_slug=params.required_group_slug,
                )
            ):
                reason = "User is not a member of the required group."

            counts: dict[str, int] | None = None
            if reason is None and params.require_zero_owned_resources:
                counts = await _owned_resource_counts(user)
                if counts["total"] > 0:
                    reason = "User owns GeoNode resources."

            if reason:
                skipped.append({
                    "user": _user_summary(user),
                    "reason": reason,
                    "resources": counts,
                })
            else:
                deletable.append(user)

        deleted: list[dict[str, Any]] = []
        if not params.dry_run:
            for user in deletable:
                await api.delete(api.route("user_detail", user_id=user["pk"]))
                deleted.append(_user_summary(user))

        return _json({
            "dry_run": params.dry_run,
            "deleted": deleted,
            "would_delete": (
                [] if not params.dry_run else [_user_summary(user) for user in deletable]
            ),
            "skipped": skipped,
            "not_found": not_found,
            "summary": {
                "requested": requested_count,
                "resolved": len(users),
                "deleted": len(deleted),
                "would_delete": 0 if not params.dry_run else len(deletable),
                "skipped": len(skipped),
                "not_found": len(not_found),
            },
        })
    except Exception as exc:
        return handle_api_error(exc)
