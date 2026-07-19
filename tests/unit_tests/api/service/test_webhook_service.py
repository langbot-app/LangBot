"""
Unit tests for WebhookService.

Tests webhook CRUD operations including:
- Webhook listing
- Webhook creation
- Webhook retrieval by ID
- Webhook updates
- Webhook deletion
- Enabled webhooks filtering

Source: src/langbot/pkg/api/http/service/webhook.py
"""

from __future__ import annotations

import datetime

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine
from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace

from langbot.pkg.api.http.authz import WorkspaceRequiredError
from langbot.pkg.api.http.service.webhook import WebhookService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.webhook import Webhook
from langbot.pkg.entity.persistence.workspace import Workspace


pytestmark = pytest.mark.asyncio
WORKSPACE_UUID = 'workspace-a'


def _create_mock_webhook(
    webhook_id: int = 1,
    name: str = 'Test Webhook',
    url: str = 'http://example.com/webhook',
    description: str = 'Test Description',
    enabled: bool = True,
) -> Mock:
    """Helper to create mock Webhook entity."""
    webhook = Mock(spec=Webhook)
    webhook.id = webhook_id
    webhook.name = name
    webhook.url = url
    webhook.description = description
    webhook.enabled = enabled
    return webhook


def _create_mock_result(items: list = None, first_item=None):
    """Create mock result object for persistence queries."""
    result = Mock()
    result.all = Mock(return_value=items or [])
    result.first = Mock(return_value=first_item)
    result.rowcount = 1
    return result


def _create_write_result(rowcount: int = 1, inserted_id: int = 1):
    result = Mock()
    result.rowcount = rowcount
    result.inserted_primary_key = [inserted_id]
    return result


class TestWebhookServiceGetWebhooks:
    """Tests for get_webhooks method."""

    async def test_get_webhooks_empty_list(self):
        """Returns empty list when no webhooks exist."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'id': entity.id,
                'name': entity.name,
                'url': entity.url,
            }
        )

        service = WebhookService(ap)

        # Execute
        result = await service.get_webhooks(WORKSPACE_UUID)

        # Verify
        assert result == []

    async def test_get_webhooks_returns_serialized_list(self):
        """Returns serialized list of webhooks."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        webhook1 = _create_mock_webhook(webhook_id=1, name='Webhook 1')
        webhook2 = _create_mock_webhook(webhook_id=2, name='Webhook 2')

        mock_result = _create_mock_result([webhook1, webhook2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'id': entity.id,
                'name': entity.name,
                'url': entity.url,
                'description': entity.description,
                'enabled': entity.enabled,
            }
        )

        service = WebhookService(ap)

        # Execute
        result = await service.get_webhooks(WORKSPACE_UUID)

        # Verify
        assert len(result) == 2
        assert result[0]['name'] == 'Webhook 1'
        assert result[1]['name'] == 'Webhook 2'


