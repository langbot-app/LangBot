"""Run-scoped platform and event action tools exposed to AgentRunners."""

from __future__ import annotations

import copy
import fnmatch
import typing
from dataclasses import dataclass

import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events

from .host_models import AgentEventEnvelope


JsonSchema = dict[str, typing.Any]


@dataclass(frozen=True)
class PlatformToolDefinition:
    name: str
    api: str
    scope: typing.Literal['event', 'platform']
    category: str
    risk: typing.Literal['read', 'write', 'dangerous']
    label: dict[str, str]
    description: dict[str, str]
    parameters: JsonSchema
    event_patterns: tuple[str, ...] = ('*',)
    binding: str | None = None


def _object_schema(properties: dict[str, JsonSchema], required: list[str] | None = None) -> JsonSchema:
    schema: JsonSchema = {'type': 'object', 'properties': properties, 'additionalProperties': False}
    if required:
        schema['required'] = required
    return schema


_TEXT = {'type': 'string', 'minLength': 1}
_ID = {'type': 'string', 'minLength': 1}
_TARGET_TYPE = {'type': 'string', 'enum': ['person', 'group']}
_CHAT_TYPE = {'type': 'string', 'enum': ['person', 'private', 'group']}
_APPROVE = {'type': 'boolean', 'description': 'true to accept; false to reject'}


