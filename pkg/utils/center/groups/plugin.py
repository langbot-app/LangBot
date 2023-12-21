from __future__ import annotations

from .. import apigroup


class V2PluginDataAPI(apigroup.APIGroup):
    """插件数据相关 API"""

    def __init__(self, prefix: str):
        super().__init__(prefix+"/plugin")

    def post_install_record(
        self,
        plugin: dict
    ):
        """提交插件安装记录"""
        return self.do(
            "POST",
            "/install",
            data={
                "basic": self.basic_info(),
                "plugin": plugin,
            }
        )

    def post_remove_record(
        self,
        plugin: dict
    ):
        """提交插件卸载记录"""
        return self.do(
            "POST",
            "/remove",
            data={
                "basic": self.basic_info(),
                "plugin": plugin,
            }
        )

    def post_update_record(
        self,
        plugin: dict,
        old_version: str,
        new_version: str,
    ):
        """提交插件更新记录"""
        return self.do(
            "POST",
            "/update",
            data={
                "basic": self.basic_info(),
                "plugin": plugin,
                "update_info": {
                    "old_version": old_version,
                    "new_version": new_version,
                }
            }
        )
