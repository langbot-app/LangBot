"""Custom menu management through the Official Account server API."""

import json
import typing

import httpx

from .access_token import TOKEN_REJECTED_CODES, AccessToken


class OfficialAccountAPIError(RuntimeError):
    """A nonzero ``errcode`` returned by the WeChat server API."""

    def __init__(self, errcode: int, errmsg: str = ''):
        self.errcode = int(errcode)
        self.errmsg = str(errmsg or '')
        super().__init__(f'OfficialAccount API error: errcode={self.errcode} errmsg={self.errmsg}')


class MenuAPI:
    def __init__(self, access_token: AccessToken, base_url: str):
        self.access_token = access_token
        self.base_url = base_url.rstrip('/')

    async def _call(self, method: str, path: str, body: dict | None = None) -> dict[str, typing.Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(2):
                token, errcode = await self.access_token.get(client)
                if errcode:
                    raise OfficialAccountAPIError(errcode, 'access_token request rejected')
                kwargs: dict[str, typing.Any] = {'params': {'access_token': token}}
                if body is not None:
                    # WeChat rejects \uXXXX escapes in button names, so send raw UTF-8.
                    kwargs['content'] = json.dumps(body, ensure_ascii=False).encode('utf-8')
                    kwargs['headers'] = {'Content-Type': 'application/json; charset=utf-8'}
                response = await client.request(method, f'{self.base_url}{path}', **kwargs)
                if response.status_code != 200:
                    raise RuntimeError(f'OfficialAccount menu API HTTP {response.status_code}')
                data = response.json()
                code = int(data.get('errcode') or 0)
                if code in TOKEN_REJECTED_CODES and attempt == 0:
                    self.access_token.invalidate()
                    continue
                if code:
                    raise OfficialAccountAPIError(code, data.get('errmsg', ''))
                return data
        raise RuntimeError('OfficialAccount token refresh failed')

    async def get_menu(self) -> dict[str, typing.Any] | None:
        """Return the menu published through the API, or ``None`` when none exists."""
        try:
            return await self._call('GET', '/cgi-bin/menu/get')
        except OfficialAccountAPIError as exc:
            if exc.errcode == 46003:
                return None
            raise

    async def get_current_selfmenu_info(self) -> dict[str, typing.Any]:
        """Return the menu currently configured for the account, including web-console menus."""
        return await self._call('GET', '/cgi-bin/get_current_selfmenu_info')

    async def create_menu(self, menu: dict[str, typing.Any]) -> None:
        await self._call('POST', '/cgi-bin/menu/create', menu)

    async def delete_menu(self) -> None:
        await self._call('GET', '/cgi-bin/menu/delete')
