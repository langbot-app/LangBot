"""Box APIs bound to the current authorized invocation."""

from langbot_plugin.api.entities.builtin.runner.box import (
    BoxStatus,
    BoxSession,
    BoxBinding,
    BoxFile,
)
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action


class RunnerBoxAPIMixin:
    async def _box_call(self, rpc_action, **data):
        return await self._api.plugin_runtime_handler.call_action(
            rpc_action,
            {"run_id": self.run_id, **data},
            self._bounded_timeout(default=180.0),
        )

    async def get_box_status(self) -> BoxStatus:
        return BoxStatus.model_validate(await self._box_call(Action.GET_BOX_STATUS))

    async def list_boxes(self) -> list[BoxSession]:
        result = await self._box_call(Action.LIST_BOXES)
        return [BoxSession.model_validate(item) for item in result["items"]]

    async def acquire_box(
        self, reuse_key: str, options: dict | None = None
    ) -> BoxSession:
        return BoxSession.model_validate(
            await self._box_call(
                Action.ACQUIRE_BOX, reuse_key=reuse_key, options=options or {}
            )
        )

    async def bind_box(self, box_id: str) -> BoxBinding:
        return BoxBinding.model_validate(
            await self._box_call(Action.BIND_BOX, box_id=box_id)
        )

    async def import_box_attachments(
        self, attachment_ids: list[str] | None = None
    ) -> list[BoxFile]:
        result = await self._box_call(
            Action.IMPORT_BOX_ATTACHMENTS, attachment_ids=attachment_ids
        )
        return [BoxFile.model_validate(item) for item in result["items"]]

    async def export_box_files(self, paths: list[str]) -> list[BoxFile]:
        """Export selected absolute sandbox paths; does not send any message."""
        result = await self._box_call(Action.EXPORT_BOX_FILES, paths=paths)
        return [
            BoxFile.model_validate({**item, "warning": result.get("warning")})
            for item in result["items"]
        ]

    async def reply_files(self, file_ids: list[str]):
        """Explicitly reply with files exported by this invocation."""
        result = await self._box_call(
            Action.CALL_PLATFORM_API,
            action="send_message",
            context_tool="event_reply",
            params={"message": []},
            file_ids=file_ids,
        )
        return result["result"]
