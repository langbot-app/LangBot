import os
import sys


def get_platform() -> str:
    """获取当前平台"""
    # 检查是不是在 docker 里

    DOCKER_ENV = os.environ.get('DOCKER_ENV', 'false')

    if os.path.exists('/.dockerenv') or DOCKER_ENV == 'true':
        return 'docker'

    return sys.platform
