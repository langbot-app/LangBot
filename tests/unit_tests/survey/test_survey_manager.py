"""Unit tests for survey manager.

Tests cover:
- SurveyManager initialization
- Event triggering and tracking
- Pending survey fetching
- Survey response submission
- Survey dismissal
"""
from __future__ import annotations

import pytest
import json
from unittest.mock import Mock, AsyncMock, MagicMock
from importlib import import_module


def get_survey_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.survey.manager')


def create_mock_app():
    """Create mock Application for testing."""
    mock_app = Mock()
    mock_app.logger = Mock()
    mock_app.instance_config = Mock()
    mock_app.instance_config.data = {'space': {'url': 'https://space.example.com'}}
    mock_app.persistence_mgr = AsyncMock()
    mock_app.persistence_mgr.execute_async = AsyncMock()
    return mock_app


class TestSurveyManagerInit:
    """Tests for SurveyManager initialization."""

    def test_init_stores_app_reference(self):
        """Test that __init__ stores Application reference."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)

        assert manager.ap is mock_app

    def test_init_creates_empty_triggered_events(self):
        """Test that triggered_events starts as empty set."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)

        assert manager._triggered_events == set()

    def test_init_pending_survey_is_none(self):
        """Test that pending_survey starts as None."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)

        assert manager._pending_survey is None

    @pytest.mark.asyncio
    async def test_initialize_loads_space_url(self):
        """Test that initialize loads space URL from config."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()
        mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(first=Mock(return_value=None)))

        manager = survey_module.SurveyManager(mock_app)
        await manager.initialize()

        assert manager._space_url == 'https://space.example.com'

    @pytest.mark.asyncio
    async def test_initialize_strips_trailing_slash_from_url(self):
        """Test that trailing slash is stripped from URL."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()
        mock_app.instance_config.data = {'space': {'url': 'https://space.example.com/'}}
        mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(first=Mock(return_value=None)))

        manager = survey_module.SurveyManager(mock_app)
        await manager.initialize()

        assert manager._space_url == 'https://space.example.com'

    @pytest.mark.asyncio
    async def test_initialize_handles_empty_space_config(self):
        """Test that initialize handles empty space config."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()
        mock_app.instance_config.data = {}
        mock_app.persistence_mgr.execute_async = AsyncMock(return_value=Mock(first=Mock(return_value=None)))

        manager = survey_module.SurveyManager(mock_app)
        await manager.initialize()

        assert manager._space_url == ''


class TestLoadTriggeredEvents:
    """Tests for _load_triggered_events method."""

    @pytest.mark.asyncio
    async def test_loads_events_from_metadata(self):
        """Test that events are loaded from metadata table."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        # Mock existing metadata row
        mock_row = Mock()
        mock_row.value = json.dumps(['event1', 'event2'])
        mock_result = Mock()
        mock_result.first = Mock(return_value=(mock_row,))
        mock_app.persistence_mgr.execute_async = AsyncMock(return_value=mock_result)

        manager = survey_module.SurveyManager(mock_app)
        await manager._load_triggered_events()

        assert 'event1' in manager._triggered_events
        assert 'event2' in manager._triggered_events

    @pytest.mark.asyncio
    async def test_handles_no_existing_events(self):
        """Test that empty set is used when no events stored."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()
        mock_app.persistence_mgr.execute_async = AsyncMock(
            return_value=Mock(first=Mock(return_value=None))
        )

        manager = survey_module.SurveyManager(mock_app)
        await manager._load_triggered_events()

        assert manager._triggered_events == set()

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """Test that exception results in empty set."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()
        mock_app.persistence_mgr.execute_async = AsyncMock(side_effect=Exception('DB error'))

        manager = survey_module.SurveyManager(mock_app)
        await manager._load_triggered_events()

        assert manager._triggered_events == set()


class TestIsSpaceConfigured:
    """Tests for _is_space_configured method."""

    def test_returns_true_when_url_set(self):
        """Test returns True when space URL is configured."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)
        manager._space_url = 'https://space.example.com'

        assert manager._is_space_configured() is True

    def test_returns_false_when_url_empty(self):
        """Test returns False when space URL is empty."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)
        manager._space_url = ''

        assert manager._is_space_configured() is False

    def test_returns_false_when_telemetry_disabled(self):
        """Test returns False when disable_telemetry is True."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()
        mock_app.instance_config.data = {'space': {'url': 'https://space.example.com', 'disable_telemetry': True}}

        manager = survey_module.SurveyManager(mock_app)
        manager._space_url = 'https://space.example.com'

        assert manager._is_space_configured() is False