class TestWebhookServiceCreateWebhook:
    """Tests for create_webhook method."""

    async def test_create_webhook_full_params(self):
        """Creates webhook with all parameters."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        # Mock insert result
        insert_result = Mock()
        insert_result.inserted_primary_key = [1]

        # Mock select result for retrieving created webhook
        created_webhook = _create_mock_webhook(
            webhook_id=1,
            name='New Webhook',
            url='http://new.example.com/webhook',
            description='New Description',
            enabled=True,
        )
        select_result = _create_mock_result(first_item=created_webhook)

        # execute_async returns different results
        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return insert_result  # Insert
            return select_result  # Select

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'id': 1,
                'name': 'New Webhook',
                'url': 'http://new.example.com/webhook',
                'description': 'New Description',
                'enabled': True,
            }
        )

        service = WebhookService(ap)

        # Execute
        result = await service.create_webhook(
            WORKSPACE_UUID,
            name='New Webhook',
            url='http://new.example.com/webhook',
            description='New Description',
            enabled=True,
        )

        # Verify
        assert result['name'] == 'New Webhook'
        assert result['url'] == 'http://new.example.com/webhook'
        assert result['description'] == 'New Description'
        assert result['enabled'] is True

    async def test_create_webhook_defaults(self):
        """Creates webhook with default description and enabled."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        created_webhook = _create_mock_webhook(
            webhook_id=1,
            name='Minimal Webhook',
            url='http://minimal.example.com',
            description='',  # Default
            enabled=True,  # Default
        )

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_write_result()  # Insert
            return _create_mock_result(first_item=created_webhook)

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'id': 1,
                'name': 'Minimal Webhook',
                'url': 'http://minimal.example.com',
                'description': '',
                'enabled': True,
            }
        )

        service = WebhookService(ap)

        # Execute - only name and url required
        result = await service.create_webhook(
            WORKSPACE_UUID,
            name='Minimal Webhook',
            url='http://minimal.example.com',
        )

        # Verify defaults
        assert result['description'] == ''
        assert result['enabled'] is True

    async def test_create_webhook_disabled(self):
        """Creates webhook with enabled=False."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        created_webhook = _create_mock_webhook(webhook_id=1, enabled=False)

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _create_write_result()
            return _create_mock_result(first_item=created_webhook)

        ap.persistence_mgr.execute_async = AsyncMock(side_effect=mock_execute)
        ap.persistence_mgr.serialize_model = Mock(return_value={'id': 1, 'enabled': False})

        service = WebhookService(ap)

        # Execute
        result = await service.create_webhook(
            WORKSPACE_UUID,
            name='Disabled',
            url='http://disabled.com',
            enabled=False,
        )

        # Verify
        assert result['enabled'] is False


class TestWebhookServiceGetWebhook:
    """Tests for get_webhook method."""

    async def test_get_webhook_by_id_found(self):
        """Returns webhook when found by ID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        webhook = _create_mock_webhook(webhook_id=1, name='Found Webhook')
        mock_result = _create_mock_result(first_item=webhook)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            return_value={
                'id': 1,
                'name': 'Found Webhook',
                'url': 'http://example.com/webhook',
            }
        )

        service = WebhookService(ap)

        # Execute
        result = await service.get_webhook(WORKSPACE_UUID, 1)

        # Verify
        assert result is not None
        assert result['id'] == 1
        assert result['name'] == 'Found Webhook'

    async def test_get_webhook_by_id_not_found(self):
        """Returns None when webhook not found."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result(first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = WebhookService(ap)

        # Execute
        result = await service.get_webhook(WORKSPACE_UUID, 999)

        # Verify
        assert result is None

    async def test_get_webhook_by_id_zero(self):
        """Handles ID=0 (edge case) correctly."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        mock_result = _create_mock_result(first_item=None)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        service = WebhookService(ap)

        # Execute
        result = await service.get_webhook(WORKSPACE_UUID, 0)

        # Verify - should return None (no webhook with ID 0)
        assert result is None


class TestWebhookServiceUpdateWebhook:
    """Tests for update_webhook method."""

    async def test_update_webhook_name_only(self):
        """Updates only the name field."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock(return_value=_create_write_result())

        service = WebhookService(ap)

        # Execute
        await service.update_webhook(WORKSPACE_UUID, 1, name='Updated Name')

        # Verify
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_update_webhook_url_only(self):
        """Updates only the url field."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock(return_value=_create_write_result())

        service = WebhookService(ap)

        # Execute
        await service.update_webhook(WORKSPACE_UUID, 1, url='http://updated.example.com')

        # Verify
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_update_webhook_description_only(self):
        """Updates only the description field."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock(return_value=_create_write_result())

        service = WebhookService(ap)

        # Execute
        await service.update_webhook(WORKSPACE_UUID, 1, description='Updated description')

        # Verify
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_update_webhook_enabled_only(self):
        """Updates only the enabled field."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock(return_value=_create_write_result())

        service = WebhookService(ap)

        # Execute
        await service.update_webhook(WORKSPACE_UUID, 1, enabled=False)

        # Verify
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_update_webhook_all_fields(self):
        """Updates all fields at once."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock(return_value=_create_write_result())

        service = WebhookService(ap)

        # Execute
        await service.update_webhook(
            WORKSPACE_UUID,
            1,
            name='All Updated',
            url='http://all.updated.com',
            description='All updated description',
            enabled=False,
        )

        # Verify
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_update_webhook_no_fields(self):
        """Does nothing when no fields provided."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        existing = _create_mock_webhook(webhook_id=1)
        ap.persistence_mgr.execute_async = AsyncMock(return_value=_create_mock_result(first_item=existing))
        ap.persistence_mgr.serialize_model = Mock(return_value={'id': 1})

        service = WebhookService(ap)

        # Execute - no update parameters
        await service.update_webhook(WORKSPACE_UUID, 1)

        # No write is issued; one scoped existence lookup is performed.
        ap.persistence_mgr.execute_async.assert_called_once()


