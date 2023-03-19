from pkg.qqbot.cmds.model import command

@command(
    "draw",
    "使用DALL·E模型作画",
    "!draw <图片提示语>",
    [],
    False
)
def cmd_draw(cmd: str, params: list, session_name: str,
             text_message: str, launcher_type: str, launcher_id: int,
                sender_id: int, is_admin: bool) -> list:
    """使用DALL·E模型作画"""
    pass