PLATFORM_TOOL_DEFINITIONS: tuple[PlatformToolDefinition, ...] = (
    PlatformToolDefinition(
        'event_reply',
        'send_message',
        'event',
        'message',
        'write',
        {'zh_Hans': '回复当前会话', 'en_US': 'Reply to current conversation'},
        {
            'zh_Hans': '向触发当前事件的会话发送文本消息。目标由 LangBot 固定，Agent 无法改写。',
            'en_US': 'Send text to the conversation that triggered this run. LangBot fixes the target.',
        },
        _object_schema({'text': {**_TEXT, 'description': 'Reply text'}}, ['text']),
        ('message.*', 'friend.*', 'group.*', 'feedback.*'),
        'reply_target',
    ),
    PlatformToolDefinition(
        'event_delete_message',
        'delete_message',
        'event',
        'message',
        'dangerous',
        {'zh_Hans': '删除当前消息', 'en_US': 'Delete current message'},
        {
            'zh_Hans': '删除触发当前事件的消息。消息与会话标识由 LangBot 固定。',
            'en_US': 'Delete the message that triggered the run. Message and chat IDs are fixed by LangBot.',
        },
        _object_schema({}),
        ('message.received', 'message.edited'),
        'current_message',
    ),
    PlatformToolDefinition(
        'event_get_actor',
        'get_user_info',
        'event',
        'identity',
        'read',
        {'zh_Hans': '查询事件发起者', 'en_US': 'Get event actor'},
        {
            'zh_Hans': '查询当前事件发起者的用户资料。用户标识由 LangBot 固定。',
            'en_US': 'Read the current event actor profile. LangBot fixes the user ID.',
        },
        _object_schema({}),
        ('*',),
        'actor',
    ),
    PlatformToolDefinition(
        'event_get_group',
        'get_group_info',
        'event',
        'group',
        'read',
        {'zh_Hans': '查询当前群组', 'en_US': 'Get current group'},
        {
            'zh_Hans': '查询当前事件所属群组的信息。群组标识由 LangBot 固定。',
            'en_US': 'Read the group associated with the current event. LangBot fixes the group ID.',
        },
        _object_schema({}),
        ('message.*', 'group.*', 'bot.invited_to_group', 'bot.removed_from_group', 'bot.muted', 'bot.unmuted'),
        'group',
    ),
    PlatformToolDefinition(
        'event_get_group_member',
        'get_group_member_info',
        'event',
        'group',
        'read',
        {'zh_Hans': '查询相关群成员', 'en_US': 'Get related group member'},
        {
            'zh_Hans': '查询当前事件发起者在当前群组中的成员信息。',
            'en_US': 'Read the current actor membership in the current group.',
        },
        _object_schema({}),
        ('message.*', 'group.*'),
        'group_actor',
    ),
    PlatformToolDefinition(
        'event_mute_member',
        'mute_member',
        'event',
        'moderation',
        'dangerous',
        {'zh_Hans': '禁言相关群成员', 'en_US': 'Mute related group member'},
        {
            'zh_Hans': '禁言当前事件关联的群成员，群组和成员标识由 LangBot 固定。',
            'en_US': 'Mute the member related to this event. LangBot fixes group and user IDs.',
        },
        _object_schema(
            {
                'duration': {
                    'type': 'integer',
                    'minimum': 0,
                    'description': 'Mute duration in seconds; 0 uses the adapter default',
                }
            }
        ),
        ('message.*', 'group.member_*'),
        'group_actor',
    ),
    PlatformToolDefinition(
        'event_unmute_member',
        'unmute_member',
        'event',
        'moderation',
        'dangerous',
        {'zh_Hans': '解除相关群成员禁言', 'en_US': 'Unmute related group member'},
        {'zh_Hans': '解除当前事件关联群成员的禁言。', 'en_US': 'Unmute the member related to this event.'},
        _object_schema({}),
        ('message.*', 'group.member_*'),
        'group_actor',
    ),
    PlatformToolDefinition(
        'event_kick_member',
        'kick_member',
        'event',
        'moderation',
        'dangerous',
        {'zh_Hans': '移出相关群成员', 'en_US': 'Kick related group member'},
        {
            'zh_Hans': '将当前事件关联的成员移出群组。',
            'en_US': 'Remove the member related to this event from the group.',
        },
        _object_schema({}),
        ('message.*', 'group.member_*'),
        'group_actor',
    ),
    PlatformToolDefinition(
        'event_respond_friend_request',
        'approve_friend_request',
        'event',
        'request',
        'dangerous',
        {'zh_Hans': '处理好友请求', 'en_US': 'Respond to friend request'},
        {
            'zh_Hans': '同意或拒绝触发当前事件的好友请求。请求标识由 LangBot 固定。',
            'en_US': 'Accept or reject the friend request that triggered this run. LangBot fixes the request ID.',
        },
        _object_schema({'approve': _APPROVE, 'remark': {'type': 'string'}}, ['approve']),
        ('friend.request_received',),
        'request',
    ),
    PlatformToolDefinition(
        'event_respond_group_invite',
        'approve_group_invite',
        'event',
        'request',
        'dangerous',
        {'zh_Hans': '处理入群邀请', 'en_US': 'Respond to group invite'},
        {
            'zh_Hans': '同意或拒绝触发当前事件的机器人入群邀请。',
            'en_US': 'Accept or reject the bot group invitation that triggered this run.',
        },
        _object_schema({'approve': _APPROVE}, ['approve']),
        ('bot.invited_to_group',),
        'request',
    ),
    PlatformToolDefinition(
        'platform_send_message',
        'send_message',
        'platform',
        'message',
        'write',
        {'zh_Hans': '发送消息', 'en_US': 'Send message'},
        {
            'zh_Hans': '使用当前机器人向指定用户或群组发送文本消息。',
            'en_US': 'Send text to a specified person or group using the current bot.',
        },
        _object_schema(
            {'target_type': _TARGET_TYPE, 'target_id': _ID, 'text': _TEXT}, ['target_type', 'target_id', 'text']
        ),
    ),
    PlatformToolDefinition(
        'platform_get_message',
        'get_message',
        'platform',
        'message',
        'read',
        {'zh_Hans': '查询消息', 'en_US': 'Get message'},
        {'zh_Hans': '按会话和消息标识查询消息。', 'en_US': 'Get a message by chat and message ID.'},
        _object_schema(
            {'chat_type': _CHAT_TYPE, 'chat_id': _ID, 'message_id': _ID}, ['chat_type', 'chat_id', 'message_id']
        ),
    ),
    PlatformToolDefinition(
        'platform_delete_message',
        'delete_message',
        'platform',
        'message',
        'dangerous',
        {'zh_Hans': '删除指定消息', 'en_US': 'Delete message'},
        {'zh_Hans': '按会话和消息标识删除消息。', 'en_US': 'Delete a message by chat and message ID.'},
        _object_schema(
            {'chat_type': _CHAT_TYPE, 'chat_id': _ID, 'message_id': _ID}, ['chat_type', 'chat_id', 'message_id']
        ),
    ),
    PlatformToolDefinition(
        'platform_get_group_info',
        'get_group_info',
        'platform',
        'group',
        'read',
        {'zh_Hans': '查询群组', 'en_US': 'Get group'},
        {'zh_Hans': '查询指定群组的信息。', 'en_US': 'Read information about a specified group.'},
        _object_schema({'group_id': _ID}, ['group_id']),
    ),
    PlatformToolDefinition(
        'platform_get_group_list',
        'get_group_list',
        'platform',
        'group',
        'read',
        {'zh_Hans': '列出群组', 'en_US': 'List groups'},
        {'zh_Hans': '列出当前机器人加入的群组。', 'en_US': 'List groups joined by the current bot.'},
        _object_schema({}),
    ),
    PlatformToolDefinition(
        'platform_get_group_member_list',
        'get_group_member_list',
        'platform',
        'group',
        'read',
        {'zh_Hans': '列出群成员', 'en_US': 'List group members'},
        {'zh_Hans': '列出指定群组的成员。', 'en_US': 'List members of a specified group.'},
        _object_schema({'group_id': _ID}, ['group_id']),
    ),
    PlatformToolDefinition(
        'platform_get_group_member_info',
        'get_group_member_info',
        'platform',
        'group',
        'read',
        {'zh_Hans': '查询群成员', 'en_US': 'Get group member'},
        {'zh_Hans': '查询指定用户在指定群组中的成员信息。', 'en_US': 'Read a specified user membership in a group.'},
        _object_schema({'group_id': _ID, 'user_id': _ID}, ['group_id', 'user_id']),
    ),
    PlatformToolDefinition(
        'platform_set_group_name',
        'set_group_name',
        'platform',
        'group',
        'dangerous',
        {'zh_Hans': '修改群名称', 'en_US': 'Rename group'},
        {'zh_Hans': '修改指定群组的名称。', 'en_US': 'Change the name of a specified group.'},
        _object_schema({'group_id': _ID, 'name': _TEXT}, ['group_id', 'name']),
    ),
    PlatformToolDefinition(
        'platform_mute_member',
        'mute_member',
        'platform',
        'moderation',
        'dangerous',
        {'zh_Hans': '禁言群成员', 'en_US': 'Mute group member'},
        {'zh_Hans': '禁言指定群组中的指定成员。', 'en_US': 'Mute a specified member in a group.'},
        _object_schema(
            {'group_id': _ID, 'user_id': _ID, 'duration': {'type': 'integer', 'minimum': 0}}, ['group_id', 'user_id']
        ),
    ),
    PlatformToolDefinition(
        'platform_unmute_member',
        'unmute_member',
        'platform',
        'moderation',
        'dangerous',
        {'zh_Hans': '解除群成员禁言', 'en_US': 'Unmute group member'},
        {'zh_Hans': '解除指定群成员的禁言。', 'en_US': 'Unmute a specified group member.'},
        _object_schema({'group_id': _ID, 'user_id': _ID}, ['group_id', 'user_id']),
    ),
    PlatformToolDefinition(
        'platform_kick_member',
        'kick_member',
        'platform',
        'moderation',
        'dangerous',
        {'zh_Hans': '移出群成员', 'en_US': 'Kick group member'},
        {'zh_Hans': '将指定成员移出指定群组。', 'en_US': 'Remove a specified member from a group.'},
        _object_schema({'group_id': _ID, 'user_id': _ID}, ['group_id', 'user_id']),
    ),
    PlatformToolDefinition(
        'platform_leave_group',
        'leave_group',
        'platform',
        'moderation',
        'dangerous',
        {'zh_Hans': '退出群组', 'en_US': 'Leave group'},
        {'zh_Hans': '让当前机器人退出指定群组。', 'en_US': 'Make the current bot leave a specified group.'},
        _object_schema({'group_id': _ID}, ['group_id']),
    ),
    PlatformToolDefinition(
        'platform_get_user_info',
        'get_user_info',
        'platform',
        'identity',
        'read',
        {'zh_Hans': '查询用户', 'en_US': 'Get user'},
        {'zh_Hans': '查询指定用户的资料。', 'en_US': 'Read a specified user profile.'},
        _object_schema({'user_id': _ID}, ['user_id']),
    ),
    PlatformToolDefinition(
        'platform_get_friend_list',
        'get_friend_list',
        'platform',
        'identity',
        'read',
        {'zh_Hans': '列出好友', 'en_US': 'List friends'},
        {'zh_Hans': '列出当前机器人的好友。', 'en_US': 'List friends of the current bot.'},
        _object_schema({}),
    ),
)

