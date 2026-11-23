import os
import sys

_TRUE_VALUES = {'1', 'true', 'yes', 'on'}
_FALSE_VALUES = {'0', 'false', 'no', 'off'}


def get_platform() -> str:
    """获取当前平台

    An explicitly set ``DOCKER_ENV`` wins over the ``/.dockerenv`` heuristic, so
    native deployments that happen to run inside a container (CI, devcontainers,
    some NAS images) can set ``DOCKER_ENV=false`` and still launch the local
    plugin runtime / Box. When ``DOCKER_ENV`` is unset (or unrecognized) we fall
    back to probing ``/.dockerenv``.
    """
    docker_env = os.environ.get('DOCKER_ENV', '').strip().lower()

    if docker_env in _TRUE_VALUES:
        return 'docker'
    if docker_env in _FALSE_VALUES:
        return sys.platform

    if os.path.exists('/.dockerenv'):
        return 'docker'

    return sys.platform


standalone_runtime = False

standalone_box = False


def use_websocket_to_connect_plugin_runtime() -> bool:
    """是否使用 websocket 连接插件运行时"""
    return standalone_runtime


def use_websocket_to_connect_box_runtime() -> bool:
    """Whether to use WebSocket to connect to an external box runtime."""
    return standalone_box
