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
    """QQ 号或群号。"""
    @abc.abstractmethod
    def get_avatar_url(self) -> str:
        """头像图片链接。"""

    @abc.abstractmethod
    def get_name(self) -> str:
        """名称。"""


class Friend(Entity):
    """好友。"""
    id: typing.Union[int, str]
    """QQ 号。"""
    nickname: typing.Optional[str]
    """昵称。"""
    remark: typing.Optional[str]
    """备注。"""
    def get_avatar_url(self) -> str:
        return f'http://q4.qlogo.cn/g?b=qq&nk={self.id}&s=140'

    def get_name(self) -> str:
        return self.nickname or self.remark or ''



class Permission(str, Enum):
    """群成员身份权限。"""
    Member = "MEMBER"
    """成员。"""
    Administrator = "ADMINISTRATOR"
    """管理员。"""
    Owner = "OWNER"
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
    def get_avatar_url(self) -> str:
        return f'https://p.qlogo.cn/gh/{self.id}/{self.id}/'

    def get_name(self) -> str:
        return self.name


class GroupMember(Entity):
    """群成员。"""
    id: typing.Union[int, str]
    """QQ 号。"""
    member_name: str
    """群成员名称。"""
    permission: Permission
    """Bot 在群中的权限。"""
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
    def get_avatar_url(self) -> str:
        return f'http://q4.qlogo.cn/g?b=qq&nk={self.id}&s=140'

    def get_name(self) -> str:
        return self.member_name


class Client(Entity):
    """来自其他客户端的用户。"""
    id: typing.Union[int, str]
    """识别 id。"""
    platform: str
    """来源平台。"""
    def get_avatar_url(self) -> str:
        raise NotImplementedError

    def get_name(self) -> str:
        return self.platform


class Subject(pydantic.BaseModel):
    """另一种实体类型表示。"""
    id: typing.Union[int, str]
    """QQ 号或群号。"""
    kind: typing.Literal['Friend', 'Group', 'Stranger']
    """类型。"""


class Config(pydantic.BaseModel):
    """配置项类型。"""
    def modify(self, **kwargs) -> 'Config':
        """修改部分设置。"""
        for k, v in kwargs.items():
            if k in self.__fields__:
                setattr(self, k, v)
            else:
                raise ValueError(f'未知配置项: {k}')
        return self


class GroupConfigModel(Config):
    """群配置。"""
    name: str
    """群名称。"""
    confess_talk: bool
    """是否允许坦白说。"""
    allow_member_invite: bool
    """是否允许成员邀请好友入群。"""
    auto_approve: bool
    """是否开启自动审批入群。"""
    anonymous_chat: bool
    """是否开启匿名聊天。"""
    announcement: str = ''
    """群公告。"""


class MemberInfoModel(Config, GroupMember):
    """群成员信息。"""
