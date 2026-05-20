"""
Unit tests for SpaceService.

Tests LangBot Space API interactions including:
- OAuth URL generation
- Token exchange and refresh
- User info retrieval
- Credits caching
- Model listing

Source: src/langbot/pkg/api/http/service/space.py
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from types import SimpleNamespace
import datetime
import time

from langbot.pkg.api.http.service.space import SpaceService
from langbot.pkg.entity.persistence.user import User


pytestmark = pytest.mark.asyncio


def _create_mock_user(
    email: str = 'test@example.com',
    account_type: str = 'space',
    space_account_uuid: str = 'space-uuid-123',
    space_access_token: str = 'access_token_123',
    space_refresh_token: str = 'refresh_token_123',
    space_access_token_expires_at: datetime.datetime = None,
) -> Mock:
    """Helper to create mock User entity."""
    user = Mock(spec=User)
    user.user = email
    user.account_type = account_type
    user.space_account_uuid = space_account_uuid
    user.space_access_token = space_access_token
    user.space_refresh_token = space_refresh_token
    user.space_access_token_expires_at = space_access_token_expires_at
    return user


def _create_mock_result(items: list = None, first_item=None):
    """Create mock result object for persistence queries."""
    result = Mock()
    result.all = Mock(return_value=items or [])
    result.first = Mock(return_value=first_item)
    return result


class TestSpaceServiceGetOAuthAuthorizeUrl:
    """Tests for get_oauth_authorize_url method."""

    def test_get_oauth_authorize_url_basic(self):
        """Returns OAuth URL with redirect_uri."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {
            'space': {
                'oauth_authorize_url': 'https://space.langbot.app/auth/authorize',
            }
        }

        service = SpaceService(ap)

        # Execute
        result = service.get_oauth_authorize_url('http://localhost/callback')

        # Verify
        assert 'redirect_uri=http://localhost/callback' in result
        assert 'https://space.langbot.app/auth/authorize' in result

    def test_get_oauth_authorize_url_with_state(self):
        """Returns OAuth URL with redirect_uri and state."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {
            'space': {
                'oauth_authorize_url': 'https://space.langbot.app/auth/authorize',
            }
        }

        service = SpaceService(ap)

        # Execute
        result = service.get_oauth_authorize_url('http://localhost/callback', state='random_state')

        # Verify
        assert 'redirect_uri=http://localhost/callback' in result
        assert 'state=random_state' in result

    def test_get_oauth_authorize_url_default_config(self):
        """Uses default OAuth URL when config not set."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}

        service = SpaceService(ap)

        # Execute
        result = service.get_oauth_authorize_url('http://localhost/callback')

        # Verify - uses default URL
        assert 'https://space.langbot.app/auth/authorize' in result


class TestSpaceServiceGetUserByEmail:
    """Tests for _get_user_by_email internal method."""

    async def test_get_user_by_email_found(self):
        """Returns user when found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_user = _create_mock_user(email='found@example.com')
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Execute
        result = await service._get_user_by_email('found@example.com')

        # Verify
        assert result is not None
        assert result.user == 'found@example.com'

    async def test_get_user_by_email_not_found(self):
        """Returns None when user not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Execute
        result = await service._get_user_by_email('notfound@example.com')

        # Verify
        assert result is None


