from __future__ import annotations

from .. import apigroup
from ....core import app


class V2UsageDataAPI(apigroup.APIGroup):
    """使用量数据相关 API"""

    def __init__(self, prefix: str, ap: app.Application):
        self.ap = ap
        super().__init__(prefix+"/usage", ap)

    async def do(self, *args, **kwargs):
        if not self.ap.system_cfg.data['report-usage']:
            return None
        return await super().do(*args, **kwargs)

    async def post_query_record(
        self,
        session_type: str,
        session_id: str,
        query_ability_provider: str,
        usage: int,
        model_name: str,
        response_seconds: int,
        retry_times: int,
    ):
        """提交请求记录"""
        return await self.do(
            "POST",
            "/query",
            data={
                "basic": self.basic_info(),
                "runtime": self.runtime_info(),
                "session_info": {
                    "type": session_type,
                    "id": session_id,
                },
                "query_info": {
                    "ability_provider": query_ability_provider,
                    "usage": usage,
                    "model_name": model_name,
                    "response_seconds": response_seconds,
                    "retry_times": retry_times,
                }
            }
        )
    
    async def post_event_record(
        self,
        plugins: list[dict],
        event_name: str,
    ):
        """提交事件触发记录"""
        return await self.do(
            "POST",
            "/event",
            data={
                "basic": self.basic_info(),
                "runtime": self.runtime_info(),
                "plugins": plugins,
                "event_info": {
                    "name": event_name,
                }
            }
        )
    
    async def post_function_record(
        self,
        plugin: dict,
        function_name: str,
        function_description: str,
    ):
        """提交内容函数使用记录"""
        return await self.do(
            "POST",
            "/function",
            data={
                "basic": self.basic_info(),
                "plugin": plugin,
                "function_info": {
                    "name": function_name,
                    "description": function_description,
                }
            }
        )
    
