"""Shared access_token cache for Official Account server APIs."""

import asyncio
import time

import httpx

# WeChat answers these when the cached token is no longer accepted.
TOKEN_REJECTED_CODES = frozenset({40001, 40014, 42001})


class AccessToken:
    """One cached access_token per Official Account client.

    Customer-service sends and menu management share this cache: requesting a
    new token through ``cgi-bin/token`` from two independent caches would make
    each one keep invalidating the other.
    """

    def __init__(self, appid: str, secret: str, base_url: str):
        self.appid = appid
        self.secret = secret
        self.base_url = base_url.rstrip('/')
        self._token = ''
        self._expires = 0.0
        self._lock = asyncio.Lock()

    def invalidate(self) -> None:
        self._expires = 0.0

    async def get(self, client: httpx.AsyncClient) -> tuple[str, int]:
        """Return ``(token, 0)`` or ``('', errcode)`` when WeChat rejects the credentials."""
        async with self._lock:
            if self._token and time.monotonic() < self._expires:
                return self._token, 0
            response = await client.get(
                f'{self.base_url}/cgi-bin/token',
                params={'grant_type': 'client_credential', 'appid': self.appid, 'secret': self.secret},
            )
            if response.status_code != 200:
                raise RuntimeError(f'OfficialAccount token request HTTP {response.status_code}')
            data = response.json()
            if data.get('errcode'):
                return '', int(data['errcode'])
            self._token = data['access_token']
            self._expires = time.monotonic() + max(0, int(data['expires_in']) - 120)
            return self._token, 0
