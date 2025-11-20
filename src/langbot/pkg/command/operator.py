from __future__ import annotations

import typing
import abc

from ..core import app
from langbot_plugin.api.entities.builtin.command import context as command_context


preregistered_operators: list[typing.Type[CommandOperator]] = []
"""预注册命令算子列表。在初始化时，所有算子类会被注册到此列表中。"""


def operator_class(
    name: str,
    help: str = '',
    usage: str = None,
    alias: list[str] = [],
    privilege: int = 1,  # 1为普通用户，2为管理员
    parent_class: typing.Type[CommandOperator] = None,
) -> typing.Callable[[typing.Type[CommandOperator]], typing.Type[CommandOperator]]:
    """命令类装饰器

    Args:
        name (str): 名称
        help (str, optional): 帮助信息. Defaults to "".
        usage (str, optional): 使用说明. Defaults to None.
        alias (list[str], optional): 别名. Defaults to [].
        privilege (int, optional): 权限，1为普通用户可用，2为仅管理员可用. Defaults to 1.
        parent_class (typing.Type[CommandOperator], optional): 父节点，若为None则为顶级命令. Defaults to None.

    Returns:
        typing.Callable[[typing.Type[CommandOperator]], typing.Type[CommandOperator]]: 装饰器
    """

    def decorator(cls: typing.Type[CommandOperator]) -> typing.Type[CommandOperator]:
        assert issubclass(cls, CommandOperator)

        cls.name = name
        cls.alias = alias
        cls.help = help
        cls.usage = usage
        cls.parent_class = parent_class
        cls.lowest_privilege = privilege

        preregistered_operators.append(cls)

        return cls

    return decorator


class CommandOperator(metaclass=abc.ABCMeta):
    """命令算子抽象类

    以下的参数均不需要在子类中设置，只需要在使用装饰器注册类时作为参数传递即可。
    命令支持级联，即一个命令可以有多个子命令，子命令可以有子命令，以此类推。
    处理命令时，若有子命令，会以当前参数列表的第一个参数去匹配子命令，若匹配成功，则转移到子命令中执行。
    若没有匹配成功或没有子命令，则执行当前命令。
    """

    ap: app.Application

    name: str
    """名称，搜索到时若符合则使用"""

    path: str
    """路径，所有父节点的name的连接，用于定义命令权限，由管理器在初始化时自动设置。
    """

    alias: list[str]
    """同name"""

    help: str
    """此节点的帮助信息"""

    usage: str = None
    """用法"""

    parent_class: typing.Union[typing.Type[CommandOperator], None] = None
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
        self, context: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        """实现此方法以执行命令

        支持多次yield以返回多个结果。
        例如：一个安装插件的命令，可能会有下载、解压、安装等多个步骤，每个步骤都可以返回一个结果。

        Args:
            context (command_context.ExecuteContext): 命令执行上下文

        Yields:
            command_context.CommandReturn: 命令返回封装
        """
        pass
