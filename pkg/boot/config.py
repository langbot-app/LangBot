import json

from ..config import manager as config_mgr
from ..config.impls import pymodule


async def load_python_module_config(config_name: str, template_name: str) -> config_mgr.ConfigManager:
    """加载Python模块配置文件"""
    cfg_inst = pymodule.PythonModuleConfigFile(
        config_name,
        template_name
    )

    cfg_mgr = config_mgr.ConfigManager(cfg_inst)
    await cfg_mgr.load_config()

    return cfg_mgr


async def override_config_manager(cfg_mgr: config_mgr.ConfigManager) -> list[str]:
    override_json = json.load(open("override.json", "r", encoding="utf-8"))
    overrided = []

    config = cfg_mgr.data
    for key in override_json:
        if key in config:
            config[key] = override_json[key]
            overrided.append(key)

    return overrided
