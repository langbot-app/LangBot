"""
Unit tests for UserService.

Tests user management operations including:
- User initialization check
- Local user creation and authentication
- JWT token generation and verification
- Password management (reset, change, set)
- Space account management

Source: src/langbot/pkg/api/http/service/user.py
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace

from langbot.pkg.api.http.service.user import UserService
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.errors.account import AccountEmailMismatchError


pytestmark = pytest.mark.asyncio


def _create_mock_user(
    email: str = 'test@example.com',
    password: str = 'hashed_password',
    account_type: str = 'local',
    space_account_uuid: str = None,
) -> Mock:
    """Helper to create mock User entity."""
    user = Mock(spec=User)
    user.user = email
    user.password = password
    user.account_type = account_type
    user.space_account_uuid = space_account_uuid
    return user


def _create_mock_result(items: list = None, first_item=None):
    """Create mock result object for persistence queries."""
    result = Mock()
    result.all = Mock(return_value=items or [])
    result.first = Mock(return_value=first_item)
    return result


class TestUserServiceIsInitialized:
    """Tests for is_initialized method."""

    async def test_is_initialized_returns_true_when_users_exist(self):
        """Returns True when at least one user exists."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_user = _create_mock_user()
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = UserService(ap)

        # Execute
        result = await service.is_initialized()

        # Verify
        assert result is True

    async def test_is_initialized_returns_false_when_no_users(self):
        """Returns False when no users exist."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = UserService(ap)

        # Execute
        result = await service.is_initialized()

        # Verify
        assert result is False

    async def test_is_initialized_returns_false_on_none_result(self):
        """Returns False when result is None."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = Mock()
        mock_result.all = Mock(return_value=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = UserService(ap)

        # Execute
        result = await service.is_initialized()

        # Verify
        assert result is False


class TestUserServiceGetUserByEmail:
    """Tests for get_user_by_email method."""

    async def test_get_user_by_email_found(self):
        """Returns user when found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_user = _create_mock_user(email='found@example.com')
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = UserService(ap)

        # Execute
        result = await service.get_user_by_email('found@example.com')

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

        service = UserService(ap)

        # Execute
        result = await service.get_user_by_email('notfound@example.com')

        # Verify
        assert result is None

    async def test_get_user_by_email_empty_string(self):
        """Handles empty email string."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = UserService(ap)

        # Execute
        result = await service.get_user_by_email('')

        # Verify
        assert result is None


class TestUserServiceGetUserBySpaceAccountUuid:
    """Tests for get_user_by_space_account_uuid method."""

    async def test_get_user_by_space_uuid_found(self):
        """Returns user when Space UUID found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_user = _create_mock_user(
            email='space@example.com',
            account_type='space',
            space_account_uuid='space-uuid-123',
        )
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = UserService(ap)

        # Execute
        result = await service.get_user_by_space_account_uuid('space-uuid-123')

        # Verify
        assert result is not None
        assert result.space_account_uuid == 'space-uuid-123'

    async def test_get_user_by_space_uuid_not_found(self):
        """Returns None when Space UUID not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = UserService(ap)

        # Execute
        result = await service.get_user_by_space_account_uuid('nonexistent-uuid')

        # Verify
        assert result is None


class TestUserServiceAuthenticate:
    """Tests for authenticate method."""

    async def test_authenticate_user_not_found_raises_error(self):
        """Raises ValueError when user not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'jwt': {'secret': 'test_secret', 'expire': 3600}}}

        service = UserService(ap)

        # Execute & Verify
        with pytest.raises(ValueError, match='用户不存在'):
            await service.authenticate('nonexistent@example.com', 'password')

    async def test_authenticate_space_user_without_password_raises_error(self):
        """Raises ValueError for Space user without local password."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        # Space user has empty password
        mock_user = _create_mock_user(
            email='space@example.com',
            password='',  # Empty password for Space user
            account_type='space',
        )
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = UserService(ap)

        # Execute & Verify
        with pytest.raises(ValueError, match='请使用 Space 账户登录'):
            await service.authenticate('space@example.com', 'password')


class TestUserServiceGenerateJwtToken:
    """Tests for generate_jwt_token method."""

    async def test_generate_jwt_token_returns_valid_token(self):
        """Generates valid JWT token."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'jwt': {'secret': 'test_secret', 'expire': 3600}}}

        service = UserService(ap)

        # Execute
        token = await service.generate_jwt_token('test@example.com')

        # Verify - JWT format (base64 encoded parts)
        assert token is not None
        assert len(token) > 0
        parts = token.split('.')
        assert len(parts) == 3  # JWT has 3 parts

    async def test_generate_jwt_token_custom_expire(self):
        """Generates token with custom expiry."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'jwt': {'secret': 'test_secret', 'expire': 7200}}}

        service = UserService(ap)

        # Execute
        token = await service.generate_jwt_token('test@example.com')

        # Verify
        assert token is not None


class TestUserServiceVerifyJwtToken:
    """Tests for verify_jwt_token method."""

    async def test_verify_jwt_token_valid(self):
        """Verifies valid JWT token and returns user email."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'jwt': {'secret': 'test_secret', 'expire': 3600}}}

        service = UserService(ap)

        # First generate a valid token
        token = await service.generate_jwt_token('verify@example.com')

        # Execute
        user_email = await service.verify_jwt_token(token)

        # Verify
        assert user_email == 'verify@example.com'

    async def test_verify_jwt_token_invalid_raises_error(self):
        """Raises error for invalid JWT token."""
        # Setup
        ap = SimpleNamespace()
        ap.instance_config = SimpleNamespace()
        ap.instance_config.data = {'system': {'jwt': {'secret': 'test_secret', 'expire': 3600}}}

        service = UserService(ap)

        # Execute & Verify - invalid token should raise JWT error
        with pytest.raises(Exception):  # jwt.DecodeError or similar
            await service.verify_jwt_token('invalid.token.here')


class TestUserServiceResetPassword:
    """Tests for reset_password method."""

    async def test_reset_password_updates_password(self):
        """Updates user password."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock()

        service = UserService(ap)

        # Execute
        await service.reset_password('test@example.com', 'new_password')

        # Verify - execute_async was called with update
        ap.persistence_mgr.execute_async.assert_called_once()


class TestUserServiceChangePassword:
    """Tests for change_password method."""

    async def test_change_password_user_not_found_raises_error(self):
        """Raises ValueError when user not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        service = UserService(ap)

        # Mock get_user_by_email to return None
        service.get_user_by_email = AsyncMock(return_value=None)

        # Execute & Verify
        with pytest.raises(ValueError, match='User not found'):
            await service.change_password('nonexistent@example.com', 'current', 'new')

    async def test_change_password_no_local_password_raises_error(self):
        """Raises ValueError when user has no local password set."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        service = UserService(ap)

        # Mock user without password
        mock_user = _create_mock_user(email='nopass@example.com', password=None)
        service.get_user_by_email = AsyncMock(return_value=mock_user)

        # Execute & Verify
        with pytest.raises(ValueError, match='No local password set'):
            await service.change_password('nopass@example.com', 'current', 'new')


class TestUserServiceGetFirstUser:
    """Tests for get_first_user method."""

    async def test_get_first_user_found(self):
        """Returns first user when exists."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_user = _create_mock_user(email='first@example.com')
        mock_result = _create_mock_result([mock_user])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = UserService(ap)

        # Execute
        result = await service.get_first_user()

        # Verify
        assert result is not None
        assert result.user == 'first@example.com'

    async def test_get_first_user_not_found(self):
        """Returns None when no users exist."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = UserService(ap)

        # Execute
        result = await service.get_first_user()

        # Verify
        assert result is None


class TestUserServiceSetPassword:
    """Tests for set_password method."""

    async def test_set_password_user_not_found_raises_error(self):
        """Raises ValueError when user not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        service = UserService(ap)

        # Mock get_user_by_email to return None
        service.get_user_by_email = AsyncMock(return_value=None)

        # Execute & Verify
        with pytest.raises(ValueError, match='User not found'):
            await service.set_password('nonexistent@example.com', 'new_password')

    async def test_set_password_with_existing_password_requires_current(self):
        """Requires current password when user has existing password."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        service = UserService(ap)

        # Mock user with existing password
        mock_user = _create_mock_user(email='haspass@example.com', password='hashed_old_password')
        service.get_user_by_email = AsyncMock(return_value=mock_user)

        # Execute & Verify - should raise when no current_password provided
        with pytest.raises(ValueError, match='Current password is required'):
            await service.set_password('haspass@example.com', 'new_password')


class TestUserServiceCreateOrUpdateSpaceUser:
    """Tests for create_or_update_space_user method."""

    async def test_create_or_update_existing_space_user(self):
        """Updates existing Space user tokens."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.provider_service = SimpleNamespace()
        ap.provider_service.update_space_model_provider_api_keys = AsyncMock()

        service = UserService(ap)

        # Mock existing Space user
        existing_user = _create_mock_user(
            email='space@example.com',
            account_type='space',
            space_account_uuid='existing-space-uuid',
        )
        service.get_user_by_space_account_uuid = AsyncMock(return_value=existing_user)
        service.get_user_by_email = AsyncMock(return_value=None)
        service.is_initialized = AsyncMock(return_value=True)

        ap.persistence_mgr.execute_async = AsyncMock()

        # Execute
        updated_user = await service.create_or_update_space_user(
            space_account_uuid='existing-space-uuid',
            email='space@example.com',
            access_token='new_access_token',
            refresh_token='new_refresh_token',
            api_key='new_api_key',
            expires_in=3600,
        )

        # Verify - update was called and user returned
        ap.persistence_mgr.execute_async.assert_called()
        assert updated_user.space_account_uuid == 'existing-space-uuid'

    async def test_create_or_update_new_space_user_first_init(self):
        """Creates new Space user on first initialization."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.provider_service = SimpleNamespace()
        ap.provider_service.update_space_model_provider_api_keys = AsyncMock()

        service = UserService(ap)

        # Mock new user to be returned after creation
        new_user = _create_mock_user(
            email='newspace@example.com',
            account_type='space',
            space_account_uuid='new-space-uuid',
        )

        # First call (line 138) returns None, second call (line 194) returns new_user
        call_count = 0
        async def mock_get_by_space_uuid(uuid):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First check for existing user
                return None
            return new_user  # After insert, return the new user

        service.get_user_by_space_account_uuid = AsyncMock(side_effect=mock_get_by_space_uuid)
        service.get_user_by_email = AsyncMock(return_value=None)
        service.is_initialized = AsyncMock(return_value=False)  # Not initialized

        ap.persistence_mgr.execute_async = AsyncMock()

        # Execute
        result = await service.create_or_update_space_user(
            space_account_uuid='new-space-uuid',
            email='newspace@example.com',
            access_token='access_token',
            refresh_token='refresh_token',
            api_key='api_key',
            expires_in=3600,
        )

        # Verify
        assert result.space_account_uuid == 'new-space-uuid'

    async def test_create_or_update_space_user_already_initialized_raises_error(self):
        """Raises AccountEmailMismatchError when system already initialized and user not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.provider_service = SimpleNamespace()
        ap.provider_service.update_space_model_provider_api_keys = AsyncMock()

        service = UserService(ap)

        # Mock system already initialized, no matching users
        service.get_user_by_space_account_uuid = AsyncMock(return_value=None)
        service.get_user_by_email = AsyncMock(return_value=None)
        service.is_initialized = AsyncMock(return_value=True)  # Already initialized

        # Execute & Verify
        with pytest.raises(AccountEmailMismatchError):
            await service.create_or_update_space_user(
                space_account_uuid='unknown-space-uuid',
                email='unknown@example.com',
                access_token='token',
                refresh_token='refresh',
                api_key='key',
                expires_in=3600,
            )

    async def test_create_or_update_space_user_no_expiry(self):
        """Creates Space user without token expiry."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.provider_service = SimpleNamespace()
        ap.provider_service.update_space_model_provider_api_keys = AsyncMock()

        service = UserService(ap)

        new_user = _create_mock_user(
            email='noexpiry@example.com',
            account_type='space',
            space_account_uuid='noexpiry-uuid',
        )

        # First call (line 138) returns None, second call (line 194) returns new_user
        call_count = 0
        async def mock_get_by_space_uuid(uuid):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First check for existing user
                return None
            return new_user  # After insert, return the new user

        service.get_user_by_space_account_uuid = AsyncMock(side_effect=mock_get_by_space_uuid)
        service.get_user_by_email = AsyncMock(return_value=None)
        service.is_initialized = AsyncMock(return_value=False)

        ap.persistence_mgr.execute_async = AsyncMock()

        # Execute with expires_in=0 (no expiry)
        result = await service.create_or_update_space_user(
            space_account_uuid='noexpiry-uuid',
            email='noexpiry@example.com',
            access_token='token',
            refresh_token='refresh',
            api_key='key',
            expires_in=0,  # No expiry
        )

        # Verify
        assert result is not None
        assert result.space_account_uuid == 'noexpiry-uuid'


class TestUserServiceCreateUserLock:
    """Tests for create_user_lock attribute."""

    def test_create_user_lock_initialized(self):
        """Verify create_user_lock is initialized as asyncio.Lock."""
        # Setup
        ap = SimpleNamespace()

        service = UserService(ap)

        # Verify lock exists
        assert hasattr(service, '_create_user_lock')
        assert service._create_user_lock is not None