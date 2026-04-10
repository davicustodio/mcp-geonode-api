"""Models for GeoNode user and group workflow tools."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PositiveUserId = Annotated[int, Field(gt=0)]


class GroupAccess(str, Enum):
    PUBLIC = "public"
    PUBLIC_INVITE = "public-invite"
    PRIVATE = "private"


class GeoNodeWorkflowUserInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(..., description="User email address")
    username: str | None = Field(
        default=None,
        description="GeoNode username. Defaults to the email address.",
    )
    first_name: str | None = Field(default=None, description="User first name")
    last_name: str | None = Field(default=None, description="User last name")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("email must contain '@'")
        return value

    @property
    def username_or_email(self) -> str:
        return self.username or self.email


def _validate_slug(value: str | None) -> str | None:
    if value is None:
        return None
    if "/" in value or "\\" in value:
        raise ValueError("slug must not contain path separators")
    return value


class CreateGroupInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    slug: str = Field(..., description="Group slug", min_length=1)
    title: str | None = Field(default=None, description="Group title. Defaults to slug.")
    description: str | None = Field(default=None, description="Group description")
    access: GroupAccess = Field(
        default=GroupAccess.PUBLIC_INVITE,
        description="Group access policy.",
    )
    categories: list[int] = Field(default_factory=list, description="GeoNode category IDs")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        return _validate_slug(value) or value


class BulkCreateUsersInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    users: list[GeoNodeWorkflowUserInput] = Field(..., min_length=1)
    password: str | None = Field(
        default=None,
        description="Optional password to set for every target user.",
    )
    dry_run: bool = Field(
        default=True,
        description="Password updates are simulated unless this is false.",
    )
    confirm: bool = Field(
        default=False,
        description="Set true to confirm password updates.",
    )
    expected_count: int | None = Field(
        default=None,
        description="Required number of target users for password updates.",
        ge=0,
    )


class AddUsersToGroupInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    group_id: int | None = Field(default=None, description="Group ID (pk)", gt=0)
    group_slug: str | None = Field(default=None, description="Group slug")
    user_ids: list[PositiveUserId] = Field(
        default_factory=list,
        description="User IDs",
        min_length=0,
    )
    emails: list[str] = Field(default_factory=list, description="User emails", min_length=0)
    usernames: list[str] = Field(default_factory=list, description="Usernames", min_length=0)

    @model_validator(mode="after")
    def validate_targets(self) -> "AddUsersToGroupInput":
        if self.group_id is None and not self.group_slug:
            raise ValueError("Provide group_id or group_slug.")
        if not self.user_ids and not self.emails and not self.usernames:
            raise ValueError("Provide at least one user identifier.")
        return self

    @field_validator("group_slug")
    @classmethod
    def validate_group_slug(cls, value: str | None) -> str | None:
        return _validate_slug(value)


class BulkCreateUsersAndAddToGroupInput(BulkCreateUsersInput):
    group: CreateGroupInput


class CountUserOwnedResourcesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_ids: list[PositiveUserId] = Field(
        default_factory=list,
        description="User IDs",
        min_length=0,
    )
    emails: list[str] = Field(default_factory=list, description="User emails", min_length=0)
    usernames: list[str] = Field(default_factory=list, description="Usernames", min_length=0)

    @model_validator(mode="after")
    def validate_user_identifiers(self) -> "CountUserOwnedResourcesInput":
        if not self.user_ids and not self.emails and not self.usernames:
            raise ValueError("Provide at least one user identifier.")
        return self


class FindGroupUsersByResourceOwnershipInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    group_id: int | None = Field(default=None, description="Group ID (pk)", gt=0)
    group_slug: str | None = Field(default=None, description="Group slug")
    email_domain: str | None = Field(
        default=None,
        description="Optional email domain filter, for example '@example.org'.",
    )

    @model_validator(mode="after")
    def validate_group_identifier(self) -> "FindGroupUsersByResourceOwnershipInput":
        if self.group_id is None and not self.group_slug:
            raise ValueError("Provide group_id or group_slug.")
        return self

    @field_validator("group_slug")
    @classmethod
    def validate_group_slug(cls, value: str | None) -> str | None:
        return _validate_slug(value)


class DeleteUsersSafelyInput(CountUserOwnedResourcesInput):
    dry_run: bool = Field(default=True, description="When true, validate and report only.")
    confirm: bool = Field(default=False, description="Set true to execute deletion.")
    expected_count: int | None = Field(
        default=None,
        description="Required number of candidate users when dry_run is false.",
        ge=0,
    )
    required_group_id: int | None = Field(
        default=None,
        description="Require each user to belong to this group ID.",
        gt=0,
    )
    required_group_slug: str | None = Field(
        default=None,
        description="Require each user to belong to this group slug.",
    )
    require_zero_owned_resources: bool = Field(
        default=True,
        description="Require zero owned datasets, documents, maps, and dashboards.",
    )
    require_not_staff: bool = Field(
        default=True,
        description="Reject staff and superuser accounts.",
    )

    @field_validator("required_group_slug")
    @classmethod
    def validate_required_group_slug(cls, value: str | None) -> str | None:
        return _validate_slug(value)
