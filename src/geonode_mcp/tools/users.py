"""Tools for users and groups."""

from __future__ import annotations

import json

from ..client import api, handle_api_error
from ..models.common import ResponseFormat, build_pagination_params, format_pagination_footer
from ..models.users import (
    GetGroupInput,
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

        data = await api.get("/users/", params=qp)
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
        data = await api.get(f"/users/{params.user_id}/")
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
            f"**Staff**: {u.get('is_staff', False)} | **Superuser**: {u.get('is_superuser', False)}",
            f"**Permissions**: {perms or 'None'}",
            f"**Avatar**: {u.get('avatar', 'N/A')}",
        ]
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

        data = await api.patch(f"/users/{params.user_id}/", data=payload)
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

        data = await api.get("/groups/", params=qp)
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
        data = await api.get(f"/groups/{params.group_id}/")
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
