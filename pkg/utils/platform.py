import os
import sys


def get_platform() -> str:
    """获取当前平台"""
    # 检查是不是在 docker 里

    DOCKER_ENV = os.environ.get('DOCKER_ENV', 'false')

    if os.path.exists('/.dockerenv') or DOCKER_ENV == 'true':
        return 'docker'

    return sys.platform


standalone_runtime = False


def use_websocket_to_connect_plugin_runtime() -> bool:
    """是否使用 websocket 连接插件运行时"""
    return standalone_runtime