PLATFORM_TOOLS_BY_NAME = {definition.name: definition for definition in PLATFORM_TOOL_DEFINITIONS}


def resolve_agent_platform_tool_names(config: typing.Mapping[str, typing.Any], event_type: str) -> list[str]:
    """Resolve platform tools plus the event actions implied by this event."""
    configured = [name for name in config.get('allowed_platform_tools', []) if isinstance(name, str)]
    selected = [
        name
        for name in configured
        if (definition := PLATFORM_TOOLS_BY_NAME.get(name)) is not None and definition.scope == 'platform'
    ]
    selected.extend(
        definition.name
        for definition in PLATFORM_TOOL_DEFINITIONS
        if definition.scope == 'event' and _event_matches(event_type, definition.event_patterns)
    )
    return selected


def platform_tool_catalog() -> list[dict[str, typing.Any]]:
    return [
        {
            'name': item.name,
            'api': item.api,
            'scope': item.scope,
            'category': item.category,
            'risk': item.risk,
            'label': item.label,
            'description': item.description,
            'event_patterns': list(item.event_patterns),
            'parameters': copy.deepcopy(item.parameters),
        }
        for item in PLATFORM_TOOL_DEFINITIONS
    ]


def validate_debug_mock_options(value: typing.Any) -> dict[str, typing.Any]:
    if not isinstance(value, dict) or set(value) - {'errors', 'results', 'unsupported_apis'}:
        raise ValueError('Mock options must contain only errors, results and unsupported_apis')
    for field in ('errors', 'results'):
        entries = value.get(field, {})
        if not isinstance(entries, dict) or set(entries) - set(PLATFORM_TOOLS_BY_NAME):
            raise ValueError(f'Mock {field} must map platform tool names to outcomes')
    if any(not isinstance(error, str) or not error.strip() for error in value.get('errors', {}).values()):
        raise ValueError('Mock errors must be non-empty strings')
    if set(value.get('errors', {})) & set(value.get('results', {})):
        raise ValueError('A mock tool cannot have both an error and a result')
    unsupported = value.get('unsupported_apis', [])
    if not isinstance(unsupported, list) or any(
        not isinstance(api, str) or api not in {tool.api for tool in PLATFORM_TOOL_DEFINITIONS} for api in unsupported
    ):
        raise ValueError('Mock unsupported_apis must be an array of platform API names')
    return copy.deepcopy(value)


