from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import base64

import pytest
from langbot_plugin.api.entities.builtin.platform.message import File, MessageChain
from langbot_plugin.box.errors import BoxValidationError
from langbot.pkg.box.runner import RunnerBoxService, RunBoxBinding, exported_message
from tests.utils.artifact_store import seed_run, _artifact_store  # noqa: F401 -- fixture
from tests.unit_tests.box.test_box_service import _CONTEXT


def service():
    sessions = {}

    async def create(context, spec, **kwargs):
        sessions.setdefault(spec['session_id'], spec)
        return sessions[spec['session_id']]

    box = SimpleNamespace(
        ap=SimpleNamespace(),
        resolve_workspace_selection=AsyncMock(return_value={'backend': None, 'e2b': {}}),
        enabled=True,
        file_transfer_mode='legacy',
        managed_admission_required=False,
        _ATTACHMENT_MAX_TOTAL_BYTES=1000000,
        clear_selected_files=AsyncMock(return_value=None),
        _ATTACHMENT_MAX_FILES=100,
        create_session=AsyncMock(side_effect=create),
        require_workspace_sandbox=AsyncMock(side_effect=lambda context: context),
        _action_context=lambda context: context,
        client=SimpleNamespace(get_sessions=AsyncMock(side_effect=lambda **kw: list(sessions.values()))),
    )
    return RunnerBoxService(box)


@pytest.mark.asyncio
async def test_acquire_reuses_key_and_bind_is_explicit_and_run_scoped():
    api = service()
    first, second = await asyncio.gather(
        api.acquire('workspace', {'reuse_key': 'global'}),
        api.acquire('workspace', {'reuse_key': 'global'}),
    )
    assert first == second
    q1, q2 = SimpleNamespace(variables={}), SimpleNamespace(variables={})
    a = await api.bind('workspace', q1, 'run-a', first['id'])
    b = await api.bind('workspace', q2, 'run-b', first['id'])
    assert a['box_id'] == b['box_id']
    assert a['outbox'] != b['outbox']
    different = await api.acquire('workspace', {'reuse_key': 'other'})
    with pytest.raises(BoxValidationError, match='cannot change'):
        await api.bind('workspace', q1, 'run-a', different['id'])
    with pytest.raises(BoxValidationError, match='not found'):
        await api.bind('workspace', SimpleNamespace(), 'run-c', 'foreign-box')


@pytest.mark.asyncio
async def test_concurrent_binding_cannot_switch_boxes():
    api = service()
    a = await api.acquire('ws', {'reuse_key': 'a'})
    b = await api.acquire('ws', {'reuse_key': 'b'})
    q = SimpleNamespace(variables={})
    results = await asyncio.gather(
        api.bind('ws', q, 'run', a['id']), api.bind('ws', q, 'run', b['id']), return_exceptions=True
    )
    assert sum(isinstance(r, BoxValidationError) for r in results) == 1


@pytest.mark.asyncio
async def test_plugin_cannot_supply_mount_or_limit_overrides():
    api = service()
    for field in ('host_path', 'extra_mounts', 'max_sessions', 'memory_mb', 'session_id'):
        with pytest.raises(BoxValidationError):
            await api.acquire('ws', {'reuse_key': 'global', 'options': {field: '/etc'}})
    api.box.create_session.assert_not_called()
    api.box.managed_admission_required = True
    with pytest.raises(BoxValidationError, match='global'):
        await api.acquire('ws', {'reuse_key': 'other'})


@pytest.mark.asyncio
async def test_selective_import_is_idempotent_and_separates_duplicate_names():
    api = service()
    q = SimpleNamespace(
        message_chain=MessageChain(
            [
                File(name='same.txt', base64=base64.b64encode(b'a').decode()),
                File(name='same.txt', base64=base64.b64encode(b'b').decode()),
            ]
        ),
        _box_binding=RunBoxBinding('run', 'box', {}, 'run'),
    )

    async def materialize(query):
        return [
            {
                'name': 'same.txt',
                'type': 'File',
                'size': 1,
                'path': f'/workspace/inbox/{query._box_binding.io_scope}/same.txt',
            }
        ]

    api.box.materialize_inbound_attachments = AsyncMock(side_effect=materialize)
    a = await api.import_attachments(q, ['att-2'])
    b = await api.import_attachments(q, None)
    assert a['items'][0] == b['items'][1]
    assert b['items'][0]['path'] != b['items'][1]['path']
    assert api.box.materialize_inbound_attachments.await_count == 2
    with pytest.raises(BoxValidationError, match='Unknown'):
        await api.import_attachments(q, ['foreign-file'])


