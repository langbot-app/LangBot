from __future__ import annotations

import logging

from . import apigroup
from .groups import main
from .groups import usage
from .groups import plugin
from ...core import app


class V2CenterAPI:
    """中央服务器 v2 API 交互类"""
    
    main: main.V2MainDataAPI = None
    """主 API 组"""

    usage: usage.V2UsageDataAPI = None
    """使用量 API 组"""

    plugin: plugin.V2PluginDataAPI = None
    """插件 API 组"""

    def __init__(self, ap: app.Application, backend_url: str, basic_info: dict = None, runtime_info: dict = None):
        """初始化"""

        logging.debug("basic_info: %s, runtime_info: %s", basic_info, runtime_info)
        
        apigroup.APIGroup._basic_info = basic_info
        apigroup.APIGroup._runtime_info = runtime_info

        self.main = main.V2MainDataAPI(backend_url, ap)
        self.usage = usage.V2UsageDataAPI(backend_url, ap)
        self.plugin = plugin.V2PluginDataAPI(backend_url, ap)

