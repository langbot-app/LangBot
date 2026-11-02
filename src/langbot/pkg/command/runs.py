"""Run records for command processor executions.

Command processors reuse the Host run ledger so their logs share the processor
run list and trace views. Recording is best-effort: a ledger failure must never
change whether a command executes or replies.
"""

from __future__ import annotations

import typing
import uuid

from langbot_plugin.api.entities.builtin.command import context as command_context

from . import processor as command_processor

COMMAND_OUTPUT_EVENT = 'command.output'


def binding_id(processor_uuid: str) -> str:
    return f'command_processor:{processor_uuid}'


def command_return_payload(ret: command_context.CommandReturn) -> dict[str, typing.Any]:
    """Project one command return into a JSON trace payload without inline image bytes."""
    payload: dict[str, typing.Any] = {}
    if ret.error is not None:
        payload['error'] = str(ret.error)
    if ret.text is not None:
        payload['text'] = ret.text
    if ret.image_url is not None:
        payload['image_url'] = ret.image_url
    if ret.image_base64 is not None:
        payload['image'] = 'base64'
    if ret.file_url is not None:
        payload['file_url'] = ret.file_url
        payload['file_name'] = ret.file_name or ''
    return payload


class CommandRunRecorder:
    """Write one command execution into the run ledger."""

    def __init__(self, ap: typing.Any, workspace_uuid: str):
        self.ap = ap
        self.workspace_uuid = workspace_uuid
        self.run_id: str | None = None
        self._failed = False

    def _store(self):
        from ..agent.runner.run_ledger_store import RunLedgerStore

        return RunLedgerStore(self.ap.persistence_mgr.get_db_engine())

    async def _safely(self, operation: typing.Callable[[], typing.Awaitable[typing.Any]]) -> None:
        if self._failed:
            return
        try:
            await operation()
        except Exception as exc:
            self._failed = True
            logger = getattr(self.ap, 'logger', None)
            if logger is not None:
                logger.warning(f'Failed to record command processor run: {exc}')

    async def start(
        self,
        *,
        processor_uuid: str,
        plugin_id: str,
        command_name: str,
        full_command_text: str,
        bot_uuid: str | None,
        conversation_id: str | None,
        source: str,
        launcher: dict[str, typing.Any] | None = None,
    ) -> None:
        run_id = f'command:{uuid.uuid4()}'

        async def create():
            await self._store().create_run(
                run_id=run_id,
                event_id=None,
                binding_id=binding_id(processor_uuid),
                runner_id=command_processor.component_ref_for_plugin(plugin_id),
                conversation_id=conversation_id,
                workspace_id=self.workspace_uuid,
                bot_id=bot_uuid,
                metadata={
                    'event_type': 'message.received',
                    'processor_type': command_processor.COMMAND_PROCESSOR_KIND,
                    'processor_id': processor_uuid,
                    'command': command_name,
                    'source': source,
                    'input_event': {
                        'text': full_command_text,
                        'command': command_name,
                        **({'launcher': launcher} if launcher else {}),
                    },
                },
            )
            self.run_id = run_id

        await self._safely(create)

    async def output(self, ret: command_context.CommandReturn) -> None:
        if self.run_id is None:
            return
        run_id = self.run_id
        await self._safely(
            lambda: self._store().append_event(
                run_id=run_id,
                sequence=None,
                event_type=COMMAND_OUTPUT_EVENT,
                data=command_return_payload(ret),
                source='host',
            )
        )

    async def finish(self, *, error: str | None = None) -> None:
        if self.run_id is None:
            return
        run_id = self.run_id
        await self._safely(
            lambda: self._store().finalize_run(
                run_id=run_id,
                status='failed' if error else 'completed',
                status_reason=error,
            )
        )
