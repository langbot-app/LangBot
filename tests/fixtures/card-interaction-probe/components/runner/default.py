"""Exercise card presentation and callback routing from typed event handlers."""

from langbot_plugin.api.definition.components.runner import Runner, RunnerContext
from langbot_plugin.api.entities.builtin.platform.events import MessageReceivedEvent, PlatformSpecificEvent
from langbot_plugin.api.entities.builtin.platform.message import Plain


class CardInteractionProbe(Runner):
    async def initialize(self) -> None:
        await super().initialize()

        @self.handler(MessageReceivedEvent)
        async def on_message(ctx: RunnerContext) -> None:
            text = ''.join(part.text for part in ctx.platform_event.message_chain if isinstance(part, Plain)).strip()
            if text != '/card-probe':
                return

            result = await ctx.call_tool(
                'present_interactive_card',
                {
                    'kind': 'choice',
                    'title': 'Card interaction probe',
                    'description': 'Choose one option to verify the callback.',
                    'actions': [
                        {'id': 'approve', 'label': 'Approve', 'style': 'primary'},
                        {'id': 'reject', 'label': 'Reject', 'style': 'danger'},
                    ],
                },
            )
            if result.get('ok') is not True:
                raise RuntimeError(f'Card delivery failed: {result}')

        @self.handler(PlatformSpecificEvent)
        async def on_submission(ctx: RunnerContext) -> None:
            if ctx.platform_event.action != 'interaction.submitted':
                return
            submission = ctx.input.interaction
            if submission is None:
                raise ValueError('Interaction callback has no validated submission')
            await ctx.reply(f'Card result: {submission.action_id or submission.values}')
