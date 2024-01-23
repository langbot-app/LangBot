import json

from ..config import manager as config_mgr
from ..config.impls import pymodule


async def load_config() -> config_mgr.ConfigManager:
    """加载配置文件"""
    cfg_inst = pymodule.PythonModuleConfigFile(
        "config.py",
        "config-template.py"
    )

    cfg_mgr = config_mgr.ConfigManager(cfg_inst)
    await cfg_mgr.load_config()

    return cfg_mgr


async def load_tips() -> config_mgr.ConfigManager:
    """加载提示文件"""
    tips_inst = pymodule.PythonModuleConfigFile(
        "tips.py",
        "tips-custom-template.py"
    )

    tips_mgr = config_mgr.ConfigManager(tips_inst)
    await tips_mgr.load_config()

    return tips_mgr


async def override_config_manager(cfg_mgr: config_mgr.ConfigManager) -> list[str]:
    override_json = json.load(open("override.json", "r", encoding="utf-8"))
    overrided = []

    config = cfg_mgr.data
    for key in override_json:
        if key in config:
            config[key] = override_json[key]
            overrided.append(key)
            
    return overrided
