"""Tests for Host-owned structured interaction persistence."""

from __future__ import annotations

import datetime
import hashlib

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.agent.runner.interaction_store import (
    DuplicateInteractionError,
    InteractionAlreadySubmittedError,
    InteractionExpiredError,
    InteractionScopeError,
    InteractionStore,
)
from langbot.pkg.entity.persistence.agent_interaction import AgentInteraction
from langbot.pkg.entity.persistence.base import Base


UTC = datetime.timezone.utc


@pytest.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "interactions.db"}', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def store(db_engine):
    return InteractionStore(db_engine)


async def _create(store: InteractionStore, **overrides):
    values = {
        'interaction_id': 'form-1',
        'run_id': 'run-1',
        'binding_id': 'binding-1',
        'runner_id': 'plugin:test/ApprovalRunner/default',
        'processor_type': 'pipeline',
        'processor_id': 'pipeline-1',
        'request': {'interaction_id': 'form-1', 'title': 'Approve?', 'fallback_text': 'Reply yes or no.'},
        'delivery_target': {'chat_id': 'chat-1'},
        'bot_id': 'bot-1',
        'conversation_id': 'group_chat-1',
        'actor_id': 'user-1',
        'expires_at': int((datetime.datetime.now(UTC) + datetime.timedelta(minutes=5)).timestamp()),
    }
    values.update(overrides)
    return await store.create_request(**values)


@pytest.mark.asyncio
async def test_create_request_returns_token_but_persists_only_hash(store, db_engine):
    record, token = await _create(store)

    assert record['status'] == 'pending'
    assert record['processor_type'] == 'pipeline'
    assert token

    async with db_engine.connect() as conn:
        result = await conn.execute(sqlalchemy.select(AgentInteraction.callback_token_hash))
        stored_hash = result.scalar_one()

    assert stored_hash == hashlib.sha256(token.encode()).hexdigest()
    assert stored_hash != token


@pytest.mark.asyncio
async def test_submission_is_scope_checked_and_consumed_once(store):
    _, token = await _create(store)

    submitted = await store.consume_submission(
        callback_token=token,
        submission={'interaction_id': 'form-1', 'action_id': 'approve', 'values': {'name': 'Alice'}},
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor_id='user-1',
    )

    assert submitted['status'] == 'submitted'
    assert submitted['submission']['action_id'] == 'approve'
    assert submitted['submission']['values'] == {'name': 'Alice'}

    with pytest.raises(InteractionAlreadySubmittedError):
        await store.consume_submission(
            callback_token=token,
            submission={'interaction_id': 'form-1', 'action_id': 'approve', 'values': {}},
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='user-1',
        )


@pytest.mark.asyncio
async def test_delivery_result_can_be_resolved_for_scoped_update(store):
    _, token = await _create(store)
    assert await store.record_delivery_success(
        'run-1',
        'form-1',
        {'message_id': 'message-1', 'rich': True},
    )
    await store.consume_submission(
        callback_token=token,
        submission={'interaction_id': 'form-1', 'action_id': 'approve', 'values': {}},
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor_id='user-1',
    )
    assert await store.record_delivery_success(
        'run-1',
        'form-1',
        {'message_id': 'message-1', 'card_id': 'card-1', 'sequence': 1, 'rich': True},
    )

    target = await store.find_update_target(
        interaction_id='form-1',
        binding_id='binding-1',
        runner_id='plugin:test/ApprovalRunner/default',
        processor_type='pipeline',
        processor_id='pipeline-1',
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor_id='user-1',
    )
    assert target['delivery_result'] == {
        'message_id': 'message-1',
        'card_id': 'card-1',
        'sequence': 1,
        'rich': True,
    }

    assert (
        await store.find_update_target(
            interaction_id='form-1',
            binding_id='binding-1',
            runner_id='plugin:test/ApprovalRunner/default',
            processor_type='pipeline',
            processor_id='pipeline-1',
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='other-user',
        )
        is None
    )


@pytest.mark.asyncio
async def test_scope_mismatch_does_not_consume_request(store):
    _, token = await _create(store)

    with pytest.raises(InteractionScopeError, match='actor'):
        await store.consume_submission(
            callback_token=token,
            submission={'interaction_id': 'form-1', 'values': {}},
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='other-user',
        )

    record = await store.get_request('run-1', 'form-1')
    assert record is not None
    assert record['status'] == 'pending'


@pytest.mark.asyncio
async def test_expired_request_is_marked_terminal(store):
    _, token = await _create(store)
    cutoff = datetime.datetime.now(UTC) + datetime.timedelta(minutes=10)
    assert await store.expire_pending(now=cutoff) == 1

    with pytest.raises(InteractionExpiredError):
        await store.consume_submission(
            callback_token=token,
            submission={'interaction_id': 'form-1', 'values': {}},
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='user-1',
        )

    record = await store.get_request('run-1', 'form-1')
    assert record is not None
    assert record['status'] == 'expired'


@pytest.mark.asyncio
async def test_forged_old_submission_time_cannot_bypass_server_expiry(store, db_engine):
    _, token = await _create(store)
    expired_at = datetime.datetime.now(UTC) - datetime.timedelta(minutes=1)
    async with db_engine.begin() as conn:
        await conn.execute(
            sqlalchemy.update(AgentInteraction).where(AgentInteraction.run_id == 'run-1').values(expires_at=expired_at)
        )

    with pytest.raises(InteractionExpiredError):
        await store.consume_submission(
            callback_token=token,
            submission={'interaction_id': 'form-1', 'values': {}},
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='user-1',
            submitted_at=int((expired_at - datetime.timedelta(minutes=1)).timestamp()),
        )

    record = await store.get_request('run-1', 'form-1')
    assert record is not None
    assert record['status'] == 'expired'


@pytest.mark.asyncio
async def test_interaction_id_is_unique_within_run_only(store):
    await _create(store)

    with pytest.raises(DuplicateInteractionError):
        await _create(store)

    second, _ = await _create(store, run_id='run-2')
    assert second['interaction_id'] == 'form-1'
    assert second['run_id'] == 'run-2'


@pytest.mark.asyncio
async def test_expire_pending_updates_only_elapsed_rows(store):
    now = datetime.datetime.now(UTC)
    await _create(
        store,
        interaction_id='expired',
        run_id='run-expired',
        expires_at=int((now + datetime.timedelta(minutes=5)).timestamp()),
    )
    await _create(
        store,
        interaction_id='future',
        run_id='run-future',
        expires_at=int((now + datetime.timedelta(minutes=20)).timestamp()),
    )
    cutoff = datetime.datetime.now(UTC) + datetime.timedelta(minutes=10)

    expired = await store.expire_pending(now=cutoff)

    assert expired == 1
    assert (await store.get_request('run-expired', 'expired'))['status'] == 'expired'
    assert (await store.get_request('run-future', 'future'))['status'] == 'pending'


@pytest.mark.asyncio
async def test_delivery_failure_is_terminal(store):
    await _create(store)

    assert await store.mark_delivery_failed('run-1', 'form-1', 'adapter rejected card')
    record = await store.get_request('run-1', 'form-1')
    assert record is not None
    assert record['status'] == 'delivery_failed'
    assert record['status_reason'] == 'adapter rejected card'
