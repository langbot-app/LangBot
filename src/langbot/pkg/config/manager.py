from __future__ import annotations

from . import model as file_model
from .impls import pymodule, json as json_file, yaml as yaml_file


class ConfigManager:
    """Config file manager"""

    name: str = None
    """Config manager name"""

    description: str = None
    """Config manager description"""

    schema: dict = None
    """Config file schema
    Must conform to JSON Schema Draft 7 specification
    """

    file: file_model.ConfigFile = None
    """Config file instance"""

    data: dict = None
    """Config data"""

    doc_link: str = None
    """Config file documentation link"""

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
    """Load Python module config file

    Args:
        config_name (str): Config file name
        template_name (str): Template file name
        completion (bool): Whether to automatically complete the config file in memory

    Returns:
        ConfigManager: Config file manager
    """
    cfg_inst = pymodule.PythonModuleConfigFile(config_name, template_name)

    cfg_mgr = ConfigManager(cfg_inst)
    await cfg_mgr.load_config(completion=completion)

    return cfg_mgr


async def load_json_config(
    config_name: str,
    template_resource_name: str = None,
    template_data: dict = None,
    completion: bool = True,
) -> ConfigManager:
    """Load JSON config file

    Args:
        config_name (str): Config file name
        template_resource_name (str): Template resource name
        template_data (dict): Template data
        completion (bool): Whether to automatically complete the config file in memory
    """
    cfg_inst = json_file.JSONConfigFile(config_name, template_resource_name, template_data)

    cfg_mgr = ConfigManager(cfg_inst)
    await cfg_mgr.load_config(completion=completion)

    return cfg_mgr


async def load_yaml_config(
    config_name: str,
    template_resource_name: str = None,
    template_data: dict = None,
    completion: bool = True,
) -> ConfigManager:
    """Load YAML config file

    Args:
        config_name (str): Config file name
        template_resource_name (str): Template resource name
        template_data (dict): Template data
        completion (bool): Whether to automatically complete the config file in memory

    Returns:
        ConfigManager: Config file manager
    """
    cfg_inst = yaml_file.YAMLConfigFile(config_name, template_resource_name, template_data)

    cfg_mgr = ConfigManager(cfg_inst)
    await cfg_mgr.load_config(completion=completion)

    return cfg_mgr
