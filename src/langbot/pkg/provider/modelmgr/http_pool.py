"""Requester-local connections, retired only after their active leases finish."""

from contextlib import asynccontextmanager

import httpx

from .errors import RequesterError


class RequesterHTTPPool:
    def __init__(self, *, follow_redirects=False):
        self.client = None
        self.active = 0
        self.retired = False
        self.follow_redirects = follow_redirects

    @asynccontextmanager
    async def lease(self):
        if self.retired:
            raise RequesterError('Provider has been retired', code='provider_retired')
        if self.client is None:
            # Authentication and timeouts belong to individual requests, not the
            # shared client. Never share this pool across runtime providers.
            self.client = httpx.AsyncClient(
                follow_redirects=self.follow_redirects,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=30),
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
