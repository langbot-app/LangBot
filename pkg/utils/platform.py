import os
import sys


def get_platform() -> str:
    """获取当前平台"""
    # 检查是不是在 docker 里
    if os.path.exists('/.dockerenv'):
        return 'docker'

    return sys.platform
