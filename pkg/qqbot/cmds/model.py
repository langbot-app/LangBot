# 指令模型

commands = {}
"""已注册的指令类"""


class AbsCommand:
    """指令抽象类"""
    @staticmethod
    def execute(cls, cmd: str, params: list, session_name: str, text_message: str, launcher_type: str, launcher_id: int,
                sender_id: int, is_admin: bool) -> list:
        raise NotImplementedError


def register(cls: type):
    """注册指令类"""
    commands[cls.name] = cls
    return cls
