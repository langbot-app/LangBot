"""Real memory plugin/Host/storage with scripted LocalAgent model responses."""

from __future__ import annotations

import asyncio
import json
import shutil
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from tests.e2e import test_local_runner_fake_provider as local

pytest_plugins = ['tests.e2e.test_local_runner_fake_provider']
pytestmark = [pytest.mark.e2e, pytest.mark.local_agent]

MEMORY_TOOLS = ['remember', 'recall_memory', 'update_profile', 'forget']


@pytest.fixture
def memory_embedding_url():
    """Serve deterministic embeddings over the actual provider HTTP protocol."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            payload = json.dumps(
                {
                    'object': 'list',
                    'model': request['model'],
                    'data': [
                        {'object': 'embedding', 'index': index, 'embedding': [0.1, 0.2, 0.3]}
                        for index, _ in enumerate(request['input'])
                    ],
                    'usage': {'prompt_tokens': 1, 'total_tokens': 1},
                }
            ).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_local_agent_memory_tools_without_pipeline(
    local_agent_e2e_tmpdir,
    local_agent_e2e_config_path,
    local_agent_runtime_process,
    memory_embedding_url,
):
    """Read/write across runs and Host restart without Pipeline or KB grants."""
    from langbot_plugin.api.entities.builtin.provider import message as provider_message
    from langbot_plugin.runtime.plugin.mgr import PluginInstallSource
    import yaml

    config = yaml.safe_load(local_agent_e2e_config_path.read_text())
    config['api']['host'] = '127.0.0.1'
    local_agent_e2e_config_path.write_text(yaml.safe_dump(config))

    plugin_root = Path(__file__).parents[2] / 'plugins' / 'KnowledgeEngine' / 'LongTermMemory'
    archive = Path(shutil.make_archive(str(local_agent_e2e_tmpdir / 'long-term-memory'), 'zip', plugin_root))
    counter = 0

    async def call(ap, model, name, params, *, group='group-a', speaker='alice', bot='bot-a', tools=None):
        nonlocal counter
        counter += 1
        model.queue_llm_responses(
            provider_message.Message(
                role='assistant',
                content='',
                tool_calls=[
                    provider_message.ToolCall(
                        id=f'memory-call-{counter}',
                        type='function',
                        function=provider_message.FunctionCall(name=name, arguments=json.dumps(params)),
                    )
                ],
            ),
            'Memory tool turn complete.',
        )
        event = local._event(
            event_id=f'memory-event-{uuid.uuid4()}',
            conversation_id=f'memory-turn-{uuid.uuid4()}',
            text=f'Call {name} for this memory test.',
        )
        event.bot_id = bot
        event.actor.actor_id = speaker
        event.delivery.reply_target = {'target_type': 'group', 'target_id': group}
        binding = local._binding(
            binding_id='memory-processor',
            allowed_tool_names=MEMORY_TOOLS if tools is None else tools,
            allowed_kb_uuids=[],
            runner_config={'knowledge-bases': [], 'box-enabled': False, 'tool-execution-mode': 'serial'},
        )
        outputs = await local._run_runner(ap, event, binding)
        assert local._content_text(outputs[-1].content) == 'Memory tool turn complete.'
        assert not ap.query_pool.cached_queries
        results = [m for m in model._invoke_payloads[-1]['messages'] if m.role == 'tool']
        assert results, 'LocalAgent must receive an actual tool result before its final model call'
        return local._message_text(results[-1])

    async def write_and_read(ap):
        model = await local._inject_fake_llm_model(ap)
        await ap.plugin_connector.install_plugin(PluginInstallSource.LOCAL, {'plugin_file': archive.read_bytes()})
        for _ in range(60):
            if 'remember' in {tool.metadata.name for tool in await ap.plugin_connector.list_tools()}:
                break
            await asyncio.sleep(1)
        else:
            pytest.fail('LongTermMemory tools were not discovered')

        context = await ap.plugin_connector._current_execution_context()
        provider = await ap.provider_service.create_provider(
            context,
            {
                'name': 'Memory test local embedding',
                'requester': 'openai-chat-completions',
                'base_url': memory_embedding_url,
                'api_keys': ['local-test-key'],
            },
        )
        embedding = await ap.embedding_models_service.create_embedding_model(
            context,
            {
                'name': 'memory-test-embedding',
                'provider_uuid': provider,
                'extra_args': {},
            },
        )
        engines = await ap.plugin_connector.list_knowledge_engines()
        engine = next(item['plugin_id'] for item in engines if 'LongTermMemory' in item['plugin_id'])
        kb = await ap.rag_mgr.create_knowledge_base(
            context,
            name='Processor memory',
            knowledge_engine_plugin_id=engine,
            creation_settings={'embedding_model_uuid': embedding, 'isolation': 'session'},
        )

        stored = await call(ap, model, 'remember', {'content': 'The release rendezvous is at Cedar Pier on Friday.'})
        assert stored.startswith('Remembered:'), stored
        updated = await call(
            ap,
            model,
            'update_profile',
            {
                'field': 'preferences',
                'action': 'add',
                'value': 'brief technical answers',
            },
        )
        assert updated.startswith('Speaker profile updated.'), updated
        updated = await call(
            ap,
            model,
            'update_profile',
            {
                'scope': 'session',
                'field': 'notes',
                'action': 'set',
                'value': 'Release coordination group',
            },
        )
        assert updated.startswith('Session profile updated.'), updated
        result = json.loads(await call(ap, model, 'recall_memory', {'query': 'release rendezvous'}))
        assert result['episodes'][0]['content'] == 'The release rendezvous is at Cedar Pier on Friday.'
        assert result['episodes'][0]['sender_id'] == 'alice'
        assert 'brief technical answers' in result['speaker_profile']
        assert 'Release coordination group' in result['session_profile']
        # Retain an old-format record to exercise deletion after an upgrade.
        items, _ = await ap.rag_runtime_service.vector_list(context, kb.uuid, limit=1)
        metadata = dict(items[0]['metadata'])
        metadata.pop('episode_id')
        await ap.rag_runtime_service.vector_upsert(
            context,
            kb.uuid,
            [[0.1, 0.2, 0.3]],
            [items[0]['id']],
            metadata=[metadata],
            documents=[result['episodes'][0]['content']],
        )
        return result['episodes'][0]['id']

    episode_id = local._run_local_agent_probe(local_agent_e2e_tmpdir, write_and_read)

    async def read_after_restart(ap):
        model = await local._inject_fake_llm_model(ap)
        result = json.loads(await call(ap, model, 'recall_memory', {'query': 'release rendezvous'}))
        assert result['episodes'][0]['id'] == episode_id
        assert 'brief technical answers' in result['speaker_profile']

        bob = json.loads(await call(ap, model, 'recall_memory', {'query': 'release rendezvous'}, speaker='bob'))
        assert bob['speaker_profile'] == ''
        assert bob['episodes'][0]['id'] == episode_id
        assert 'Release coordination group' in bob['session_profile']
        for kwargs in ({'group': 'group-b'}, {'bot': 'bot-b'}):
            assert (
                await call(ap, model, 'recall_memory', {'query': 'release rendezvous'}, **kwargs)
                == 'No relevant memories found.'
            )

        denied = await call(ap, model, 'remember', {'content': 'Unauthorized memory'}, tools=['recall_memory'])
        assert 'not authorized' in denied
        unchanged = json.loads(await call(ap, model, 'recall_memory', {'query': 'release rendezvous'}))
        assert len(unchanged['episodes']) == 1

        await call(ap, model, 'forget', {'episode_id': episode_id}, group='group-b')
        still_present = json.loads(await call(ap, model, 'recall_memory', {'query': 'release rendezvous'}))
        assert still_present['episodes'][0]['id'] == episode_id
        deleted = await call(ap, model, 'forget', {'episode_id': episode_id})
        assert deleted == f'Deleted episode {episode_id}.'
        profiles_only = json.loads(await call(ap, model, 'recall_memory', {'query': 'release rendezvous'}))
        assert profiles_only['episodes'] == []
        assert 'brief technical answers' in profiles_only['speaker_profile']

    local._run_local_agent_probe(local_agent_e2e_tmpdir, read_after_restart)
