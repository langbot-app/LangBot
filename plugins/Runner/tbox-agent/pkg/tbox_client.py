"""Tbox API client wrapper for Runner.

This module provides an async wrapper around tboxsdk for use with the Runner plugin.
"""

from __future__ import annotations

import base64
import logging
from contextlib import aclosing
from pathlib import Path

from pkg.vendor_process import vendor_stream

logger = logging.getLogger(__name__)


class TboxAPIError(Exception):
    """Tbox API error."""

    def __init__(self, message: str, code: str = "tbox.api_error", retryable: bool = False):
        self.message = message
        self.code = code
        self.retryable = retryable
        super().__init__(message)


class TboxConfigError(Exception):
    """Tbox configuration error."""

    def __init__(self, message: str, code: str = "tbox.config_invalid"):
        self.message = message
        self.code = code
        super().__init__(message)


class AsyncTboxClient:
    """Run the official synchronous SDK in a killable, bounded child process."""

    def __init__(self, api_key, timeout=120.0):
        self.api_key = api_key
        self.timeout = timeout

    async def upload_file(self, file_bytes, file_name):
        if len(file_bytes) > 10 * 1024 * 1024:
            raise TboxAPIError("Upload exceeds the 10 MiB size limit", code="tbox.input_error")
        suffix = Path(file_name).suffix
        if len(suffix) > 32 or not all(c.isalnum() or c == "." for c in suffix):
            suffix = ".bin"
        payload = dict(
            operation="upload",
            api_key=self.api_key,
            data=base64.b64encode(file_bytes).decode(),
            suffix=suffix or ".bin",
        )
        try:
            async with aclosing(vendor_stream(payload, timeout=self.timeout)) as stream:
                result = await anext(stream)
                file_id = result.get("data", "")
                if not isinstance(file_id, str) or not file_id:
                    raise TboxAPIError("Upload returned no file id", code="tbox.upload_error")
                return file_id
        except TimeoutError:
            raise TboxAPIError("Tbox upload timed out", code="tbox.timeout", retryable=True) from None
        except (RuntimeError, ValueError):
            raise TboxAPIError("Tbox upload worker failed", code="tbox.upload_error") from None

    async def chat(self, app_id, user_id, query, stream=True, conversation_id=None, files=None):
        payload = dict(
            operation="chat",
            api_key=self.api_key,
            kwargs=dict(
                app_id=app_id, user_id=user_id, query=query, stream=stream, conversation_id=conversation_id, files=files
            ),
        )
        try:
            async with aclosing(vendor_stream(payload, timeout=self.timeout)) as chunks:
                async for chunk in chunks:
                    yield chunk
        except TimeoutError:
            raise TboxAPIError("Tbox chat timed out", code="tbox.timeout", retryable=True) from None
        except (RuntimeError, ValueError):
            raise TboxAPIError("Tbox chat worker failed", code="tbox.chat_error") from None