@pytest.mark.asyncio
async def test_export_does_not_send_and_references_cannot_cross_runs_or_repeat(artifact_store):
    api = service()
    await artifact_store(api.box.ap, _CONTEXT)
    await seed_run(api.box.ap, _CONTEXT, 'run')
    q = SimpleNamespace(_box_binding=RunBoxBinding('run', 'box', {}, 'run'), _execution_context=_CONTEXT)
    api.box.collect_selected_files = AsyncMock(
        return_value=[
            {'name': 'answer.txt', 'type': 'File', 'base64': base64.b64encode(b'answer').decode()},
        ]
    )
    result = await api.export_files(q, ['/workspace/a'])
    file = result['items'][0]
    assert 'base64' not in file and file['size'] == 6
    other = SimpleNamespace(_box_binding=RunBoxBinding('other-run', 'box', {}, 'other-run'))
    with pytest.raises(BoxValidationError):
        await exported_message(api.box.ap, other, [file['id']])
    chain = await exported_message(api.box.ap, q, [file['id']], consume=True)
    assert chain[0].name == 'answer.txt'
    with pytest.raises(BoxValidationError, match='already'):
        await exported_message(api.box.ap, q, [file['id']])


@pytest.mark.asyncio
async def test_status_preserves_unknown_capacity_and_connection_failure():
    api = service()
    api.box.get_status = AsyncMock(return_value={'available': False, 'connector_error': 'offline'})
    result = await api.status('ws')
    assert result['remaining'] is None and result['limit'] is None
    assert result['available'] is False


def test_event_attachments_preserved_without_eager_io_or_host_path_access():
    from langbot_plugin.api.entities.builtin.runner.input import AgentInput, InputAttachment
    from langbot.pkg.box.runner import prepare_input_files, input_files
    from langbot_plugin.api.entities.builtin.provider.message import ContentElement

    q = SimpleNamespace(message_chain=MessageChain([]))
    value = AgentInput(attachments=[InputAttachment(type='file', name='a.txt', content='YQ==', path='/etc/passwd')])
    prepare_input_files(q, value)
    # The envelope payload moves into the run registry; the Runner gets a ref only.
    assert value.attachments[0].content is None
    assert value.attachments[0].ref == 'att-1'
    assert value.attachments[0].path is None
    assert input_files(q)['att-1'].base64 == 'YQ=='
    assert not input_files(q)['att-1'].path
    image = AgentInput(contents=[ContentElement.from_image_url('https://example.invalid/image.png')])
    image_query = SimpleNamespace(message_chain=MessageChain([]))
    prepare_input_files(image_query, image)
    assert image.attachments[0].url is None
    assert image.contents[0].text == '[attachment att-1: image]'
    assert input_files(image_query)['att-1'].url == 'https://example.invalid/image.png'


def test_platform_media_keep_rendered_refs_and_never_carry_bytes():
    from langbot_plugin.api.entities.builtin.platform.message import Image
    from langbot_plugin.api.entities.builtin.runner.input import AgentInput
    from langbot.pkg.agent.runner.input_media import remember_media, render_input
    from langbot.pkg.box.runner import input_files, prepare_input_files

    image = Image(url='https://example.invalid/i.png', base64='data:image/png;base64,YQ==')
    report = File(name='report.pdf', base64='Yg==')
    query = SimpleNamespace(message_chain=MessageChain([image, report]))
    rendered = render_input(query.message_chain, include_quotes=True)
    remember_media(query, rendered.media)
    value = AgentInput(contents=rendered.contents, attachments=rendered.attachments(include_content=True))

    prepare_input_files(query, value)

    assert [(item.ref, item.type, item.content) for item in value.attachments] == [
        ('att-1', 'image', None),
        ('att-2', 'file', None),
    ]
    assert input_files(query) == {'att-1': image, 'att-2': report}
    assert all(item.type == 'text' for item in value.contents)
    assert all(item.url is None and item.path is None for item in value.attachments)


