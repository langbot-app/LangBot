from __future__ import annotations

from . import model as file_model
from .impls import pymodule, json as json_file


managers: ConfigManager = []


class ConfigManager:
    """配置文件管理器"""

    file: file_model.ConfigFile = None
    """配置文件实例"""

    data: dict = None
    """配置数据"""

    def __init__(self, cfg_file: file_model.ConfigFile) -> None:
        self.file = cfg_file
        self.data = {}

    async def load_config(self):
        self.data = await self.file.load()

    async def dump_config(self):
        await self.file.save(self.data)

    def dump_config_sync(self):
        self.file.save_sync(self.data)


async def load_python_module_config(config_name: str, template_name: str) -> ConfigManager:
    """加载Python模块配置文件"""
    cfg_inst = pymodule.PythonModuleConfigFile(
        config_name,
        template_name
    )

    cfg_mgr = ConfigManager(cfg_inst)
    await cfg_mgr.load_config()

    return cfg_mgr


async def load_json_config(config_name: str, template_name: str=None, template_data: dict=None) -> ConfigManager:
    """加载JSON配置文件"""
    cfg_inst = json_file.JSONConfigFile(
        config_name,
        template_name,
        template_data
    )

    cfg_mgr = ConfigManager(cfg_inst)
    await cfg_mgr.load_config()

    return cfg_mgr