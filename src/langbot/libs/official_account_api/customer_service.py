"""Optional asynchronous replies through WeChat's customer service API."""

import httpx

from .access_token import TOKEN_REJECTED_CODES, AccessToken


class CustomerServiceReplies:
    def __init__(self, appid: str, secret: str, base_url: str, access_token: AccessToken | None = None):
        self.base_url = base_url.rstrip('/')
        self.access_token = access_token or AccessToken(appid, secret, base_url)

    async def send(self, user_id: str, content: str) -> int:
        # Retry only explicit token rejection, never an ambiguous network failure.
        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(2):
                token, errcode = await self.access_token.get(client)
                if errcode:
                    return errcode
                response = await client.post(
                    f'{self.base_url}/cgi-bin/message/custom/send',
                    params={'access_token': token},
                    json={'touser': user_id, 'msgtype': 'text', 'text': {'content': content}},
                )
                if response.status_code != 200:
                    raise RuntimeError(f'OfficialAccount customer message HTTP {response.status_code}')
                code = int(response.json()['errcode'])
                if code in TOKEN_REJECTED_CODES and attempt == 0:
                    self.access_token.invalidate()
                    continue
                return code
        raise RuntimeError('OfficialAccount token refresh failed')
