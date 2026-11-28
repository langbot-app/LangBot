"""Plugin-local bounded HTTP reads, matching native runtime safety budgets."""

from __future__ import annotations

import codecs

import httpx

MAX_RESPONSE_BYTES = 1024 * 1024
MAX_LINE_CHARS = 1024 * 1024
MAX_STREAM_BYTES = 16 * 1024 * 1024
MAX_STREAM_BUDGET_MB = 256
MAX_STREAM_BUDGET_BYTES = MAX_STREAM_BUDGET_MB * 1024 * 1024


async def limited_bytes(response, error, max_stream_bytes: int = MAX_STREAM_BYTES):
    if not isinstance(max_stream_bytes, int) or not 0 < max_stream_bytes <= MAX_STREAM_BUDGET_BYTES:
        raise error(f"Provider stream budget must be between 1 byte and {MAX_STREAM_BUDGET_BYTES} bytes")
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_stream_bytes:
            raise error(f"Provider stream budget exceeded: {total} bytes received, limit is {max_stream_bytes} bytes")
        yield chunk


async def limited_lines(
    response,
    error,
    max_stream_bytes: int = MAX_STREAM_BYTES,
    max_line_bytes: int = MAX_LINE_CHARS,
):
    def check(line: str) -> None:
        size = len(line.encode("utf-8"))
        if size > max_line_bytes:
            raise error(f"Provider event too large: {size} bytes in one event, limit is {max_line_bytes} bytes")

    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    buffer = ""
    async for chunk in limited_bytes(response, error, max_stream_bytes):
        buffer += decoder.decode(chunk)
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            check(line)
            yield line.rstrip("\r")
        check(buffer)
    buffer += decoder.decode(b"", final=True)
    if buffer:
        check(buffer)
        yield buffer.rstrip("\r")


async def limited_body(response, error):
    body = bytearray()
    async for chunk in response.aiter_bytes(chunk_size=8192):
        body.extend(chunk)
        if len(body) > MAX_RESPONSE_BYTES:
            raise error("Provider response exceeds the runtime limit")
    return bytes(body)


async def limited_post(client, url, error, **kwargs):
    # client.post() eagerly buffers the entire response before returning.
    async with client.stream("POST", url, **kwargs) as response:
        body = await limited_body(response, error)
        # aiter_bytes() has already decompressed the body. Do not decode twice.
        headers = dict(response.headers)
        headers.pop("content-encoding", None)
        headers.pop("content-length", None)
        return httpx.Response(response.status_code, headers=headers, content=body, request=response.request)
