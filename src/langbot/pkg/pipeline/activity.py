"""Sequential, request-scoped Pipeline activity notices."""

import asyncio

from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain

from ..i18n import language_scope, t
from ..i18n.workspace import get_workspace_language
from ..pipeline.pool import get_query_execution_context


async def notify_activity(ap, query, activity: str, name: str, *, source: str = '', source_name: str = '') -> None:
    """Send an optional notice without interrupting the actual operation."""
    if query is None:
        return
    config = getattr(query, 'pipeline_config', {}).get('output', {}).get('misc', {})
    if not config.get('activity-enabled', False) or not config.get(f'activity-{activity}', True):
        return
    templates = {
        'tool': 'Agent is calling tool: {name}',
        'knowledge': 'Agent is searching knowledge base: {name}',
    }
    if activity not in templates:
        return
    lock = getattr(query, '_activity_notice_lock', None)
    if lock is None:
        lock = asyncio.Lock()
        object.__setattr__(query, '_activity_notice_lock', lock)
    try:
        async with lock:
            async with asyncio.timeout(3):
                context = get_query_execution_context(query)
                locale = await get_workspace_language(ap, context.workspace_uuid)
                with language_scope(locale):
                    if activity == 'tool':
                        custom = config.get('tool-call-hint')
                        text = (
                            custom.replace('{tools}', name)
                            if isinstance(custom, str) and custom.strip()
                            else '🛠️ ' + t(templates[activity], name=name)
                        )
                    else:
                        custom = config.get('knowledge-retrieval-hint')
                        text = (
                            custom.replace('{name}', name)
                            if isinstance(custom, str) and custom.strip()
                            else '🔍 ' + t(templates[activity], name=name)
                        )
                    if config.get('activity-show-source', False):
                        labels = {
                            'plugin': 'Plugin',
                            'mcp': 'MCP',
                            'native': 'Built-in',
                            'builtin': 'Built-in',
                            'skill': 'Skill',
                            'platform': 'Platform',
                            'knowledge': 'Knowledge base',
                        }
                        if source in labels:
                            origin = t(labels[source])
                            if source_name:
                                origin += ': ' + source_name
                            text += ' · ' + origin
                message = MessageChain([Plain(text=text)])
                progress_reply = getattr(query.adapter, 'reply_progress', None)
                if progress_reply is not None:
                    await progress_reply(query.message_event, message)
                else:
                    await query.adapter.reply_message(query.message_event, message, False)
    except Exception:
        ap.logger.debug('Pipeline activity notification failed', exc_info=True)
