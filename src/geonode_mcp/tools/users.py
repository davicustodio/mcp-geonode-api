"""Tools for users and groups."""

from __future__ import annotations

import json

from ..client import api, handle_api_error
from ..models.common import ResponseFormat, build_pagination_params, format_pagination_footer
from ..models.users import (
    GetGroupInput,
    GetUserGroupsInput,
    GetUserInput,
    ListGroupsInput,
    ListUsersInput,
    UpdateUserInput,
)


async def geonode_list_users(params: ListUsersInput) -> str:
    """Lists GeoNode users by name, username, or email.

    Returns:
        Paginated list of users with name, username, and email.
    """
    try:
        qp = build_pagination_params(params.limit, params.offset)
        if params.search:
            qp["search"] = params.search

        data = await api.get(api.route("users"), params=qp)
        items = data.get("users", [])
        total = data.get("total", 0)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {"total": total, "count": len(items), "offset": params.offset,
                 "users": items}, indent=2, ensure_ascii=False,
            )

        if not items:
            return f"No users found. Total: {total}"

        lines = [f"# Users ({total} found)\n"]
        for u in items:
            name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            lines.append(
                f"- **{name or 'Unnamed'}** | Username: `{u.get('username', '')}` "
                f"| ID: {u['pk']} | Email: {u.get('email', 'N/A')} "
                f"| Staff: {u.get('is_staff', False)} | Super: {u.get('is_superuser', False)}"
            )
        lines.append("")
        lines.append(format_pagination_footer(total, len(items), params.offset, params.limit))
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_get_user(params: GetUserInput) -> str:
    """Returns details for a specific user by ID.

    Returns:
        Full user data including permissions and avatar.
    """
    try:
        data = await api.get(api.route("user_detail", user_id=params.user_id))
        u = data.get("user", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"user": u}, indent=2, ensure_ascii=False)

        name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
        perms = ", ".join(u.get("perms", []))

        lines = [
            f"# {name or 'Unnamed'} (ID: {u.get('pk', params.user_id)})",
            "",
            f"**Username**: `{u.get('username', 'N/A')}`",
            f"**Email**: {u.get('email', 'N/A')}",
            (
                f"**Staff**: {u.get('is_staff', False)} | "
                f"**Superuser**: {u.get('is_superuser', False)}"
            ),
            f"**Permissions**: {perms or 'None'}",
            f"**Avatar**: {u.get('avatar', 'N/A')}",
        ]
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_get_user_groups(params: GetUserGroupsInput) -> str:
    """Returns a user's groups by ID or exact username.

    Returns:
        List of groups associated with the user, including IDs and internal names.
    """
    try:
        user = None
        user_id = params.user_id

        if user_id is None:
            if not params.username:
                return "Error: Provide `user_id` or `username`."
            lookup = await api.get(
                api.route("users"),
                params={"filter{username}": params.username, "page": 1, "page_size": 2},
            )
            matches = lookup.get("users", [])
            if not matches:
                return f"No user found with username `{params.username}`."
            user = matches[0]
            user_id = user.get("pk")

        data = await api.get(api.route("user_groups", user_id=user_id))
        groups = (
            data
            if isinstance(data, list)
            else data.get("groups", data.get("group_profiles", []))
        )

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {
                    "user": user or {"pk": user_id, "username": params.username},
                    "groups": groups,
                },
                indent=2,
                ensure_ascii=False,
            )

        username = (
            (user or {}).get("username")
            or params.username
            or f"id={user_id}"
        )
        if not groups:
            return f"The user `{username}` has no associated groups."

        lines = [f"# User groups for `{username}`", ""]
        for group in groups:
            inner_group = group.get("group", {})
            lines.append(f"- **{group.get('title', group.get('name', 'N/A'))}**")
            lines.append(f"  ID: {group.get('pk', 'N/A')}")
            lines.append(f"  Internal name: {inner_group.get('name', 'N/A')}")
            if group.get("description"):
                lines.append(f"  Description: {group['description']}")
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_update_user(params: UpdateUserInput) -> str:
    """Updates data for an existing user.

    Returns:
        Updated user data.
    """
    try:
        payload: dict = {}
        if params.first_name is not None:
            payload["first_name"] = params.first_name
        if params.last_name is not None:
            payload["last_name"] = params.last_name

        if not payload:
            return "Error: Nenhum campo para atualizar foi informado."

        data = await api.patch(api.route("user_detail", user_id=params.user_id), data=payload)
        u = data.get("user", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"user": u}, indent=2, ensure_ascii=False)

        return (
            f"User updated successfully!\n\n"
            f"- **ID**: {u.get('pk', params.user_id)}\n"
            f"- **Name**: {u.get('first_name', '')} {u.get('last_name', '')}\n"
        )

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_list_groups(params: ListGroupsInput) -> str:
    """Lists GeoNode groups.

    Returns:
        Paginated list of groups with name and member count.
    """
    try:
        qp = build_pagination_params(params.limit, params.offset)
        if params.search:
            qp["search"] = params.search

        data = await api.get(api.route("groups"), params=qp)
        items = data.get("groups", [])
        total = data.get("total", 0)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {"total": total, "count": len(items), "offset": params.offset,
                 "groups": items}, indent=2, ensure_ascii=False,
            )

        if not items:
            return f"No groups found. Total: {total}"

        lines = [f"# Groups ({total} found)\n"]
        for g in items:
            lines.append(f"- **{g.get('title', g.get('name', 'N/A'))}** (ID: {g.get('pk', 'N/A')})")
        lines.append("")
        lines.append(format_pagination_footer(total, len(items), params.offset, params.limit))
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)


async def geonode_get_group(params: GetGroupInput) -> str:
    """Returns details for a specific group by ID.

    Returns:
        Group data including name, description, and members.
    """
    try:
        data = await api.get(api.route("group_detail", group_id=params.group_id))
        g = data.get("group", data)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"group": g}, indent=2, ensure_ascii=False)

        lines = [
            f"# {g.get('title', g.get('name', 'N/A'))} (ID: {g.get('pk', params.group_id)})",
            "",
            f"**Name**: {g.get('name', 'N/A')}",
            f"**Description**: {g.get('description', 'N/A')}",
            f"**Email**: {g.get('email', 'N/A')}",
        ]
        return "\n".join(lines)

    except Exception as exc:
        return handle_api_error(exc)