def test_repeated_prepare_keeps_envelope_registrations():
    from langbot_plugin.api.entities.builtin.runner.input import AgentInput, InputAttachment
    from langbot.pkg.box.runner import input_files, prepare_input_files

    images = ['data:image/png;base64,YQ==', 'data:image/png;base64,Yg==']
    query = SimpleNamespace(message_chain=MessageChain([]))
    value = AgentInput(attachments=[InputAttachment(type='image', content=image) for image in images])
    prepare_input_files(query, value)
    value = AgentInput.model_validate(value.model_dump())
    value.attachments.reverse()
    for _ in range(3):
        prepare_input_files(query, value)
        assert [input_files(query)[item.ref].base64 for item in value.attachments] == images[::-1]
        assert all(item.content is None for item in value.attachments)

    other_query = SimpleNamespace(message_chain=MessageChain([]))
    prepare_input_files(other_query, value)
    assert all(not item.base64 for item in input_files(other_query).values())


def test_contents_only_files_keep_distinct_sources_behind_markers():
    from langbot_plugin.api.entities.builtin.runner.input import AgentInput
    from langbot_plugin.api.entities.builtin.provider.message import ContentElement
    from langbot.pkg.box.runner import input_files, prepare_input_files

    query = SimpleNamespace(message_chain=MessageChain([]))
    value = AgentInput(
        contents=[
            ContentElement.from_file_url('https://files.example/one', 'report.pdf'),
            ContentElement.from_file_url('https://files.example/two', 'report.pdf'),
        ]
    )
    prepare_input_files(query, value)
    assert [item.ref for item in value.attachments] == ['att-1', 'att-2']
    assert [item.text for item in value.contents] == [
        '[attachment att-1: file report.pdf]',
        '[attachment att-2: file report.pdf]',
    ]
    assert [item.url for item in input_files(query).values()] == [
        'https://files.example/one',
        'https://files.example/two',
    ]
    assert all(item.url is None and item.content is None for item in value.attachments)


@pytest.mark.asyncio
async def test_image_export_accepts_data_url_and_enforces_total_bytes(artifact_store):
    api = service()
    await artifact_store(api.box.ap, _CONTEXT)
    await seed_run(api.box.ap, _CONTEXT, 'run')
    q = SimpleNamespace(_box_binding=RunBoxBinding('run', 'box', {}, 'run'), _execution_context=_CONTEXT)
    api.box.collect_selected_files = AsyncMock(
        return_value=[{'name': 'a.png', 'type': 'Image', 'base64': 'data:image/png;base64,YQ=='}]
    )
    result = await api.export_files(q, ['/workspace/a'])
    assert result['items'][0]['size'] == 1
    # Retrying unchanged content reuses the accepted ID; new content consumes budget.
    assert await api.export_files(q, ['/workspace/a']) == result
    api.box.collect_selected_files.return_value[0]['base64'] = 'data:image/png;base64,Yg=='
    api.box._ATTACHMENT_MAX_TOTAL_BYTES = 1
    with pytest.raises(BoxValidationError, match='byte limit'):
        await api.export_files(q, ['/workspace/a'])


