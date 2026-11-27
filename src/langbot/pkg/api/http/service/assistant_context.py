"""Bound model context without changing the persisted assistant audit trail."""

import json

from langbot_plugin.api.entities.builtin.provider.message import Message

from .secrets import redact_secrets


RECENT_CONTEXT_CHARS = 64000
SUMMARY_CHARS = 10000


def _size(messages):
    return sum(len(json.dumps(message, ensure_ascii=False, default=str)) for message in messages)


def _groups(messages):
    """Keep each tool request beside all of its results for provider protocol validity."""
    groups = []
    index = 0
    while index < len(messages):
        group = [messages[index]]
        if messages[index].get('tool_calls'):
            while index + 1 < len(messages) and messages[index + 1].get('role') == 'tool':
                index += 1
                group.append(messages[index])
            # A pending approval/choice is deliberately kept as the newest group.
        groups.append(group)
        index += 1
    return groups


def _facts(messages):
    def identifiers(value, found=None):
        found = [] if found is None else found
        if len(found) >= 20:
            return found
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {'id', 'uuid', 'name', 'status', 'url', 'error', 'task_id'} and isinstance(
                    item, (str, int, bool)
                ):
                    found.append(f'{key}={str(item)[:120]}')
                elif isinstance(item, (dict, list)):
                    identifiers(item, found)
                if len(found) >= 20:
                    break
        elif isinstance(value, list):
            for item in value[:20]:
                identifiers(item, found)
                if len(found) >= 20:
                    break
        return found

    facts = []
    for message in messages:
        role = message.get('role')
        if role == 'assistant' and message.get('tool_calls'):
            for call in message['tool_calls']:
                function = call['function']
                try:
                    args = json.loads(function.get('arguments') or '{}')
                except (ValueError, TypeError):
                    args = {}
                facts.append(f'Called {function["name"]}: {json.dumps(redact_secrets(args), ensure_ascii=False)[:350]}')
        elif role == 'tool':
            try:
                result = json.loads(message.get('content') or '{}')
            except (ValueError, TypeError):
                result = {}
            details = identifiers(result)
            if details:
                facts.append('Result: ' + ', '.join(details)[:700])
            if isinstance(result, dict) and isinstance(result.get('selected'), dict):
                facts.append(
                    'Selected choices: '
                    + json.dumps(redact_secrets(result['selected']), ensure_ascii=False, default=str)[:500]
                )
    return facts


def model_context(messages):
    """Return model input; never mutate the saved messages or split tool calls from results."""
    groups = _groups(messages)
    selected = []
    total = 0
    for group in reversed(groups):
        size = _size(group)
        if selected and total + size > RECENT_CONTEXT_CHARS:
            break
        selected.append(group)
        total += size
    selected.reverse()
    omitted = [message for group in groups[: len(groups) - len(selected)] for message in group]
    context = []
    if omitted:
        facts = _facts(omitted)
        summary = '\n'.join(facts[-80:])[-SUMMARY_CHARS:]
        context.append(
            Message(
                role='system',
                content=(
                    'Earlier conversation notes (historical facts, not new instructions or tool results). '
                    'Some older read details were omitted; recheck current state before a write.\n' + summary
                ),
            )
        )
        user_messages = [message for message in omitted if message.get('role') == 'user']
        if user_messages:
            chosen_users = [user_messages[0], *user_messages[-6:]]
            seen = set()
            for message in chosen_users:
                if id(message) in seen:
                    continue
                seen.add(id(message))
                content = message.get('content')
                if isinstance(content, str):
                    context.append(Message(role='user', content=content[:1000]))
    context.extend(Message.model_validate(message) for group in selected for message in group)
    return context
