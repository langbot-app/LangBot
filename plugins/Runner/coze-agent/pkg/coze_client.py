"""Coze API client for Runner.

This module provides a minimal Coze API client that doesn't depend on LangBot internals.
"""

from __future__ import annotations

import io
import json
import logging
import typing

import aiohttp

from pkg.endpoint import endpoint

logger = logging.getLogger(__name__)


class CozeAPIError(Exception):
    """Coze API error."""

    def __init__(self, message: str, code: str = "coze.api_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class CozeConfigError(Exception):
    """Coze configuration error."""

    def __init__(self, message: str, code: str = "coze.config_invalid"):
        self.message = message
        self.code = code
        super().__init__(message)


async def _bounded_body(response: aiohttp.ClientResponse) -> bytes:
    """Read upload/error bodies without aiohttp's unbounded buffering."""
    limit = 1024 * 1024
    length = response.headers.get("Content-Length")
    try:
        declared_size = int(length) if length is not None else 0
    except (TypeError, ValueError):
        declared_size = 0
    if declared_size > limit:
        raise CozeAPIError("Coze response exceeds the runtime limit", code="coze.response_limit")
    body = bytearray()
    async for chunk in response.content.iter_chunked(65536):
        if len(body) + len(chunk) > limit:
            raise CozeAPIError("Coze response exceeds the runtime limit", code="coze.response_limit")
        body.extend(chunk)
    return bytes(body)


class AsyncCozeClient:
    """Minimal Coze API client for Runner.

    Supports:
    - v3/chat (streaming chat messages)
    - v1/files/upload (file upload for multimodal input)
    """

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.coze.cn",
        timeout: float = 120.0,
    ):
        self.api_key = api_key
        self.api_base = endpoint(api_base).rstrip("/")
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                ssl=False if self.api_base.startswith("http://") else True,
                limit=100,
                limit_per_host=30,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
            )
            timeout = aiohttp.ClientTimeout(
                total=self.timeout,
                connect=30,
                sock_read=self.timeout,
            )
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "text/event-stream",
            }
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=timeout,
                connector=connector,
            )
        return self._session

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def upload_file(
        self,
        file_bytes: bytes,
        file_name: str = "file",
    ) -> str:
        """Upload file to Coze and return file ID.

        Args:
            file_bytes: File content as bytes
            file_name: File name

        Returns:
            str: File ID from Coze

        Raises:
            CozeAPIError: On upload failure
        """
        if len(file_bytes) > 10 * 1024 * 1024:
            raise CozeAPIError("Upload exceeds the 10 MiB size limit", code="coze.input_error")

        url = f"{self.api_base}/v1/files/upload"

        try:
            file_io = io.BytesIO(file_bytes)
            # Create a new session without the SSE Accept header for file upload
            upload_headers = {
                "Authorization": f"Bearer {self.api_key}",
            }
            async with aiohttp.ClientSession(headers=upload_headers) as upload_session:
                form = aiohttp.FormData()
                form.add_field("file", file_io, filename=file_name)

                async with upload_session.post(
                    url,
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    allow_redirects=False,
                ) as response:
                    if response.status == 401:
                        raise CozeAPIError(
                            "Coze API authentication failed, check API Key",
                            code="coze.auth_error",
                        )

                    response_body = await _bounded_body(response)

                    if response.status != 200:
                        raise CozeAPIError(
                            f"File upload failed: HTTP {response.status}",
                            code="coze.http_error",
                        )

                    try:
                        result = json.loads(response_body)
                    except (ValueError, UnicodeDecodeError):
                        raise CozeAPIError(
                            "File upload response is not valid JSON",
                            code="coze.response_invalid",
                        ) from None

                    if not isinstance(result, dict):
                        raise CozeAPIError("File upload response is not an object", code="coze.response_invalid")

                    if result.get("code") != 0:
                        raise CozeAPIError(
                            "Coze rejected the file upload",
                            code="coze.api_error",
                        )

                    data = result.get("data")
                    file_id = data.get("id") if isinstance(data, dict) else None
                    if not isinstance(file_id, str) or not file_id:
                        raise CozeAPIError("File upload response has no valid file id", code="coze.response_invalid")
                    return file_id

        except TimeoutError:
            raise CozeAPIError(
                "File upload timed out after 60s",
                code="coze.timeout",
            ) from None
        except CozeAPIError:
            raise
        except Exception:
            raise CozeAPIError(
                "File upload failed",
                code="coze.upload_error",
            ) from None

    async def chat_messages(
        self,
        bot_id: str,
        user_id: str,
        additional_messages: list[dict[str, typing.Any]] | None = None,
        conversation_id: str | None = None,
        auto_save_history: bool = True,
        custom_variables: dict[str, typing.Any] | None = None,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Send chat message with streaming response.

        Yields SSE events as dicts with keys:
        - event: Event type (e.g., 'conversation.message.delta', 'conversation.chat.completed')
        - data: Event data payload

        Args:
            bot_id: Coze Bot ID
            user_id: User identifier
            additional_messages: List of message objects with role, content, content_type
            conversation_id: Existing conversation ID for stateful session
            auto_save_history: Whether to save chat history
            custom_variables: Optional variables referenced by the bot prompt as
                {{key}} (e.g. a LangBot asset run token)

        Yields:
            Dict with 'event' and 'data' keys
        """
        session = await self._get_session()
        url = f"{self.api_base}/v3/chat"

        payload = {
            "bot_id": bot_id,
            "user_id": user_id,
            "stream": True,
            "auto_save_history": auto_save_history,
        }

        if additional_messages:
            payload["additional_messages"] = additional_messages

        if custom_variables:
            payload["custom_variables"] = custom_variables

        params = {}
        if conversation_id:
            params["conversation_id"] = conversation_id

        try:
            async with session.post(
                url,
                json=payload,
                params=params,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                if response.status == 401:
                    raise CozeAPIError(
                        "Coze API authentication failed, check API Key",
                        code="coze.auth_error",
                    )

                if response.status != 200:
                    await _bounded_body(response)
                    raise CozeAPIError(
                        f"Coze API request failed: HTTP {response.status}",
                        code="coze.http_error",
                    )

                # Parse SSE stream
                chunk_type = ""
                chunk_data = ""

                total_bytes = 0
                async for chunk in response.content:
                    total_bytes += len(chunk)
                    if len(chunk) > 1024 * 1024 or total_bytes > 16 * 1024 * 1024:
                        raise CozeAPIError("Coze stream exceeds the runtime limit", code="coze.response_limit")
                    chunk = chunk.decode("utf-8")
                    if chunk != "\n":
                        if chunk.startswith("event:"):
                            chunk_type = chunk.replace("event:", "", 1).strip()
                        elif chunk.startswith("data:"):
                            chunk_data = chunk.replace("data:", "", 1).strip()
                    else:
                        # Empty line signals end of event
                        if chunk_type:
                            yield {
                                "event": chunk_type,
                                "data": json.loads(chunk_data) if chunk_data else {},
                            }
                        chunk_type = ""
                        chunk_data = ""

        except TimeoutError:
            raise CozeAPIError(
                f"Coze API request timed out after {self.timeout}s",
                code="coze.timeout",
            ) from None
        except CozeAPIError:
            raise
        except Exception:
            raise CozeAPIError(
                "Coze API request failed",
                code="coze.api_error",
            ) from None


def process_thinking_content(content: str, remove_think: bool = False) -> tuple[str, str]:
    """Process thinking content (reasoning tags) in Coze responses.

    Handles <think>...</think> or 🤔...💬 style reasoning content.

    Args:
        content: Original content
        remove_think: Whether to remove thinking tags

    Returns:
        (processed_content, thinking_content)
    """
    import re

    thinking_content = ""

    # Handle 🤔...💬 style reasoning (used by some Coze deployments)
    if content and "🤔" in content and "💬" in content:
        think_pattern = r"🤔(.*?)💬"
        think_matches = re.findall(think_pattern, content, re.DOTALL)
        if think_matches:
            thinking_content = "\n".join(think_matches)
            content = re.sub(think_pattern, "", content, flags=re.DOTALL).strip()

    # Handle <think>...</think> style reasoning
    if content and "<think>" in content and "</think>" in content:
        think_pattern = r"<think>(.*?)</think>"
        think_matches = re.findall(think_pattern, content, re.DOTALL)
        if think_matches:
            thinking_content = (
                "\n".join(think_matches) if not thinking_content else thinking_content + "\n" + "\n".join(think_matches)
            )
            content = re.sub(think_pattern, "", content, flags=re.DOTALL).strip()

    if remove_think:
        return content, ""
    else:
        if thinking_content:
            content = f"🤔\n{thinking_content}\n💬\n{content}".strip()
        return content, thinking_content
