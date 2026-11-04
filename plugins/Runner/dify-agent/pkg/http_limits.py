"""Plugin-local bounded HTTP reads, matching native runtime safety budgets."""

from __future__ import annotations

import codecs

import httpx

MAX_RESPONSE_BYTES = 1024 * 1024
MAX_LINE_CHARS = 1024 * 1024
MAX_STREAM_BYTES = 16 * 1024 * 1024


async def limited_bytes(response, error, max_stream_bytes: int = MAX_STREAM_BYTES):
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_stream_bytes:
            raise error(f"Provider stream budget exceeded: {total} bytes received, limit is {max_stream_bytes} bytes")
        yield chunk


async def limited_lines(response, error, max_stream_bytes: int = MAX_STREAM_BYTES):
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    buffer = ""
    async for chunk in limited_bytes(response, error, max_stream_bytes):
        buffer += decoder.decode(chunk)
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if len(line.encode("utf-8")) > MAX_LINE_CHARS:
                raise error("Provider event exceeds the runtime limit")
            yield line.rstrip("\r")
        if len(buffer.encode("utf-8")) > MAX_LINE_CHARS:
            raise error("Provider event exceeds the runtime limit")
    buffer += decoder.decode(b"", final=True)
    if buffer:
        if len(buffer.encode("utf-8")) > MAX_LINE_CHARS:
            raise error("Provider event exceeds the runtime limit")
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
