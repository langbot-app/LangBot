from __future__ import annotations

import typing

import pydantic
import mirai

from ..core import app, entities as core_entities
from . import errors, operator


class CommandReturn(pydantic.BaseModel):
    """命令返回值
    """

    text: typing.Optional[str]
    """文本
    """

    image: typing.Optional[mirai.Image]

    error: typing.Optional[errors.CommandError]= None
    """错误
    """

    class Config:
        arbitrary_types_allowed = True


class ExecuteContext(pydantic.BaseModel):
    """单次命令执行上下文
    """

    query: core_entities.Query
    """本次消息的请求对象"""

    session: core_entities.Session
    """本次消息所属的会话对象"""

    command_text: str
    """命令完整文本"""

    command: str
    """命令名称"""

    crt_command: str
    """当前命令
    
    多级命令中crt_command为当前命令，command为根命令。
    例如：!plugin on Webwlkr
    处理到plugin时，command为plugin，crt_command为plugin
    处理到on时，command为plugin，crt_command为on
    """

    params: list[str]
    """命令参数
    
    整个命令以空格分割后的参数列表
    """

    crt_params: list[str]
    """当前命令参数

    多级命令中crt_params为当前命令参数，params为根命令参数。
    例如：!plugin on Webwlkr
    处理到plugin时，params为['on', 'Webwlkr']，crt_params为['on', 'Webwlkr']
    处理到on时，params为['on', 'Webwlkr']，crt_params为['Webwlkr']
    """

    privilege: int
    """发起人权限"""
