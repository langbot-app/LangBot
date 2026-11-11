from __future__ import annotations

import asyncio
import os
import typing
import logging


from langbot_plugin.api.definition.components.manifest import ComponentManifest
from langbot_plugin.runtime.plugin.container import (
    ComponentContainer,
    PluginContainer,
    PluginInstallationSlot,
    RuntimeContainerStatus,
)
from langbot_plugin.api.proxies.invocation import freeze_config
from langbot_plugin.cli.run.handler import PluginRuntimeHandler
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.runtime.io.controllers.stdio import (
    server as stdio_controller_server,
)
from langbot_plugin.runtime.io.controllers.ws import (
    client as ws_controller_client,
)
from langbot_plugin.runtime.io.controller import Controller
from langbot_plugin.api.definition.plugin import NonePlugin, BasePlugin
from langbot_plugin.api.definition.components.base import NoneComponent, BaseComponent
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.definition.components.command.command import Command
from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.definition.components.knowledge_engine.engine import (
    KnowledgeEngine,
)
from langbot_plugin.api.definition.components.page import Page
from langbot_plugin.api.definition.components.parser.parser import Parser
from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.entities.io.errors import ConnectionClosedError
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.cli.run.hotreload import HotReloader, reload_plugin_modules
from langbot_plugin.runtime.security import (
    PLUGIN_DEBUG_KEY_ENV,
    PLUGIN_DEBUG_KEY_HEADER,
    PLUGIN_REGISTRATION_CAPABILITY_ENV,
    PLUGIN_REGISTRATION_CAPABILITY_HEADER,
    validate_runtime_secret,
)

logger = logging.getLogger(__name__)


async def notify_installation_revoked(
    plugin_container: PluginContainer,
    binding: InstallationBinding,
) -> None:
    """Let a plugin release process-local state held for one installation.

    One object graph is shared by every installation of an artifact digest and is
    never destroyed per installation, so a revoked installation's in-process state
    is only released here. Dedicated workers are shut down instead of detached, so
    this runs for shared placement.

    There is no active invocation, so per-invocation APIs (Host storage, config
    and binding lookups) are unavailable; the hook may only touch process-local
    state. Failures are logged and never block revocation.
    """

    if plugin_container.status is not RuntimeContainerStatus.INITIALIZED:
        return
    hook = getattr(plugin_container.plugin_instance, "on_installation_revoked", None)
    if hook is None:
        return
    try:
        await hook(binding)
    except Exception as exc:
        logger.warning(
            "Plugin on_installation_revoked failed for installation %s: %s",
            binding.installation_uuid,
            exc,
        )


class _SlotHandlerProxy:
    """Bind every worker-to-Runtime call to one exact installation slot."""

    def __init__(self, handler: PluginRuntimeHandler, binding: InstallationBinding):
        self._handler = handler
        self._binding = binding

    async def call_action(self, action, data, timeout=15.0, **kwargs):
        kwargs["action_context"] = self._binding
        return await self._handler.call_action(action, data, timeout=timeout, **kwargs)

    def call_action_generator(self, action, data, timeout=15.0, **kwargs):
        kwargs["action_context"] = self._binding
        return self._handler.call_action_generator(
            action, data, timeout=timeout, **kwargs
        )

    async def send_file(self, file_bytes, file_extension, **kwargs):
        kwargs["action_context"] = self._binding
        return await self._handler.send_file(file_bytes, file_extension, **kwargs)

    async def read_local_file(self, file_key, **kwargs):
        kwargs["action_context"] = self._binding
        return await self._handler.read_local_file(file_key, **kwargs)

    async def delete_local_file(self, file_key, **kwargs):
        kwargs["action_context"] = self._binding
        return await self._handler.delete_local_file(file_key, **kwargs)

    def __getattr__(self, name):
        return getattr(self._handler, name)


def _apply_runner_class_defaults(
    component_manifest: ComponentManifest,
    component_impl_cls: type[Runner],
) -> None:
    """Fill empty Runner manifest declarations from class overrides."""
    spec = component_manifest.spec
    if not isinstance(spec, dict):
        return

    config_schema = component_impl_cls.get_config_schema()
    if not spec.get("config") and config_schema != Runner.get_config_schema():
        spec["config"] = config_schema

    component_manifest.manifest["spec"] = spec


