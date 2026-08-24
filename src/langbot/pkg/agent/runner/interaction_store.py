"""Persistent Host store for structured interaction requests."""

from __future__ import annotations

import datetime
import hashlib
import json
import secrets
import typing

import sqlalchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from ...entity.persistence.agent_interaction import AgentInteraction


UTC = datetime.timezone.utc
INTERACTION_STATUSES = {'pending', 'submitted', 'expired', 'cancelled', 'delivery_failed'}
PROCESSOR_TYPES = {'agent', 'pipeline'}


class InteractionStoreError(Exception):
    """Base error for interaction persistence operations."""


class InteractionNotFoundError(InteractionStoreError):
    """Raised when a callback token does not identify an interaction."""


class InteractionScopeError(InteractionStoreError):
    """Raised when a callback does not belong to the stored delivery scope."""


class InteractionExpiredError(InteractionStoreError):
    """Raised when an interaction is no longer accepting submissions."""


class InteractionAlreadySubmittedError(InteractionStoreError):
    """Raised when an interaction callback is replayed."""


class DuplicateInteractionError(InteractionStoreError):
    """Raised when one run emits the same interaction ID more than once."""


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(UTC)


def _as_utc(value: datetime.datetime | None) -> datetime.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _epoch_to_datetime(value: int | float | None) -> datetime.datetime | None:
    if value is None:
        return None
    try:
        return datetime.datetime.fromtimestamp(float(value), UTC)
    except (TypeError, ValueError, OSError) as exc:
        raise ValueError('expires_at must be a valid epoch timestamp') from exc


def _datetime_to_epoch(value: datetime.datetime | None) -> int | None:
    normalized = _as_utc(value)
    return int(normalized.timestamp()) if normalized is not None else None


