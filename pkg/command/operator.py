from __future__ import annotations

import typing
import abc

from ..core import app, entities as core_entities
from ..openai.session import entities as session_entities
from . import entities


preregistered_operators: list[typing.Type[CommandOperator]] = []


def operator_class(
    name: str,
    alias: list[str],
    help: str,
    privilege: int=1,  # 1为普通用户，2为管理员
    parent_class: typing.Type[CommandOperator] = None
) -> typing.Callable[[typing.Type[CommandOperator]], typing.Type[CommandOperator]]:
    def decorator(cls: typing.Type[CommandOperator]) -> typing.Type[CommandOperator]:
        cls.name = name
        cls.alias = alias
        cls.help = help
        cls.parent_class = parent_class

        preregistered_operators.append(cls)

        return cls

    return decorator


class CommandOperator(metaclass=abc.ABCMeta):
    """命令算子
    """

    ap: app.Application

    name: str
    """名称，搜索到时若符合则使用"""

    alias: list[str]
    """同name"""

    help: str
    """此节点的帮助信息"""

    parent_class: typing.Type[CommandOperator]
    """父节点类。标记以供管理器在初始化时编织父子关系。"""

    lowest_privilege: int = 0
    """最低权限。若权限低于此值，则不予执行。"""

    children: list[CommandOperator]
    """子节点。解析命令时，若节点有子节点，则以下一个参数去匹配子节点，
    若有匹配中的，转移到子节点中执行，若没有匹配中的或没有子节点，执行此节点。"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.children = []

    async def initialize(self):
        pass

    @abc.abstractmethod
    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        pass
