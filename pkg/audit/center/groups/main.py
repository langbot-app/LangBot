from __future__ import annotations

from .. import apigroup
from ....core import app


class V2MainDataAPI(apigroup.APIGroup):
    """主程序相关 数据API"""

    def __init__(self, prefix: str, ap: app.Application):
        self.ap = ap
        super().__init__(prefix+"/main", ap)

    async def do(self, *args, **kwargs):
        if not self.ap.system_cfg.data['report-usage']:
            return None
        return await super().do(*args, **kwargs)

    async def post_update_record(
        self,
        spent_seconds: int,
        infer_reason: str,
        old_version: str,
        new_version: str,
    ):
        """提交更新记录"""
        return await self.do(
            "POST",
            "/update",
            data={
                "basic": self.basic_info(),
                "update_info": {
                    "spent_seconds": spent_seconds,
                    "infer_reason": infer_reason,
                    "old_version": old_version,
                    "new_version": new_version,
                }
            }
        )
    
    async def post_announcement_showed(
        self,
        ids: list[int],
    ):
        """提交公告已阅"""
        return await self.do(
            "POST",
            "/announcement",
            data={
                "basic": self.basic_info(),
                "announcement_info": {
                    "ids": ids,
                }
            }
        )