@pytest.mark.asyncio
async def test_cleanup_retry_preserves_ids_and_never_redelivers_consumed_files(artifact_store):
    api = service()
    await artifact_store(api.box.ap, _CONTEXT)
    await seed_run(api.box.ap, _CONTEXT, 'run')
    q = SimpleNamespace(_box_binding=RunBoxBinding('run', 'box', {}, 'run'), _execution_context=_CONTEXT)
    # A best-effort cleanup can leave the same files in the outbox.
    api.box.collect_selected_files = AsyncMock(
        return_value=[
            {'name': 'same.txt', '_outbox_path': 'a/same.txt', 'type': 'File', 'base64': 'YQ=='},
            {'name': 'same.txt', '_outbox_path': 'b/same.txt', 'type': 'File', 'base64': 'YQ=='},
            {'name': 'empty.txt', '_outbox_path': 'empty.txt', 'type': 'File', 'base64': ''},
        ]
    )
    first = await api.export_files(q, ['/workspace/a'])
    assert len(first['items']) == 3
    assert all('_outbox_path' not in item for item in first['items'])
    assert await api.export_files(q, ['/workspace/a']) == first
    await exported_message(api.box.ap, q, [item['id'] for item in first['items']], consume=True)
    assert await api.export_files(q, ['/workspace/a']) == {'items': [], 'warning': None}
    assert len(q._box_binding.exported) == 3
    api.box.collect_selected_files.return_value[0]['base64'] = 'Yg=='
    changed = await api.export_files(q, ['/workspace/a'])
    assert len(changed['items']) == 1
    assert changed['items'][0]['id'] not in {item['id'] for item in first['items']}


