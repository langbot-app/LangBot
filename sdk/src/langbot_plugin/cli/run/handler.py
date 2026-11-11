from __future__ import annotations

import asyncio
import base64
import contextlib
import os
import mimetypes
import typing
import logging
from copy import deepcopy
from pathlib import Path

from langbot_plugin.utils.deadline import anext_with_deadline
from langbot_plugin.api.entities.builtin.pipeline.query import provider_session
from langbot_plugin.runtime.io import connection
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.plugin.container import PluginContainer, ComponentContainer
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.api.entities import events
from langbot_plugin.api.definition.components.base import NoneComponent
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.entities.io.actions.enums import CommonAction, PluginToRuntimeAction
from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.api.proxies.invocation import (
    bind_invocation,
    event_origin_scope,
    thaw_config,
)
from langbot_plugin.runtime.plugin.container import PluginInstallationSlot
from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.definition.components.command.command import Command
from langbot_plugin.api.definition.components.knowledge_engine.engine import (
    KnowledgeEngine,
)
from langbot_plugin.api.definition.components.page import (
    Page,
    PageRequest,
    PageResponse,
)
from langbot_plugin.api.definition.components.parser.parser import Parser
from langbot_plugin.utils import git_sync as git_sync_util
from langbot_plugin.utils import packaging as packaging_util
from langbot_plugin.api.entities.builtin.rag.context import RetrievalContext
from langbot_plugin.api.entities.builtin.rag.models import (
    IngestionContext,
    ParseContext,
)
from langbot_plugin.api.proxies.event_context import EventContextProxy
from langbot_plugin.api.proxies.execute_context import ExecuteContextProxy

logger = logging.getLogger(__name__)
MAX_RUNTIME_UI_FILE_BYTES = 4 * 1024 * 1024


async def _read_runtime_ui_file_limited(path: str | Path) -> bytes:
    file_path = Path(path)
    if file_path.stat().st_size > MAX_RUNTIME_UI_FILE_BYTES:
        raise ValueError(
            f"Plugin UI file exceeds the {MAX_RUNTIME_UI_FILE_BYTES}-byte limit"
        )
    with file_path.open("rb") as file:
        content = file.read(MAX_RUNTIME_UI_FILE_BYTES + 1)
    if len(content) > MAX_RUNTIME_UI_FILE_BYTES:
        raise ValueError(
            f"Plugin UI file exceeds the {MAX_RUNTIME_UI_FILE_BYTES}-byte limit"
        )
    return content


def _resolve_asset_path(file_key: str) -> Path | None:
    plugin_root = Path.cwd().resolve()
    requested = Path(file_key)

    if requested.is_absolute():
        return None

    if requested.parts and requested.parts[0] in {"assets", "components"}:
        candidates = [plugin_root / requested]
    else:
        candidates = [plugin_root / "assets" / requested]

    for candidate in candidates:
        resolved = candidate.resolve()
        if not resolved.is_file():
            continue
        try:
            relative = resolved.relative_to(plugin_root)
        except ValueError:
            continue
        if relative.parts[:1] == ("assets",) or relative.parts[:2] == (
            "components",
            "pages",
        ):
            return resolved

    return None


async def _iter_runner_results_with_deadline(
    runner_instance: typing.Any,
    run_context: typing.Any,
) -> typing.AsyncGenerator[typing.Any, None]:
    """Iterate runner results and cancel the runner when the run deadline expires."""
    from langbot_plugin.api.entities.builtin.runner.result import RunnerResult

    result_gen = runner_instance.invoke(run_context)
    sequence = 0
    try:
        while True:
            try:
                result = await anext_with_deadline(
                    result_gen,
                    lambda: run_context.runtime.deadline_at,
                )
            except StopAsyncIteration:
                break

            sequence += 1
            if hasattr(result, "model_copy"):
                result = result.model_copy(update={"sequence": sequence})
            yield result
    except asyncio.TimeoutError:
        sequence += 1
        yield RunnerResult.run_failed(
            run_id=run_context.run_id,
            error="Agent runner timed out",
            code="runner.timeout",
            retryable=True,
            sequence=sequence,
        )
    except Exception as e:
        sequence += 1
        yield RunnerResult.run_failed(
            run_id=run_context.run_id,
            error=f"Error running agent: {e}",
            code="runner.exception",
            sequence=sequence,
        )
    finally:
        try:
            await result_gen.aclose()
        except Exception as exc:
            logger.debug(
                "Failed to close Runner result generator: %s", exc, exc_info=True
            )


