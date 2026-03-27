from __future__ import annotations

from .wecomcs import WecomCSAdapter


class WecomKFAppAdapter(WecomCSAdapter):
    """企微应用授权管理微信客服适配器。"""

    def __init__(self, config: dict, logger):
        # 中文注释：当前官方“企微应用授权管理微信客服”模式在收发消息协议上仍然沿用
        # 微信客服 kf/* 接口，因此第一版直接复用 WecomCSAdapter 的成熟实现，
        # 只把后台可选类型和产品语义独立出来，避免继续混用 wecom / wecomcs。
        super().__init__(config, logger)
