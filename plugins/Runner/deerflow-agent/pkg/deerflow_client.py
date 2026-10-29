"""DeerFlow LangGraph HTTP API client for Runner.

Ported from LangBot's legacy core DeerFlow client and kept plugin-local so the
runner can be distributed without importing LangBot core modules.
"""

from __future__ import annotations

import codecs
import json
import typing
from collections.abc import AsyncGenerator

import httpx

from pkg.deadline import deadline
from pkg.endpoint import endpoint
from pkg.errors import DeerFlowAPIError
from pkg.http_limits import limited_body, limited_bytes, limited_post

SSE_MAX_BUFFER_CHARS = 1_048_576


def _normalize_sse_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _parse_sse_data_lines(data_lines: list[str]) -> typing.Any:
    raw_data = "\n".join(data_lines)
    try:
        return json.loads(raw_data)
    except json.JSONDecodeError:
        parsed_lines: list[typing.Any] = []
        can_parse_all = True
        for line in data_lines:
            line = line.strip()
            if not line:
                continue
            try:
                parsed_lines.append(json.loads(line))
            except json.JSONDecodeError:
                can_parse_all = False
                break
        if can_parse_all and parsed_lines:
            return parsed_lines[0] if len(parsed_lines) == 1 else parsed_lines
        return raw_data


def _parse_sse_block(block: str) -> dict[str, typing.Any] | None:
    if not block.strip():
        return None

    event_name = "message"
    data_lines: list[str] = []
    for line in block.splitlines():
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    if not data_lines:
        return None
    return {"event": event_name, "data": _parse_sse_data_lines(data_lines)}


class AsyncDeerFlowClient:
    """Minimal DeerFlow LangGraph HTTP API client."""

    def __init__(
        self,
        api_base: str = "http://127.0.0.1:2026",
        api_key: str = "",
        auth_header: str = "",
    ) -> None:
        self.api_base = endpoint(api_base).rstrip("/")
        self.headers: dict[str, str] = {}
        if auth_header:
            self.headers["Authorization"] = auth_header
        elif api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    @deadline
    async def create_thread(self, timeout: float = 20) -> dict[str, typing.Any]:
        """Create a new LangGraph thread."""
        url = f"{self.api_base}/api/langgraph/threads"
        payload = {"metadata": {}}

        try:
            async with httpx.AsyncClient(trust_env=False, timeout=timeout) as http_client:
                response = await limited_post(
                    http_client,
                    url,
                    DeerFlowAPIError,
                    headers=self.headers,
                    json=payload,
                )
        except httpx.TimeoutException:
            raise DeerFlowAPIError(
                f"DeerFlow create thread timed out after {timeout}s",
                operation="create thread",
                url=url,
                code="deerflow.timeout",
                retryable=True,
            ) from None
        if response.status_code not in (200, 201):
            raise DeerFlowAPIError(
                operation="create thread",
                status=response.status_code,
                body=response.text,
                url=url,
                code="deerflow.http_error",
            )
        return response.json()

    @deadline
    async def stream_run(
        self,
        thread_id: str,
        payload: dict[str, typing.Any],
        timeout: float = 120,
    ) -> AsyncGenerator[dict[str, typing.Any], None]:
        """Run a LangGraph stream request and yield parsed SSE events."""
        url = f"{self.api_base}/api/langgraph/threads/{thread_id}/runs/stream"
        stream_timeout = httpx.Timeout(
            connect=min(timeout, 30),
            read=timeout,
            write=timeout,
            pool=timeout,
        )

        try:
            async with httpx.AsyncClient(trust_env=False, timeout=stream_timeout) as http_client:
                async with http_client.stream(
                    "POST",
                    url,
                    headers={
                        **self.headers,
                        "Accept": "text/event-stream",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        body = await limited_body(response, DeerFlowAPIError)
                        raise DeerFlowAPIError(
                            operation="runs/stream request",
                            status=response.status_code,
                            body=body.decode("utf-8", errors="replace"),
                            url=url,
                            thread_id=thread_id,
                            code="deerflow.http_error",
                        )

                    decoder = codecs.getincrementaldecoder("utf-8")("replace")
                    buffer = ""

                    async for chunk in limited_bytes(response, DeerFlowAPIError):
                        buffer += _normalize_sse_newlines(decoder.decode(chunk))

                        while "\n\n" in buffer:
                            block, buffer = buffer.split("\n\n", 1)
                            if len(block) > SSE_MAX_BUFFER_CHARS:
                                raise DeerFlowAPIError("DeerFlow event exceeds the runtime limit")
                            parsed = _parse_sse_block(block)
                            if parsed is not None:
                                yield parsed

                        if len(buffer) > SSE_MAX_BUFFER_CHARS:
                            raise DeerFlowAPIError("DeerFlow event exceeds the runtime limit")

                    buffer += _normalize_sse_newlines(decoder.decode(b"", final=True))
                    while "\n\n" in buffer:
                        block, buffer = buffer.split("\n\n", 1)
                        parsed = _parse_sse_block(block)
                        if parsed is not None:
                            yield parsed
                    if buffer.strip():
                        parsed = _parse_sse_block(buffer)
                        if parsed is not None:
                            yield parsed
        except httpx.TimeoutException:
            raise DeerFlowAPIError(
                f"DeerFlow stream timed out after {timeout}s",
                operation="runs/stream request",
                url=url,
                thread_id=thread_id,
                code="deerflow.timeout",
                retryable=True,
            ) from None
