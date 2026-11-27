import json

from langbot.pkg.api.http.service.assistant_context import model_context


def test_model_context_keeps_tool_pairs_and_original_history():
    messages = [{'role': 'user', 'content': 'Build a QQ bot with RAG'}]
    for index in range(12):
        if index == 3:
            messages.append({'role': 'user', 'content': 'Also add welcome messages'})
        messages.extend(
            [
                {
                    'role': 'assistant',
                    'content': '',
                    'tool_calls': [
                        {
                            'id': f'call-{index}',
                            'type': 'function',
                            'function': {'name': 'workspace_call', 'arguments': json.dumps({'id': index})},
                        }
                    ],
                },
                {'role': 'tool', 'tool_call_id': f'call-{index}', 'content': json.dumps({'result': 'x' * 7000})},
            ]
        )
    original = json.dumps(messages)
    context = [message.model_dump(mode='json') for message in model_context(messages)]
    assert json.dumps(messages) == original
    assert any(
        message['role'] == 'system' and 'Earlier conversation notes' in message['content'] for message in context
    )
    assert any(message['role'] == 'user' and 'Build a QQ bot' in message['content'] for message in context)
    assert any(message['role'] == 'user' and 'welcome messages' in message['content'] for message in context)
    calls = {call['id'] for message in context for call in message.get('tool_calls') or []}
    assert all(message['tool_call_id'] in calls for message in context if message['role'] == 'tool')
    assert len(json.dumps(context)) < 80000
