"""Requester-local connections, retired only after their active leases finish."""

from contextlib import asynccontextmanager
import asyncio
import re

import httpx

from .errors import RequesterError


class _CompletedSSEStream(httpx.AsyncByteStream):
    """Finish bounded HTTP framing before SDKs stop at the SSE DONE record."""

    _done = re.compile(rb'\ndata: ?\[DONE\]\r?\n\r?\n')

    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        iterator = self.stream.__aiter__()
        tail = b'\n'
        async for chunk in iterator:
            probe = tail + chunk
            if self._done.search(probe):
                # SDK parsers stop at [DONE] before httpcore observes EOF. This
                # otherwise discards the connection on every successful stream.
                # Do not drain on cancellation, truncation, or merely a finish
                # reason: providers can still send usage before the DONE record.
                try:
                    async with asyncio.timeout(0.05):
                        drained = 0
                        async for extra in iterator:
                            drained += len(extra)
                            if drained >= 65536:
                                break
                except (TimeoutError, httpx.HTTPError):
                    pass
                yield chunk
                return
            tail = probe[-32:]
            yield chunk

    async def aclose(self):
        await self.stream.aclose()


async def _finish_sse_body(response):
    if response.headers.get('content-type', '').split(';')[0].strip() == 'text/event-stream':
        response.stream = _CompletedSSEStream(response.stream)


class RequesterHTTPPool:
    def __init__(self, *, follow_redirects=False, drain_sse=False):
        self.client = None
        self.active = 0
        self.retired = False
        self.follow_redirects = follow_redirects
        self.drain_sse = drain_sse
        self._creation_lock = asyncio.Lock()

    @asynccontextmanager
    async def lease(self):
        if self.retired:
            raise RequesterError('Provider has been retired', code='provider_retired')
        if self.client is None:
            async with self._creation_lock:
                if self.retired:
                    raise RequesterError('Provider has been retired', code='provider_retired')
                if self.client is None:
                    # HTTPX otherwise reloads the same CA bundle for its direct
                    # transport and each environment proxy mount. Load it once,
                    # off the event loop, preserving HTTPX's TLS/env semantics.
                    # Cancellation here leaves no open HTTP client or sockets.
                    ssl_context = await asyncio.to_thread(httpx.create_ssl_context)
                    if self.retired:
                        raise RequesterError('Provider has been retired', code='provider_retired')
                    # Auth and deadlines remain request-local. No pool or TLS
                    # context is shared across runtime providers.
                    self.client = httpx.AsyncClient(
                        verify=ssl_context,
                        follow_redirects=self.follow_redirects,
                        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=30),
                        event_hooks={'response': [_finish_sse_body]} if self.drain_sse else None,
                    )
        self.active += 1
        try:
            yield self.client
        finally:
            self.active -= 1
            if self.retired and not self.active:
                await self._close()

    async def _close(self):
        client, self.client = self.client, None
        if client is not None:
            await client.aclose()

    async def aclose(self):
        self.retired = True
        if not self.active:
            await self._close()


@asynccontextmanager
async def requester_http_client(owner):
    pool = getattr(owner, '_http_pool', None)
    if pool is not None:
        async with pool.lease() as client:
            yield client
    else:
        # Preserve direct/uninitialized requester use by older extensions/tests.
        async with httpx.AsyncClient(follow_redirects=False) as client:
            yield client
