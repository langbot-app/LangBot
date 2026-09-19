from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import base64

import pytest
from langbot_plugin.api.entities.builtin.platform.message import File, MessageChain
from langbot_plugin.box.errors import BoxValidationError
from langbot.pkg.box.runner import RunnerBoxService, RunBoxBinding, exported_message


def service():
    sessions = {}

    async def create(context, spec):
        sessions.setdefault(spec['session_id'], spec)
        return sessions[spec['session_id']]

    box = SimpleNamespace(
        enabled=True,
        managed_admission_required=False,
        _ATTACHMENT_MAX_TOTAL_BYTES=1000000,
        create_session=AsyncMock(side_effect=create),
        require_workspace_sandbox=AsyncMock(side_effect=lambda context: context),
        _action_context=lambda context: context,
        client=SimpleNamespace(get_sessions=AsyncMock(side_effect=lambda **kw: list(sessions.values()))),
        build_skill_extra_mounts=lambda query: [],
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
    q1, q2 = SimpleNamespace(), SimpleNamespace()
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
    q = SimpleNamespace()
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
    a = await api.import_attachments(q, ['attachment-1'])
    b = await api.import_attachments(q, None)
    assert a['items'][0] == b['items'][1]
    assert b['items'][0]['path'] != b['items'][1]['path']
    assert api.box.materialize_inbound_attachments.await_count == 2
    with pytest.raises(BoxValidationError, match='Unknown'):
        await api.import_attachments(q, ['foreign-file'])


@pytest.mark.asyncio
async def test_export_does_not_send_and_references_cannot_cross_runs_or_repeat():
    api = service()
    q = SimpleNamespace(_box_binding=RunBoxBinding('run', 'box', {}, 'run'))
    api.box.collect_outbound_attachments = AsyncMock(
        return_value=[
            {'name': 'answer.txt', 'type': 'File', 'base64': base64.b64encode(b'answer').decode()},
        ]
    )
    result = await api.export_files(q)
    file = result['items'][0]
    assert 'base64' not in file and file['size'] == 6
    other = SimpleNamespace(_box_binding=RunBoxBinding('other-run', 'box', {}, 'other-run'))
    with pytest.raises(BoxValidationError):
        exported_message(other, [file['id']])
    chain = exported_message(q, [file['id']], consume=True)
    assert chain[0].name == 'answer.txt'
    with pytest.raises(BoxValidationError, match='already'):
        exported_message(q, [file['id']])


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
    assert value.attachments[0].content == 'YQ=='
    assert value.attachments[0].ref == 'attachment-0'
    assert value.attachments[0].path is None
    assert input_files(q)[0].base64 == 'YQ=='
    assert not input_files(q)[0].path
    image = AgentInput(contents=[ContentElement.from_image_url('https://example.invalid/image.png')])
    prepare_input_files(SimpleNamespace(message_chain=MessageChain([])), image)
    assert image.attachments[0].url == 'https://example.invalid/image.png'


def test_attachment_references_follow_metadata_not_platform_list_order():
    from langbot_plugin.api.entities.builtin.runner.input import AgentInput, InputAttachment
    from langbot.pkg.box.runner import prepare_input_files, input_files
    from langbot_plugin.api.entities.builtin.platform.message import Image

    a, b = File(name='a', base64='YQ=='), Image(url='https://example.invalid/b')
    q = SimpleNamespace(message_chain=MessageChain([a, b]))
    value = AgentInput(
        attachments=[InputAttachment(type='image', url=b.url), InputAttachment(type='file', name='a', content='YQ==')]
    )
    prepare_input_files(q, value)
    assert input_files(q) == [b, a]


@pytest.mark.asyncio
async def test_image_export_accepts_data_url_and_enforces_total_bytes():
    api = service()
    q = SimpleNamespace(_box_binding=RunBoxBinding('run', 'box', {}, 'run'))
    api.box.collect_outbound_attachments = AsyncMock(
        return_value=[{'name': 'a.png', 'type': 'Image', 'base64': 'data:image/png;base64,YQ=='}]
    )
    result = await api.export_files(q)
    assert result['items'][0]['size'] == 1
    api.box._ATTACHMENT_MAX_TOTAL_BYTES = 1
    with pytest.raises(BoxValidationError, match='byte limit'):
        await api.export_files(q)
