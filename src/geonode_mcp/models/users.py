"""Models for user and group tools."""

from __future__ import annotations

from typing import Optional

from pydantic import ConfigDict, Field

from .common import PaginationInput


class ListUsersInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: Optional[str] = Field(default=None, description="Search by name, username, or email")


class GetUserInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: int = Field(..., description="User ID (pk)", gt=0)


class GetUserGroupsInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: Optional[int] = Field(default=None, description="User ID (pk)", gt=0)
    username: Optional[str] = Field(
        default=None,
        description="Exact user username when the ID is not known",
    )


class UpdateUserInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: int = Field(..., description="User ID (pk)", gt=0)
    first_name: Optional[str] = Field(default=None, description="New first name")
    last_name: Optional[str] = Field(default=None, description="New last name")


class ListGroupsInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: Optional[str] = Field(default=None, description="Search by group name")


class GetGroupInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    group_id: int = Field(..., description="Group ID (pk)", gt=0)


class ListCategoriesInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)


class ListKeywordsInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: Optional[str] = Field(default=None, description="Search by keyword name")


class ListRegionsInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: Optional[str] = Field(default=None, description="Search by region name or code")


class ListOwnersInput(PaginationInput):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: Optional[str] = Field(default=None, description="Search by owner name")
