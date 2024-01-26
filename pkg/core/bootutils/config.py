from __future__ import annotations

import json

from ...config import manager as config_mgr
from ...config.impls import pymodule


load_python_module_config = config_mgr.load_python_module_config
load_json_config = config_mgr.load_json_config


async def override_config_manager(cfg_mgr: config_mgr.ConfigManager) -> list[str]:
    override_json = json.load(open("override.json", "r", encoding="utf-8"))
    overrided = []

    config = cfg_mgr.data
    for key in override_json:
        if key in config:
            config[key] = override_json[key]
            overrided.append(key)

    return overrided