class PluginRuntimeHandler(Handler):
    """The handler for running plugins."""

    _base_plugin_container: PluginContainer

    shutdown_callback: (
        typing.Callable[[], typing.Coroutine[typing.Any, typing.Any, None]] | None
    ) = None
    """Callback to trigger shutdown and reconnect."""

    def __init__(
        self,
        connection: connection.Connection,
        plugin_initialize_callback: typing.Callable[
            [dict[str, typing.Any]], typing.Coroutine[typing.Any, typing.Any, None]
        ],
    ):
        super().__init__(connection)
        self.name = "FromRuntime"
        self._shutdown_task: asyncio.Task[None] | None = None
        self._slot_containers: dict[str, PluginInstallationSlot] = {}
        self._slot_generations: dict[str, int] = {}
        self._slot_initialize_callback: (
            typing.Callable[
                [InstallationBinding, dict[str, typing.Any]],
                typing.Coroutine[typing.Any, typing.Any, PluginInstallationSlot],
            ]
            | None
        ) = None
        self._slot_detach_callback: (
            typing.Callable[[str], typing.Coroutine[typing.Any, typing.Any, None]]
            | None
        ) = None
        self._slot_cancel_callback: typing.Callable[[str], None] | None = None

        @self.action(RuntimeToPluginAction.INITIALIZE_PLUGIN)
        async def initialize_plugin(data: dict[str, typing.Any]) -> ActionResponse:
            action_context = self.current_action_context
            if action_context is not None:
                self.bind_action_context(action_context)
            await plugin_initialize_callback(data["plugin_settings"])
            return ActionResponse.success({})

        @self.action(RuntimeToPluginAction.ATTACH_PLUGIN_SLOT)
        async def attach_plugin_slot(data: dict[str, typing.Any]) -> ActionResponse:
            binding = self.current_action_context
            if not isinstance(binding, InstallationBinding):
                raise ValueError("Shared slot attach requires InstallationBinding")
            if self._slot_initialize_callback is None:
                raise ValueError("Shared slot initialization is unavailable")
            slot_id = binding.installation_uuid
            generation = self._slot_generations.get(slot_id, 0) + 1
            self._slot_generations[slot_id] = generation

            fenced = False

            def cancel_slot_attach() -> None:
                nonlocal fenced
                if fenced:
                    return
                fenced = True
                if self._slot_generations.get(slot_id) == generation:
                    self._slot_generations[slot_id] = generation + 1
                if self._slot_cancel_callback is not None:
                    self._slot_cancel_callback(slot_id)

            self.set_current_action_cancel_callback(cancel_slot_attach)
            try:
                container = await self._slot_initialize_callback(
                    binding,
                    data["plugin_settings"],
                )
            except asyncio.CancelledError:
                cancel_slot_attach()
                raise
            if self._slot_generations.get(slot_id) != generation:
                raise RuntimeError("Shared plugin slot attach was superseded")
            self._slot_containers[binding.installation_uuid] = container
            return ActionResponse.success({})

        @self.action(RuntimeToPluginAction.DETACH_PLUGIN_SLOT)
        async def detach_plugin_slot(data: dict[str, typing.Any]) -> ActionResponse:
            del data
            binding = self.current_action_context
            if not isinstance(binding, InstallationBinding):
                raise ValueError("Shared slot detach requires InstallationBinding")
            slot_id = binding.installation_uuid
            slot = self._slot_containers.get(slot_id)
            if slot is not None and slot.binding != binding:
                raise ValueError("Shared slot detach binding is stale")
            self._slot_generations[slot_id] = self._slot_generations.get(slot_id, 0) + 1
            if self._slot_detach_callback is not None:
                await self._slot_detach_callback(binding.installation_uuid)
            self._slot_containers.pop(binding.installation_uuid, None)
            return ActionResponse.success({})

        @self.action(RuntimeToPluginAction.GET_PLUGIN_SLOT_CONTAINER)
        async def get_plugin_slot_container(
            data: dict[str, typing.Any],
        ) -> ActionResponse:
            del data
            binding = self.current_action_context
            if not isinstance(binding, InstallationBinding):
                raise ValueError("Shared slot lookup requires InstallationBinding")
            container = self._slot_containers.get(binding.installation_uuid)
            if container is None:
                raise ValueError("Shared plugin slot is not attached")
            return ActionResponse.success(
                {
                    "enabled": container.enabled,
                    "priority": container.priority,
                    "plugin_config": thaw_config(container.plugin_config),
                    "plugin_container": container.plugin_container.model_dump(),
                }
            )

        @self.action(CommonAction.PING)
        async def ping(data: dict[str, typing.Any]) -> ActionResponse:
            return ActionResponse.success({"alive": True})

        @self.action(RuntimeToPluginAction.GET_PLUGIN_CONTAINER)
        async def get_plugin_container(data: dict[str, typing.Any]) -> ActionResponse:
            return ActionResponse.success(self.plugin_container.model_dump())

        @self.action(RuntimeToPluginAction.GET_PLUGIN_ICON)
        async def get_plugin_icon(data: dict[str, typing.Any]) -> ActionResponse:
            icon_path = self.plugin_container.manifest.icon_rel_path
            if icon_path is None:
                return ActionResponse.success(
                    {"plugin_icon_file_key": "", "mime_type": ""}
                )
            icon_bytes = await _read_runtime_ui_file_limited(icon_path)

            mime_type = mimetypes.guess_type(icon_path)[0]

            plugin_icon_file_key = await self.send_file(icon_bytes, "")

            return ActionResponse.success(
                {"plugin_icon_file_key": plugin_icon_file_key, "mime_type": mime_type}
            )

        @self.action(RuntimeToPluginAction.GET_PLUGIN_README)
        async def get_plugin_readme(data: dict[str, typing.Any]) -> ActionResponse:
            language = data["language"]
            readme_path = (
                os.path.join("readme", f"README_{language}.md")
                if language != "en"
                else "README.md"
            )
            if not os.path.exists(readme_path):
                readme_path = "README.md"

            readme_bytes = await _read_runtime_ui_file_limited(readme_path)
            readme_file_key = await self.send_file(readme_bytes, "md")
            return ActionResponse.success(
                {
                    "plugin_readme_file_key": readme_file_key,
                    "mime_type": "text/markdown",
                }
            )

        @self.action(RuntimeToPluginAction.GET_PLUGIN_ASSETS_FILE)
        async def get_plugin_assets_file(data: dict[str, typing.Any]) -> ActionResponse:
            file_key = data["file_key"]
            file_path = _resolve_asset_path(file_key)
            if file_path is None:
                return ActionResponse.success(
                    {"file_file_key": None, "mime_type": None}
                )

            file_bytes = await _read_runtime_ui_file_limited(file_path)

            mime_type = (
                mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            )
            file_file_key = await self.send_file(file_bytes, "")
            return ActionResponse.success(
                {"file_file_key": file_file_key, "mime_type": mime_type}
            )

        @self.action(RuntimeToPluginAction.PAGE_API)
        async def page_api(data: dict[str, typing.Any]) -> ActionResponse:
            """Handle a page API call from the frontend."""
            page_id = data.get("page_id", "")
            if not page_id:
                return ActionResponse.success(
                    PageResponse.fail("page_id is required").model_dump()
                )

            for component in self.plugin_container.components:
                if component.manifest.kind != Page.__kind__:
                    continue
                if component.manifest.metadata.name != page_id:
                    continue
                if isinstance(component.component_instance, NoneComponent):
                    return ActionResponse.success(
                        PageResponse.fail(
                            "Page component is not initialized"
                        ).model_dump()
                    )
                if not isinstance(component.component_instance, Page):
                    return ActionResponse.success(
                        PageResponse.fail("Page component type mismatch").model_dump()
                    )
                request = PageRequest(
                    endpoint=data.get("endpoint", ""),
                    method=data.get("method", "POST"),
                    body=data.get("body"),
                )
                response = await component.component_instance.handle_api(request)
                if not isinstance(response, PageResponse):
                    response = PageResponse(data=response)
                return ActionResponse.success(response.model_dump())

            return ActionResponse.success(
                PageResponse.fail(f"Page '{page_id}' not found").model_dump()
            )

        @self.action(RuntimeToPluginAction.EMIT_EVENT)
        async def emit_event(data: dict[str, typing.Any]) -> ActionResponse:
            """Emit an event to the plugin.

            {
                "event_context": dict[str, typing.Any],
            }
            """

            event_name = data["event_context"]["event_name"]

            if getattr(events, event_name) is None:
                return ActionResponse.error(f"Event {event_name} not found")

            args = deepcopy(data["event_context"])

            args["plugin_runtime_handler"] = self

            event_context = EventContextProxy.model_validate(args)

            emitted: bool = False

            # Plugin calls made while handling this event are attributed to it,
            # but only for Hosts that declared they accept the extra field.
            with event_origin_scope(
                event_context.query_uuid if event_context.origin_attribution else None
            ):
                # check if the event is registered
                for component in self.plugin_container.components:
                    if component.manifest.kind == EventListener.__kind__:
                        if component.component_instance is None:
                            return ActionResponse.error(
                                "Event listener is not initialized"
                            )

                        assert isinstance(component.component_instance, EventListener)

                        if (
                            event_context.event.__class__
                            not in component.component_instance.registered_handlers
                        ):
                            continue

                        for handler in component.component_instance.registered_handlers[
                            event_context.event.__class__
                        ]:
                            await handler(event_context)
                            emitted = True

                        break

            return ActionResponse.success(
                data={
                    "emitted": emitted,
                    "event_context": event_context.model_dump(),
                }
            )

        @self.action(RuntimeToPluginAction.PLUGIN_DIAGNOSTIC)
        async def plugin_diagnostic(data: dict[str, typing.Any]) -> ActionResponse:
            _log_plugin_diagnostic(data)
            return ActionResponse.success({})

        @self.action(RuntimeToPluginAction.CALL_TOOL)
        async def call_tool(data: dict[str, typing.Any]) -> ActionResponse:
            """Call a tool."""
            tool_name = data["tool_name"]
            tool_parameters = data["tool_parameters"]
            session = data["session"]
            query_id = data["query_id"]
            query_uuid = data.get("query_uuid")

            for component in self.plugin_container.components:
                if component.manifest.kind == Tool.__kind__:
                    if component.manifest.metadata.name != tool_name:
                        continue

                    if isinstance(component.component_instance, NoneComponent):
                        return ActionResponse.error("Tool is not initialized")

                    assert isinstance(component.component_instance, Tool)

                    tool_instance = component.component_instance

                    # Pass only the context parameters supported by the plugin.
                    import inspect

                    call_sig = inspect.signature(tool_instance.call)
                    params = call_sig.parameters

                    if "session" in params and "query_id" in params:
                        session = provider_session.Session.model_validate(session)
                        call_kwargs = {"session": session, "query_id": query_id}
                        if "query_uuid" in params:
                            call_kwargs["query_uuid"] = query_uuid
                        resp = await tool_instance.call(tool_parameters, **call_kwargs)
                    else:
                        resp = await tool_instance.call(tool_parameters)

                    return ActionResponse.success(
                        data={
                            "tool_response": resp,
                        }
                    )

            return ActionResponse.error(f"Tool {tool_name} not found")

        @self.action(RuntimeToPluginAction.EXECUTE_COMMAND)
        async def execute_command(
            data: dict[str, typing.Any],
        ) -> typing.AsyncGenerator[ActionResponse, None]:
            """Execute a command."""

            args = deepcopy(data["command_context"])
            args["plugin_runtime_handler"] = self
            command_context = ExecuteContextProxy.model_validate(args)

            for component in self.plugin_container.components:
                if component.manifest.kind == Command.__kind__:
                    if component.manifest.metadata.name != command_context.command:
                        continue

                    if isinstance(component.component_instance, NoneComponent):
                        yield ActionResponse.error("Command is not initialized")

                    command_instance = component.component_instance
                    assert isinstance(command_instance, Command)
                    async for return_value in command_instance._execute(
                        command_context
                    ):
                        yield ActionResponse.success(
                            data={
                                "command_response": return_value.model_dump(mode="json")
                            }
                        )
                    break
            else:
                yield ActionResponse.error(
                    f"Command {command_context.command} not found"
                )

        @self.action(RuntimeToPluginAction.RUN_RUNNER)
        async def run_runner(
            data: dict[str, typing.Any],
        ) -> typing.AsyncGenerator[ActionResponse, None]:
            """Run a Runner component."""
            from langbot_plugin.api.definition.components.runner.runner import (
                Runner,
            )
            from langbot_plugin.api.entities.builtin.runner.context import (
                RunnerContext,
            )
            from langbot_plugin.api.entities.builtin.runner.result import (
                RunnerResult,
            )

            runner_name = data["runner_name"]
            context_data = data["context"]
            run_id = (
                context_data.get("run_id", "unknown")
                if isinstance(context_data, dict)
                else "unknown"
            )

            # Validate context
            try:
                run_context = RunnerContext.model_validate(context_data)
            except Exception as e:
                yield ActionResponse.success(
                    RunnerResult.run_failed(
                        run_id=run_id,
                        error=f"Context validation failed: {e}",
                        code="runner.context_invalid",
                        sequence=1,
                    ).model_dump(mode="json")
                )
                return

            # Find the Runner component
            component_kind = run_context.runtime.metadata.get(
                "component_kind", "Runner"
            )
            if component_kind not in {"Runner"}:
                raise ValueError("Unsupported processor component kind")
            runner_component = None
            for component in self.plugin_container.components:
                if component.manifest.kind == component_kind:
                    if component.manifest.metadata.name == runner_name:
                        runner_component = component
                        break

            if runner_component is None:
                yield ActionResponse.success(
                    RunnerResult.run_failed(
                        run_id=run_context.run_id,
                        error=f"Runner {runner_name} not found",
                        code="runner.not_found",
                        sequence=1,
                    ).model_dump(mode="json")
                )
                return

            # Check if initialized
            if isinstance(runner_component.component_instance, NoneComponent):
                yield ActionResponse.success(
                    RunnerResult.run_failed(
                        run_id=run_context.run_id,
                        error=f"Runner {runner_name} not initialized",
                        code="runner.not_initialized",
                        sequence=1,
                    ).model_dump(mode="json")
                )
                return

            runner_instance = runner_component.component_instance
            assert isinstance(runner_instance, Runner)

            # Run the agent and stream results
            last_sequence = 0
            try:
                async for result in _iter_runner_results_with_deadline(
                    runner_instance,
                    run_context,
                ):
                    result_sequence = getattr(result, "sequence", None)
                    if isinstance(result_sequence, int) and result_sequence > 0:
                        last_sequence = result_sequence
                    else:
                        last_sequence += 1
                    yield ActionResponse.success(result.model_dump(mode="json"))
            except Exception as e:
                logger.exception("Runner %s failed", runner_name)
                yield ActionResponse.success(
                    RunnerResult.run_failed(
                        run_id=run_context.run_id,
                        error=f"Error running agent: {e}",
                        code="runner.exception",
                        sequence=last_sequence + 1,
                    ).model_dump(mode="json")
                )

        @self.action(RuntimeToPluginAction.RETRIEVE_KNOWLEDGE)
        async def retrieve_knowledge(data: dict[str, typing.Any]) -> ActionResponse:
            """Retrieve knowledge using a KnowledgeEngine instance."""
            retriever_name = data["retriever_name"]
            retrieval_context = RetrievalContext.model_validate(
                data["retrieval_context"]
            )

            rag_component = None
            for component in self.plugin_container.components:
                if component.manifest.kind == KnowledgeEngine.__kind__:
                    # If retriever_name is empty, use the first found KnowledgeEngine.
                    # Otherwise, find the specific named component.
                    if (
                        not retriever_name
                        or component.manifest.metadata.name == retriever_name
                    ):
                        rag_component = component
                        break

            if rag_component is None:
                return ActionResponse.error(
                    f"KnowledgeEngine {retriever_name} not found"
                )

            if isinstance(rag_component.component_instance, NoneComponent):
                return ActionResponse.error(
                    f"KnowledgeEngine {retriever_name} is not initialized"
                )

            assert isinstance(rag_component.component_instance, KnowledgeEngine)

            # Call retrieve method - KnowledgeEngine returns RetrievalResponse
            response = await rag_component.component_instance.retrieve(
                retrieval_context
            )

            return ActionResponse.success(response.model_dump(mode="json"))

        @self.action(RuntimeToPluginAction.SHUTDOWN)
        async def shutdown(data: dict[str, typing.Any]) -> ActionResponse:
            """Handle shutdown request from runtime.

            In debug mode (when shutdown_callback is set), this will trigger reconnection.
            In production mode, this will just acknowledge the shutdown.
            """
            if self.shutdown_callback is not None:
                if self._shutdown_task is None or self._shutdown_task.done():
                    self._shutdown_task = asyncio.create_task(self.shutdown_callback())

                    def shutdown_done(task: asyncio.Task[None]) -> None:
                        if task.cancelled():
                            return
                        exc = task.exception()
                        if exc is not None:
                            logger.error(
                                "Plugin debug shutdown callback failed",
                                exc_info=exc,
                            )

                    self._shutdown_task.add_done_callback(shutdown_done)

            return ActionResponse.success({})

        # ================= Knowledge Engine Actions =================

        def _find_knowledge_engine_component() -> ComponentContainer | None:
            """Find the KnowledgeEngine component in the plugin."""
            for component in self.plugin_container.components:
                if component.manifest.kind == KnowledgeEngine.__kind__:
                    return component
            return None

        def _get_knowledge_engine_or_error() -> tuple[
            KnowledgeEngine | None, ActionResponse | None
        ]:
            """Get KnowledgeEngine singleton instance or error response.

            Returns:
                (knowledge_engine, None) if successful
                (None, error_response) if failed
            """
            rag_component = _find_knowledge_engine_component()
            if rag_component is None:
                return None, ActionResponse.error(
                    "KnowledgeEngine component not found in this plugin"
                )

            if isinstance(rag_component.component_instance, NoneComponent):
                return None, ActionResponse.error(
                    "KnowledgeEngine component is not initialized"
                )
            assert isinstance(rag_component.component_instance, KnowledgeEngine)
            return rag_component.component_instance, None

        @self.action(RuntimeToPluginAction.INGEST_DOCUMENT)
        async def ingest_document(data: dict[str, typing.Any]) -> ActionResponse:
            """Ingest a document using the KnowledgeEngine component."""
            context_data = data["context"]

            ingestion_context = IngestionContext.model_validate(context_data)
            knowledge_engine, error = _get_knowledge_engine_or_error()
            if error:
                return error

            result = await knowledge_engine.ingest(ingestion_context)

            return ActionResponse.success(result.model_dump(mode="json"))

        @self.action(RuntimeToPluginAction.DELETE_DOCUMENT)
        async def delete_document(data: dict[str, typing.Any]) -> ActionResponse:
            """Delete a document using the KnowledgeEngine component."""
            kb_id = data["kb_id"]
            document_id = data["document_id"]

            knowledge_engine, error = _get_knowledge_engine_or_error()
            if error:
                return error

            success = await knowledge_engine.delete_document(kb_id, document_id)

            return ActionResponse.success({"success": success})

        @self.action(RuntimeToPluginAction.ON_KB_CREATE)
        async def on_kb_create(data: dict[str, typing.Any]) -> ActionResponse:
            """Notify KnowledgeEngine about KB creation."""
            kb_id = data["kb_id"]
            config = data.get("config", {})

            knowledge_engine, error = _get_knowledge_engine_or_error()
            if error:
                return error

            await knowledge_engine.on_knowledge_base_create(kb_id, config)

            return ActionResponse.success({"success": True})

        @self.action(RuntimeToPluginAction.ON_KB_DELETE)
        async def on_kb_delete(data: dict[str, typing.Any]) -> ActionResponse:
            """Notify KnowledgeEngine about KB deletion."""
            kb_id = data["kb_id"]

            knowledge_engine, error = _get_knowledge_engine_or_error()
            if error:
                return error

            await knowledge_engine.on_knowledge_base_delete(kb_id)

            return ActionResponse.success({"success": True})

        @self.action(RuntimeToPluginAction.GET_RAG_CAPABILITIES)
        async def get_rag_capabilities(data: dict[str, typing.Any]) -> ActionResponse:
            """Get RAG capabilities from the KnowledgeEngine component."""
            rag_component = _find_knowledge_engine_component()
            if rag_component is None:
                return ActionResponse.error(
                    "KnowledgeEngine component not found in this plugin"
                )

            # Get capabilities from the class method (doesn't need instance)
            component_class = rag_component.manifest.get_python_component_class()
            if issubclass(component_class, KnowledgeEngine):
                capabilities = component_class.get_capabilities()
            else:
                capabilities = []

            return ActionResponse.success({"capabilities": capabilities})

        # ========== Parser Handlers ==========

        def _find_parser_component() -> ComponentContainer | None:
            """Find Parser component in plugin."""
            for component in self.plugin_container.components:
                if component.manifest.kind == Parser.__kind__:
                    return component
            return None

        def _get_parser_or_error() -> tuple[Parser | None, ActionResponse | None]:
            """Get Parser instance or error response."""
            parser_component = _find_parser_component()
            if parser_component is None:
                return None, ActionResponse.error(
                    "Parser component not found in this plugin"
                )
            if isinstance(parser_component.component_instance, NoneComponent):
                return None, ActionResponse.error("Parser component is not initialized")
            assert isinstance(parser_component.component_instance, Parser)
            return parser_component.component_instance, None

        @self.action(RuntimeToPluginAction.PARSE_DOCUMENT)
        async def parse_document(data: dict[str, typing.Any]) -> ActionResponse:
            """Parse a document using the Parser component."""
            context_data = data["context"]

            # Read file from local temp storage (transferred via FILE_CHUNK)
            file_key = context_data.get("file_key", "")
            if file_key:
                file_bytes = await self.read_local_file(file_key)
                await self.delete_local_file(file_key)
            else:
                file_bytes = b""

            parse_context = ParseContext(
                file_content=file_bytes,
                mime_type=context_data.get("mime_type", "application/octet-stream"),
                filename=context_data.get("filename", ""),
                metadata=context_data.get("metadata", {}),
            )

            parser_instance, error = _get_parser_or_error()
            if error:
                return error

            result = await parser_instance.parse(parse_context)

            return ActionResponse.success(result.model_dump(mode="json"))

        # ========== Plugin source packaging / GitHub sync (upload flow) ==========
        #
        # These handlers run inside the plugin worker process, whose working
        # directory *is* the plugin source tree. That makes this process the only
        # component that can package the developer's live source and run git on
        # it. The Runtime relays the request and LangBot orchestrates the upload.

        def _manifest_overrides(data: dict[str, typing.Any]) -> dict[str, typing.Any]:
            overrides = data.get("manifest_overrides")
            return overrides if isinstance(overrides, dict) else {}

        def _icon_extra_files(
            overrides: dict[str, typing.Any],
        ) -> tuple[dict[str, bytes], dict[str, typing.Any]]:
            """Extract an uploaded base64 icon into an archive-file mapping.

            Returns ``(extra_files, sanitized_overrides)``; ``icon_base64`` is
            removed from the overrides so the manifest only carries the icon
            path.
            """

            icon_base64 = overrides.get("icon_base64")
            clean = {
                key: value for key, value in overrides.items() if key != "icon_base64"
            }
            if not isinstance(icon_base64, str) or not icon_base64.strip():
                return {}, clean

            raw = icon_base64.strip()
            if "," in raw and raw.split(",", 1)[0].startswith("data:"):
                raw = raw.split(",", 1)[1]
            try:
                icon_bytes = base64.b64decode(raw, validate=True)
            except Exception:
                raise ValueError("Invalid plugin icon data")

            # Bound the icon weight. 10MB raw is ~13.3MB base64, which stays
            # under the 16MB single-message cap (and is mirrored by the page).
            if len(icon_bytes) > 10 * 1024 * 1024:
                raise ValueError("Plugin icon exceeds the 10MB limit")

            content_type = ""
            if isinstance(icon_base64, str) and icon_base64.startswith("data:"):
                content_type = icon_base64[5:].split(";", 1)[0]
            ext = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/gif": ".gif",
                "image/webp": ".webp",
                "image/svg+xml": ".svg",
            }.get(content_type.lower(), ".png")

            icon_path = f"assets/icon{ext}"
            clean["icon"] = icon_path
            return {icon_path: icon_bytes}, clean

        @self.action(RuntimeToPluginAction.BUILD_PLUGIN_PACKAGE)
        async def build_plugin_package(data: dict[str, typing.Any]) -> ActionResponse:
            """Build a ``.lbpkg`` from the plugin working directory.

            Publisher edits made on the upload page (label/description/version/
            repository/icon) are written back into the plugin's own
            ``manifest.yaml`` and assets first, so the on-disk configuration
            matches what is packaged and published instead of only differing
            inside the archive.
            """

            plugin_root = os.getcwd()
            try:
                extra_files, overrides = _icon_extra_files(_manifest_overrides(data))
                await asyncio.to_thread(
                    packaging_util.write_manifest_overrides,
                    plugin_root,
                    overrides,
                )
                await asyncio.to_thread(
                    packaging_util.write_extra_files,
                    plugin_root,
                    extra_files,
                )
                package_bytes, filename = await asyncio.to_thread(
                    packaging_util.build_plugin_package,
                    plugin_root,
                    manifest_overrides=overrides,
                    extra_files=extra_files,
                )
                manifest = await asyncio.to_thread(
                    packaging_util.read_plugin_manifest_metadata,
                    plugin_root,
                )
            except ValueError as e:
                return ActionResponse.error(str(e))
            except FileNotFoundError:
                return ActionResponse.error(
                    "Plugin manifest not found in the working directory"
                )
            except Exception as e:  # noqa: BLE001 - surface a readable reason
                return ActionResponse.error(f"Failed to build plugin package: {e}")

            package_file_key = await self.send_file(package_bytes, "lbpkg")
            metadata = manifest.get("metadata") or {}
            return ActionResponse.success(
                {
                    "package_file_key": package_file_key,
                    "filename": filename,
                    "size": len(package_bytes),
                    "metadata": metadata,
                    "manifest": manifest,
                }
            )

        @self.action(RuntimeToPluginAction.GIT_SYNC_PLUGIN)
        async def git_sync_plugin(data: dict[str, typing.Any]) -> ActionResponse:
            """Commit and push the plugin working directory to GitHub."""

            plugin_root = os.getcwd()
            try:
                extra_files, overrides = _icon_extra_files(_manifest_overrides(data))
                # Persist edits (and any uploaded icon) so the synchronised
                # repository records the same assets that are published.
                await asyncio.to_thread(
                    packaging_util.write_manifest_overrides,
                    plugin_root,
                    overrides,
                )
                await asyncio.to_thread(
                    packaging_util.write_extra_files,
                    plugin_root,
                    extra_files,
                )
                result = await asyncio.to_thread(
                    git_sync_util.sync_plugin_to_github,
                    plugin_root,
                    repo_url=str(data.get("repo_url") or ""),
                    token=str(data.get("token") or ""),
                    branch=str(data.get("branch") or ""),
                    commit_message=str(data.get("commit_message") or ""),
                )
            except git_sync_util.GitSyncError as e:
                return ActionResponse.error(str(e))
            except ValueError as e:
                return ActionResponse.error(str(e))
            except Exception as e:  # noqa: BLE001 - surface a readable reason
                return ActionResponse.error(f"Git sync failed: {e}")

            return ActionResponse.success(result.to_dict())

    def _uses_reserved_admission(self, req_data):
        return req_data.get(
            "action"
        ) == CommonAction.PING.value or super()._uses_reserved_admission(req_data)

    @property
    def plugin_container(self) -> PluginContainer:
        return self._base_plugin_container

    @plugin_container.setter
    def plugin_container(self, value: PluginContainer) -> None:
        self._base_plugin_container = value

    @contextlib.contextmanager
    def action_invocation_scope(self, action, action_context):
        if action == CommonAction.PING.value:
            yield
            return
        if not isinstance(action_context, InstallationBinding):
            yield
            return
        if action == RuntimeToPluginAction.DETACH_PLUGIN_SLOT.value:
            yield
            return
        if action == RuntimeToPluginAction.ATTACH_PLUGIN_SLOT.value:
            # Attach may execute process-scoped plugin/component initialize hooks.
            # Give those hooks a revocable capability for the attach lifetime so
            # detached tasks cannot retain the installation binding afterwards.
            with bind_invocation(self, config={}, binding=action_context):
                yield
            return
        # The first dedicated INITIALIZE_PLUGIN arrives before the handler has
        # bound the trusted installation from Runtime. Bind it here, before
        # entering the invocation scope, so initialize() can use Host APIs.
        # Shared workers initialize through ATTACH_PLUGIN_SLOT instead.
        if (
            action == RuntimeToPluginAction.INITIALIZE_PLUGIN.value
            and self.bound_action_context is None
        ):
            self.bind_action_context(action_context)
        # Dedicated workers have no shared slot. All subsequent calls must
        # match the exact installation binding; other bindings need a slot.
        if self.bound_action_context == action_context:
            with bind_invocation(
                self,
                config=self.plugin_container.plugin_config,
                binding=action_context,
            ):
                yield
            return
        slot = self._slot_containers.get(action_context.installation_uuid)
        if slot is None or slot.binding != action_context:
            raise ValueError("Shared plugin slot is not attached")
        with bind_invocation(
            self,
            config=slot.plugin_config,
            binding=slot.binding,
        ):
            yield

    async def register_plugin(
        self,
        prod_mode: bool = False,
        registration_capability: str = "",
    ) -> dict[str, typing.Any]:
        # The shared key is only a development credential. Installed plugin
        # processes authenticate with a launch-scoped, one-use capability.
        plugin_debug_key = "" if prod_mode else os.environ.get("PLUGIN_DEBUG_KEY", "")

        resp = await self.call_action(
            PluginToRuntimeAction.REGISTER_PLUGIN,
            {
                "plugin_container": self.plugin_container.model_dump(),
                "prod_mode": prod_mode,
                "plugin_debug_key": plugin_debug_key,
                "registration_capability": (
                    registration_capability if prod_mode else ""
                ),
            },
        )
        return resp

    async def get_plugin_container(self) -> dict[str, typing.Any]:
        """Get the current plugin container data."""
        return self.plugin_container.model_dump()


def _log_plugin_diagnostic(data: dict[str, typing.Any]) -> None:
    level_name = str(data.get("level", "ERROR")).upper()
    level = logging.getLevelName(level_name)
    if not isinstance(level, int):
        level = logging.ERROR

    code = data.get("code") or "plugin_diagnostic"
    message = data.get("message") or "Plugin diagnostic"
    details = data.get("details")
    if not isinstance(details, dict):
        details = {}

    parts = [f"[{code}] {message}"]
    event_name = details.get("event_name")
    stage = details.get("stage")
    delivery_error = details.get("delivery_error")
    query_id = details.get("query_id")
    if query_id is not None:
        parts.append(f"query_id={query_id}")
    if event_name:
        parts.append(f"event={event_name}")
    if stage:
        parts.append(f"stage={stage}")
    if delivery_error:
        parts.append(f"delivery_error={delivery_error}")

    logger.log(level, " | ".join(parts))


# {"action": "get_plugin_container", "data": {}, "seq_id": 1}
