from pkg.qqbot.cmds.model import command

@command(
    "help",
    "获取帮助信息",
    "!help",
    [],
    False
)
def cmd_help(cmd: str, params: list, session_name: str, 
             text_message: str, launcher_type: str, launcher_id: int,
                sender_id: int, is_admin: bool) -> list:
    """获取帮助信息"""
    pass


@command(
    "usage",
    "获取使用情况",
    "!usage",
    [],
    False
)
def cmd_usage(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """获取使用情况"""
    pass


@command(
    "version",
    "查看版本信息",
    "!version",
    [],
    False
)
def cmd_version(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """查看版本信息"""
    pass


@command(
    "plugin",
    "插件相关操作",
    "!plugin\n!plugin <插件仓库地址>",
    [],
    False
)
def cmd_plugin(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """插件相关操作"""
    pass


@command(
    "reload",
    "执行热重载",
    "!reload",
    [],
    True
)
def cmd_reload(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """执行热重载"""
    pass


@command(
    "update",
    "更新程序",
    "!update",
    [],
    True
)
def cmd_update(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """更新程序"""
    pass


@command(
    "cfg",
    "配置文件相关操作",
    "!cfg all\n!cfg <配置项名称>\n!cfg <配置项名称> <配置项新值>",
    [],
    True
)
def cmd_cfg(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """配置文件相关操作"""
    pass