def _event_matches(event_type: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(event_type, pattern) for pattern in patterns)


def _event_binding_available(event: AgentEventEnvelope, binding: str | None) -> bool:
    if binding is None:
        return True
    reply_target = event.delivery.reply_target or {}
    if binding == 'reply_target':
        return bool(reply_target.get('target_type') and reply_target.get('target_id'))
    if binding == 'current_message':
        return bool(
            reply_target.get('target_type') and reply_target.get('target_id') and reply_target.get('message_id')
        )
    if binding == 'actor':
        return bool(event.actor and event.actor.actor_id)
    group_id = reply_target.get('group_id') or (
        event.subject.subject_id if event.subject and event.subject.subject_type == 'group' else None
    )
    if binding == 'group':
        return bool(group_id)
    if binding == 'group_actor':
        return bool(group_id and event.actor and event.actor.actor_id)
    if binding == 'request':
        # A Host event reference is only a journal identity.  It is not a
        # platform request token and must never be forwarded to an adapter as
        # one.  Request actions are therefore available only when the adapter
        # event supplied its real request_id.
        return bool(event.data.get('request_id'))
    return False


def build_platform_tool_resources(
    event: AgentEventEnvelope, selected_names: typing.Iterable[str] | None, operations: list[str]
) -> tuple[list[dict[str, typing.Any]], dict[str, typing.Any]]:
    selected = list(dict.fromkeys(selected_names or []))
    supported_apis = set((event.delivery.platform_capabilities or {}).get('supported_apis') or [])
    resources: list[dict[str, typing.Any]] = []
    unavailable: list[dict[str, str]] = []
    if 'call' not in operations:
        capabilities = copy.deepcopy(event.delivery.platform_capabilities or {})
        capabilities.update(
            {
                'authorized_tools': [],
                'unavailable_tools': [{'name': name, 'reason': 'runner_call_permission_missing'} for name in selected],
            }
        )
        return resources, capabilities
    for name in selected:
        definition = PLATFORM_TOOLS_BY_NAME.get(name)
        reason = None
        if definition is None:
            reason = 'unknown_tool'
        elif definition.api not in supported_apis:
            reason = 'adapter_api_unsupported'
        elif definition.scope == 'event' and not _event_matches(event.event_type, definition.event_patterns):
            reason = 'event_incompatible'
        elif definition.scope == 'event' and not _event_binding_available(event, definition.binding):
            reason = 'event_target_unavailable'
        if reason:
            unavailable.append({'name': name, 'reason': reason})
            continue
        assert definition is not None
        resources.append(
            {
                'tool_name': definition.name,
                'tool_type': 'platform',
                'description': definition.description.get('en_US') or definition.description.get('zh_Hans'),
                'operations': list(operations),
                'parameters': copy.deepcopy(definition.parameters),
                'source': 'platform',
                'source_id': definition.name,
            }
        )
    capabilities = copy.deepcopy(event.delivery.platform_capabilities or {})
    capabilities.update(
        {'authorized_tools': [item['tool_name'] for item in resources], 'unavailable_tools': unavailable}
    )
    return resources, capabilities


