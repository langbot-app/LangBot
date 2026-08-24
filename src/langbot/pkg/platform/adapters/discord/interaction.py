"""Discord component rendering and callbacks for structured interactions."""

from __future__ import annotations

import time
import typing

import discord

from langbot_plugin.api.entities.builtin.platform import events as platform_events


def interaction_delivery_capabilities() -> dict[str, typing.Any]:
    return {
        'field_types': ['select'],
        'action_styles': ['default', 'primary', 'danger'],
        'supports_updates': True,
        'max_fields': 1,
    }


def parse_interaction_custom_id(custom_id: str | None) -> dict[str, typing.Any] | None:
    if not custom_id or not custom_id.startswith('lbi:'):
        return None
    parts = custom_id.split(':')
    if len(parts) == 4 and parts[1] and parts[2] == 'a' and parts[3].isdigit():
        return {'callback_token': parts[1], 'action_ref': int(parts[3])}
    if len(parts) == 5 and parts[1] and parts[2] == 'f' and parts[3].isdigit() and parts[4].isdigit():
        return {
            'callback_token': parts[1],
            'field_ref': int(parts[3]),
            'option_ref': int(parts[4]),
        }
    raise ValueError('invalid Discord interaction custom_id')


def _style(value: str) -> discord.ButtonStyle:
    if value == 'primary':
        return discord.ButtonStyle.primary
    if value == 'danger':
        return discord.ButtonStyle.danger
    return discord.ButtonStyle.secondary


def build_interaction_view(request: dict[str, typing.Any], callback_token: str) -> discord.ui.View | None:
    fields = request.get('fields') if isinstance(request.get('fields'), list) else []
    actions = request.get('actions') if isinstance(request.get('actions'), list) else []
    view = discord.ui.View(timeout=None)

    if actions and not fields:
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                continue
            view.add_item(
                discord.ui.Button(
                    label=str(action.get('label') or action.get('id') or index + 1)[:80],
                    style=_style(str(action.get('style') or 'default')),
                    custom_id=f'lbi:{callback_token}:a:{index}',
                )
            )
    elif len(fields) == 1 and not actions and isinstance(fields[0], dict):
        field = fields[0]
        if field.get('type') != 'select':
            return None
        options = field.get('options') if isinstance(field.get('options'), list) else []
        for option_index, option in enumerate(options):
            if not isinstance(option, dict):
                continue
            view.add_item(
                discord.ui.Button(
                    label=str(option.get('label') or option.get('value') or option_index + 1)[:80],
                    style=discord.ButtonStyle.secondary,
                    custom_id=f'lbi:{callback_token}:f:0:{option_index}',
                )
            )
    else:
        return None
    return view if view.children else None


def _content(request: dict[str, typing.Any], *, rich: bool) -> str:
    parts = [str(request.get('title') or '').strip()]
    description = str(request.get('description') or '').strip()
    if description:
        parts.append(description)
    fields = request.get('fields') if isinstance(request.get('fields'), list) else []
    if rich and len(fields) == 1 and isinstance(fields[0], dict):
        label = str(fields[0].get('label') or '').strip()
        if label:
            parts.append(label)
    if not rich:
        fallback = str(request.get('fallback_text') or '').strip()
        if fallback:
            parts.append(fallback)
    return '\n\n'.join(part for part in parts if part)[:2000]


async def send_interaction(adapter: typing.Any, params: dict[str, typing.Any]) -> dict[str, typing.Any]:
    request = params.get('request')
    reply_target = params.get('reply_target')
    callback_token = str(params.get('callback_token') or '')
    if not isinstance(request, dict) or not isinstance(reply_target, dict) or not callback_token:
        raise ValueError('interaction.request requires request, reply_target, and callback_token')
    target_id = str(reply_target.get('target_id') or '')
    if not target_id:
        raise ValueError('interaction.request has no target_id')
    channel = await adapter._get_channel(target_id)
    view = build_interaction_view(request, callback_token)
    sent = await channel.send(content=_content(request, rich=view is not None), view=view)
    return {'ok': True, 'message_id': sent.id, 'rich': view is not None}


def interaction_event_from_component(
    interaction: discord.Interaction,
    parsed: dict[str, typing.Any],
) -> platform_events.PlatformSpecificEvent:
    if interaction.user is None or interaction.channel is None:
        raise ValueError('Discord interaction has no actor or channel')
    return platform_events.PlatformSpecificEvent(
        type='platform.specific',
        adapter_name='discord',
        action='interaction.submitted',
        data={
            **parsed,
            'actor_id': str(interaction.user.id),
            'target_type': 'group' if interaction.guild is not None else 'person',
            'target_id': str(interaction.channel.id),
            'display_text': 'submitted',
        },
        timestamp=time.time(),
        source_platform_object=interaction,
    )
