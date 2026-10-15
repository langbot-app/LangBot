"""Packaged into the isolated E2E plugin; calls only public SDK LLM APIs."""

from contextlib import aclosing
import json

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.api.proxies.langbot_api import LangBotAPIProxy


class DefaultRunner(Runner):
    async def run(self, ctx):
        options = json.loads(ctx.input.to_text())
        mode = options['mode']
        cancel = mode.startswith('cancel-')
        if cancel:
            mode = mode.removeprefix('cancel-')
        api = LangBotAPIProxy(self._plugin_runtime_handler) if mode.startswith('plugin-') else ctx.api
        message_type = Message
        if mode.startswith('legacy-'):
            # Historical files are supplied verbatim from a released SDK tag.
            # Its proxy and serializers use the real current runtime transport.
            import legacy_api
            import legacy_message

            legacy_api.provider_message = legacy_message
            api = legacy_api.LangBotAPIProxy(self._plugin_runtime_handler)
            message_type = legacy_message.Message
        extra = {
            **options['extra'],
            'extra_headers': {
                **options['extra'].get('extra_headers', {}),
                'x-e2e-case': options['case'],
            },
        }
        kwargs = {
            'llm_model_uuid': options['model'],
            'messages': [
                message_type.model_validate(m)
                for m in options.get(
                    'messages',
                    [
                        {'role': 'user', 'content': 'Hello'},
                    ],
                )
            ],
            'extra_args': extra,
        }
        if options.get('tool'):
            from langbot_plugin.api.entities.builtin.resource.tool import LLMTool

            async def lookup(**kwargs):
                return 'result'

            kwargs['funcs'] = [
                LLMTool(
                    name='e2e_lookup',
                    human_desc='Lookup',
                    description='Lookup',
                    parameters={'type': 'object', 'properties': {}},
                    func=lookup,
                )
            ]
        result = {'text': '', 'usage': None}
        if 'remove_think' in options:
            kwargs['remove_think'] = options['remove_think']
        try:
            if mode.endswith('message'):
                message = await api.invoke_llm(**kwargs)
                assert isinstance(message, message_type)
                result['text'] = message.content
            elif mode.endswith('usage'):
                response = await api.invoke_llm_with_usage(**kwargs)
                result.update(
                    text=response.message.content, usage=response.usage.model_dump() if response.usage else None
                )
            else:
                events = mode.endswith('events')
                method = api.invoke_llm_stream_events if events else api.invoke_llm_stream
                async with aclosing(method(**kwargs)) as stream:
                    async for item in stream:
                        chunk = item.chunk if events else item
                        if chunk:
                            result['text'] += chunk.content or ''
                        if events and item.usage:
                            result['usage'] = item.usage.model_dump()
                        if cancel and result['text']:
                            break
        except Exception as exc:
            result['error'] = type(exc).__name__ + ': ' + str(exc)
        yield RunnerResult.message_completed(ctx.run_id, Message(role='assistant', content=json.dumps(result)))
        yield RunnerResult.run_completed(ctx.run_id, finish_reason='stop')
