"""The installed input action uses active sessions and real Artifact persistence."""
# ruff: noqa: F811

import asyncio
import base64
from dataclasses import replace
import datetime as dt
import json
from types import SimpleNamespace
import uuid

import pytest
import sqlalchemy as sa
from langbot_plugin.api.entities.builtin.platform.message import File, MessageChain
from langbot_plugin.api.entities.builtin.runner.resources import AgentResources
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action

from langbot.pkg.agent.runner import input_media
from langbot.pkg.agent.runner.session_registry import AgentRunSessionRegistry
from langbot.pkg.api.context import PrincipalContext, PrincipalType
from langbot.pkg.entity.persistence.artifact import Artifact
from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.plugin import agent_run_support, input_attachment_actions
from tests.integration.storage.test_artifacts import (
    artifact_replicas,  # noqa: F401
    persistence_case,  # noqa: F401
    replicas,  # noqa: F401
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_BODY = 'A猫🙂Z'.encode()


@pytest.fixture
async def input_actions(artifact_replicas, monkeypatch):
    case = artifact_replicas
    registry = AgentRunSessionRegistry()
    monkeypatch.setattr(agent_run_support, 'get_session_registry', lambda: registry)
    run_id = str(uuid.uuid4())
    query = SimpleNamespace(
        message_chain=MessageChain([File(name='sample.txt', base64=base64.b64encode(_BODY).decode())]),
        _execution_context=case.a.context,
    )

    async def register(run):
        await registry.register(
            run_id=run,
            runner_id='plugin:test/runner/default',
            query_id=None,
            plugin_identity='test/runner',
            resources=AgentResources().model_dump(mode='json'),
            available_apis={'input_attachments': True},
            execution_query=query,
            workspace_id=case.context.workspace_uuid,
        )

    await register(run_id)

    class Handler:
        ap = case.a.app

        def __init__(self):
            self.actions = {}

        def action(self, name):
            def attach(function):
                self.actions[name] = function
                return function

            return attach

        async def _require_plugin_action_context(self):
            return case.a.context, None

    handler = Handler()
    input_attachment_actions.register(handler)
    return SimpleNamespace(
        case=case,
        query=query,
        run_id=run_id,
        registry=registry,
        register=register,
        render=handler.actions[Action.READ_INPUT_ATTACHMENT_CONTENT],
        raw=handler.actions[Action.READ_INPUT_ATTACHMENT],
        arguments={'run_id': run_id, 'ref': 'att-1', 'caller_plugin_identity': 'test/runner'},
    )


async def _count(case):
    async with case.a.app.persistence_mgr.tenant_uow(case.context.workspace_uuid) as uow:
        return (await uow.execute(sa.select(sa.func.count()).select_from(Artifact))).scalar_one()


async def test_first_content_read_creates_one_run_asset_and_reuses_it(input_actions):
    x = input_actions
    response = await x.render({**x.arguments, 'offset': 1, 'max_chars': 2})
    assert response.code == 0
    result = json.loads(response.data['contents'][0]['text'])
    assert result['text'] == '猫🙂' and result['next_offset'] == 3
    assert result['artifact']['source'] == 'input_attachment'
    asset_id = x.query._input_artifact_refs['att-1']
    assert await _count(x.case) == 1
    raw = await x.raw(x.arguments)
    assert raw.code == 0 and base64.b64decode(raw.data['content']) == _BODY
    assert await _count(x.case) == 1
    assert x.query._input_attachment_read_bytes == 2 * len(_BODY)
    other_run = str(uuid.uuid4())
    await x.register(other_run)
    with pytest.raises(FileNotFoundError):
        await x.render({**x.arguments, 'run_id': other_run})
    assert x.query._input_artifact_refs['att-1'] == asset_id
    assert (await x.case.a.client.get('/api/v1/artifacts/' + asset_id, headers=x.case.headers)).status_code == 404


async def test_uploaded_debug_ids_require_an_authorized_live_run_binding(input_actions):
    x = input_actions
    metadata = await x.case.a.app.artifact_service.create(x.case.context, 'uploaded.txt', _BODY, 'text/plain')
    service = x.case.a.app.artifact_service
    run_context = replace(
        x.query._execution_context,
        trigger_principal=PrincipalContext(PrincipalType.PROCESSOR, run_id=x.run_id),
    )
    async with x.case.a.app.persistence_mgr.tenant_uow(x.case.context.workspace_uuid) as uow:
        await uow.execute(
            sa.insert(AgentRun).values(
                run_id=x.run_id,
                workspace_id=x.case.context.workspace_uuid,
                runner_id='plugin:test/runner/default',
                status='running',
                execution_owner_id=str(uuid.uuid4()),
                execution_lease_expires_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
                + dt.timedelta(minutes=5),
            )
        )
    x.query._input_artifact_ids = frozenset({metadata['id']})
    x.query._input_artifact_context = x.case.context
    request = {**x.arguments, 'ref': metadata['id']}
    with pytest.raises(FileNotFoundError):
        await x.render(request)
    foreign_owner = replace(
        x.case.context,
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid=str(uuid.uuid4())),
    )
    with pytest.raises(FileNotFoundError):
        await service.bind_run_inputs(foreign_owner, run_context, [metadata['id']])
    await service.bind_run_inputs(x.case.context, run_context, [metadata['id']])
    response = await x.render(request)
    result = json.loads(response.data['contents'][0]['text'])
    assert result['text'] == _BODY.decode() and result['artifact']['id'] == metadata['id']
    assert await _count(x.case) == 1
    # Frozen Host authorization is carried by the exact run reference, not a later actor value.
    x.query._input_artifact_context = foreign_owner
    response = await x.render(request)
    assert response.code == 0
    await service.release_run_inputs(run_context)
    with pytest.raises(FileNotFoundError):
        await x.render(request)
    assert await _count(x.case) == 1


