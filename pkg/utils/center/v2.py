from __future__ import annotations

from . import apigroup
from .groups import main
from .groups import usage
from .groups import plugin


BACKEND_URL = "https://api.qchatgpt.rockchin.top/api/v2"

class V2CenterAPI:
    """中央服务器 v2 API 交互类"""
    
    main: main.V2MainDataAPI = None
    """主 API 组"""

    usage: usage.V2UsageDataAPI = None
    """使用量 API 组"""

    plugin: plugin.V2PluginDataAPI = None
    """插件 API 组"""

    def __init__(self, basic_info: dict = None, runtime_info: dict = None):
        """初始化"""

        print("basic_info:", basic_info)
        print("runtime_info:", runtime_info)
        apigroup.APIGroup._basic_info = basic_info
        apigroup.APIGroup._runtime_info = runtime_info

        self.main = main.V2MainDataAPI(BACKEND_URL)
        self.usage = usage.V2UsageDataAPI(BACKEND_URL)
        self.plugin = plugin.V2PluginDataAPI(BACKEND_URL)