class TestSpaceServiceEnsureValidToken:
    """Tests for _ensure_valid_token internal method."""

    async def test_ensure_valid_token_user_not_found(self):
        """Returns None when user not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Execute
        result = await service._ensure_valid_token('notfound@example.com')

        # Verify
        assert result is None

    async def test_ensure_valid_token_not_space_account(self):
        """Returns None when user is not a space account."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_user = _create_mock_user(email='local@example.com', account_type='local')
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Execute
        result = await service._ensure_valid_token('local@example.com')

        # Verify
        assert result is None

    async def test_ensure_valid_token_no_access_token(self):
        """Returns None when user has no access token."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_user = _create_mock_user(space_access_token=None)
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Execute
        result = await service._ensure_valid_token('test@example.com')

        # Verify
        assert result is None

    async def test_ensure_valid_token_valid_token(self):
        """Returns valid access token when not expired."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        # Token expires in 1 hour (valid)
        mock_user = _create_mock_user(
            space_access_token='valid_token',
            space_access_token_expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),
        )
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Execute
        result = await service._ensure_valid_token('test@example.com')

        # Verify
        assert result == 'valid_token'

    async def test_ensure_valid_token_expired_no_refresh(self):
        """Returns None when token expired and no refresh token."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        # Token expired 1 hour ago
        mock_user = _create_mock_user(
            space_access_token='expired_token',
            space_refresh_token=None,
            space_access_token_expires_at=datetime.datetime.now() - datetime.timedelta(hours=1),
        )
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Execute
        result = await service._ensure_valid_token('test@example.com')

        # Verify
        assert result is None


class TestSpaceServiceGetCredits:
    """Tests for get_credits method."""

    async def test_get_credits_no_user(self):
        """Returns None when user not found."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Execute
        result = await service.get_credits('notfound@example.com')

        # Verify
        assert result is None

    async def test_get_credits_returns_cached_value(self):
        """Returns cached credits without API call."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Pre-populate cache
        service._credits_cache = {'cached@example.com': (100, time.time())}

        # Execute
        result = await service.get_credits('cached@example.com')

        # Verify - returns cached value without API call
        assert result == 100

    async def test_get_credits_cache_expired_refreshes(self):
        """Refreshes expired cache."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}
        ap.persistence_mgr = SimpleNamespace()

        mock_user = _create_mock_user(
            space_access_token='valid_token',
            space_access_token_expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),
        )
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Pre-populate expired cache (70 seconds ago, past 60s TTL)
        service._credits_cache = {'test@example.com': (50, time.time() - 70)}

        # Mock get_user_info to return new credits
        service.get_user_info = AsyncMock(return_value={'credits': 200})

        # Execute
        result = await service.get_credits('test@example.com')

        # Verify - cache was refreshed
        assert result == 200
        assert service._credits_cache['test@example.com'][0] == 200

    async def test_get_credits_force_refresh(self):
        """Force refresh ignores cache."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}
        ap.persistence_mgr = SimpleNamespace()

        mock_user = _create_mock_user(
            space_access_token='valid_token',
            space_access_token_expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),
        )
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Pre-populate cache
        service._credits_cache = {'test@example.com': (100, time.time())}

        # Mock get_user_info to return new credits
        service.get_user_info = AsyncMock(return_value={'credits': 300})

        # Execute with force_refresh=True
        result = await service.get_credits('test@example.com', force_refresh=True)

        # Verify - fresh value returned
        assert result == 300

    async def test_get_credits_returns_cached_on_exception(self):
        """Returns cached fallback value when API fails."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}
        ap.persistence_mgr = SimpleNamespace()

        mock_user = _create_mock_user(
            space_access_token='valid_token',
            space_access_token_expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),
        )
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Pre-populate expired cache - will try to refresh and fail
        service._credits_cache = {'test@example.com': (150, time.time() - 70)}

        # Mock get_user_info to raise exception
        service.get_user_info = AsyncMock(side_effect=Exception('API Error'))

        # Execute - should return cached fallback value (even though expired)
        result = await service.get_credits('test@example.com')

        # Verify - returns cached fallback value (150) because API failed
        assert result == 150


