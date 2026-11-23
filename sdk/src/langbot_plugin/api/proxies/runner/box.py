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
        options = {}
        if rpc_action in {Action.READ_RUN_FILE, Action.COMMIT_RUN_FILES}:
            self._require_context_api("box")
        if rpc_action in {
            Action.EXPORT_BOX_FILES,
            Action.READ_RUN_FILE,
            Action.COMMIT_RUN_FILES,
        }:
            options["cancel_peer_on_cancel"] = True
        return await self._api.plugin_runtime_handler.call_action(
            rpc_action,
            {"run_id": self.run_id, **data},
            self._bounded_timeout(default=180.0),
            **options,
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

    async def read_run_file(
        self,
        file_id: str,
        *,
        mode: str = "auto",
        offset: int = 0,
        max_chars: int = 8192,
        page_start: int = 1,
        page_end: int | None = None,
    ) -> list[dict]:
        """Read bounded text or structured media from this run's exported file."""
        result = await self._box_call(
            Action.READ_RUN_FILE,
            file_id=file_id,
            mode=mode,
            offset=offset,
            max_chars=max_chars,
            page_start=page_start,
            page_end=page_end,
        )
        return self._expect_key(result, "contents", Action.READ_RUN_FILE)

    async def commit_run_files(self, file_ids: list[str]) -> list[BoxFile]:
        """Publish selected files under the producer's frozen Host policy."""
        result = await self._box_call(Action.COMMIT_RUN_FILES, file_ids=file_ids)
        return [
            BoxFile.model_validate(item)
            for item in self._expect_key(result, "items", Action.COMMIT_RUN_FILES)
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
