from __future__ import annotations

import aiohttp
import typing
import datetime
import time
import sqlalchemy

from ....core import app
from ....entity.persistence import user
from ....entity.dto.space_model import SpaceModel


class SpaceService:
    """Service for interacting with LangBot Space API"""

    ap: app.Application
    _credits_cache: typing.Dict[str, typing.Tuple[int, float]]  # {user_email: (credits, timestamp)}

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self._credits_cache = {}

    def _get_space_config(self) -> typing.Dict[str, str]:
        """Get Space configuration from config file"""
        space_config = self.ap.instance_config.data.get('space', {})
        return {
            'url': space_config.get('url', 'https://space.langbot.app'),
            'oauth_authorize_url': space_config.get('oauth_authorize_url', 'https://space.langbot.app/auth/authorize'),
        }

    async def _get_user_by_email(self, user_email: str) -> user.User | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(user.User).where(user.User.user == user_email)
        )
        result_list = result.all()
        return result_list[0] if result_list else None

    async def _ensure_valid_token(self, user_email: str) -> str | None:
        """Ensure access token is valid, refresh if expired. Returns valid access_token or None."""
        user_obj = await self._get_user_by_email(user_email)
        if not user_obj or user_obj.account_type != 'space':
            return None

        if not user_obj.space_access_token:
            return None

        # Check if token is expired (with 60s buffer)
        if user_obj.space_access_token_expires_at:
            if datetime.datetime.now() >= user_obj.space_access_token_expires_at - datetime.timedelta(seconds=60):
                # Token expired, try to refresh
                if user_obj.space_refresh_token:
                    try:
                        new_token = await self._refresh_and_save_token(user_obj)
                        return new_token
                    except Exception:
                        return None
                return None

        return user_obj.space_access_token

    async def _refresh_and_save_token(self, user_obj: user.User) -> str:
        """Refresh token and save to database"""
        token_data = await self.refresh_token(user_obj.space_refresh_token)
        access_token = token_data.get('access_token')
        expires_in = token_data.get('expires_in', 0)

        if not access_token:
            raise ValueError('Failed to refresh token')

        expires_at = datetime.datetime.now() + datetime.timedelta(seconds=expires_in) if expires_in > 0 else None

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(user.User)
            .where(user.User.user == user_obj.user)
            .values(
                space_access_token=access_token,
                space_access_token_expires_at=expires_at,
            )
        )

        return access_token

    # === Raw API calls (no token validation) ===

    def get_oauth_authorize_url(self, redirect_uri: str, state: str = '') -> str:
        """Get the Space OAuth authorization URL for redirect"""
        space_config = self._get_space_config()
        authorize_url = space_config['oauth_authorize_url']
        params = f'redirect_uri={redirect_uri}'
        if state:
            params += f'&state={state}'
        return f'{authorize_url}?{params}'

    async def exchange_oauth_code(self, code: str) -> typing.Dict:
        """Exchange OAuth authorization code for tokens"""
        from langbot.pkg.utils import constants

        space_config = self._get_space_config()
        space_url = space_config['url']

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{space_url}/api/v1/accounts/oauth/token',
                json={'code': code, 'instance_id': constants.instance_id},
            ) as response:
                if response.status != 200:
                    raise ValueError(f'Failed to exchange OAuth code: {await response.text()}')
                data = await response.json()
                if data.get('code') != 0:
                    raise ValueError(f'Failed to exchange OAuth code: {data.get("msg")}')
                return data.get('data', {})

    async def refresh_token(self, refresh_token: str) -> typing.Dict:
        """Refresh Space access token"""
        space_config = self._get_space_config()
        space_url = space_config['url']

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{space_url}/api/v1/accounts/token/refresh', json={'refresh_token': refresh_token}
            ) as response:
                if response.status != 200:
                    raise ValueError(f'Failed to refresh token: {await response.text()}')
                data = await response.json()
                if data.get('code') != 0:
                    raise ValueError(f'Failed to refresh token: {data.get("msg")}')
                return data.get('data', {})

    async def get_user_info_raw(self, access_token: str) -> typing.Dict:
        """Get user info from Space using access token (no validation)"""
        space_config = self._get_space_config()
        space_url = space_config['url']

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{space_url}/api/v1/accounts/me', headers={'Authorization': f'Bearer {access_token}'}
            ) as response:
                if response.status != 200:
                    raise ValueError(f'Failed to get user info: {await response.text()}')
                data = await response.json()
                if data.get('code') != 0:
                    raise ValueError(f'Failed to get user info: {data.get("msg")}')
                return data.get('data', {})

    # === API calls with token validation ===

    async def get_user_info(self, user_email: str) -> typing.Dict | None:
        """Get user info from Space (with token validation)"""
        access_token = await self._ensure_valid_token(user_email)
        if not access_token:
            return None
        return await self.get_user_info_raw(access_token)

    async def get_credits(self, user_email: str, force_refresh: bool = False) -> int | None:
        """Get Space credits for user with caching (60s TTL)"""
        cache_ttl = 60

        if not force_refresh and user_email in self._credits_cache:
            credits, ts = self._credits_cache[user_email]
            if time.time() - ts < cache_ttl:
                return credits

        try:
            info = await self.get_user_info(user_email)
            if info is None:
                return None
            credits = info.get('credits')
            if credits is not None:
                self._credits_cache[user_email] = (credits, time.time())
            return credits
        except Exception:
            return self._credits_cache.get(user_email, (None, 0))[0]

    async def get_models(self) -> typing.List[SpaceModel]:
        """Get models from Space"""

        space_config = self._get_space_config()
        space_url = space_config['url']

        async with aiohttp.ClientSession() as session:
            async with session.get(f'{space_url}/api/v1/models') as response:
                if response.status != 200:
                    raise ValueError(f'Failed to get models: {await response.text()}')
                data = await response.json()
                if data.get('code') != 0:
                    raise ValueError(f'Failed to get models: {data.get("msg")}')
                models_data = data.get('data', {}).get('models', [])
                return [SpaceModel.model_validate(model_dict) for model_dict in models_data]
