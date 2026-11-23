"""Optional asynchronous replies through WeChat's customer service API."""

import asyncio
import time

import httpx


class CustomerServiceReplies:
    def __init__(self, appid: str, secret: str, base_url: str):
        self.appid = appid
        self.secret = secret
        self.base_url = base_url.rstrip('/')
        self._token = ''
        self._expires = 0.0
        self._lock = asyncio.Lock()

    async def send(self, user_id: str, content: str) -> int:
        # Retry only explicit token rejection, never an ambiguous network failure.
        async with self._lock, httpx.AsyncClient(timeout=20) as client:
            for attempt in range(2):
                if time.monotonic() >= self._expires:
                    response = await client.get(
                        f'{self.base_url}/cgi-bin/token',
                        params={'grant_type': 'client_credential', 'appid': self.appid, 'secret': self.secret},
                    )
                    if response.status_code != 200:
                        raise RuntimeError(f'OfficialAccount token request HTTP {response.status_code}')
                    data = response.json()
                    if data.get('errcode'):
                        return int(data['errcode'])
                    self._token = data['access_token']
                    self._expires = time.monotonic() + max(0, int(data['expires_in']) - 120)
                response = await client.post(
                    f'{self.base_url}/cgi-bin/message/custom/send',
                    params={'access_token': self._token},
                    json={'touser': user_id, 'msgtype': 'text', 'text': {'content': content}},
                )
                if response.status_code != 200:
                    raise RuntimeError(f'OfficialAccount customer message HTTP {response.status_code}')
                code = int(response.json()['errcode'])
                if code in {40001, 40014, 42001} and attempt == 0:
                    self._expires = 0.0
                    continue
                return code
        raise RuntimeError('OfficialAccount token refresh failed')
