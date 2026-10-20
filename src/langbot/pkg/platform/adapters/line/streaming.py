# -*- coding: utf-8 -*-
"""
streaming.py — LINE Streaming WebSocket 流式模組（WO-LINE-03 子模块）。

⚠️ 未定案線程（SDK Streaming WebSocket 端未實測／未入箱）：
blueprint §3.1／§407／§418 明示：LINE 端 streaming（WebSocket 長連、版本協議 v2、
SDK 保活重連）未實測、全部 ⚠️ 提案，需依 LINE Developers 官方文件 + line-bot-sdk 實測後方可定案。

本檔據 blueprint §4.2「native handler 入口」骨架 + AbstractPlatformAdapter 流式選類（§82
`reply_message_chunk`／`is_stream_output_supported`）產出**骨架**，
明確標註 SDK Streaming WebSocket 調用約定實測待確認（§9/§23 禁捏造未定案線程）。

含：
- ②a run_async WebSocket 流式線程骨架（據 blueprint §3.1 A. Streaming，SDK 连接/版本/保活待測）。
- ②d Streaming Chunk 打字機流式推送到 LINE 端骨架（據 blueprint §82 reply_message_chunk）。
- ②e 斷線自癒／退避（用 RetryPolicy 通用骨架；SDK stream 重连细节待測）。

解耦：据 send_api.RetryPolicy（本地导入）；仅 stdlib。
"""
import asyncio
from typing import Any, List, Optional

from send_api import RetryPolicy, SendError


class LineStreamClient:
    """Streaming WebSocket 長連骨架（②a run_async 流式入口）。

    **SDK 實測待確認**：LINE streaming SDK 长连入口、版本協議、保活／重连。
    本档据 blueprint §3.1「A. Streaming」骨架 + RetryPolicy 通用退避骨架，
    不含未定案 WebSocket 真实连接代码（禁捏造）。
    """

    def __init__(self, logger=None, retry: RetryPolicy = None,
                 reconnect_retries: int = 3, reconnect_base_delay: float = 1.0):
        self.logger = logger
        self.retry = retry or RetryPolicy(
            retries=reconnect_retries, base_delay=reconnect_base_delay,
            backoff_factor=2.0, max_delay=30.0,
        )
        self._connected = False

    async def _log(self, level: str, msg: str):
        if self.logger:
            fn = getattr(self.logger, level, None) or getattr(self.logger, "info", None)
            if fn:
                await fn(f"[LineStreamClient] {msg}")

    async def start_stream(self):
        """据 blueprint §3.1 A. Streaming 骨架：维护 WebSocket 長連，收事件走 SDK 回调。

        ⚠️ SDK 连接入口／版本協議／保活重连 待實測確認（未捏造）。
        run_async（adapter.py）据本骨架维护長連；事件走 native callback → _handle_native_event。
        """
        await self._log("info", "LineStreamClient.start_stream 骨架初始化（SDK WebSocket 连接待實測）")
        # 据 blueprint §3.1 A：bot streaming API 長連 WebSocket 收事件。
        # SDK 长连入口待 LINE Developers 官方文件 + line-bot-sdk 實測後定稿（禁捏造）。
        self._connected = True
        return "streaming_skeleton (SDK WebSocket entry 待實測)"

    async def stop_stream(self):
        self._connected = False
        await self._log("info", "LineStreamClient.stop_stream")
        return True

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect_with_retry(self):
        """②e 斷線自癒骨架：据 blueprint §3.1 保活重连 + RetryPolicy 通用退避。

        ⚠️ SDK stream 重连细节（保活心跳、版本協議）實測待確認。
        """
        try:
            await self.retry.run(self.start_stream)
            await self._log("info", "connect_with_retry 成功")
            return True
        except SendError:
            await self._log("error", "connect_with_retry 超限重試仍失败（斷線未癒合）")
            raise


class LineStreamOutput:
    """Streaming Chunk 打字機流式推送骨架（②d）。

    据 blueprint §82 `reply_message_chunk`／`is_stream_output_supported` 流式選類 +
    AbstractPlatformAdapter 流式契约。
    ⚠️ SDK 流式發送端點／chunk 形態 待實測確認。
    """

    def __init__(self, push_api, chunk_delay: float = 0.05, logger=None):
        # push_api: LineSendApi 实例（逐块 push 补完可见文本到 LINE 端）。
        self.push_api = push_api
        self.chunk_delay = chunk_delay
        self.logger = logger

    async def _log(self, level: str, msg: str):
        if self.logger:
            fn = getattr(self.logger, level, None) or getattr(self.logger, "info", None)
            if fn:
                await fn(f"[LineStreamOutput] {msg}")

    def is_stream_output_supported(self) -> bool:
        """据 blueprint §82 流式選類。

        ⚠️ LINE 是否支援流式輸出待 SDK 實測確認；保守預設 False（不宣称支持未測能力）。
        """
        return False

    async def reply_message_chunk(self, target_id: str, chunks: List[str]) -> Any:
        """流式打字機推送：逐 chunk 以打字機效果推送到 LINE 端（②d 骨架）。

        - chunks: 打字機流序（每個 chunk 是逐步累积的可见文本）。
        - 逐 chunk 延迟 + 推送（用 push_api push 逐块补完）。
        - ⚠️ SDK 流式發送端點／chunk 形態 待實測確認（未捏造）。
        """
        if not chunks:
            raise SendError("chunks 不能為空")
        if len(chunks) > 2000:
            # LINE 單消息上限約 5000 字；流式累積文本超限則警告（据 LINE 通用認知）
            await self._log("warn", f"流式累積文本超限 {len(chunks) > 2000}，注意 LINE 單消息上限")
        for chunk in chunks:
            async def _send_chunk(c=chunk):
                await self.push_api.push_message(
                    target_id=target_id,
                    content={"type": "text", "text": c},
                )
                if self.chunk_delay > 0:
                    await asyncio.sleep(self.chunk_delay)
            await self.push_api.retry.run(_send_chunk)
        await self._log("info", f"streaming chunk 打字機推送完成，chunks={len(chunks)}")
        return "streaming_done"
