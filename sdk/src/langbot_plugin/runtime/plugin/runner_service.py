from __future__ import annotations

import asyncio
import logging
import typing

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.runner.manifest import (
    RunnerManifest,
)
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction
from langbot_plugin.entities.io.errors import ActionCallTimeoutError
from langbot_plugin.runtime.plugin import container as runtime_plugin_container
from langbot_plugin.utils.deadline import (
    remaining_deadline_seconds,
)

logger = logging.getLogger(__name__)


def _remaining_deadline_seconds(context: dict[str, typing.Any]) -> float | None:
    return remaining_deadline_seconds((context.get("runtime") or {}).get("deadline_at"))


def _ensure_result_sequence(
    result_data: dict[str, typing.Any],
    sequence: int,
) -> dict[str, typing.Any]:
    if not isinstance(result_data, dict):
        return result_data
    result_data = dict(result_data)
    result_data["sequence"] = sequence
    return result_data


class RunnerRuntimeService:
    """Discovers Runner components and forwards Host runs to plugin processes."""

    def __init__(
        self,
        *,
        plugins: typing.Callable[
            [], typing.Iterable[runtime_plugin_container.PluginContainer]
        ],
        find_plugin: typing.Callable[
            [str, str], runtime_plugin_container.PluginContainer | None
        ],
    ):
        self._plugins = plugins
        self._find_plugin = find_plugin

    async def list_runners(
        self, include_plugins: list[str] | None = None
    ) -> list[dict[str, typing.Any]]:
        """List available Runner components using Protocol v1 transport shape."""
        runners: list[dict[str, typing.Any]] = []

        for plugin in self._plugins():
            if not self._is_plugin_ready(plugin):
                continue

            if (
                include_plugins is not None
                and self._plugin_id(plugin) not in include_plugins
            ):
                continue

            for component in plugin.components:
                if component.manifest.kind not in {"Runner"}:
                    continue

                runner_entry = self._build_runner_entry(plugin, component)
                if runner_entry is not None:
                    runners.append(runner_entry)

        return runners

    async def run_runner(
        self,
        plugin_author: str,
        plugin_name: str,
        runner_name: str,
        context: dict[str, typing.Any],
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Forward a Host Runner run to the selected plugin process."""
        run_id = context.get("run_id", "unknown")
        target_plugin = self._find_plugin(plugin_author, plugin_name)

        if target_plugin is None:
            yield self._run_failed(
                run_id=run_id,
                error=f"Plugin {plugin_author}/{plugin_name} not found",
                code="runner.plugin_not_found",
            )
            return

        if not target_plugin.enabled:
            yield self._run_failed(
                run_id=run_id,
                error=f"Plugin {plugin_author}/{plugin_name} is disabled",
                code="runner.plugin_disabled",
            )
            return

        if (
            target_plugin.status
            != runtime_plugin_container.RuntimeContainerStatus.INITIALIZED
        ):
            yield self._run_failed(
                run_id=run_id,
                error=f"Plugin {plugin_author}/{plugin_name} is not initialized",
                code="runner.plugin_not_initialized",
            )
            return

        component_kind = (
            (context.get("runtime") or {})
            .get("metadata", {})
            .get("component_kind", "Runner")
        )
        if component_kind not in {"Runner"}:
            raise ValueError("Unsupported processor component kind")
        if (
            self._find_runner_component(target_plugin, runner_name, component_kind)
            is None
        ):
            yield self._run_failed(
                run_id=run_id,
                error=f"Runner {runner_name} not found in plugin {plugin_author}/{plugin_name}",
                code="runner.not_found",
            )
            return

        if target_plugin._runtime_plugin_handler is None:
            yield self._run_failed(
                run_id=run_id,
                error=f"Plugin {plugin_author}/{plugin_name} has no runtime handler",
                code="runner.handler_not_found",
            )
            return

        sequence = 0
        try:
            if (
                remaining := _remaining_deadline_seconds(context)
            ) is not None and remaining <= 0:
                raise asyncio.TimeoutError
            gen = target_plugin._runtime_plugin_handler.call_action_generator(
                RuntimeToPluginAction.RUN_RUNNER,
                {
                    "runner_name": runner_name,
                    "context": context,
                },
                timeout=None,
            )

            async for result_data in gen:
                sequence += 1
                yield _ensure_result_sequence(result_data, sequence)

        except (asyncio.TimeoutError, ActionCallTimeoutError):
            yield self._run_failed(
                run_id=run_id,
                error="Agent runner timed out",
                code="runner.timeout",
                retryable=True,
                sequence=sequence + 1,
            )
        except Exception as e:
            logger.exception(
                "Error forwarding Runner %s/%s:%s",
                plugin_author,
                plugin_name,
                runner_name,
            )
            yield self._run_failed(
                run_id=run_id,
                error=f"Error forwarding to plugin: {e}",
                code="runner.forward_exception",
                sequence=sequence + 1,
            )

    def _build_runner_entry(
        self,
        plugin: runtime_plugin_container.PluginContainer,
        component: runtime_plugin_container.ComponentContainer,
    ) -> dict[str, typing.Any] | None:
        spec = component.manifest.spec or {}
        runner_cls = (
            type(component.component_instance)
            if isinstance(component.component_instance, Runner)
            else Runner
        )
        config_schema = spec.get("config") or runner_cls.get_config_schema()
        runner_name = component.manifest.metadata.name
        runner_id = f"plugin:{plugin.manifest.metadata.author}/{plugin.manifest.metadata.name}/{runner_name}"

        try:
            if "event" in spec.get("usages", []) and not spec.get("events"):
                raise ValueError(
                    "Event usage requires an explicit spec.events declaration"
                )
            runner_manifest = RunnerManifest(
                id=runner_id,
                component_kind=component.manifest.kind,
                usages=spec.get("usages"),
                supported_event_patterns=spec.get("events") or ["*"],
                name=runner_name,
                label=component.manifest.metadata.label.to_dict(),
                description=component.manifest.metadata.description.to_dict()
                if component.manifest.metadata.description is not None
                else None,
                capabilities=spec.get("capabilities") or {},
                permissions=spec.get("permissions") or {},
                config_schema=config_schema,
                metadata={
                    "plugin_author": plugin.manifest.metadata.author,
                    "plugin_name": plugin.manifest.metadata.name,
                    "runner_name": runner_name,
                    "supports_resume": spec.get("resume", False) is True,
                },
            )
        except Exception as exc:
            logger.warning(
                "Skipping invalid Runner manifest %s/%s/%s: %s",
                plugin.manifest.metadata.author,
                plugin.manifest.metadata.name,
                runner_name,
                exc,
            )
            return None

        manifest_data = runner_manifest.model_dump(mode="json")
        return {
            "plugin_author": plugin.manifest.metadata.author,
            "plugin_name": plugin.manifest.metadata.name,
            "plugin_version": plugin.manifest.metadata.version,
            "runner_name": runner_name,
            "runner_description": manifest_data["description"],
            "manifest": manifest_data,
            "capabilities": manifest_data["capabilities"],
            "permissions": manifest_data["permissions"],
            "config": config_schema,
        }

    def _find_runner_component(
        self,
        plugin: runtime_plugin_container.PluginContainer,
        runner_name: str,
        component_kind: str = "Runner",
    ) -> runtime_plugin_container.ComponentContainer | None:
        for component in plugin.components:
            if (
                component.manifest.kind == component_kind
                and component.manifest.metadata.name == runner_name
            ):
                return component
        return None

    @staticmethod
    def _is_plugin_ready(
        plugin: runtime_plugin_container.PluginContainer,
    ) -> bool:
        return (
            plugin.enabled
            and plugin.status
            == runtime_plugin_container.RuntimeContainerStatus.INITIALIZED
        )

    @staticmethod
    def _plugin_id(plugin: runtime_plugin_container.PluginContainer) -> str:
        return f"{plugin.manifest.metadata.author}/{plugin.manifest.metadata.name}"

    @staticmethod
    def _run_failed(
        *,
        run_id: str,
        error: str,
        code: str,
        retryable: bool = False,
        sequence: int = 1,
    ) -> dict[str, typing.Any]:
        return RunnerResult.run_failed(
            run_id=run_id,
            error=error,
            code=code,
            retryable=retryable,
            sequence=sequence,
        ).model_dump(mode="json")
