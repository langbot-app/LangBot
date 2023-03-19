# 指令模型

commands = []
"""已注册的指令类
{
    "name": "指令名",
    "description": "指令描述",
    "usage": "指令用法",
    "aliases": ["别名1", "别名2"],
    "admin_only": "是否仅管理员可用",
    "func": "指令执行函数"
}
"""


def command(name: str, description: str, usage: str, aliases: list = None, admin_only: bool = False):
    """指令装饰器"""

    def wrapper(fun: function):
        commands.append({
            "name": name,
            "description": description,
            "usage": usage,
            "aliases": aliases,
            "admin_only": admin_only,
            "func": fun
        })
        return fun
    
    return wrapper