@pytest.mark.asyncio
async def test_run_quota_failure_is_atomic_and_reports_remaining_budget(artifact_store):
    from langbot.pkg.box.export_errors import BoxExportError

    api = service()
    await artifact_store(api.box.ap, _CONTEXT)
    await seed_run(api.box.ap, _CONTEXT, 'run')
    api.box._ATTACHMENT_MAX_TOTAL_BYTES = 2
    q = SimpleNamespace(_box_binding=RunBoxBinding('run', 'box', {}, 'run'), _execution_context=_CONTEXT)
    api.box.collect_selected_files = AsyncMock(
        return_value=[
            {'name': 'a.txt', 'type': 'File', 'base64': 'YQ=='},
        ]
    )
    await api.export_files(q, ['/workspace/a'])
    api.box.collect_selected_files.return_value = [
        {'name': 'b.txt', 'type': 'File', 'base64': 'Yg=='},
        {'name': 'c.txt', 'type': 'File', 'base64': 'Yw=='},
    ]
    with pytest.raises(BoxExportError) as caught:
        await api.export_files(q, ['/workspace/a'])
    assert caught.value.error.details['limit'] == 2
    assert caught.value.error.details['actual'] == 3
    assert caught.value.error.details['remaining'] == 1
    assert len(q._box_binding.exported) == len(q._box_binding.exported_fingerprints) == 1
    api.box.clear_selected_files.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_task_cannot_bind_a_box_from_an_old_e2b_configuration():
    api = service()
    old_config = {
        'config': {
            'api_url': 'http://old.test',
            'sandbox_url': 'http://old-sandbox.test',
            'api_key': 'old-private',
            'template': 'base',
        },
        'revision': 'old',
    }
    new_config = {'config': {**old_config['config'], 'api_key': 'new-private'}, 'revision': 'new'}
    api.box.client.get_sessions = AsyncMock(
        return_value=[{'session_id': 'runner-backend-e2b-old', 'backend_name': 'e2b'}]
    )
    previous = SimpleNamespace(variables={}, _sandbox_backend='e2b', _sandbox_e2b_config=old_config)
    current = SimpleNamespace(variables={}, _sandbox_backend='e2b', _sandbox_e2b_config=new_config)
    await api.bind('workspace', previous, 'old-run', 'runner-backend-e2b-old')
    assert previous._box_binding.spec['e2b_config']['api_key'] == 'old-private'
    with pytest.raises(BoxValidationError, match='task E2B configuration'):
        await api.bind('workspace', current, 'new-run', 'runner-backend-e2b-old')


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['error', 'cancel'])
async def test_output_asset_batch_failure_preserves_all_sources_and_registry(artifact_store, monkeypatch, failure):
    import sqlalchemy as sa
    from langbot.pkg.entity.persistence.artifact import Artifact
    from langbot.pkg.entity.persistence.content import ContentObject

    api = service()
    await artifact_store(api.box.ap, _CONTEXT)
    await seed_run(api.box.ap, _CONTEXT, 'run')
    q = SimpleNamespace(_box_binding=RunBoxBinding('run', 'box', {}, 'run'), _execution_context=_CONTEXT)
    api.box.collect_selected_files = AsyncMock(
        return_value=[
            {'name': 'one.txt', 'type': 'File', 'base64': 'YQ=='},
            {'name': 'two.txt', 'type': 'File', 'base64': 'Yg=='},
        ]
    )
    create = api.box.ap.artifact_service.create_run_output
    second_started = asyncio.Event()
    calls = 0

    async def fail_second(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            second_started.set()
            if failure == 'cancel':
                await asyncio.Event().wait()
            raise RuntimeError('second asset unavailable')
        return await create(*args)

    monkeypatch.setattr(api.box.ap.artifact_service, 'create_run_output', fail_second)
    operation = asyncio.create_task(api.export_files(q, ['/workspace/one.txt', '/workspace/two.txt']))
    if failure == 'cancel':
        await second_started.wait()
        operation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await operation
    else:
        with pytest.raises(RuntimeError, match='second asset unavailable'):
            await operation
    assert not q._box_binding.exported and not q._box_binding.exported_fingerprints
    api.box.clear_selected_files.assert_not_awaited()
    async with api.box.ap.persistence_mgr.tenant_uow(_CONTEXT.workspace_uuid) as uow:
        assert (await uow.execute(sa.select(sa.func.count()).select_from(Artifact))).scalar_one() == 0
        assert (await uow.execute(sa.select(sa.func.count()).select_from(ContentObject))).scalar_one() == 0


@pytest.mark.asyncio
async def test_submitted_file_can_be_read_and_committed_without_redelivery(artifact_store):
    from langbot.pkg.box.runner import run_artifact_context

    api = service()
    await artifact_store(api.box.ap, _CONTEXT)
    await seed_run(api.box.ap, _CONTEXT, 'run')
    q = SimpleNamespace(_box_binding=RunBoxBinding('run', 'box', {}, 'run'), _execution_context=_CONTEXT)
    import uuid
    import sqlalchemy as sa
    from langbot.pkg.api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
    from langbot.pkg.entity.persistence.agent import Agent
    from langbot.pkg.entity.persistence.apikey import ApiKey

    manager_id, producer_id = str(uuid.uuid4()), str(uuid.uuid4())
    async with api.box.ap.persistence_mgr.tenant_uow(_CONTEXT.workspace_uuid) as uow:
        await uow.execute(
            sa.insert(ApiKey).values(
                uuid=manager_id,
                workspace_uuid=_CONTEXT.workspace_uuid,
                name='test-manager',
                key_hash=uuid.uuid4().hex,
                scopes=['resource.view', 'resource.manage'],
            )
        )
        await uow.execute(
            sa.insert(Agent).values(
                uuid=producer_id,
                workspace_uuid=_CONTEXT.workspace_uuid,
                name='published-producer',
                kind='agent',
            )
        )
    manager = RequestContext(
        instance_uuid=_CONTEXT.instance_uuid,
        placement_generation=1,
        request_id='publish-test',
        auth_type='api-key',
        principal=PrincipalContext(PrincipalType.API_KEY, api_key_uuid=manager_id),
        workspace=WorkspaceContext(
            _CONTEXT.workspace_uuid, None, None, frozenset({'resource.view', 'resource.manage'})
        ),
    )
    q._output_publication = await api.box.ap.artifact_publication_service.set(manager, 'agent', producer_id, True)

    api.box.collect_selected_files = AsyncMock(
        return_value=[
            {'name': 'answer.txt', 'type': 'File', 'base64': base64.b64encode(b'answer').decode()},
        ]
    )
    item = (await api.export_files(q, ['/workspace/answer.txt']))['items'][0]
    assert item['artifact_id'].startswith('art_') and item['id'] != item['artifact_id']
    assert 'base64' not in q._box_binding.exported[item['id']]
    message = await exported_message(api.box.ap, q, [item['id']], consume=True)
    assert base64.b64decode(message[0].base64) == b'answer'
    content = await api.read_file(q, item['id'])
    import json

    assert json.loads(content['contents'][0]['text'])['text'] == 'answer'
    committed = (await api.commit_files(q, [item['id']]))['items'][0]
    assert committed['id'] == item['id'] and committed['artifact_id'] == item['artifact_id']
    assert committed['lifecycle'] == 'persistent' and committed['expires_at'] is None
    assert await api.box.ap.artifact_service.expire_run_outputs(run_artifact_context(q)) == 0
    assert (await api.read_file(q, item['id'])) == content
    with pytest.raises(BoxValidationError, match='already been submitted'):
        await exported_message(api.box.ap, q, [item['id']])


@pytest.mark.asyncio
async def test_repeated_run_file_reads_share_a_cumulative_content_budget(artifact_store):
    api = service()
    await artifact_store(api.box.ap, _CONTEXT)
    await seed_run(api.box.ap, _CONTEXT, 'run')
    api.box._ATTACHMENT_MAX_TOTAL_BYTES = 1024
    q = SimpleNamespace(_box_binding=RunBoxBinding('run', 'box', {}, 'run'), _execution_context=_CONTEXT)
    api.box.collect_selected_files = AsyncMock(
        return_value=[
            {'name': 'answer.txt', 'type': 'File', 'base64': base64.b64encode(b'answer').decode()},
        ]
    )
    item = (await api.export_files(q, ['/workspace/answer.txt']))['items'][0]
    first = await api.read_file(q, item['id'])
    assert first['contents']
    for _ in range(8):
        try:
            await api.read_file(q, item['id'])
        except BoxValidationError as exc:
            assert 'budget is exhausted' in str(exc)
            break
    else:
        pytest.fail('Repeated successful reads exceeded the configured per-run return budget')


@pytest.mark.asyncio
async def test_export_commit_return_after_finalization_expires_without_accepting_handles(artifact_store, monkeypatch):
    from contextlib import asynccontextmanager
    import sqlalchemy as sa
    from langbot.pkg.box.runner import run_artifact_context
    from langbot.pkg.entity.persistence.artifact import Artifact
    import datetime as dt

    api = service()
    await artifact_store(api.box.ap, _CONTEXT)
    await seed_run(api.box.ap, _CONTEXT, 'run')
    binding = RunBoxBinding('run', 'box', {}, 'run')
    query = SimpleNamespace(_box_binding=binding, _execution_context=_CONTEXT)
    context = run_artifact_context(query)
    api.box.collect_selected_files = AsyncMock(return_value=[{'name': 'late.txt', 'type': 'File', 'base64': 'YQ=='}])
    manager = api.box.ap.persistence_mgr
    actual_uow = manager.tenant_uow
    closed = False

    @asynccontextmanager
    async def close_after_commit(workspace_uuid):
        nonlocal closed
        outer = manager.current_session() is None
        async with actual_uow(workspace_uuid) as uow:
            yield uow
        if outer and not closed:
            async with actual_uow(workspace_uuid) as probe:
                has_output = (await probe.execute(sa.select(Artifact.id))).first() is not None
            if has_output:
                closed = binding.closing = True
                object.__setattr__(query, '_run_files_closing', True)
                object.__delattr__(query, '_box_binding')

    monkeypatch.setattr(manager, 'tenant_uow', close_after_commit)
    with pytest.raises(BoxValidationError, match='access has ended'):
        await api.export_files(query, ['/workspace/late.txt'])
    assert not binding.exported and not binding.exported_fingerprints
    api.box.clear_selected_files.assert_not_awaited()
    async with actual_uow(context.workspace_uuid) as uow:
        expires_at = (await uow.execute(sa.select(Artifact.expires_at))).scalar_one()
    assert expires_at <= dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_export_finishing_source_cleanup_after_run_close_expires_accepted_files(artifact_store):
    from langbot.pkg.box.runner import run_artifact_context
    import datetime as dt
    import sqlalchemy as sa
    from langbot.pkg.entity.persistence.artifact import Artifact

    api = service()
    await artifact_store(api.box.ap, _CONTEXT)
    await seed_run(api.box.ap, _CONTEXT, 'run')
    binding = RunBoxBinding('run', 'box', {}, 'run')
    query = SimpleNamespace(_box_binding=binding, _execution_context=_CONTEXT)
    context = run_artifact_context(query)
    api.box.collect_selected_files = AsyncMock(
        return_value=[{'name': 'accepted.txt', 'type': 'File', 'base64': 'YQ=='}]
    )

    async def close_during_cleanup(*args):
        binding.closing = True
        object.__setattr__(query, '_run_files_closing', True)
        object.__delattr__(query, '_box_binding')

    api.box.clear_selected_files = AsyncMock(side_effect=close_during_cleanup)
    with pytest.raises(BoxValidationError, match='access has ended'):
        await api.export_files(query, ['/workspace/accepted.txt'])
    api.box.clear_selected_files.assert_awaited_once()
    assert len(binding.exported) == 1
    artifact_id = next(iter(binding.exported.values()))['artifact_id']
    async with api.box.ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        expires_at = (await uow.execute(sa.select(Artifact.expires_at).where(Artifact.id == artifact_id))).scalar_one()
    assert expires_at <= dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['legacy', 'network'])