class PluginRuntimeController:
    """The controller for running plugins."""

    _stdio: bool
    """Check if the controller is using stdio for connection."""

    handler: PluginRuntimeHandler

    _controller_task: asyncio.Task[None]

    plugin_container: PluginContainer

    _connection_waiter: asyncio.Future[Connection]

    prod_mode: bool
    """Mark a Runtime-managed child that must use one-use registration auth."""

    hot_reloader: HotReloader | None = None
    """Hot reloader for watching file changes in debug mode"""

    _reload_event: asyncio.Event | None = None
    """Event to signal hot reload"""

    def __init__(
        self,
        plugin_manifest: ComponentManifest,
        component_manifests: list[ComponentManifest],
        stdio: bool,
        ws_debug_url: str,
        prod_mode: bool = False,
    ) -> None:
        self._stdio = stdio
        self.ws_debug_url = ws_debug_url
        self.prod_mode = prod_mode
        self._registration_capability = (
            os.environ.pop(PLUGIN_REGISTRATION_CAPABILITY_ENV, "").strip()
            if prod_mode
            else ""
        )
        self._reload_event = None
        # discover components
        components_containers = [
            ComponentContainer(
                manifest=component_manifest,
                component_instance=NoneComponent(),
                component_config={},
            )
            for component_manifest in component_manifests
        ]

        self.plugin_container = PluginContainer(
            manifest=plugin_manifest,
            plugin_instance=NonePlugin(),  # will be set later
            enabled=True,
            priority=0,
            plugin_config={},
            status=RuntimeContainerStatus.UNMOUNTED,
            components=components_containers,
        )
        self._slot_containers: dict[str, PluginInstallationSlot] = {}
        self._slot_generations: dict[str, int] = {}
        self._shared_initialize_lock = asyncio.Lock()

    async def run(self) -> None:
        await self._controller_task

    async def mount(self) -> None:
        logger.info(
            f"Mounting plugin {self.plugin_container.manifest.metadata.author}/{self.plugin_container.manifest.metadata.name}..."
        )

        # Setup hot reloader in debug mode
        if not self.prod_mode:
            self._reload_event = asyncio.Event()

            async def on_file_change():
                logger.info("File change detected, triggering hot reload...")
                try:
                    # Clean up current instances
                    await self.cleanup_instances()

                    # Reload all Python modules
                    reload_plugin_modules(os.getcwd())

                    # Re-initialize using the current plugin settings
                    # This will create new instances with the reloaded code
                    if hasattr(self, "handler") and self.handler is not None:
                        # Get current plugin container to retrieve settings
                        container_data = await self.handler.get_plugin_container()
                        plugin_settings = {
                            "enabled": container_data["enabled"],
                            "priority": container_data["priority"],
                            "plugin_config": container_data["plugin_config"],
                        }
                        await self.initialize(plugin_settings)
                        logger.info("Hot reload completed successfully")
                except Exception as e:
                    logger.error(f"Failed to hot reload: {e}", exc_info=True)

            self.hot_reloader = HotReloader(os.getcwd(), on_file_change)
            self.hot_reloader.start()

        try:
            while True:
                controller: Controller
                self._connection_waiter = asyncio.Future()
                should_reconnect = asyncio.Event()

                async def new_connection_callback(connection: Connection):
                    self.handler = PluginRuntimeHandler(connection, self.initialize)
                    self.handler._slot_initialize_callback = self.initialize_slot
                    self.handler._slot_detach_callback = self.detach_slot
                    self.handler._slot_cancel_callback = self.invalidate_slot

                    async def disconnect_callback(hdl: PluginRuntimeHandler):
                        if self.prod_mode:
                            # In production mode, exit when disconnected
                            os._exit(0)
                        else:
                            # In debug mode, trigger reconnection
                            logger.info("Connection lost, triggering reconnection...")
                            should_reconnect.set()

                    self.handler.set_disconnect_callback(disconnect_callback)

                    # Set shutdown callback for debug mode
                    if not self.prod_mode:

                        async def shutdown_callback():
                            logger.info(
                                "Received shutdown request, triggering reconnection..."
                            )
                            should_reconnect.set()
                            await connection.close()

                        self.handler.shutdown_callback = shutdown_callback

                    self.handler.plugin_container = self.plugin_container
                    self._connection_waiter.set_result(connection)
                    await self.handler.run()

                async def make_connection_failed_callback(
                    controller: Controller, e: Exception = None
                ):
                    if self.prod_mode:
                        # In production mode, exit on connection failure
                        logger.error(
                            f"Connection failed to {self.plugin_container.manifest.metadata.author}/{self.plugin_container.manifest.metadata.name} {e}, exit"
                        )
                        self._connection_waiter.set_exception(
                            ConnectionClosedError(f"Connection failed: {e}")
                        )
                        exit(1)
                    else:
                        # In debug mode, log error and trigger retry
                        logger.warning(f"Connection failed: {e}, will retry...")
                        if not self._connection_waiter.done():
                            self._connection_waiter.set_exception(
                                ConnectionClosedError(f"Connection failed: {e}")
                            )

                if self._stdio:
                    controller = stdio_controller_server.StdioServerController()
                    controller.reserve_first_message_send = self.prod_mode
                else:
                    if self.prod_mode:
                        registration_capability = validate_runtime_secret(
                            self._registration_capability,
                            name=PLUGIN_REGISTRATION_CAPABILITY_ENV,
                        )
                        authentication_headers = {
                            PLUGIN_REGISTRATION_CAPABILITY_HEADER: (
                                registration_capability
                            )
                        }
                    else:
                        debug_key = validate_runtime_secret(
                            os.environ.get(PLUGIN_DEBUG_KEY_ENV, ""),
                            name=PLUGIN_DEBUG_KEY_ENV,
                        )
                        authentication_headers = {PLUGIN_DEBUG_KEY_HEADER: debug_key}
                    controller = ws_controller_client.WebSocketClientController(
                        self.ws_debug_url,
                        make_connection_failed_callback,
                        additional_headers=authentication_headers,
                    )

                self._controller_task = asyncio.create_task(
                    controller.run(new_connection_callback)
                )

                # wait for the connection to be established
                try:
                    _ = await self._connection_waiter
                except ConnectionClosedError:
                    if self.prod_mode:
                        # In production mode, propagate the error
                        raise
                    else:
                        # In debug mode, retry after delay
                        logger.info("Retrying connection in 3 seconds...")
                        await asyncio.sleep(3)
                        continue

                # send manifest info to runtime
                self.plugin_container.status = RuntimeContainerStatus.MOUNTED

                logger.info(
                    f"Plugin {self.plugin_container.manifest.metadata.author}/{self.plugin_container.manifest.metadata.name} mounted"
                )

                # register plugin
                registration_capability = self._registration_capability
                try:
                    await self.handler.register_plugin(
                        prod_mode=self.prod_mode,
                        registration_capability=registration_capability,
                    )
                finally:
                    if self.prod_mode:
                        self._registration_capability = ""

                # If in production mode, break the loop after first connection
                if self.prod_mode:
                    await self._controller_task
                    break

                # In debug mode, wait for shutdown signal
                await should_reconnect.wait()

                # Cancel the current controller task
                self._controller_task.cancel()
                try:
                    await self._controller_task
                except asyncio.CancelledError:
                    pass

                # Reset plugin status for next connection
                self.plugin_container.status = RuntimeContainerStatus.UNMOUNTED

                logger.info("Reconnecting to runtime...")
        finally:
            # Stop hot reloader when exiting
            if self.hot_reloader is not None:
                self.hot_reloader.stop()

    async def initialize(self, plugin_settings: dict[str, typing.Any]) -> None:
        logger.info(
            f"Initializing plugin {self.plugin_container.manifest.metadata.author}/{self.plugin_container.manifest.metadata.name}..."
        )
        logger.debug(f"plugin_settings: {plugin_settings}")

        await self._initialize_container(
            self.plugin_container,
            self.handler,
            plugin_settings,
        )

    async def _initialize_container(
        self,
        plugin_container: PluginContainer,
        runtime_handler: typing.Any,
        plugin_settings: dict[str, typing.Any],
    ) -> None:
        """Initialize one object graph without mutating controller-global routing."""

        plugin_container.enabled = plugin_settings["enabled"]
        plugin_container.priority = plugin_settings["priority"]
        plugin_container.plugin_config = plugin_settings["plugin_config"]
        # initialize plugin instance
        plugin_cls = plugin_container.manifest.get_python_component_class()
        assert isinstance(plugin_cls, type(BasePlugin))
        plugin_container.plugin_instance = plugin_cls()
        plugin_container.plugin_instance.config = plugin_container.plugin_config
        plugin_container.plugin_instance.plugin_runtime_handler = runtime_handler
        await plugin_container.plugin_instance.initialize()

        preinitialize_component_classes: list[type[BaseComponent]] = [
            EventListener,
            Tool,
            Command,
            KnowledgeEngine,
            Parser,
            Page,
            Runner,
        ]

        for component_cls in preinitialize_component_classes:
            for component_container in plugin_container.components:
                logger.debug(
                    f"Checking component {component_container.manifest.metadata.name}: "
                    f"kind={component_container.manifest.kind}, expected={component_cls.__kind__}"
                )
                if component_container.manifest.kind == component_cls.__kind__:
                    logger.info(
                        f"Initializing {component_cls.__kind__} component: "
                        f"{component_container.manifest.metadata.name}"
                    )
                    component_impl_cls = (
                        component_container.manifest.get_python_component_class()
                    )
                    assert issubclass(component_impl_cls, component_cls)
                    component_container.component_instance = component_impl_cls()
                    if issubclass(component_impl_cls, Runner):
                        _apply_runner_class_defaults(
                            component_container.manifest,
                            component_impl_cls,
                        )
                        component_container.component_instance.bind_runtime(
                            plugin_runtime_handler=runtime_handler,
                            plugin_config=plugin_container.plugin_config,
                            plugin_identity=(
                                f"{plugin_container.manifest.metadata.author}/"
                                f"{plugin_container.manifest.metadata.name}"
                            ),
                        )
                    component_container.component_instance.plugin = (
                        plugin_container.plugin_instance
                    )
                    await component_container.component_instance.initialize()
                    logger.info(
                        f"Component {component_container.manifest.metadata.name} initialized, "
                        f"instance type: {type(component_container.component_instance).__name__}"
                    )

        logger.info(
            f"Plugin {self.plugin_container.manifest.metadata.author}/{self.plugin_container.manifest.metadata.name} initialized"
        )

        plugin_container.status = RuntimeContainerStatus.INITIALIZED

    async def initialize_slot(
        self,
        installation_uuid: InstallationBinding,
        plugin_settings: dict[str, typing.Any],
    ) -> PluginInstallationSlot:
        """Attach lightweight tenant state to one process-wide object graph."""

        if not isinstance(installation_uuid, InstallationBinding):
            raise ValueError("Shared plugin slots require InstallationBinding")
        execution = self.plugin_container.manifest.execution
        if (
            execution is None
            or execution.shared_runtime != "shared-runtime-v1"
            or execution.component_model != "stateless-v1"
        ):
            raise ValueError(
                "Shared plugin slots require shared-runtime-v1/stateless-v1"
            )
        slot_key = installation_uuid.installation_uuid
        generation = self._slot_generations.get(slot_key, 0) + 1
        self._slot_generations[slot_key] = generation
        async with self._shared_initialize_lock:
            if self.plugin_container.status is not RuntimeContainerStatus.INITIALIZED:
                await self._initialize_container(
                    self.plugin_container,
                    self.handler,
                    {"enabled": True, "priority": 0, "plugin_config": {}},
                )
        if self._slot_generations.get(slot_key) != generation:
            raise RuntimeError("Shared plugin slot initialization was superseded")
        slot = PluginInstallationSlot(
            binding=installation_uuid,
            enabled=bool(plugin_settings["enabled"]),
            priority=int(plugin_settings["priority"]),
            plugin_config=freeze_config(plugin_settings["plugin_config"]),
            plugin_container=self.plugin_container,
        )
        self._slot_containers[slot_key] = slot
        return slot

    def plugin_container_for_slot(
        self,
        installation_uuid: str,
    ) -> PluginInstallationSlot | None:
        return self._slot_containers.get(installation_uuid)

    def invalidate_slot(self, installation_uuid: str) -> None:
        """Fence an in-flight initializer before cancellation reaches plugin code."""

        self._slot_generations[installation_uuid] = (
            self._slot_generations.get(installation_uuid, 0) + 1
        )

    async def detach_slot(self, installation_uuid: str) -> None:
        """Drop exactly one slot; sibling instances remain resident."""

        self.invalidate_slot(installation_uuid)
        slot = self._slot_containers.pop(installation_uuid, None)
        if slot is None:
            return
        # The slot is no longer routable while the object graph stays resident for
        # sibling installations, so this is the only chance to release state the
        # plugin keyed by the revoked binding.
        await notify_installation_revoked(self.plugin_container, slot.binding)

    async def cleanup_instances(self) -> None:
        """Clean up all plugin and component instances."""
        logger.info("Cleaning up plugin instances...")

        self._slot_containers.clear()
        # Clear component instances
        for component_container in self.plugin_container.components:
            # Reset component instance
            component_container.component_instance = NoneComponent()

        # Reset plugin instance
        self.plugin_container.plugin_instance = NonePlugin()
        self.plugin_container.status = RuntimeContainerStatus.UNMOUNTED

        logger.info("Plugin instances cleaned up")

    async def reload_and_reinitialize(self) -> None:
        """Reload plugin code and reinitialize all instances."""
        logger.info("Reloading plugin code...")

        # Clean up current instances
        await self.cleanup_instances()

        # Reload all Python modules
        reload_plugin_modules(os.getcwd())

        # Reinitialize plugin (this will be called by runtime via INITIALIZE_PLUGIN action)
        logger.info("Waiting for reinitialization from runtime...")


# {"seq_id": 1, "code": 0, "data": {"enabled": true, "priority": 0, "plugin_config": {}}}