def _json_dumps(value: typing.Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _json_loads(value: str | None, default: typing.Any) -> typing.Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


class InteractionStore:
    """Store interaction correlation and consume callbacks exactly once."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self._session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def create_request(
        self,
        *,
        interaction_id: str,
        run_id: str,
        binding_id: str,
        runner_id: str,
        processor_type: str,
        processor_id: str,
        request: dict[str, typing.Any],
        delivery_target: dict[str, typing.Any] | None,
        replaces_interaction_id: str | None = None,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        conversation_id: str | None = None,
        thread_id: str | None = None,
        actor_id: str | None = None,
        expires_at: int | float | None = None,
    ) -> tuple[dict[str, typing.Any], str]:
        """Persist a request and return its record plus one-time callback token."""
        if not interaction_id or not run_id or not binding_id or not runner_id or not processor_id:
            raise ValueError('interaction, run, binding, runner, and processor IDs are required')
        if processor_type not in PROCESSOR_TYPES:
            raise ValueError(f'Unsupported processor type: {processor_type}')

        request_json = _json_dumps(request)
        delivery_target_json = _json_dumps(delivery_target) if delivery_target is not None else None
        expires_at_dt = _epoch_to_datetime(expires_at)
        now = _utc_now()
        if expires_at_dt is not None and expires_at_dt <= now:
            raise ValueError('expires_at must be in the future')

        callback_token = secrets.token_urlsafe(18)
        row = AgentInteraction(
            interaction_id=interaction_id,
            run_id=run_id,
            binding_id=binding_id,
            runner_id=runner_id,
            processor_type=processor_type,
            processor_id=processor_id,
            bot_id=bot_id,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            thread_id=thread_id,
            actor_id=actor_id,
            status='pending',
            request_json=request_json,
            delivery_target_json=delivery_target_json,
            replaces_interaction_id=replaces_interaction_id,
            callback_token_hash=_token_hash(callback_token),
            expires_at=expires_at_dt,
            created_at=now,
            updated_at=now,
        )

        async with self._session_factory() as session:
            existing = await self._get_by_run_interaction(session, run_id, interaction_id)
            if existing is not None:
                raise DuplicateInteractionError(f'Interaction {interaction_id} already exists for run {run_id}')
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise DuplicateInteractionError(
                    f'Interaction {interaction_id} could not be created for run {run_id}'
                ) from exc
            return self._to_dict(row), callback_token

    async def record_delivery_success(
        self,
        run_id: str,
        interaction_id: str,
        delivery_result: dict[str, typing.Any],
    ) -> bool:
        """Persist the platform presentation handle returned after delivery."""
        payload = _json_dumps(delivery_result)
        if len(payload.encode('utf-8')) > 64 * 1024:
            raise ValueError('interaction delivery result exceeds 64 KiB')
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.update(AgentInteraction)
                .where(
                    AgentInteraction.run_id == run_id,
                    AgentInteraction.interaction_id == interaction_id,
                    AgentInteraction.status.in_(['pending', 'submitted']),
                )
                .values(delivery_result_json=payload, updated_at=_utc_now())
            )
            await session.commit()
            return result.rowcount == 1

    async def find_update_target(
        self,
        *,
        interaction_id: str,
        binding_id: str,
        runner_id: str,
        processor_type: str,
        processor_id: str,
        bot_id: str | None,
        conversation_id: str | None,
        actor_id: str | None,
    ) -> dict[str, typing.Any] | None:
        """Find a submitted interaction whose platform presentation can be replaced."""
        if not interaction_id:
            return None
        conditions = [
            AgentInteraction.interaction_id == interaction_id,
            AgentInteraction.binding_id == binding_id,
            AgentInteraction.runner_id == runner_id,
            AgentInteraction.processor_type == processor_type,
            AgentInteraction.processor_id == processor_id,
            AgentInteraction.status == 'submitted',
            AgentInteraction.delivery_result_json.is_not(None),
        ]
        for column, value in (
            (AgentInteraction.bot_id, bot_id),
            (AgentInteraction.conversation_id, conversation_id),
            (AgentInteraction.actor_id, actor_id),
        ):
            conditions.append(column.is_(None) if value is None else column == value)

        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(AgentInteraction)
                .where(*conditions)
                .order_by(AgentInteraction.submitted_at.desc(), AgentInteraction.id.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return self._to_dict(row) if row is not None else None

    async def get_request(self, run_id: str, interaction_id: str) -> dict[str, typing.Any] | None:
        """Return a request by the runner-visible identity."""
        async with self._session_factory() as session:
            row = await self._get_by_run_interaction(session, run_id, interaction_id)
            return self._to_dict(row) if row is not None else None

    async def get_by_callback_token(self, callback_token: str) -> dict[str, typing.Any] | None:
        """Resolve callback metadata without exposing the stored token hash."""
        if not callback_token:
            return None
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(AgentInteraction).where(
                    AgentInteraction.callback_token_hash == _token_hash(callback_token)
                )
            )
            row = result.scalar_one_or_none()
            return self._to_dict(row) if row is not None else None

    async def consume_submission(
        self,
        *,
        callback_token: str,
        submission: dict[str, typing.Any],
        bot_id: str | None,
        conversation_id: str | None,
        actor_id: str | None,
        submitted_at: int | float | None = None,
    ) -> dict[str, typing.Any]:
        """Validate and atomically consume one platform callback."""
        if not callback_token:
            raise InteractionNotFoundError('Missing interaction callback token')
        now = _utc_now()
        submission_time = _epoch_to_datetime(submitted_at) or now
        token_hash = _token_hash(callback_token)

        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(AgentInteraction).where(AgentInteraction.callback_token_hash == token_hash)
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise InteractionNotFoundError('Unknown interaction callback token')
            if row.status == 'submitted':
                raise InteractionAlreadySubmittedError('Interaction was already submitted')
            if row.status != 'pending':
                raise InteractionExpiredError(f'Interaction is not pending: {row.status}')

            if submission.get('interaction_id') != row.interaction_id:
                raise InteractionScopeError('Interaction ID does not match callback token')

            expires_at = _as_utc(row.expires_at)
            if expires_at is not None and expires_at <= now:
                row.status = 'expired'
                row.status_reason = 'interaction expired before submission'
                row.updated_at = now
                await session.commit()
                raise InteractionExpiredError('Interaction has expired')

            self._validate_scope(row, bot_id, conversation_id, actor_id)

            update_result = await session.execute(
                sqlalchemy.update(AgentInteraction)
                .where(
                    AgentInteraction.id == row.id,
                    AgentInteraction.status == 'pending',
                )
                .values(
                    status='submitted',
                    submitted_at=submission_time,
                    submission_json=_json_dumps(submission),
                    updated_at=now,
                )
            )
            if update_result.rowcount != 1:
                await session.rollback()
                raise InteractionAlreadySubmittedError('Interaction callback lost an idempotency race')
            await session.commit()

            refreshed = await session.get(AgentInteraction, row.id)
            if refreshed is None:
                raise InteractionNotFoundError('Interaction disappeared after submission')
            return self._to_dict(refreshed)

    async def mark_delivery_failed(self, run_id: str, interaction_id: str, reason: str) -> bool:
        """Mark an undelivered pending interaction terminal."""
        now = _utc_now()
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.update(AgentInteraction)
                .where(
                    AgentInteraction.run_id == run_id,
                    AgentInteraction.interaction_id == interaction_id,
                    AgentInteraction.status == 'pending',
                )
                .values(status='delivery_failed', status_reason=reason, updated_at=now)
            )
            await session.commit()
            return result.rowcount == 1

    async def expire_pending(self, *, now: datetime.datetime | None = None) -> int:
        """Expire pending interactions whose deadline has elapsed."""
        cutoff = _as_utc(now) or _utc_now()
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.update(AgentInteraction)
                .where(
                    AgentInteraction.status == 'pending',
                    AgentInteraction.expires_at.is_not(None),
                    AgentInteraction.expires_at <= cutoff,
                )
                .values(
                    status='expired',
                    status_reason='interaction expired',
                    updated_at=cutoff,
                )
            )
            await session.commit()
            return int(result.rowcount or 0)

    @staticmethod
    def _validate_scope(
        row: AgentInteraction,
        bot_id: str | None,
        conversation_id: str | None,
        actor_id: str | None,
    ) -> None:
        checks = (
            ('bot', row.bot_id, bot_id),
            ('conversation', row.conversation_id, conversation_id),
            ('actor', row.actor_id, actor_id),
        )
        for label, expected, actual in checks:
            if expected is not None and expected != actual:
                raise InteractionScopeError(f'Interaction {label} scope mismatch')

    @staticmethod
    async def _get_by_run_interaction(
        session: AsyncSession,
        run_id: str,
        interaction_id: str,
    ) -> AgentInteraction | None:
        result = await session.execute(
            sqlalchemy.select(AgentInteraction).where(
                AgentInteraction.run_id == run_id,
                AgentInteraction.interaction_id == interaction_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_dict(row: AgentInteraction) -> dict[str, typing.Any]:
        return {
            'id': row.id,
            'interaction_id': row.interaction_id,
            'run_id': row.run_id,
            'binding_id': row.binding_id,
            'runner_id': row.runner_id,
            'processor_type': row.processor_type,
            'processor_id': row.processor_id,
            'bot_id': row.bot_id,
            'workspace_id': row.workspace_id,
            'conversation_id': row.conversation_id,
            'thread_id': row.thread_id,
            'actor_id': row.actor_id,
            'status': row.status,
            'request': _json_loads(row.request_json, {}),
            'delivery_target': _json_loads(row.delivery_target_json, None),
            'delivery_result': _json_loads(row.delivery_result_json, None),
            'replaces_interaction_id': row.replaces_interaction_id,
            'expires_at': _datetime_to_epoch(row.expires_at),
            'submitted_at': _datetime_to_epoch(row.submitted_at),
            'submission': _json_loads(row.submission_json, None),
            'status_reason': row.status_reason,
            'created_at': _datetime_to_epoch(row.created_at),
            'updated_at': _datetime_to_epoch(row.updated_at),
        }
