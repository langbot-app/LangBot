"""
Unit tests for ApiKeyService.

Tests API key CRUD operations with mocked persistence layer.

Source: src/langbot/pkg/api/http/service/apikey.py
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace

from langbot.pkg.api.http.service.apikey import ApiKeyService
from langbot.pkg.entity.persistence.apikey import ApiKey


pytestmark = pytest.mark.asyncio


class TestApiKeyServiceGetApiKeys:
    """Tests for get_api_keys method."""

    async def test_get_api_keys_empty_list(self):
        """Returns empty list when no API keys exist."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = Mock()
        mock_result.all = Mock(return_value=[])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'id': entity.id,
                'name': entity.name,
                'key': entity.key,
                'description': entity.description,
            }
            if entity
            else {}
        )

        service = ApiKeyService(ap)

        # Execute
        result = await service.get_api_keys()

        # Verify
        assert result == []
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_get_api_keys_returns_serialized_list(self):
        """Returns serialized list of API keys."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        # Create mock API key entities
        key1 = Mock(spec=ApiKey)
        key1.id = 1
        key1.name = 'Test Key 1'
        key1.key = 'lbk_test_key_1'
        key1.description = 'First test key'

        key2 = Mock(spec=ApiKey)
        key2.id = 2
        key2.name = 'Test Key 2'
        key2.key = 'lbk_test_key_2'
        key2.description = 'Second test key'

        mock_result = Mock()
        mock_result.all = Mock(return_value=[key1, key2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'id': entity.id,
                'name': entity.name,
                'key': entity.key,
                'description': entity.description,
            }
        )

        service = ApiKeyService(ap)

        # Execute
        result = await service.get_api_keys()

        # Verify
        assert len(result) == 2
        assert result[0]['name'] == 'Test Key 1'
        assert result[1]['name'] == 'Test Key 2'


class TestApiKeyServiceCreateApiKey:
    """Tests for create_api_key method."""

    async def test_create_api_key_generates_key_with_prefix(self):
        """Creates API key with 'lbk_' prefix."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        created_key = Mock(spec=ApiKey)
        created_key.id = 1
        created_key.name = 'New Key'
        created_key.key = 'lbk_fixed-token'
        created_key.description = 'Test description'
        select_result = Mock()
        select_result.first = Mock(return_value=created_key)
        insert_params = []

        async def mock_execute(query):
            params = query.compile().params
            if {'name', 'key', 'description'}.issubset(params):
                insert_params.append(params)
                return Mock()
            return select_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'id': 1,
                'name': entity.name,
                'key': entity.key,
                'description': entity.description,
            }
        )

        service = ApiKeyService(ap)

        with patch('langbot.pkg.api.http.service.apikey.secrets.token_urlsafe', return_value='fixed-token'):
            result = await service.create_api_key('New Key', 'Test description')

        assert insert_params == [
            {'name': 'New Key', 'key': 'lbk_fixed-token', 'description': 'Test description'}
        ]
        assert result['key'].startswith('lbk_')
        assert result['key'] == 'lbk_fixed-token'
        assert result['name'] == 'New Key'
        assert result['description'] == 'Test description'

    async def test_create_api_key_without_description(self):
        """Creates API key with empty description when not provided."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        created_key = Mock(spec=ApiKey)
        created_key.id = 1
        created_key.name = 'No Desc Key'
        created_key.key = 'lbk_no_desc_key'
        created_key.description = ''

        select_result = Mock()
        select_result.first = Mock(return_value=created_key)
        insert_result = Mock()

        async def mock_execute(query):
            if hasattr(query, 'values'):
                return insert_result
            return select_result

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'id': 1,
                'name': 'No Desc Key',
                'key': 'lbk_no_desc_key',
                'description': '',
            }
        )

        service = ApiKeyService(ap)

        # Execute
        result = await service.create_api_key('No Desc Key')

        # Verify
        assert result['description'] == ''


class TestApiKeyServiceGetApiKey:
    """Tests for get_api_key method."""

    async def test_get_api_key_by_id_found(self):
        """Returns API key when found by ID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        key = Mock(spec=ApiKey)
        key.id = 1
        key.name = 'Found Key'
        key.key = 'lbk_found_key'
        key.description = 'Found'

        mock_result = Mock()
        mock_result.first = Mock(return_value=key)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'id': 1,
                'name': 'Found Key',
                'key': 'lbk_found_key',
                'description': 'Found',
            }
        )

        service = ApiKeyService(ap)

        # Execute
        result = await service.get_api_key(1)

        # Verify
        assert result is not None
        assert result['id'] == 1
        assert result['name'] == 'Found Key'

    async def test_get_api_key_by_id_not_found(self):
        """Returns None when API key not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = Mock()
        mock_result.first = Mock(return_value=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ApiKeyService(ap)

        # Execute
        result = await service.get_api_key(999)

        # Verify
        assert result is None

    async def test_get_api_key_by_id_zero(self):
        """Handles ID=0 (edge case) correctly."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = Mock()
        mock_result.first = Mock(return_value=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ApiKeyService(ap)

        # Execute
        result = await service.get_api_key(0)

        # Verify - should return None (no key with ID 0)
        assert result is None


class TestApiKeyServiceVerifyApiKey:
    """Tests for verify_api_key method."""

    async def test_verify_api_key_valid(self):
        """Returns True for valid API key."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        key = Mock(spec=ApiKey)
        mock_result = Mock()
        mock_result.first = Mock(return_value=key)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ApiKeyService(ap)

        # Execute
        result = await service.verify_api_key('lbk_valid_key')

        # Verify
        assert result is True

    async def test_verify_api_key_invalid(self):
        """Returns False for invalid API key."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = Mock()
        mock_result.first = Mock(return_value=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ApiKeyService(ap)

        # Execute
        result = await service.verify_api_key('lbk_invalid_key')

        # Verify
        assert result is False

    async def test_verify_api_key_empty_string(self):
        """Returns False for empty key string."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = Mock()
        mock_result.first = Mock(return_value=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ApiKeyService(ap)

        # Execute
        result = await service.verify_api_key('')

        # Verify
        assert result is False

    async def test_verify_api_key_unknown_key(self):
        """Returns False when the key is not present in persistence."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = Mock()
        mock_result.first = Mock(return_value=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = ApiKeyService(ap)

        # Execute
        result = await service.verify_api_key('unknown_key')

        # Verify
        assert result is False


class TestApiKeyServiceDeleteApiKey:
    """Tests for delete_api_key method."""

    async def test_delete_api_key_by_id(self):
        """Deletes API key by ID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock()

        service = ApiKeyService(ap)

        # Execute
        await service.delete_api_key(1)

        # Verify - execute_async was called (delete operation)
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_delete_api_key_nonexistent_id(self):
        """Delete operation completes even for nonexistent ID (no error raised)."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock()

        service = ApiKeyService(ap)

        # Execute - should not raise error
        await service.delete_api_key(999)

        # Verify - execute_async was called regardless
        ap.persistence_mgr.execute_async.assert_called_once()


class TestApiKeyServiceUpdateApiKey:
    """Tests for update_api_key method."""

    async def test_update_api_key_name_only(self):
        """Updates only the name field."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock()

        service = ApiKeyService(ap)

        # Execute
        await service.update_api_key(1, name='Updated Name')

        # Verify - execute_async was called with update
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_update_api_key_description_only(self):
        """Updates only the description field."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock()

        service = ApiKeyService(ap)

        # Execute
        await service.update_api_key(1, description='Updated description')

        # Verify
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_update_api_key_both_fields(self):
        """Updates both name and description."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock()

        service = ApiKeyService(ap)

        # Execute
        await service.update_api_key(1, name='New Name', description='New description')

        # Verify
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_update_api_key_no_fields(self):
        """Does nothing when no fields provided."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock()

        service = ApiKeyService(ap)

        # Execute
        await service.update_api_key(1)

        # Verify - no execute call since no update_data
        ap.persistence_mgr.execute_async.assert_not_called()
