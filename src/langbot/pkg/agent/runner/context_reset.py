"""Scoped context reset markers, independent of retained monitoring history."""

import hashlib
import json

import sqlalchemy as sa

from ...entity.persistence.runner_state import RunnerState

HOST_RESET_RUNNER = '__langbot_context_reset__'


def reset_scope(workspace, bot, conversation):
    return 'host-reset:' + hashlib.sha256(json.dumps([workspace, bot, conversation]).encode()).hexdigest()


async def get_reset_generation(engine, workspace, bot, conversation):
    if not all((workspace, bot, conversation)):
        return None
    async with engine.connect() as connection:
        value = (
            await connection.execute(
                sa.select(RunnerState.value_json).where(
                    RunnerState.scope_key == reset_scope(workspace, bot, conversation),
                    RunnerState.state_key == 'generation',
                    RunnerState.runner_id == HOST_RESET_RUNNER,
                )
            )
        ).scalar_one_or_none()
    return json.loads(value) if value else None


def active_history_condition(transcript):
    cutoff = (
        sa.select(sa.func.max(RunnerState.created_at))
        .where(
            RunnerState.runner_id == HOST_RESET_RUNNER,
            RunnerState.state_key == 'generation',
            RunnerState.workspace_id == transcript.workspace_id,
            RunnerState.bot_id == transcript.bot_id,
            RunnerState.conversation_id == transcript.conversation_id,
        )
        .correlate(transcript)
        .scalar_subquery()
    )
    return sa.or_(cutoff.is_(None), transcript.created_at > cutoff)