class TestTriggerEvent:
    """Tests for trigger_event method."""

    @pytest.mark.asyncio
    async def test_skips_already_triggered_event(self):
        """Test that already triggered events are skipped."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)
        manager._triggered_events.add('event1')

        await manager.trigger_event('event1')

        # Should not call save
        mock_app.persistence_mgr.execute_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_space_not_configured(self):
        """Test that event is skipped when space not configured."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)
        manager._space_url = ''

        await manager.trigger_event('new_event')

        assert 'new_event' not in manager._triggered_events

    @pytest.mark.asyncio
    async def test_adds_new_event_and_saves(self):
        """Test that new event is added and saved."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()
        mock_app.persistence_mgr.execute_async = AsyncMock(
            return_value=Mock(first=Mock(return_value=None))
        )

        manager = survey_module.SurveyManager(mock_app)
        manager._space_url = 'https://space.example.com'

        await manager.trigger_event('new_event')

        assert 'new_event' in manager._triggered_events


class TestPendingSurvey:
    """Tests for get_pending_survey and clear_pending_survey."""

    def test_returns_none_when_no_pending(self):
        """Test returns None when no pending survey."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)

        assert manager.get_pending_survey() is None

    def test_returns_pending_survey(self):
        """Test returns the pending survey."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)
        manager._pending_survey = {'survey_id': '123', 'questions': []}

        result = manager.get_pending_survey()

        assert result['survey_id'] == '123'

    def test_clear_pending_survey(self):
        """Test that clear_pending_survey sets to None."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)
        manager._pending_survey = {'survey_id': '123'}

        manager.clear_pending_survey()

        assert manager._pending_survey is None


class TestSubmitResponse:
    """Tests for submit_response method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_space_not_configured(self):
        """Test returns False when space not configured."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)
        manager._space_url = ''

        result = await manager.submit_response('survey123', {'q1': 'answer1'})

        assert result is False

    @pytest.mark.asyncio
    async def test_clears_pending_on_success(self):
        """Test that pending survey is cleared on success."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)
        manager._space_url = 'https://space.example.com'
        manager._pending_survey = {'survey_id': 'survey123'}

        # Mock successful HTTP response
        import httpx
        mock_response = Mock()
        mock_response.status_code = 200

        with pytest.MonkeyPatch().context() as m:
            m.setattr(httpx, 'AsyncClient', lambda **kwargs: MagicMock(
                __aenter__=AsyncMock(return_value=Mock(post=AsyncMock(return_value=mock_response))),
                __aexit__=AsyncMock(return_value=None)
            ))
            result = await manager.submit_response('survey123', {'q1': 'answer1'})

        assert result is True
        assert manager._pending_survey is None


class TestDismissSurvey:
    """Tests for dismiss_survey method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_space_not_configured(self):
        """Test returns False when space not configured."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)
        manager._space_url = ''

        result = await manager.dismiss_survey('survey123')

        assert result is False

    @pytest.mark.asyncio
    async def test_clears_pending_on_success(self):
        """Test that pending survey is cleared on success."""
        survey_module = get_survey_module()
        mock_app = create_mock_app()

        manager = survey_module.SurveyManager(mock_app)
        manager._space_url = 'https://space.example.com'
        manager._pending_survey = {'survey_id': 'survey123'}

        # Mock successful HTTP response
        import httpx
        mock_response = Mock()
        mock_response.status_code = 200

        with pytest.MonkeyPatch().context() as m:
            m.setattr(httpx, 'AsyncClient', lambda **kwargs: MagicMock(
                __aenter__=AsyncMock(return_value=Mock(post=AsyncMock(return_value=mock_response))),
                __aexit__=AsyncMock(return_value=None)
            ))
            result = await manager.dismiss_survey('survey123')

        assert result is True
        assert manager._pending_survey is None