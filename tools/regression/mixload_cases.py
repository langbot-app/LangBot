"""Deterministic transaction families built from the real Daily Bot stack."""

from copy import deepcopy


# Tiny generated 2x2 RGB image. No external file URL, image service or
# inference is needed; the fixture oracle requires these exact wire bytes.
MEDIA_DATA_URL = (
    'data:image/png;base64,'
    'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGPQmndqp0YUg7ex7K87IgAlpwVTYiOAKQAAAABJRU5ErkJggg=='
)
CASE_MODELS = {
    'chat': 'mock-chat',
    'box': 'mock-smoke-box',
    'rag_chat': 'mock-rag',
    'media_chat': 'mock-media',
    'memory_chat': 'mock-memory',
}
CASE_WIRE_STREAMS = {'chat': 'mock', 'box': 'mock_box', 'rag_chat': 'mock_rag', 'media_chat': 'mock'}
CASE_RECEIPTS = {
    'chat': 'LANGBOT_CHAT_OK',
    'box': 'LANGBOT_BOX_OK',
    'rag_chat': 'LANGBOT_RAG_OK',
    'media_chat': 'LANGBOT_MEDIA_OK',
    'memory_chat': 'LANGBOT_MEMORY_OK',
}
_MOCK_SENTINEL = 'LANGBOT_BOX_SENTINEL'
_BOX_FILE = 'mixload-box-probe.txt'


def _validate_backend(box_backend):
    if box_backend not in ('docker', 'host'):
        raise ValueError('mixed Box fixtures require an explicitly selected docker or host backend')


def extend_mixload_profile(profile, *, box_backend, enable_memory=False):
    """Add a signed image transaction, preserving the real LocalAgent paths.

    The caller chooses case weights after building this catalog. The existing
    chat and RAG cases already exercise repeat-group history independently at
    the model boundary; no duplicate "history" transaction is counted.
    """
    _validate_backend(box_backend)
    result = deepcopy(profile)
    resources = {resource['id']: resource for resource in result['resources']}
    cases = {case['name']: case for case in result['cases']}
    cases['box']['box_exec']['backend'] = box_backend

    model = deepcopy(resources['chat_model'])
    model['id'] = 'media_model'
    model['body']['name'] = CASE_MODELS['media_chat']
    model['body']['abilities'] = ['func_call', 'vision']

    pipeline = deepcopy(resources['chat_pipeline'])
    pipeline['id'] = 'media_pipeline'
    pipeline['body'].update(
        name='mixload image chat',
        description='Signed image input verified in the model request',
    )
    ai = pipeline['body']['config']['ai']
    ai['runner_config'][ai['runner']['id']]['model']['primary'] = '${media_model}'

    bot = deepcopy(resources['chat_bot'])
    bot['id'] = 'media_bot'
    bot['body']['name'] = 'mixload group image'
    (binding,) = bot['body']['event_bindings']
    binding['target_uuid'] = '${media_pipeline}'

    result['resources'].extend([model, pipeline, bot])
    result['cases'].append(
        {
            'name': 'media_chat',
            'weight': 1,
            'http_group': {
                'url': '${core_base_url}/bots/${media_bot}/sync',
                'secret_env': cases['chat']['http_group']['secret_env'],
                'message': 'ai Please inspect the attached test image.',
                'components': [{'type': 'Image', 'base64': MEDIA_DATA_URL}],
            },
            'expect': CASE_RECEIPTS['media_chat'],
        }
    )
    if enable_memory:
        memory = deepcopy(model)
        memory['id'] = 'memory_model'
        memory['body'].update(name=CASE_MODELS['memory_chat'], abilities=['func_call'])
        memory_kb = {
            'id': 'memory_kb',
            'kind': 'knowledge-base',
            'body': {
                'name': 'mixload persistent session memory',
                'knowledge_engine_plugin_id': 'langbot-team/LongTermMemory',
                'creation_settings': {
                    'embedding_model_uuid': '${embedding_model}',
                    'isolation': 'session',
                    'retrieval_strategy': 'vector',
                    'candidate_extraction_enabled': False,
                    'consolidation_enabled': False,
                },
                'retrieval_settings': {'search_type': 'vector', 'top_k': 3},
            },
        }
        memory_pipeline = deepcopy(pipeline)
        memory_pipeline['id'] = 'memory_pipeline'
        memory_pipeline['body'].update(name='mixload session memory', description='Real per-group memory tools')
        mem_ai = memory_pipeline['body']['config']['ai']
        runner_config = mem_ai['runner_config'][mem_ai['runner']['id']]
        runner_config['model']['primary'] = '${memory_model}'
        runner_config['knowledge-bases'] = ['${memory_kb}']
        runner_config.update({'enable-all-tools': False, 'tools': ['remember', 'recall_memory']})
        memory_bot = deepcopy(bot)
        memory_bot['id'] = 'memory_bot'
        memory_bot['body']['name'] = 'mixload persistent memory'
        memory_bot['body']['event_bindings'][0]['target_uuid'] = '${memory_pipeline}'
        result['resources'].extend([memory, memory_kb, memory_pipeline, memory_bot])
        result['cases'].append(
            {
                'name': 'memory_chat',
                'weight': 1,
                'http_group': {
                    'url': '${core_base_url}/bots/${memory_bot}/sync',
                    'secret_env': cases['chat']['http_group']['secret_env'],
                    'message': 'ai Resolve the QA memory record for this conversation.',
                },
                'expect': CASE_RECEIPTS['memory_chat'],
            }
        )
    return result