async def test_session_identity_expiry_and_budget_precede_content_access(input_actions):
    x = input_actions
    refused = await x.render({**x.arguments, 'caller_plugin_identity': 'other/plugin'})
    assert refused.code != 0 and await _count(x.case) == 0
    x.query._input_attachment_read_bytes = input_media.MAX_RUN_READ_BYTES - len(_BODY)
    first, second = await asyncio.gather(x.raw(x.arguments), x.raw(x.arguments))
    assert sorted([first.code == 0, second.code == 0]) == [False, True]
    assert x.query._input_attachment_read_bytes == input_media.MAX_RUN_READ_BYTES
    assert await _count(x.case) == 0
    await x.registry.unregister(x.run_id)
    expired = await x.render(x.arguments)
    assert expired.code != 0 and 'expired' in expired.message


async def test_cancellation_before_payload_resolution_leaves_no_asset_and_releases_lock(input_actions, monkeypatch):
    x = input_actions
    started = asyncio.Event()
    original = input_media.read_component_bytes

    async def stalled(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(input_media, 'read_component_bytes', stalled)
    task = asyncio.create_task(x.render(x.arguments))
    await asyncio.wait_for(started.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await _count(x.case) == 0
    assert getattr(x.query, '_input_attachment_read_bytes', 0) == 0
    monkeypatch.setattr(input_media, 'read_component_bytes', original)
    response = await asyncio.wait_for(x.render(x.arguments), 5)
    assert response.code == 0 and await _count(x.case) == 1


async def test_text_continuation_charges_materialization_once_and_bounds_repeated_output(input_actions, monkeypatch):
    x = input_actions
    text = 'BEGIN:' + '0123456789' * 818 + ':END!!'
    assert len(text.encode()) == 8192
    monkeypatch.setattr(input_media, 'MAX_RUN_READ_BYTES', 16 * 1024)
    x.query.message_chain = MessageChain(
        [
            File(name='continued.txt', base64=base64.b64encode(text.encode()).decode()),
        ]
    )

    offset = 0
    chunks = []
    for _ in range(10):
        response = await x.render({**x.arguments, 'offset': offset, 'max_chars': 900})
        assert response.code == 0, response.message
        result = json.loads(response.data['contents'][0]['text'])
        assert result['offset'] == offset
        chunks.append(result['text'])
        if result['next_offset'] is None:
            assert result['truncated'] is False
            break
        assert result['truncated'] is True
        assert result['next_offset'] == offset + len(result['text'])
        offset = result['next_offset']
    assert len(chunks) == 10
    assert ''.join(chunks) == text
    assert await _count(x.case) == 1

    # Cached source bytes may be reused, but repeated model output remains bounded.
    for _ in range(32):
        response = await x.render({**x.arguments, 'offset': 0, 'max_chars': 900})
        if response.code != 0:
            assert 'budget' in response.message.lower()
            break
    else:
        pytest.fail('Repeated content output bypassed the run budget')
