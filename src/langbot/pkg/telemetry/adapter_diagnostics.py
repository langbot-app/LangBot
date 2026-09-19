"""Finite adapter acceptance evidence, without message contents or target IDs."""

from __future__ import annotations

from .diagnostic_catalog import catalog


def boundary_fields(module, kind, operation, bound, parent):
    """Only the actual adapter API / EBA conversion boundary counts as a test."""
    entry = next((v for k, v in catalog().items() if k in module.split('.')), None)
    if entry is None or '.platform.adapters.' not in module:
        return {}
    evidence = kind == 'event' and operation == 'platform.target2yiri'
    resolved = operation
    if kind == 'api':
        evidence = True
        if operation == 'call_platform_api':
            action = bound.get('action')
            if isinstance(action, str) and 'platform_api.' + action in entry['specific_apis']:
                resolved = 'platform_api.' + action
            elif action in entry['apis'] and action != 'call_platform_api':
                resolved = action
            else:
                # Keep the generic boundary for investigation, not a false named test.
                evidence = False
        if (
            entry['adapter'] == 'lark-omni'
            and resolved
            in {
                'platform_api.check_tenant_access_token',
                'platform_api.refresh_app_access_token',
                'platform_api.refresh_tenant_access_token',
            }
            and getattr(bound.get('self'), 'config', {}).get('app_type', 'self') != 'isv'
        ):
            # Self-built apps return {'ok': True} without checking/refreshing a token.
            evidence = False
        # A forwarding API may call another decorated method. Count the outer call.
        if parent and parent.adapter_api_active:
            evidence = False
    if not evidence:
        return {'_adapter_api_active': kind == 'api'}
    return {
        '_adapter_api_active': kind == 'api',
        '_adapter_void_ack': completed_void_api(module, resolved),
        '_adapter_read_ack': completed_read_api(module, resolved),
        'operation': resolved,
        'attributes': {'adapter_evidence': True, **message_scenario(bound)},
    }


def message_scenario(bound):
    """Read typed routing/media categories only; never serialize a payload."""
    from langbot_plugin.api.entities.builtin.platform.events import MessageReceivedEvent
    from langbot_plugin.api.entities.builtin.platform.message import MessageChain

    event = bound.get('event') or bound.get('message_source')
    target = bound.get('target_type') or bound.get('chat_type')
    message = bound.get('message') or bound.get('new_content')
    if isinstance(event, MessageReceivedEvent):
        target = event.chat_type
        message = event.message_chain
    result = {}
    if target is not None:
        target = getattr(target, 'value', target)
        if target == 'private':
            target = 'person'
        result['chat_type'] = target if target in ('person', 'group') else 'unknown'
    if isinstance(message, MessageChain):
        types = set()
        for item in message:
            name = type(item).__name__
            types.add(
                {
                    'Plain': 'text',
                    'Image': 'image',
                    'Voice': 'audio',
                    'Audio': 'audio',
                    'Video': 'video',
                    'File': 'file',
                }.get(name, 'other')
            )
        result['content_type'] = next(iter(types)) if len(types) == 1 else 'mixed' if types else 'unknown'
    return result


# These exact API implementations always await an exception-raising SDK call,
# including SDKs whose successful acknowledgement has no return payload.
# Do not extend this to methods with conditional no-op or queued work.
VOID_ACKNOWLEDGED_APIS = {
    'aiocqhttp': frozenset(
        {
            'delete_message',
            'set_group_name',
            'mute_member',
            'unmute_member',
            'kick_member',
            'leave_group',
            'approve_friend_request',
            'approve_group_invite',
        }
    ),
    'discord': frozenset(
        {
            'edit_message',
            'delete_message',
            'mute_member',
            'unmute_member',
            'kick_member',
            'leave_group',
        }
    ),
    'kook': frozenset({'delete_message'}),
}


def completed_void_api(module, operation):
    return module.endswith('.api_impl') and any(
        directory in module.split('.') and operation in operations
        for directory, operations in VOID_ACKNOWLEDGED_APIS.items()
    )


