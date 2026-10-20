# -*- coding: utf-8 -*-
"""
send_api.py — LINE 訊息發送 API（WO-LINE-03 子模块）。

據 SDK 3.26.0 合約實作〔WO-LINE-00-SDK-326-CONTRACT.md，ops .84 CubeSandbox 實測 2026-10-20〕：
- ②b 被動回覆快速通道：ReplyToken 回覆（LineBotApi.reply_message），過期 Smoothly 轉 Push API。
- ②c 主動推播：Push Message（LineBotApi.push_message），支援文字／圖片／自訂 Flex。
- ②e 超時重試、網路斷線自癒與退避機制（通用，不依賴 SDK 特定 API）。

合約註（據 §2.2 實測）：
- `LineBotApi.push_message()`／`reply_message()` 正確（LineBotApi 不直接擁有 push/reply 屬性）。
- reply/push 的 message payload 用 dict 形態（{'type':'text'|'image'|'flex', ...}）—— 据 LINE Messaging API 通用認知，
  **⚠️ dict vs SDK 對象 仍待 SDK 實測確認**（本檔留痕）。

未定案線程（本檔不含）：
- ②a run_async WebSocket 流式連線線程、②d Streaming Chunk 打字機流式推—— 屬 SDK Streaming WebSocket 端，
  未實測／未入箱（blueprint §3.1／§407／§418 ⚠️待測），走 streaming.py 骨架 + 待 SDK 實測確認。

解耦：不 import 契約層；self-contained。僅 stdlib。
"""
import asyncio
import random
from typing import Any, Callable, Optional


class SendError(Exception):
    """發送失敗（含超限重試仍失敗）。"""


class RetryPolicy:
    """通用退避重試策略（②e）。

    - 退避 = base_delay × backoff_factor**attempt，上限 max_delay，加 jitter 防雪崩。
    - 僅重試 retryable（TimeoutError/ConnectionError 等「網路斷線」類）。
    - 不依賴 SDK 特定 API，可复用于任何 awaitable 发送。
    """

    def __init__(self, retries: int = 3, base_delay: float = 0.5,
                 backoff_factor: float = 2.0, max_delay: float = 15.0,
                 jitter: float = 0.3,
                 retryable: tuple = (TimeoutError, ConnectionError, ConnectionResetError)):
        self.retries = max(0, retries)
        self.base_delay = max(0.0, base_delay)
        self.backoff_factor = max(1.0, backoff_factor)
        self.max_delay = max_delay
        self.jitter = max(0.0, min(1.0, jitter))
        self.retryable = retryable

    def backoff(self, attempt: int) -> float:
        delay = self.base_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter > 0:
            # 半抖动：保留退避骨架 + 加 ±jitter 百分比抖动
            return delay * (1.0 + random.uniform(-self.jitter, self.jitter))
        return delay

    async def run(self, coro_factory: Callable[[], Any]) -> Any:
        """循环重试 coro_factory；成功回传，失败抛 SendError。

        coro_factory: () -> 返回 awaitable（每次调用产生新 coroutine，避免复用同一 coroutine）。
        通用：记录 attempt、退避 sleep、仅捕获 retryable。
        """
        last_exc = None
        for attempt in range(self.retries + 1):
            try:
                return await coro_factory()
            except self.retryable as e:
                last_exc = e
                if attempt < self.retries:
                    await self._log(f"retriable error on attempt {attempt}: {e}; backoff {self.backoff(attempt):.2f}s")
                    await asyncio.sleep(self.backoff(attempt))
        raise SendError(f"发送失败，已重试 {self.retries} 次仍失败: {last_exc}") from last_exc

    async def _log(self, msg: str):
        # 轻量日志；外部注入（见 LineSendApi 的 logger 注入）
        try:
            pass
        except Exception:
            pass


