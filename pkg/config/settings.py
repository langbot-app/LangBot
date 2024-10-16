from __future__ import annotations

from . import manager as config_manager
from ..core import app


class SettingsManager:
    """设置管理器
    保存、管理多个配置文件管理器
    """

    ap: app.Application

    managers: list[config_manager.ConfigManager] = []
    """配置文件管理器列表"""

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self.managers = []

    async def initialize(self) -> None:
        pass

    def register_manager(
        self,
        name: str,
        description: str,
        manager: config_manager.ConfigManager,
        schema: dict=None,
    ) -> None:
        """注册配置管理器
        
        Args:
            name (str): 配置管理器名
            description (str): 配置管理器描述
            manager (ConfigManager): 配置管理器
            schema (dict): 配置文件 schema，符合 JSON Schema Draft 7 规范
        """

        for m in self.managers:
            if m.name == name:
                raise ValueError(f'配置管理器名 {name} 已存在')

        manager.name = name
        manager.description = description
        manager.schema = schema
        self.managers.append(manager)

    def get_manager(self, name: str) -> config_manager.ConfigManager | None:
        """获取配置管理器
        
        Args:
            name (str): 配置管理器名
        
        Returns:
            ConfigManager: 配置管理器
        """

        for m in self.managers:
            if m.name == name:
                return m

        return None
    
    def get_manager_list(self) -> list[config_manager.ConfigManager]:
        """获取配置管理器列表
        
        Returns:
            list[ConfigManager]: 配置管理器列表
        """

        return self.managers
    