# These read methods return actual fetched/cached data or raise. Exclude the
# known identity-only placeholders and file-ID passthroughs: a typed result alone
# is not evidence that a lookup worked. Unsupported methods still raise normally.
_READ_APIS = frozenset(
    {
        'get_message',
        'get_group_info',
        'get_group_list',
        'get_group_member_list',
        'get_group_member_info',
        'get_user_info',
        'get_friend_list',
        'get_file_url',
    }
)
READ_ACKNOWLEDGED_APIS = {
    'aiocqhttp': _READ_APIS,
    'telegram': _READ_APIS,
    'discord': _READ_APIS - {'get_file_url'},
    'dingtalk': _READ_APIS - {'get_group_info', 'get_user_info'},
    'kook': _READ_APIS - {'get_file_url'},
    'lark': _READ_APIS - {'get_user_info', 'get_group_member_info', 'get_file_url'},
    'officialaccount': _READ_APIS,
    'qqofficial': _READ_APIS,
    'slack': _READ_APIS,
    'wecom': _READ_APIS - {'get_user_info'},
    'wecombot': _READ_APIS,
    'wecomcs': _READ_APIS,
}


def completed_read_api(module, operation):
    return module.endswith('.api_impl') and any(
        directory in module.split('.') and operation in operations
        for directory, operations in READ_ACKNOWLEDGED_APIS.items()
    )


def response_outcome(value, adapter=None):
    """Finite acknowledgement contracts; never inspect or export message content.

    A MessageResult may contain an *inbound* message ID even when nothing was
    sent. Only its actual raw acknowledgement is eligible. Empty/queued/unknown
    returns are unconfirmed, not failures. Unknown SDK shapes need an explicit
    confirmation at their operation boundary, not a truthiness fallback.
    """
    from langbot_plugin.api.entities.builtin.platform.events import MessageResult

    message_result = isinstance(value, MessageResult)
    if message_result:
        value = value.raw
    if not isinstance(value, dict):
        return 'skipped'
    if (
        value.get('ok') is False
        or value.get('status') == 'failed'
        or any(type(value.get(key)) is int and value[key] != 0 for key in ('retcode', 'errcode', 'code'))
    ):
        return 'failed'
    if value.get('queued') is True or value.get('status') == 'async':
        return 'skipped'
    # The wrappers that batch sends retain the real responses in these fields.
    if 'results' in value:
        results = value['results']
        if not isinstance(results, list) or not results:
            return 'skipped'
        outcomes = [response_outcome(item, adapter) for item in results]
        return 'failed' if 'failed' in outcomes else 'skipped' if 'skipped' in outcomes else 'succeeded'
    for key in ('result', 'raw'):
        if key in value:
            return response_outcome(value[key], adapter)
    if (
        value.get('ok') is True
        or value.get('status') == 'ok'
        or any(type(value.get(key)) is int and value[key] == 0 for key in ('retcode', 'errcode', 'code'))
    ):
        return 'succeeded'
    if message_result:
        # These wrappers put only SDK-returned IDs in raw (never the source ID).
        if adapter in {'aiocqhttp-omni', 'discord-omni', 'telegram-omni'}:
            message_id = value.get('message_id')
            if type(message_id) in (str, int) and message_id:
                return 'succeeded'
        if adapter == 'lark-omni':
            ids = value.get('message_ids')
            if isinstance(ids, list) and ids and all(isinstance(item, str) and item for item in ids):
                return 'succeeded'
    return 'skipped'


def record_api_result(value, *, edited_content=None):
    """Record Telegram's Message/True acknowledgement and return it unchanged.

    This runs after the SDK await, not after conversion or local stream setup.
    No payload is retained; exceptions and the adapter's public return stay intact.
    """
    try:
        from .diagnostics import current_span

        span = current_span()
        if span is not None and span.kind == 'api' and span.fields.get('attributes', {}).get('adapter_evidence'):
            from telegram import Message

            outcome = (
                'succeeded'
                if value is True or isinstance(value, Message)
                else 'failed'
                if value is False
                else 'skipped'
            )
            if outcome == 'succeeded' and edited_content is not None:
                from langbot_plugin.api.entities.builtin.platform.message import Plain

                if any(not isinstance(item, Plain) for item in edited_content):
                    outcome = 'partial'
            # One unacknowledged component must not be hidden by a later success.
            prior = span.adapter_api_result
            span.adapter_api_result = (
                'failed'
                if 'failed' in (prior, outcome)
                else 'skipped'
                if 'skipped' in (prior, outcome)
                else 'partial'
                if 'partial' in (prior, outcome)
                else outcome
            )
    except Exception:
        pass
    return value