def memory_scenario():
    """Turn one stores and reads; later turns only recall the same episode."""
    recall = {'tool_calls': [{'name': 'recall_memory', 'arguments': {'query': '{memory_marker}'}}]}
    verified = {'expect_memory_episode': True, 'content': CASE_RECEIPTS['memory_chat']}
    return {
        'delay_seconds': 0.6,
        'session_memory': True,
        'steps': [recall, verified],
        'first_turn_steps': [
            {'tool_calls': [{'name': 'remember', 'arguments': {'content': '{memory_marker}'}}]},
            {**recall, 'expect_memory_write': True},
            verified,
        ],
    }


def configure_mock_scenarios(scenarios, *, box_backend):
    """Return per-run model scenarios whose ordinary steps are fully scripted."""
    _validate_backend(box_backend)
    result = deepcopy(scenarios)
    for name in ('mock-chat', 'mock-smoke-box', 'mock-rag'):
        result[name]['delay_seconds'] = 0.6
    (rag_step,) = result[CASE_MODELS['rag_chat']]['steps']
    rag_step['expect_current_retrieved'] = rag_step['expect_prompt']
    result[CASE_MODELS['media_chat']] = {
        'delay_seconds': 0.6,
        'read_current_image': True,
        'steps': [
            {
                'tool_calls': [
                    {
                        'name': 'langbot_read_input_attachment',
                        'arguments': {'ref': '{current_image_ref}', 'mode': 'native'},
                    }
                ]
            },
            {'expect_tool_image': MEDIA_DATA_URL, 'content': CASE_RECEIPTS['media_chat']},
        ],
    }

    result[CASE_MODELS['memory_chat']] = memory_scenario()

    # File writes stay relative to the selected Box workdir. The first command
    # writes/reads, the second reads only, and both must produce the sentinel.
    # Docker can additionally report the real container hostname. For host,
    # the external oracle uses the real persisted Box result session ID.
    prefix = 'printf \'LB_BOX_HOST=%s\\n\' "$(hostname)"; ' if box_backend == 'docker' else ''
    commands = (
        f'{prefix}sleep 1; printf %s {_MOCK_SENTINEL} > {_BOX_FILE} && cat {_BOX_FILE}',
        f'{prefix}sleep 1; cat {_BOX_FILE}',
    )
    tool_calls = [call for step in result['mock-smoke-box']['steps'] for call in step.get('tool_calls', [])]
    if len(tool_calls) != len(commands) or any(call['name'] != 'exec' for call in tool_calls):
        raise ValueError('stock Box fixture no longer has the expected two exec steps')
    for call, command in zip(tool_calls, commands, strict=True):
        call['arguments']['command'] = command
    return result
