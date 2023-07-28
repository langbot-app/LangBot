import time
import threading
import logging


sessions = {}


class SessionOfflineStatus:
    ON_GOING = "on_going"
    EXPLICITLY_CLOSED = "explicitly_closed"


def reset_session_prompt(session_name, prompt):
    pass


def load_sessions():
    pass


def get_session(session_name: str) -> 'Session':
    pass


def dump_session(session_name: str):
    pass


class Session:
    name: str = ''

    default_prompt: list = []
    """会话系统提示语"""

    messages: list = []
    """保存消息历史记录"""

    token_counts: list = []
    """记录每回合的token数量"""

    create_ts: int = 0
    """会话创建时间戳"""

    last_active_ts: int = 0
    """会话最后活跃时间戳"""

    just_switched_to_exist_session: bool = False

    response_lock = None

    def __init__(self, name: str):
        self.name = name
        self.default_prompt = self.get_runtime_default_prompt()
        logging.debug("prompt is: {}".format(self.default_prompt))
        self.messages = []
        self.token_counts = []
        self.create_ts = int(time.time())
        self.last_active_ts = int(time.time())

        self.response_lock = threading.Lock()

        self.schedule()
        
    def get_runtime_default_prompt(self, use_default: str = None) -> list:
        """从提示词管理器中获取所需提示词"""
        import pkg.openai.dprompt as dprompt

        if use_default is None:
            use_default = dprompt.mode_inst().get_using_name()

        current_default_prompt, _ = dprompt.mode_inst().get_prompt(use_default)
        return current_default_prompt

    def schedule(self):
        """定时会话过期检查任务"""

    def expire_check_timer_loop(self):
        """会话过期检查任务"""