class TestWebhookServiceDeleteWebhook:
    """Tests for delete_webhook method."""

    async def test_delete_webhook_by_id(self):
        """Deletes webhook by ID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock(return_value=_create_write_result())

        service = WebhookService(ap)

        # Execute
        await service.delete_webhook(WORKSPACE_UUID, 1)

        # Verify
        ap.persistence_mgr.execute_async.assert_called_once()

    async def test_delete_webhook_nonexistent_id(self):
        """Delete operation completes even for nonexistent ID."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        ap.persistence_mgr.execute_async = AsyncMock(return_value=_create_write_result(rowcount=0))

        service = WebhookService(ap)

        # Execute - should not raise
        await service.delete_webhook(WORKSPACE_UUID, 999)

        # Verify - still called
        ap.persistence_mgr.execute_async.assert_called_once()


class TestWebhookServiceGetEnabledWebhooks:
    """Tests for get_enabled_webhooks method."""

    async def test_get_enabled_webhooks_empty(self):
        """Returns empty list when no enabled webhooks."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(return_value={})

        service = WebhookService(ap)

        # Execute
        result = await service.get_enabled_webhooks(WORKSPACE_UUID)

        # Verify
        assert result == []

    async def test_get_enabled_webhooks_filters_enabled(self):
        """Returns only enabled webhooks."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        # All returned webhooks should be enabled (SQL filter)
        webhook1 = _create_mock_webhook(webhook_id=1, name='Enabled 1', enabled=True)
        webhook2 = _create_mock_webhook(webhook_id=2, name='Enabled 2', enabled=True)

        mock_result = _create_mock_result([webhook1, webhook2])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(
            side_effect=lambda model_cls, entity: {
                'id': entity.id,
                'name': entity.name,
                'enabled': entity.enabled,
            }
        )

        service = WebhookService(ap)

        # Execute
        result = await service.get_enabled_webhooks(WORKSPACE_UUID)

        # Verify
        assert len(result) == 2
        assert all(w['enabled'] for w in result)

    async def test_get_enabled_webhooks_filters_disabled(self):
        """Does not return disabled webhooks."""
        # Setup
        ap = SimpleNamespace()
        ap.persistence_mgr = SimpleNamespace()

        # Empty result because query filters on enabled=True
        mock_result = _create_mock_result([])
        ap.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)
        ap.persistence_mgr.serialize_model = Mock(return_value={})

        service = WebhookService(ap)

        # Execute
        result = await service.get_enabled_webhooks(WORKSPACE_UUID)

        # Verify - should be empty (SQL would filter disabled)
        assert result == []


ISOLATION_WORKSPACE_A = '00000000-0000-0000-0000-00000000000a'
ISOLATION_WORKSPACE_B = '00000000-0000-0000-0000-00000000000b'


class _RealPersistenceManager:
    def __init__(self, engine):
        self.engine = engine

    async def execute_async(self, *args, **kwargs):
        async with self.engine.connect() as connection:
            result = await connection.execute(*args, **kwargs)
            await connection.commit()
            return result

    @staticmethod
    def serialize_model(model, data, masked_columns=None):
        return {
            column.name: (
                getattr(data, column.name).isoformat()
                if isinstance(getattr(data, column.name), datetime.datetime)
                else getattr(data, column.name)
            )
            for column in model.__table__.columns
            if column.name not in (masked_columns or [])
        }


@pytest.fixture
async def tenant_webhook_service(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "webhooks.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            sqlalchemy.insert(Workspace),
            [
                {
                    'uuid': ISOLATION_WORKSPACE_A,
                    'instance_uuid': 'instance',
                    'name': 'A',
                    'slug': 'a',
                    'source': 'cloud_projection',
                },
                {
                    'uuid': ISOLATION_WORKSPACE_B,
                    'instance_uuid': 'instance',
                    'name': 'B',
                    'slug': 'b',
                    'source': 'cloud_projection',
                },
            ],
        )
    service = WebhookService(SimpleNamespace(persistence_mgr=_RealPersistenceManager(engine)))
    yield service
    await engine.dispose()


