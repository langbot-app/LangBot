"""Survey manager: tracks events, communicates with Space to fetch/submit surveys."""

from __future__ import annotations

import asyncio
import json
import typing
import httpx
import sqlalchemy

from ..core import app as core_app
from ..entity.persistence.metadata import Metadata
from ..utils import constants

SURVEY_TRIGGERED_KEY = 'survey_triggered_events'
BOT_RESPONSE_COUNT_KEY = 'survey_bot_response_count'

# Milestone event fired when an instance accumulates this many successful bot responses
BOT_RESPONSE_MILESTONE = 100
BOT_RESPONSE_MILESTONE_EVENT = f'bot_response_success_{BOT_RESPONSE_MILESTONE}'


class SurveyManager:
    """Manages survey lifecycle: event tracking, pending survey fetch, submission."""

    def __init__(self, ap: core_app.Application):
        self.ap = ap
        self._triggered_events: set[str] = set()
        self._pending_survey: typing.Optional[dict] = None
        self._space_url: str = ''
        self._bot_response_count: int = 0

    async def initialize(self):
        space_config = self.ap.instance_config.data.get('space', {})
        self._space_url = space_config.get('url', '').rstrip('/')
        await self._load_triggered_events()
        await self._load_bot_response_count()

    async def _load_triggered_events(self):
        """Load previously triggered events from metadata table."""
        try:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(Metadata).where(Metadata.key == SURVEY_TRIGGERED_KEY)
            )
            row = result.first()
            if row:
                self._triggered_events = set(json.loads(row[0].value))
        except Exception:
            self._triggered_events = set()

    async def _save_triggered_events(self):
        """Persist triggered events to metadata table."""
        try:
            value = json.dumps(list(self._triggered_events))
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(Metadata).where(Metadata.key == SURVEY_TRIGGERED_KEY)
            )
            if result.first():
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(Metadata).where(Metadata.key == SURVEY_TRIGGERED_KEY).values(value=value)
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(Metadata).values(key=SURVEY_TRIGGERED_KEY, value=value)
                )
        except Exception as e:
            self.ap.logger.debug(f'Failed to save survey triggered events: {e}')

    def _is_space_configured(self) -> bool:
        space_config = self.ap.instance_config.data.get('space', {})
        if space_config.get('disable_telemetry', False):
            return False
        return bool(self._space_url)

    async def _load_bot_response_count(self):
        """Load the persisted successful bot response count from metadata table."""
        try:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(Metadata).where(Metadata.key == BOT_RESPONSE_COUNT_KEY)
            )
            row = result.first()
            if row:
                self._bot_response_count = int(row[0].value)
        except Exception:
            self._bot_response_count = 0

    async def _save_bot_response_count(self):
        """Persist the successful bot response count to metadata table."""
        try:
            value = str(self._bot_response_count)
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(Metadata).where(Metadata.key == BOT_RESPONSE_COUNT_KEY)
            )
            if result.first():
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.update(Metadata).where(Metadata.key == BOT_RESPONSE_COUNT_KEY).values(value=value)
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.insert(Metadata).values(key=BOT_RESPONSE_COUNT_KEY, value=value)
                )
        except Exception as e:
            self.ap.logger.debug(f'Failed to save survey bot response count: {e}')

    async def record_bot_response_success(self):
        """Count a successful bot response; fires the milestone event at the threshold.

        Called by the chat handler after each successful (non-WebSocket) response.
        The count is persisted so it survives restarts. Once the milestone event
        has been triggered, counting stops (no further writes needed).
        """
        if BOT_RESPONSE_MILESTONE_EVENT in self._triggered_events:
            return
        if not self._is_space_configured():
            return

        self._bot_response_count += 1
        await self._save_bot_response_count()

        if self._bot_response_count >= BOT_RESPONSE_MILESTONE:
            await self.trigger_event(BOT_RESPONSE_MILESTONE_EVENT)

    async def trigger_event(self, event: str):
        """Called when an event occurs. Checks Space for a pending survey."""
        if event in self._triggered_events:
            return
        if not self._is_space_configured():
            return

        self._triggered_events.add(event)
        await self._save_triggered_events()

        # Check for pending survey asynchronously
        asyncio.create_task(self._fetch_pending_survey(event))

    async def _fetch_pending_survey(self, event: str):
        """Fetch pending survey from Space for this event."""
        try:
            url = f'{self._space_url}/api/v1/survey/pending'
            payload = {
                'instance_id': constants.instance_id,
                'event': event,
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('code') == 0 and data.get('data', {}).get('survey'):
                        self._pending_survey = data['data']['survey']
                        self.ap.logger.info(f'Survey pending: {self._pending_survey.get("survey_id")}')
        except Exception as e:
            self.ap.logger.debug(f'Failed to fetch pending survey: {e}')

    def get_pending_survey(self) -> typing.Optional[dict]:
        """Return the current pending survey (if any) for the frontend to display."""
        return self._pending_survey

    def clear_pending_survey(self):
        """Clear the pending survey (after user responds or dismisses)."""
        self._pending_survey = None

    async def _build_base_metadata(self, user_email: str | None = None) -> dict:
        metadata = {
            'version': constants.semantic_version,
            'instance_id': constants.instance_id,
        }
        if user_email:
            metadata['login_account'] = user_email
            try:
                user_obj = await self.ap.user_service.get_user_by_email(user_email)
                metadata['account_type'] = getattr(user_obj, 'account_type', '') or 'local'
                metadata['space_account_uuid'] = getattr(user_obj, 'space_account_uuid', '') or ''
            except Exception:
                pass
        return metadata

    async def submit_response(self, survey_id: str, answers: dict, completed: bool = True) -> bool:
        """Submit a survey response to Space."""
        if not self._is_space_configured():
            return False
        try:
            url = f'{self._space_url}/api/v1/survey/respond'
            payload = {
                'survey_id': survey_id,
                'instance_id': constants.instance_id,
                'answers': answers,
                'metadata': await self._build_base_metadata(),
                'completed': completed,
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    self.clear_pending_survey()
                    return True
        except Exception as e:
            self.ap.logger.warning(f'Failed to submit survey response: {e}')
        return False

    async def submit_feedback(
        self,
        content: str,
        attachments: list[dict],
        page_url: str,
        user_agent: str,
        user_email: str | None = None,
    ) -> bool:
        """Submit an on-demand user feedback item to Space."""
        if not self._is_space_configured():
            return False
        try:
            url = f'{self._space_url}/api/v1/survey/feedback'
            metadata = await self._build_base_metadata(user_email)
            metadata.update(
                {
                    'page_url': page_url,
                    'user_agent': user_agent,
                }
            )
            payload = {
                'instance_id': constants.instance_id,
                'content': content,
                'attachments': attachments,
                'metadata': metadata,
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    return True
                self.ap.logger.warning(f'Failed to submit feedback: {resp.status_code} {resp.text[:200]}')
        except Exception as e:
            self.ap.logger.warning(f'Failed to submit feedback: {e}')
        return False

    async def dismiss_survey(self, survey_id: str) -> bool:
        """Dismiss a survey."""
        if not self._is_space_configured():
            return False
        try:
            url = f'{self._space_url}/api/v1/survey/dismiss'
            payload = {
                'survey_id': survey_id,
                'instance_id': constants.instance_id,
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    self.clear_pending_survey()
                    return True
        except Exception as e:
            self.ap.logger.warning(f'Failed to dismiss survey: {e}')
        return False
