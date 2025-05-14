# -*- coding: utf-8 -*-
"""
此模块提供实体和配置项模型。
"""

import abc
from datetime import datetime
from enum import Enum
import typing

import pydantic.v1 as pydantic


class Entity(pydantic.BaseModel):
    """实体，表示一个用户或群。"""

    id: int
    """ID。"""

    @abc.abstractmethod
    def get_name(self) -> str:
        """名称。"""


class Friend(Entity):
    """私聊对象。"""

    id: typing.Union[int, str]
    """ID。"""
    nickname: typing.Optional[str]
    """昵称。"""
    remark: typing.Optional[str]
    """备注。"""

    def get_name(self) -> str:
        return self.nickname or self.remark or ''


class Permission(str, Enum):
    """群成员身份权限。"""

    Member = 'MEMBER'
    """成员。"""
    Administrator = 'ADMINISTRATOR'
    """管理员。"""
    Owner = 'OWNER'
    """群主。"""

    def __repr__(self) -> str:
        return repr(self.value)


class Group(Entity):
    """群。"""

    id: typing.Union[int, str]
    """群号。"""
    name: str
    """群名称。"""
    permission: Permission
    """Bot 在群中的权限。"""

    def get_name(self) -> str:
        return self.name


class GroupMember(Entity):
    """群成员。"""

    id: typing.Union[int, str]
    """群员 ID。"""
    member_name: str
    """群员名称。"""
    permission: Permission
    """在群中的权限。"""
    group: Group
    """群。"""
    special_title: str = ''
    """群头衔。"""
    join_timestamp: datetime = datetime.utcfromtimestamp(0)
    """加入群的时间。"""
    last_speak_timestamp: datetime = datetime.utcfromtimestamp(0)
    """最后一次发言的时间。"""
    mute_time_remaining: int = 0
    """禁言剩余时间。"""

    def get_name(self) -> str:
        return self.member_name
