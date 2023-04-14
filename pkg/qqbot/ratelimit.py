# 限速相关模块
import time
import logging
import threading

__crt_minute_usage__ = {}
"""当前分钟每个会话的对话次数"""


__timer_thr__: threading.Thread = None


def get_limitation(session_name: str) -> int:
    """获取会话的限制次数"""
    import config

    if type(config.rate_limitation) == dict:
        # 如果被指定了
        if session_name in config.rate_limitation:
            return config.rate_limitation[session_name]
        else:
            return config.rate_limitation["default"]
    elif type(config.rate_limitation) == int:
        return config.rate_limitation


def add_usage(session_name: str):
    """增加会话的对话次数"""
    global __crt_minute_usage__
    if session_name in __crt_minute_usage__:
        __crt_minute_usage__[session_name] += 1
    else:
        __crt_minute_usage__[session_name] = 1


def start_timer():
    """启动定时器"""
    global __timer_thr__
    __timer_thr__ = threading.Thread(target=run_timer, daemon=True)
    __timer_thr__.start()


def run_timer():
    """启动定时器，每分钟清空一次对话次数"""
    global __crt_minute_usage__
    global __timer_thr__
    
    # 等待直到整分钟
    time.sleep(60 - time.time() % 60)

    while True:
        if __timer_thr__ != threading.current_thread():
            break
        
        logging.debug("清空当前分钟的对话次数")
        __crt_minute_usage__ = {}
        time.sleep(60)


def get_usage(session_name: str) -> int:
    """获取会话的对话次数"""
    global __crt_minute_usage__
    if session_name in __crt_minute_usage__:
        return __crt_minute_usage__[session_name]
    else:
        return 0


def get_rest_wait_time(session_name: str, spent: float) -> float:
    """获取会话此回合的剩余等待时间"""
    global __crt_minute_usage__

    min_seconds_per_round = 60.0 / get_limitation(session_name)

    if session_name in __crt_minute_usage__:
        return max(0, min_seconds_per_round - spent)
    else:
        return 0


def is_reach_limit(session_name: str) -> bool:
    """判断会话是否超过限制"""
    global __crt_minute_usage__

    if session_name in __crt_minute_usage__:
        return __crt_minute_usage__[session_name] >= get_limitation(session_name)
    else:
        return False

start_timer()
