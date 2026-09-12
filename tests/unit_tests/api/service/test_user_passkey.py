"""
Unit tests for Passkey WebAuthn service operations in UserService.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.user import UserService
from langbot.pkg.entity.persistence.user import AccountStatus, User


pytestmark = pytest.mark.asyncio


class TestPasskeyChallengeLifecycle:
    async def test_challenge_issuance_and_consumption(self):
        service = UserService(SimpleNamespace())
        token, challenge_bytes = await service.issue_passkey_challenge(
            purpose='register',
            rp_id='localhost',
            origin='http://localhost:3000',
            account_uuid='acc-123',
            user_email='user@example.com',
        )

        assert len(token) > 20
        assert len(challenge_bytes) == 32

        data = await service.consume_passkey_challenge(token, 'register')
        assert data.challenge == challenge_bytes
        assert data.rp_id == 'localhost'
        assert data.origin == 'http://localhost:3000'
        assert data.account_uuid == 'acc-123'
        assert data.user_email == 'user@example.com'

        # Replay should fail
        with pytest.raises(ValueError, match='Invalid or expired passkey challenge'):
            await service.consume_passkey_challenge(token, 'register')

    async def test_challenge_purpose_mismatch_fails(self):
        service = UserService(SimpleNamespace())
        token, _ = await service.issue_passkey_challenge(
            purpose='register',
            rp_id='localhost',
            origin='http://localhost:3000',
        )

        with pytest.raises(ValueError, match='Passkey challenge purpose mismatch'):
            await service.consume_passkey_challenge(token, 'auth')

    async def test_challenge_expiration(self):
        service = UserService(SimpleNamespace())
        token, _ = await service.issue_passkey_challenge(
            purpose='auth',
            rp_id='localhost',
            origin='http://localhost:3000',
            ttl_seconds=0,
        )

        with pytest.raises(ValueError, match='Invalid or expired passkey challenge'):
            await service.consume_passkey_challenge(token, 'auth')


class TestPasskeyOptionsGeneration:
    async def test_generate_registration_options(self):
        service = UserService(SimpleNamespace())
        mock_user = Mock(spec=User)
        mock_user.uuid = 'acc-test-uuid'
        mock_user.user = 'test@example.com'
        mock_user.status = AccountStatus.ACTIVE.value
        service.get_user_by_uuid = AsyncMock(return_value=mock_user)
        service.get_user_passkeys = AsyncMock(return_value=[])

        options, token = await service.generate_passkey_registration_options(
            account_uuid='acc-test-uuid',
            rp_id='localhost',
            origin='http://localhost:3000',
            rp_name='LangBot Test',
        )

        assert isinstance(options, dict)
        assert options['rp']['name'] == 'LangBot Test'
        assert options['rp']['id'] == 'localhost'
        assert options['user']['name'] == 'test@example.com'
        assert 'challenge' in options
        assert len(token) > 0

    async def test_generate_authentication_options_discoverable(self):
        service = UserService(SimpleNamespace())

        options, token = await service.generate_passkey_authentication_options(
            rp_id='localhost',
            origin='http://localhost:3000',
        )

        assert isinstance(options, dict)
        assert options['rpId'] == 'localhost'
        assert 'challenge' in options
        assert len(token) > 0
