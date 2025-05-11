from __future__ import annotations

from . import model as file_model
from .impls import pymodule, json as json_file, yaml as yaml_file


class ConfigManager:
    """配置文件管理器"""

    name: str = None
    """配置管理器名"""

    description: str = None
    """配置管理器描述"""

    schema: dict = None
    """配置文件 schema
    需要符合 JSON Schema Draft 7 规范
    """

    file: file_model.ConfigFile = None
    """配置文件实例"""

    data: dict = None
    """配置数据"""

    doc_link: str = None
    """配置文件文档链接"""

    def __init__(self, cfg_file: file_model.ConfigFile) -> None:
        self.file = cfg_file
        self.data = {}

    async def load_config(self, completion: bool = True):
        self.data = await self.file.load(completion=completion)

    async def dump_config(self):
        await self.file.save(self.data)

    def dump_config_sync(self):
        self.file.save_sync(self.data)


async def load_python_module_config(config_name: str, template_name: str, completion: bool = True) -> ConfigManager:
    """加载Python模块配置文件

    Args:
        config_name (str): 配置文件名
        template_name (str): 模板文件名
        completion (bool): 是否自动补全内存中的配置文件

    Returns:
        ConfigManager: 配置文件管理器
    """
    cfg_inst = pymodule.PythonModuleConfigFile(config_name, template_name)

    cfg_mgr = ConfigManager(cfg_inst)
    await cfg_mgr.load_config(completion=completion)

    return cfg_mgr


async def load_json_config(
    config_name: str,
    template_name: str = None,
    template_data: dict = None,
    completion: bool = True,
) -> ConfigManager:
    """加载JSON配置文件

    Args:
        config_name (str): 配置文件名
        template_name (str): 模板文件名
        template_data (dict): 模板数据
        completion (bool): 是否自动补全内存中的配置文件
    """
    cfg_inst = json_file.JSONConfigFile(config_name, template_name, template_data)

    cfg_mgr = ConfigManager(cfg_inst)
    await cfg_mgr.load_config(completion=completion)

    return cfg_mgr


async def load_yaml_config(
    config_name: str,
    template_name: str = None,
    template_data: dict = None,
    completion: bool = True,
) -> ConfigManager:
    """加载YAML配置文件

    Args:
        config_name (str): 配置文件名
        template_name (str): 模板文件名
        template_data (dict): 模板数据
        completion (bool): 是否自动补全内存中的配置文件

    Returns:
        ConfigManager: 配置文件管理器
    """
    cfg_inst = yaml_file.YAMLConfigFile(config_name, template_name, template_data)

    cfg_mgr = ConfigManager(cfg_inst)
    await cfg_mgr.load_config(completion=completion)

    return cfg_mgr
