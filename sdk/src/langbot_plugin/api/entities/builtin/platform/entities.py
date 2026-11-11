# -*- coding: utf-8 -*-
"""
Platform entity models.
"""

import abc
from enum import Enum
import typing

import pydantic


class Entity(pydantic.BaseModel):
    """Base entity representing a user or group."""

    id: typing.Union[int, str]
    """Entity ID."""

    @abc.abstractmethod
    def get_name(self) -> str:
        """Get display name."""


###############################
# EBA entities (backward-compatible additions)
###############################


class ChatType(str, Enum):
    """Chat/session type."""

    PRIVATE = "private"
    """Private (direct) chat."""
    GROUP = "group"
    """Group chat."""


class MemberRole(str, Enum):
    """Group member role."""

    OWNER = "owner"
    """Group owner."""
    ADMIN = "admin"
    """Administrator."""
    MEMBER = "member"
    """Regular member."""


class User(pydantic.BaseModel):
    """Unified user entity.

    Provides a common representation for Friend / GroupMember basics.
    """

    id: typing.Union[int, str]
    """User ID."""

    nickname: str = ""
    """Display name / nickname."""

    avatar_url: typing.Optional[str] = None
    """Avatar URL."""

    is_bot: bool = False
    """Whether this user is a bot."""

    username: typing.Optional[str] = None
    """Platform username (e.g. Telegram @username)."""

    remark: typing.Optional[str] = None
    """Remark / alias set by the current user."""


class UserGroup(pydantic.BaseModel):
    """Group entity (EBA version).

    Coexists with the legacy Group class; named UserGroup to avoid conflicts.
    """

    id: typing.Union[int, str]
    """Group ID."""

    name: str = ""
    """Group name."""

    description: typing.Optional[str] = None
    """Group description."""

    member_count: typing.Optional[int] = None
    """Number of members."""

    avatar_url: typing.Optional[str] = None
    """Group avatar URL."""

    owner_id: typing.Optional[typing.Union[int, str]] = None
    """Owner's user ID."""


class UserGroupMember(pydantic.BaseModel):
    """Group member entity (EBA version)."""

    user: User
    """User information."""

    group_id: typing.Union[int, str]
    """ID of the group this member belongs to."""

    role: MemberRole = MemberRole.MEMBER
    """Role within the group."""

    display_name: typing.Optional[str] = None
    """Display name within the group."""

    joined_at: typing.Optional[float] = None
    """Timestamp when the user joined the group."""

    title: typing.Optional[str] = None
    """Special title / badge within the group."""


###############################
# Legacy entities (unchanged)
###############################


class Friend(Entity):
    """Friend (direct-chat peer)."""

    id: typing.Union[int, str]
    """ID."""
    nickname: typing.Optional[str]
    """Nickname."""
    remark: typing.Optional[str]
    """Remark."""

    def get_name(self) -> str:
        return self.nickname or self.remark or ""


class Permission(str, Enum):
    """Group member permission level."""

    Member = "MEMBER"
    """Regular member."""
    Administrator = "ADMINISTRATOR"
    """Administrator."""
    Owner = "OWNER"
    """Group owner."""

    def __repr__(self) -> str:
        return repr(self.value)


class Group(Entity):
    """Group."""

    id: typing.Union[int, str]
    """Group ID."""
    name: str
    """Group name."""
    permission: Permission
    """Bot's permission level in this group."""

    def get_name(self) -> str:
        return self.name


class GroupMember(Entity):
    """Group member."""

    id: typing.Union[int, str]
    """Member ID."""
    member_name: str
    """Member display name."""
    permission: Permission
    """Permission level in the group."""
    group: Group
    """The group this member belongs to."""
    special_title: str = ""
    """Special title within the group."""

    def get_name(self) -> str:
        return self.member_name