class TestSpaceServiceRefreshToken:
    """Tests for refresh_token method."""

    async def test_refresh_token_success(self):
        """Refreshes token successfully."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}

        service = SpaceService(ap)

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'code': 0,
            'data': {
                'access_token': 'new_access_token',
                'refresh_token': 'new_refresh_token',
                'expires_in': 3600,
            }
        })

        with patch('langbot.pkg.api.http.service.space.httpclient.get_session') as mock_session:
            mock_session_obj = MagicMock()
            mock_session_obj.post = MagicMock(return_value=mock_response)
            mock_session.return_value = mock_session_obj

            # Use async context manager mock
            mock_session_obj.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_obj.post.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute
            result = await service.refresh_token('old_refresh_token')

        # Verify
        assert result['access_token'] == 'new_access_token'

    async def test_refresh_token_api_error(self):
        """Raises ValueError on API error."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}

        service = SpaceService(ap)

        # Mock HTTP response with error
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'code': 1,
            'msg': 'Invalid refresh token',
        })
        mock_response.text = AsyncMock(return_value='{"code":1,"msg":"Invalid refresh token"}')

        with patch('langbot.pkg.api.http.service.space.httpclient.get_session') as mock_session:
            mock_session_obj = MagicMock()
            mock_session_obj.post = MagicMock(return_value=mock_response)
            mock_session.return_value = mock_session_obj

            mock_session_obj.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_obj.post.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute & Verify
            with pytest.raises(ValueError, match='Failed to refresh token'):
                await service.refresh_token('invalid_refresh_token')

    async def test_refresh_token_http_error(self):
        """Raises ValueError on HTTP error."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}

        service = SpaceService(ap)

        # Mock HTTP response with error status
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value='Internal Server Error')

        with patch('langbot.pkg.api.http.service.space.httpclient.get_session') as mock_session:
            mock_session_obj = MagicMock()
            mock_session_obj.post = MagicMock(return_value=mock_response)
            mock_session.return_value = mock_session_obj

            mock_session_obj.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_obj.post.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute & Verify
            with pytest.raises(ValueError, match='Failed to refresh token'):
                await service.refresh_token('refresh_token')


class TestSpaceServiceExchangeOAuthCode:
    """Tests for exchange_oauth_code method."""

    async def test_exchange_oauth_code_success(self):
        """Exchanges OAuth code successfully."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}

        service = SpaceService(ap)

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'code': 0,
            'data': {
                'access_token': 'new_access_token',
                'refresh_token': 'new_refresh_token',
                'expires_in': 3600,
            }
        })

        with patch('langbot.pkg.api.http.service.space.httpclient.get_session') as mock_session:
            mock_session_obj = MagicMock()
            mock_session_obj.post = MagicMock(return_value=mock_response)
            mock_session.return_value = mock_session_obj

            mock_session_obj.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_obj.post.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute
            result = await service.exchange_oauth_code('auth_code')

        # Verify
        assert result['access_token'] == 'new_access_token'

    async def test_exchange_oauth_code_api_error(self):
        """Raises ValueError on API error."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}

        service = SpaceService(ap)

        # Mock HTTP response with error
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={'code': 1, 'msg': 'Invalid code'})
        mock_response.text = AsyncMock(return_value='{"code":1,"msg":"Invalid code"}')

        with patch('langbot.pkg.api.http.service.space.httpclient.get_session') as mock_session:
            mock_session_obj = MagicMock()
            mock_session_obj.post = MagicMock(return_value=mock_response)
            mock_session.return_value = mock_session_obj

            mock_session_obj.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_obj.post.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute & Verify
            with pytest.raises(ValueError, match='Failed to exchange OAuth code'):
                await service.exchange_oauth_code('invalid_code')


class TestSpaceServiceGetUserInfoRaw:
    """Tests for get_user_info_raw method."""

    async def test_get_user_info_raw_success(self):
        """Gets user info successfully."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}

        service = SpaceService(ap)

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'code': 0,
            'data': {
                'email': 'test@example.com',
                'credits': 100,
            }
        })

        with patch('langbot.pkg.api.http.service.space.httpclient.get_session') as mock_session:
            mock_session_obj = MagicMock()
            mock_session_obj.get = MagicMock(return_value=mock_response)
            mock_session.return_value = mock_session_obj

            mock_session_obj.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_obj.get.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute
            result = await service.get_user_info_raw('access_token')

        # Verify
        assert result['email'] == 'test@example.com'
        assert result['credits'] == 100

    async def test_get_user_info_raw_api_error(self):
        """Raises ValueError on API error."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}

        service = SpaceService(ap)

        # Mock HTTP response with error
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={'code': 1, 'msg': 'Unauthorized'})
        mock_response.text = AsyncMock(return_value='{"code":1,"msg":"Unauthorized"}')

        with patch('langbot.pkg.api.http.service.space.httpclient.get_session') as mock_session:
            mock_session_obj = MagicMock()
            mock_session_obj.get = MagicMock(return_value=mock_response)
            mock_session.return_value = mock_session_obj

            mock_session_obj.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_obj.get.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute & Verify
            with pytest.raises(ValueError, match='Failed to get user info'):
                await service.get_user_info_raw('invalid_token')


class TestSpaceServiceGetUserInfo:
    """Tests for get_user_info method (with token validation)."""

    async def test_get_user_info_no_token(self):
        """Returns None when no valid token."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Execute
        result = await service.get_user_info('notfound@example.com')

        # Verify
        assert result is None

    async def test_get_user_info_with_valid_token(self):
        """Returns user info with valid token."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}
        ap.persistence_mgr = SimpleNamespace()

        mock_user = _create_mock_user(
            space_access_token='valid_token',
            space_access_token_expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),
        )
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Mock get_user_info_raw
        service.get_user_info_raw = AsyncMock(return_value={'email': 'test@example.com', 'credits': 100})

        # Execute
        result = await service.get_user_info('test@example.com')

        # Verify
        assert result['email'] == 'test@example.com'


class TestSpaceServiceGetModels:
    """Tests for get_models method."""

    async def test_get_models_success(self):
        """Gets models successfully."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}

        service = SpaceService(ap)

        # Mock HTTP response with proper model data matching SpaceModel schema
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'code': 0,
            'data': {
                'models': [
                    {
                        'uuid': 'uuid-1',
                        'model_id': 'model-1',
                        'provider': 'provider-1',
                        'category': 'chat',
                        'status': 'active',
                    },
                    {
                        'uuid': 'uuid-2',
                        'model_id': 'model-2',
                        'provider': 'provider-2',
                        'category': 'chat',
                        'status': 'active',
                    },
                ]
            }
        })

        with patch('langbot.pkg.api.http.service.space.httpclient.get_session') as mock_session:
            mock_session_obj = MagicMock()
            mock_session_obj.get = MagicMock(return_value=mock_response)
            mock_session.return_value = mock_session_obj

            mock_session_obj.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_obj.get.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute
            result = await service.get_models()

        # Verify
        assert len(result) == 2

    async def test_get_models_api_error(self):
        """Raises ValueError on API error."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}

        service = SpaceService(ap)

        # Mock HTTP response with error
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={'code': 1, 'msg': 'Unauthorized'})
        mock_response.text = AsyncMock(return_value='{"code":1,"msg":"Unauthorized"}')

        with patch('langbot.pkg.api.http.service.space.httpclient.get_session') as mock_session:
            mock_session_obj = MagicMock()
            mock_session_obj.get = MagicMock(return_value=mock_response)
            mock_session.return_value = mock_session_obj

            mock_session_obj.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session_obj.get.return_value.__aexit__ = AsyncMock(return_value=None)

            # Execute & Verify
            with pytest.raises(ValueError, match='Failed to get models'):
                await service.get_models()


class TestSpaceServiceCreditsCache:
    """Tests for credits cache behavior."""

    def test_credits_cache_initialized(self):
        """Verify _credits_cache is initialized as empty dict."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}

        service = SpaceService(ap)

        # Verify
        assert hasattr(service, '_credits_cache')
        assert service._credits_cache == {}

    async def test_credits_cache_updates_on_success(self):
        """Cache updates when get_credits succeeds."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {}
        ap.persistence_mgr = SimpleNamespace()

        mock_user = _create_mock_user(
            space_access_token='valid_token',
            space_access_token_expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),
        )
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = SpaceService(ap)

        # Mock get_user_info
        service.get_user_info = AsyncMock(return_value={'credits': 500})

        # Execute
        result = await service.get_credits('test@example.com')

        # Verify - cache updated
        assert result == 500
        assert 'test@example.com' in service._credits_cache
        assert service._credits_cache['test@example.com'][0] == 500