# 会话管理相关指令
from pkg.qqbot.cmds.model import command


@command(
    "reset",
    "重置当前会话",
    "!reset\n!reset [使用情景预设名称]",
    [],
    False
)
def cmd_reset(cmd: str, params: list, session_name: str, 
              text_message: str, launcher_type: str, launcher_id: int,
                sender_id: int, is_admin: bool) -> list:
    """重置会话"""
    pass


@command(
    "last",
    "切换到前一次会话",
    "!last",
    [],
    False
)
def cmd_last(cmd: str, params: list, session_name: str, 
             text_message: str, launcher_type: str, launcher_id: int,
                sender_id: int, is_admin: bool) -> list:
    """切换到前一次会话"""
    pass


@command(
    "next",
    "切换到后一次会话",
    "!next",
    [],
    False
)
def cmd_next(cmd: str, params: list, session_name: str, 
             text_message: str, launcher_type: int, launcher_id: int,
                sender_id: int, is_admin: bool) -> list:
    """切换到后一次会话"""
    pass


@command(
    "prompt",
    "获取当前会话的前文",
    "!prompt",
    [],
    False
)
def cmd_prompt(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
     """获取当前会话的前文"""
     pass


@command(
    "list",
    "列出当前会话的所有历史记录",
    "!list\n!list [页数]",
    [],
    False
)
def cmd_list(cmd: str, params: list, session_name: str,
              text_message: str, launcher_type: str, launcher_id: int,
               sender_id: int, is_admin: bool) -> list:
    """列出当前会话的所有历史记录"""
    pass


@command(
    "resend"
    "重新获取上一次问题的回复",
    "!resend",
    [],
    False
)
def cmd_resend(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """重新获取上一次问题的回复"""
    pass


@command(
    "del",
    "删除当前会话的历史记录",
    "!del <序号>\n!del all",
    [],
    False
)
def cmd_del(cmd: str, params: list, session_name: str,
             text_message: str, launcher_type: str, launcher_id: int,
              sender_id: int, is_admin: bool) -> list:
    """删除当前会话的历史记录"""
    pass


@command(
    "default",
    "操作情景预设",
    "!default\n!default [指定情景预设为默认]",
    [],
    False
)
def cmd_default(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """操作情景预设"""
    pass


@command(
    "delhst",
    "删除指定会话的所有历史记录",
    "!delhst <会话名称>\n!delhst all",
    [],
    True
)
def cmd_delhst(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """删除指定会话的所有历史记录"""
    pass