async def test_bound_upload_import_uses_authorized_bytes_and_preserves_initial_descriptor(artifact_store, mode):
    from langbot.pkg.box.runner import run_artifact_context
    from tests.utils.artifact_store import named_key_context

    api = service()
    api.box.file_transfer_mode = mode
    await artifact_store(api.box.ap, _CONTEXT)
    await seed_run(api.box.ap, _CONTEXT, 'run')
    manager = await named_key_context(api.box.ap, _CONTEXT)
    asset = await api.box.ap.artifact_service.create(manager, 'uploaded.txt', b'bound upload', 'text/plain')
    original = File(name='uploaded.txt')
    query = SimpleNamespace(
        _box_binding=RunBoxBinding('run', 'box', {}, 'run'),
        _execution_context=_CONTEXT,
        _input_artifact_ids=frozenset({asset['id']}),
        _input_components={asset['id']: original},
    )
    api.box._ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024
    await api.box.ap.artifact_service.bind_run_inputs(manager, run_artifact_context(query), [asset['id']])

    async def materialize(transfer, *, resolved=None):
        if mode == 'network':
            component, content = resolved
            assert component is original and content == b'bound upload'
            assert not hasattr(transfer, 'message_chain')
        else:
            component = transfer.message_chain[0]
            assert component is not original and base64.b64decode(component.base64) == b'bound upload'
            assert not component.url and not component.path
        return [{'name': component.name, 'type': 'File', 'size': 12, 'path': '/workspace/inbox/bound/uploaded.txt'}]

    api.box.materialize_inbound_attachments = AsyncMock(side_effect=materialize)
    first = await api.import_attachments(query, [asset['id']])
    assert await api.import_attachments(query, [asset['id']]) == first
    api.box.materialize_inbound_attachments.assert_awaited_once()
    assert not original.base64 and not original.url and not original.path
    await seed_run(api.box.ap, _CONTEXT, 'foreign-run')
    foreign = SimpleNamespace(
        _box_binding=RunBoxBinding('foreign-run', 'box', {}, 'foreign-run'),
        _execution_context=_CONTEXT,
        _input_artifact_ids=query._input_artifact_ids,
        _input_components=query._input_components,
    )
    with pytest.raises(FileNotFoundError):
        await api.import_attachments(foreign, [asset['id']])
    other_asset = await api.box.ap.artifact_service.create(manager, 'unbound.txt', b'unbound', 'text/plain')
    query._input_artifact_ids = frozenset({asset['id'], other_asset['id']})
    query._input_components[other_asset['id']] = File(name='unbound.txt')
    with pytest.raises(FileNotFoundError):
        await api.import_attachments(query, [other_asset['id']])
    api.box.materialize_inbound_attachments.assert_awaited_once()
