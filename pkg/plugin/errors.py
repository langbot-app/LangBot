from __future__ import annotations


class PluginSystemError(Exception):
    message: str

    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return self.message


class PluginNotFoundError(PluginSystemError):
    def __init__(self, message: str):
        super().__init__(f'未找到插件: {message}')


class PluginInstallerError(PluginSystemError):
    def __init__(self, message: str):
        super().__init__(f'安装器操作错误: {message}')
