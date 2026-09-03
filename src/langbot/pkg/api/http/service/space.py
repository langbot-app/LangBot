from __future__ import annotations

from collections import OrderedDict

from langbot.pkg.utils import httpclient
import typing
import datetime
import time
import sqlalchemy

from ....core import app
from ....entity.persistence import user
from ....entity.dto.space_model import SpaceModel
from ....entity.dto.space_model import SpaceModelSelection
from ....entity.persistence import model as persistence_model
from ....cloud.model_catalog import LANGBOT_MODELS_PROVIDER_REQUESTER


_CREDITS_CACHE_TTL_SECONDS = 60
_CREDITS_CACHE_MAX_ENTRIES = 4096


class SpaceService:
    """Service for interacting with LangBot Space API"""

    ap: app.Application
    _credits_cache: typing.Dict[str, typing.Tuple[int, float]]  # {user_email: (credits, timestamp)}

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self._credits_cache = OrderedDict()

    def _ordered_credits_cache(
        self,
    ) -> OrderedDict[str, tuple[int, float]]:
        if not isinstance(self._credits_cache, OrderedDict):
            # Preserve compatibility with tests and callers that seed the cache.
            self._credits_cache = OrderedDict(self._credits_cache)
        return self._credits_cache

    def _prune_credits_cache(self, now: float) -> None:
        cache = self._ordered_credits_cache()
        while cache:
            email = next(iter(cache))
            _, cached_at = cache[email]
            if now - cached_at < _CREDITS_CACHE_TTL_SECONDS:
                break
            cache.pop(email, None)

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

    async def get_valid_access_token(self, user_email: str) -> str | None:
        """Return a current Space bearer, refreshing and persisting it when needed."""
        return await self._ensure_valid_token(user_email)

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
        from urllib.parse import urlencode

        space_config = self._get_space_config()
        authorize_url = space_config['oauth_authorize_url']
        params = {'redirect_uri': redirect_uri}
        if state:
            params['state'] = state
        return f'{authorize_url}?{urlencode(params)}'

    def get_cloud_entry_url(self) -> str:
        """Return the Space-owned Cloud selector for a Cloud Account login."""

        return f'{self._get_space_config()["url"].rstrip("/")}/cloud?environment=beta&auto_launch=1'

    async def exchange_oauth_code(
        self,
        code: str,
        workspace_uuids: list[str] | None = None,
        workspace_created_ats: dict[str, int] | None = None,
    ) -> typing.Dict:
        """Exchange OAuth authorization code for tokens"""
        from langbot.pkg.utils import constants

        space_config = self._get_space_config()
        space_url = space_config['url']

        session = httpclient.get_session()
        async with session.post(
            f'{space_url}/api/v1/accounts/oauth/token',
            json={
                'code': code,
                'instance_id': constants.instance_id,
                # Sending an explicit empty list tells new Space servers not to
                # synthesize a legacy instance-derived Workspace binding.
                'workspace_uuids': workspace_uuids if workspace_uuids is not None else [],
                'workspace_created_ats': workspace_created_ats or {},
            },
        ) as response:
            if response.status != 200:
                error = await httpclient.read_text_limited(response)
                raise ValueError(f'Failed to exchange OAuth code: {error}')
            data = await httpclient.read_json_limited(response)
            if data.get('code') != 0:
                raise ValueError(f'Failed to exchange OAuth code: {data.get("msg")}')
            return data.get('data', {})

    async def refresh_token(self, refresh_token: str) -> typing.Dict:
        """Refresh Space access token"""
        space_config = self._get_space_config()
        space_url = space_config['url']

        session = httpclient.get_session()
        async with session.post(
            f'{space_url}/api/v1/accounts/token/refresh', json={'refresh_token': refresh_token}
        ) as response:
            if response.status != 200:
                error = await httpclient.read_text_limited(response)
                raise ValueError(f'Failed to refresh token: {error}')
            data = await httpclient.read_json_limited(response)
            if data.get('code') != 0:
                raise ValueError(f'Failed to refresh token: {data.get("msg")}')
            return data.get('data', {})

    async def get_user_info_raw(self, access_token: str) -> typing.Dict:
        """Get user info from Space using access token (no validation)"""
        space_config = self._get_space_config()
        space_url = space_config['url']

        session = httpclient.get_session()
        async with session.get(
            f'{space_url}/api/v1/accounts/me', headers={'Authorization': f'Bearer {access_token}'}
        ) as response:
            if response.status != 200:
                error = await httpclient.read_text_limited(response)
                raise ValueError(f'Failed to get user info: {error}')
            data = await httpclient.read_json_limited(response)
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
        now = time.time()
        cached_fallback = self._credits_cache.get(user_email)
        self._prune_credits_cache(now)

        if not force_refresh and user_email in self._credits_cache:
            credits, ts = self._credits_cache[user_email]
            if now - ts < _CREDITS_CACHE_TTL_SECONDS:
                return credits

        try:
            info = await self.get_user_info(user_email)
            if info is None:
                return None
            credits = info.get('credits')
            if credits is not None:
                cache = self._ordered_credits_cache()
                cache.pop(user_email, None)
                if len(cache) >= _CREDITS_CACHE_MAX_ENTRIES:
                    cache.popitem(last=False)
                cache[user_email] = (credits, time.time())
            return credits
        except Exception:
            return cached_fallback[0] if cached_fallback is not None else None

    async def get_models(self) -> typing.List[SpaceModel]:
        """Get models from Space"""

        space_config = self._get_space_config()
        space_url = space_config['url']

        session = httpclient.get_session()
        async with session.get(f'{space_url}/api/v1/models', params={'page_size': 100}) as response:
            if response.status != 200:
                error = await httpclient.read_text_limited(response)
                raise ValueError(f'Failed to get models: {error}')
            data = await httpclient.read_json_limited(response)
            if data.get('code') != 0:
                raise ValueError(f'Failed to get models: {data.get("msg")}')
            models_data = data.get('data', {}).get('models', [])
            return [SpaceModel.model_validate(model_dict) for model_dict in models_data]

    async def get_model_selection(self, category: str) -> typing.List[SpaceModelSelection]:
        """Return Space models in the availability-ranked selection order."""
        space_url = self._get_space_config()['url']
        session = httpclient.get_session()
        async with session.get(
            f'{space_url}/api/v1/models/selection',
            params={'category': category},
        ) as response:
            if response.status != 200:
                error = await httpclient.read_text_limited(response)
                raise ValueError(f'Failed to get model selection: {error}')
            payload = await httpclient.read_json_limited(response)
            if payload.get('code') != 0:
                raise ValueError(f'Failed to get model selection: {payload.get("msg")}')

            data = payload.get('data', [])
            if isinstance(data, dict):
                data = data.get('models', data.get('items', []))
            if not isinstance(data, list):
                raise ValueError('Failed to get model selection: invalid response')

            models = []
            for selection in data:
                if isinstance(selection, dict) and isinstance(selection.get('model'), dict):
                    models.append(selection['model'])
                else:
                    models.append(selection)
            return [SpaceModelSelection.model_validate(model) for model in models]

    async def get_recommended_chat_model(self, context: typing.Any) -> dict:
        """Resolve Space's first ranked chat model to a local Workspace model."""
        selection = await self.get_model_selection('chat')
        if not selection:
            raise ValueError('No recommended chat model is available')
        recommended = selection[0]

        async def find_local_model():
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_model.LLMModel)
                .join(
                    persistence_model.ModelProvider,
                    sqlalchemy.and_(
                        persistence_model.ModelProvider.workspace_uuid == persistence_model.LLMModel.workspace_uuid,
                        persistence_model.ModelProvider.uuid == persistence_model.LLMModel.provider_uuid,
                    ),
                )
                .where(
                    persistence_model.LLMModel.workspace_uuid == context.workspace_uuid,
                    persistence_model.ModelProvider.requester == LANGBOT_MODELS_PROVIDER_REQUESTER,
                    sqlalchemy.or_(
                        persistence_model.LLMModel.uuid == recommended.uuid,
                        persistence_model.LLMModel.name == recommended.model_id,
                    ),
                )
            )
            return result.first()

        local_model = await find_local_model()
        if local_model is None:
            # OSS synchronizes the public catalog locally. Refresh once in case
            # the recommendation was published after this process started.
            from ..context import ExecutionContext

            try:
                await self.ap.model_mgr.sync_new_models_from_space(ExecutionContext.from_request(context))
            except Exception:
                pass
            local_model = await find_local_model()

        if local_model is None:
            raise ValueError('Recommended chat model is not available in this Workspace')
        return {'uuid': local_model.uuid, 'name': local_model.name}
