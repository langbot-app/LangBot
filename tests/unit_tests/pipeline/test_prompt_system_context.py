from __future__ import annotations

from langbot_plugin.api.entities.builtin.provider.message import Message

from langbot.pkg.pipeline.preproc.prompt_context import added_system_context, system_messages


def test_added_system_context_preserves_hook_order_without_replaying_history():
    history = [
        Message(role='system', content='Existing system history'),
        Message(role='user', content='Earlier question'),
        Message(role='assistant', content='Earlier answer'),
    ]
    original = system_messages(history)
    final = history + [
        Message(role='system', content='First retrieved evidence'),
        Message(role='system', content='Second retrieved evidence'),
    ]
    projected = added_system_context(original, final)
    assert [item['content'] for item in projected] == ['First retrieved evidence', 'Second retrieved evidence']


def test_snapshot_detects_in_place_system_edits_and_honors_final_removal():
    message = Message(role='system', content='Old evidence')
    original = system_messages([message])
    message.content = 'Updated evidence'
    assert [item['content'] for item in added_system_context(original, [message])] == ['Updated evidence']
    assert added_system_context(original, []) == []
    assert original[0]['content'] == 'Old evidence'


def test_identical_history_occurrences_are_not_inserted_twice():
    item = {'role': 'system', 'content': 'Repeated evidence'}
    assert added_system_context([item, item], [item, item]) == []
    assert added_system_context([item], [item, item]) == [item]


def test_replaced_system_blocks_use_final_hook_order():
    original = system_messages([Message(role='system', content='Removed evidence')])
    final = [Message(role='system', content='Replacement evidence')]
    projected = added_system_context(original, final)
    assert [item['content'] for item in projected] == ['Replacement evidence']
    final[0].content = 'Later mutation'
    assert projected[0]['content'] == 'Replacement evidence'