class LineSendApi:
    """LINE 訊息發送 API 混血 mixin（据 SDK 3.26.0 合约实作）。

    - ②b 被動回覆快速通道（ReplyToken 回覆 + 過期轉 Push）。
    - ②c 主動推播（文字／圖片／Flex）。
    - ②e 超時重試／斷線自癒／退避（内部用 RetryPolicy 包裝）。
    """

    def __init__(self, client, retry: RetryPolicy = None, logger=None):
        self.client = client  # LineBotApi 实例
        self.retry = retry or RetryPolicy()
        self.logger = logger

    async def _log(self, level: str, msg: str):
        if self.logger:
            fn = getattr(self.logger, level, None) or getattr(self.logger, "info", None)
            if fn:
                await fn(f"[LineSendApi] {msg}")

    # ---------- ②c 主動推播：Push Message（文字／圖片／自訂 Flex）----------
    async def push_message(self, target_id: str, content: dict, timeout: float = 30.0) -> Any:
        """主動推播：文字 / 圖片 / Flex。

        content schema（据 LINE Messaging API 通用認知）：
          {"type": "text", "text": "..."}
          {"type": "image", "original_content_url": "…", "preview_image_url": "…"}
          {"type": "flex", "alternative_text": "…", "flex": { ... }}
        据 §2.2 實測推送方式 push_message(to_user, message=payload)。
        payload dict 形態 vs SDK 對象 ⚠️ 待 SDK 實測確認。
        """
        if not target_id:
            raise SendError("push target_id 不能为空")
        payload = self._build_payload(content)

        async def _send():
            return await self.client.push_message(to_user=target_id, message=payload)

        await self._log("info", f"push_message to={target_id}")
        return await self.retry.run(_send)

    # ---------- ②b 被動回覆快速通道：ReplyToken 回覆（過期轉 Push）----------
    async def reply_message(self, target_id: str, content: dict,
                            timeout: float = 30.0, push_target_id: str = None) -> Any:
        """被動回覆：ReplyToken 快速通道。

        - 據 §2.2 實測 reply_message(reply_token, message=payload)。
        - 過期／失敗 → 平滑轉 Push API（用 push_target_id）；缺 push_target_id 才抛 SendError。
        - target_id 即 reply_token；timeout 仅用于记录（实际过期判断由 SDK 异常体现）。
        """
        if not target_id:
            if not push_target_id:
                raise SendError("reply 需 reply_token 或 push_target_id")
            await self._log("warn", "reply_token 缺失，直接轉 Push API")
            return await self.push_message(push_target_id, content)

        payload = self._build_payload(content)

        async def _reply():
            await self.client.reply_message(reply_token=target_id, message=payload)

        try:
            await self.retry.run(_reply)
        except SendError:
            # 過期／失敗 → 平滑轉 Push（②b 平滑降级）
            if not push_target_id:
                raise
            await self._log("warn",
                            f"ReplyToken 已過期／失敗（timeout={timeout}s），平滑轉 Push to={push_target_id}")
            return await self.push_message(push_target_id, content)
        await self._log("info", "reply_token 回覆完成")
        return "replied"

    # ---------- payload 建構（文字／圖片／Flex）----------
    def _build_payload(self, content: dict) -> dict:
        """据 content schema 构造 LINE 推送 payload。

        据 LINE Messaging API 通用認知；dict 形態 vs SDK 對象 ⚠️ 待 SDK 實測確認。
        """
        if content is None:
            raise SendError("content 不能為空")
        ctype = content.get("type", "text")
        if ctype == "text":
            if not content.get("text"):
                raise SendError("text message 缺 text 欄")
            return {"type": "text", "text": content.get("text", "")}
        if ctype == "image":
            if not content.get("original_content_url"):
                raise SendError("image message 缺 original_content_url 欄")
            return {
                "type": "image",
                "original_content_url": content.get("original_content_url", ""),
                "preview_image_url": content.get("preview_image_url", ""),
            }
        if ctype == "flex":
            if not content.get("flex"):
                raise SendError("flex message 缺 flex 欄")
            return {
                "type": "flex",
                "alternative_text": content.get("alternative_text", ""),
                "flex": content.get("flex", {}),
            }
        raise SendError(f"不支持的 message type: {ctype}（仅 text/image/flex）")