async def test_webhook_service_requires_workspace(tenant_webhook_service):
    with pytest.raises(WorkspaceRequiredError):
        await tenant_webhook_service.get_webhooks(None)


async def test_same_name_webhooks_are_isolated(tenant_webhook_service):
    created_a = await tenant_webhook_service.create_webhook(
        ISOLATION_WORKSPACE_A,
        'deploy',
        'https://a.invalid',
    )
    created_b = await tenant_webhook_service.create_webhook(
        ISOLATION_WORKSPACE_B,
        'deploy',
        'https://b.invalid',
    )

    assert created_a['workspace_uuid'] == ISOLATION_WORKSPACE_A
    assert created_b['workspace_uuid'] == ISOLATION_WORKSPACE_B
    assert [item['url'] for item in await tenant_webhook_service.get_webhooks(ISOLATION_WORKSPACE_A)] == ['***']
    assert [item['url'] for item in await tenant_webhook_service.get_webhooks(ISOLATION_WORKSPACE_B)] == ['***']
    assert [
        item['url'] for item in await tenant_webhook_service.get_webhooks(ISOLATION_WORKSPACE_A, include_secret=True)
    ] == ['https://a.invalid']
    assert [
        item['url'] for item in await tenant_webhook_service.get_webhooks(ISOLATION_WORKSPACE_B, include_secret=True)
    ] == ['https://b.invalid']


async def test_cross_workspace_id_guessing_is_not_found(tenant_webhook_service):
    created = await tenant_webhook_service.create_webhook(
        ISOLATION_WORKSPACE_A,
        'secret',
        'https://a.invalid/hook',
    )
    webhook_id = created['id']

    assert await tenant_webhook_service.get_webhook(ISOLATION_WORKSPACE_B, webhook_id) is None
    assert not await tenant_webhook_service.update_webhook(
        ISOLATION_WORKSPACE_B,
        webhook_id,
        name='stolen',
    )
    assert not await tenant_webhook_service.delete_webhook(ISOLATION_WORKSPACE_B, webhook_id)
    assert (await tenant_webhook_service.get_webhook(ISOLATION_WORKSPACE_A, webhook_id))['name'] == 'secret'


async def test_update_and_delete_are_scoped(tenant_webhook_service):
    created = await tenant_webhook_service.create_webhook(
        ISOLATION_WORKSPACE_A,
        'old',
        'https://a.invalid/old',
    )
    assert await tenant_webhook_service.update_webhook(
        ISOLATION_WORKSPACE_A,
        created['id'],
        name='new',
        enabled=False,
    )
    assert await tenant_webhook_service.get_enabled_webhooks(ISOLATION_WORKSPACE_A) == []
    assert await tenant_webhook_service.delete_webhook(ISOLATION_WORKSPACE_A, created['id'])
    assert await tenant_webhook_service.get_webhook(ISOLATION_WORKSPACE_A, created['id']) is None


async def test_masked_webhook_url_roundtrip_preserves_replace_and_clear(tenant_webhook_service):
    created = await tenant_webhook_service.create_webhook(
        ISOLATION_WORKSPACE_A,
        'roundtrip',
        'https://a.invalid/bearer-secret',
    )

    masked = await tenant_webhook_service.get_webhook(ISOLATION_WORKSPACE_A, created['id'])
    assert masked['url'] == '***'
    assert await tenant_webhook_service.update_webhook(
        ISOLATION_WORKSPACE_A,
        created['id'],
        name='preserved',
        url=masked['url'],
    )
    preserved = await tenant_webhook_service.get_webhook(
        ISOLATION_WORKSPACE_A,
        created['id'],
        include_secret=True,
    )
    assert preserved['url'] == 'https://a.invalid/bearer-secret'

    assert await tenant_webhook_service.update_webhook(
        ISOLATION_WORKSPACE_A,
        created['id'],
        url='https://a.invalid/replacement',
    )
    replaced = await tenant_webhook_service.get_webhook(
        ISOLATION_WORKSPACE_A,
        created['id'],
        include_secret=True,
    )
    assert replaced['url'] == 'https://a.invalid/replacement'

    assert await tenant_webhook_service.update_webhook(ISOLATION_WORKSPACE_A, created['id'], url='')
    cleared = await tenant_webhook_service.get_webhook(
        ISOLATION_WORKSPACE_A,
        created['id'],
        include_secret=True,
    )
    assert cleared['url'] == ''
