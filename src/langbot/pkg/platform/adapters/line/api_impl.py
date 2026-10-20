"""LineAPIMixin（EBA skeleton）。

对照 slack api_impl.py 的 call_platform_api 透传模式。
PLATFORM_API_MAP 由本 adapter 的 platform_api.py 提供；当前为空骨架（待填）。
"""

from __future__ import annotations

from langbot.pkg.platform.adapters.line.platform_api import PLATFORM_API_MAP


class LineAPIMixin:
    """LINE API 混血。透传 call_platform_api 至 PLATFORM_API_MAP。

    ⚠️ 映射表待 LINE Messaging API 端點實測後逐一定稿（action → callable）。
    """

    async def call_platform_api(self, action: str, **args):
        """对照 slack call_platform_api（api_impl.py 31-82）：依 action 查 PLATFORM_API_MAP。"""
        if action not in PLATFORM_API_MAP:
            raise NotImplementedError(f"call_platform_api: unknown action {action!r}")
        api = PLATFORM_API_MAP[action]
        # 占位：未定稿的 action 暂以 NotImplementedError 阻斷，待實測後註冊真实 callable
        result = await api(self, **args)
        return result