def freeze_platform_context(event: AgentEventEnvelope) -> dict[str, typing.Any]:
    return {
        'event_type': event.event_type,
        'data': copy.deepcopy(event.data),
        'actor': event.actor.model_dump(mode='json') if event.actor else None,
        'subject': event.subject.model_dump(mode='json') if event.subject else None,
        'delivery': event.delivery.model_dump(mode='json'),
        'raw_ref': event.raw_ref.model_dump(mode='json') if event.raw_ref else None,
    }


def get_platform_tool_detail(session: typing.Mapping[str, typing.Any], tool_name: str) -> dict[str, typing.Any] | None:
    for tool in session.get('authorization', {}).get('resources', {}).get('tools', []):
        if tool.get('tool_name') == tool_name and tool.get('source') == 'platform':
            return {
                'name': tool_name,
                'description': tool.get('description'),
                'parameters': copy.deepcopy(tool.get('parameters') or _object_schema({})),
            }
    return None


def _require_string(parameters: dict[str, typing.Any], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a non-empty string')
    return value.strip()


def _event_params(
    definition: PlatformToolDefinition, context: dict[str, typing.Any], parameters: dict[str, typing.Any]
) -> dict[str, typing.Any]:
    reply_target = (context.get('delivery') or {}).get('reply_target') or {}
    actor = context.get('actor') or {}
    subject = context.get('subject') or {}
    data = context.get('data') or {}
    group_id = reply_target.get('group_id') or (
        subject.get('subject_id') if subject.get('subject_type') == 'group' else None
    )
    actor_id = actor.get('actor_id')
    if definition.binding == 'reply_target':
        return {
            'target_type': reply_target.get('target_type'),
            'target_id': reply_target.get('target_id'),
            'text': _require_string(parameters, 'text'),
        }
    if definition.binding == 'current_message':
        return {
            'chat_type': reply_target.get('target_type'),
            'chat_id': reply_target.get('target_id'),
            'message_id': reply_target.get('message_id'),
        }
    if definition.binding == 'actor':
        return {'user_id': actor_id}
    if definition.binding == 'group':
        return {'group_id': group_id}
    if definition.binding == 'group_actor':
        result = {'group_id': group_id, 'user_id': actor_id}
        if definition.api == 'mute_member':
            duration = parameters.get('duration', 0)
            if not isinstance(duration, int) or duration < 0:
                raise ValueError('duration must be a non-negative integer')
            result['duration'] = duration
        return result
    if definition.binding == 'request':
        result = {
            'request_id': data.get('request_id'),
            'approve': parameters.get('approve'),
        }
        if not isinstance(result['approve'], bool):
            raise ValueError('approve must be a boolean')
        if definition.api == 'approve_friend_request' and isinstance(parameters.get('remark'), str):
            result['remark'] = parameters['remark']
        return result
    return dict(parameters)


def _normalize_platform_params(
    definition: PlatformToolDefinition, parameters: dict[str, typing.Any]
) -> dict[str, typing.Any]:
    if not isinstance(parameters, dict):
        raise ValueError('parameters must be an object')
    allowed = set((definition.parameters.get('properties') or {}).keys())
    extra = set(parameters) - allowed
    if extra:
        raise ValueError(f'Unexpected parameters: {", ".join(sorted(extra))}')
    for required in definition.parameters.get('required', []):
        if required not in parameters:
            raise ValueError(f'{required} is required')
    for name, value in parameters.items():
        field = definition.parameters['properties'][name]
        expected_type = field.get('type')
        if expected_type == 'string' and not isinstance(value, str):
            raise ValueError(f'{name} must be a string')
        if expected_type == 'boolean' and not isinstance(value, bool):
            raise ValueError(f'{name} must be a boolean')
        if expected_type == 'integer' and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError(f'{name} must be an integer')
        if isinstance(value, str) and field.get('minLength', 0) > len(value):
            raise ValueError(f'{name} must be a non-empty string')
        if isinstance(value, int) and 'minimum' in field and value < field['minimum']:
            raise ValueError(f'{name} must be at least {field["minimum"]}')
        if 'enum' in field and value not in field['enum']:
            raise ValueError(f'{name} must be one of: {", ".join(field["enum"])}')
    return dict(parameters)


async def execute_platform_tool(
    ap: typing.Any,
    execution_context: typing.Any,
    session: typing.Mapping[str, typing.Any],
    tool_name: str,
    parameters: dict[str, typing.Any],
) -> typing.Any:
    definition = PLATFORM_TOOLS_BY_NAME.get(tool_name)
    if definition is None:
        raise ValueError(f'Unknown platform tool: {tool_name}')
    authorization = session.get('authorization', {})
    context = authorization.get('platform_context') or {}
    delivery = context.get('delivery') or {}
    normalized = _normalize_platform_params(definition, parameters)
    if definition.scope == 'event':
        normalized = _event_params(definition, context, normalized)
    # This flag is frozen by the Host from the synthetic debug envelope, not tool arguments.
    if delivery.get('surface') == 'webui' and (delivery.get('platform_capabilities') or {}).get('debug_mock') is True:
        return _execute_mock_platform_tool(definition, context, normalized)
    bot_id = authorization.get('bot_id')
    if not bot_id:
        raise ValueError('This run is not associated with a platform bot')
    bot = await ap.platform_mgr.get_bot_by_uuid(execution_context, bot_id)
    if bot is None:
        raise ValueError(f'Bot {bot_id} is not running')
    if definition.api not in set(bot.adapter.get_supported_apis() or []):
        raise ValueError(f'Platform API {definition.api} is no longer supported by bot {bot_id}')
    api_func = getattr(bot.adapter, definition.api, None)
    if not callable(api_func):
        raise ValueError(f'Platform API {definition.api} is declared but not implemented')
    if definition.api == 'send_message':
        normalized = {
            'target_type': _require_string(normalized, 'target_type'),
            'target_id': _require_string(normalized, 'target_id'),
            'message': platform_message.MessageChain(
                [platform_message.Plain(text=_require_string(normalized, 'text'))]
            ),
        }
    return await api_func(**normalized)


def _execute_mock_platform_tool(
    definition: PlatformToolDefinition, context: dict[str, typing.Any], parameters: dict[str, typing.Any]
) -> dict[str, typing.Any]:
    """Simulate the adapter boundary while preserving real model calls and validated targets."""
    data = context.get('data') or {}
    actor = context.get('actor') or {}
    options = ((context.get('delivery') or {}).get('platform_capabilities') or {}).get('mock_options') or {}
    result: typing.Any = None
    user_id = parameters.get('user_id') or actor.get('actor_id') or 'debug-user'
    user = platform_entities.User(
        id=user_id,
        nickname=(actor.get('actor_name') or 'Debug User')
        if user_id == actor.get('actor_id')
        else f'Mock user {user_id}',
    )
    group_id = parameters.get('group_id') or data.get('group_id') or 'debug-group'
    group = platform_entities.UserGroup(id=group_id, name=data.get('group_name') or 'Mock group')
    member = platform_entities.UserGroupMember(user=user, group_id=group_id)
    if definition.api == 'send_message':
        for field in ('target_type', 'target_id', 'text'):
            _require_string(parameters, field)
        result = {'message_id': 'mock-message'}
    elif definition.api == 'get_user_info':
        result = user.model_dump(mode='json')
    elif definition.api == 'get_group_member_info':
        result = member.model_dump(mode='json')
    elif definition.api == 'get_group_info':
        result = group.model_dump(mode='json')
    elif definition.api == 'get_group_list':
        result = [group.model_dump(mode='json')]
    elif definition.api == 'get_group_member_list':
        result = [member.model_dump(mode='json')]
    elif definition.api == 'get_friend_list':
        result = [user.model_dump(mode='json')]
    elif definition.api == 'get_message':
        result = platform_events.MessageReceivedEvent(
            message_id=parameters['message_id'],
            chat_id=parameters['chat_id'],
            chat_type='group' if parameters['chat_type'] == 'group' else 'private',
            sender=user,
            message_chain=platform_message.MessageChain(
                [platform_message.Plain(text=str(data.get('text') or 'Mock message'))]
            ),
        ).model_dump(mode='json')
    error = options.get('errors', {}).get(definition.name)
    if definition.name in options.get('results', {}):
        result = copy.deepcopy(options['results'][definition.name])
    return {
        'ok': error is None,
        'mock': True,
        'delivery': 'simulated',
        'tool': definition.name,
        'api': definition.api,
        'parameters': parameters,
        'result': None if error else result,
        **({'error': error} if error else {}),
        'notice': 'Simulated platform operation. No real platform API was called.',
    }


__all__ = [
    'PLATFORM_TOOL_DEFINITIONS',
    'build_platform_tool_resources',
    'execute_platform_tool',
    'freeze_platform_context',
    'get_platform_tool_detail',
    'platform_tool_catalog',
    'resolve_agent_platform_tool_names',
]
