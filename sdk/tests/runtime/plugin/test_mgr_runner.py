"""Tests for PluginManager Runner methods (Protocol v1)."""

from __future__ import annotations

import asyncio
import time
import typing
from unittest.mock import Mock

import pytest

from langbot_plugin.api.definition.components.base import NoneComponent
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.api.entities.builtin.runner.trigger import AgentTrigger
from langbot_plugin.api.entities.builtin.runner.input import AgentInput
from langbot_plugin.api.entities.builtin.runner.resources import AgentResources
from langbot_plugin.api.entities.builtin.runner.runtime import AgentRuntimeContext
from langbot_plugin.api.entities.builtin.runner.event import AgentEventContext
from langbot_plugin.api.entities.builtin.runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.runtime.plugin.container import RuntimeContainerStatus


@pytest.fixture(autouse=True)
def bind_test_runners(monkeypatch):
    monkeypatch.setattr(Runner, "get_run_api", lambda self, ctx: Mock())


class MockRunner(Runner):
    """Mock Runner for testing."""

    async def run(
        self, ctx: RunnerContext
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        """Mock run that yields results."""
        yield RunnerResult.message_completed(
            run_id=ctx.run_id,
            message=Message(role="assistant", content=f"Echo: {ctx.input.to_text()}"),
        )
        yield RunnerResult.run_completed(run_id=ctx.run_id, finish_reason="stop")


class StreamingRunner(Runner):
    """Mock Runner that streams."""

    async def run(
        self, ctx: RunnerContext
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        """Mock run that streams chunks using MessageChunk."""
        for word in ["Hello", " ", "world"]:
            chunk = MessageChunk(role="assistant", content=word)
            yield RunnerResult.message_delta(run_id=ctx.run_id, chunk=chunk)
        yield RunnerResult.run_completed(run_id=ctx.run_id, finish_reason="stop")


class FailingRunner(Runner):
    """Mock Runner that fails."""

    async def run(
        self, ctx: RunnerContext
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        """Mock run that raises an exception after yielding."""
        # Must have at least one yield to be an async generator
        chunk = MessageChunk(role="assistant", content="Starting...")
        yield RunnerResult.message_delta(run_id=ctx.run_id, chunk=chunk)
        raise RuntimeError("Intentional test failure")


class SlowRunner(Runner):
    """Mock Runner that exceeds the run deadline."""

    async def run(
        self, ctx: RunnerContext
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        import asyncio

        await asyncio.sleep(0.05)
        yield RunnerResult.run_completed(run_id=ctx.run_id, finish_reason="stop")


class PresequencedRunner(Runner):
    """Runner that emits its own sequence values."""

    async def run(
        self, ctx: RunnerContext
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        yield RunnerResult.message_completed(
            run_id=ctx.run_id,
            message=Message(role="assistant", content="presequenced"),
            sequence=99,
        )
        yield RunnerResult.run_completed(
            run_id=ctx.run_id,
            finish_reason="stop",
            sequence=100,
        )


class ClassDeclaredRunner(Runner):
    """Runner that declares runner metadata in Python class defaults."""

    @classmethod
    def get_config_schema(cls) -> list[dict[str, typing.Any]]:
        return [{"type": "llm-model-selector", "name": "model"}]

    async def run(
        self, ctx: RunnerContext
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        yield RunnerResult.run_completed(run_id=ctx.run_id, finish_reason="stop")


def _i18n(value: str):
    i18n = Mock()
    i18n.to_dict.return_value = {"en_US": value}
    return i18n


def create_mock_component_manifest(
    runner_name: str,
    spec: dict | None = None,
):
    """Create a mock ComponentManifest-like object."""
    mock_manifest = Mock()
    mock_manifest.kind = "Runner"
    mock_manifest.metadata = Mock()
    mock_manifest.metadata.name = runner_name
    mock_manifest.metadata.label = _i18n(f"Test runner {runner_name}")
    mock_manifest.metadata.description = _i18n(f"Test runner {runner_name}")
    mock_manifest.spec = spec or {
        "config": [],
        "capabilities": {},
        "permissions": {},
    }
    mock_manifest.spec = {"usages": ["agent"], **mock_manifest.spec}
    mock_manifest.manifest = {
        "kind": "Runner",
        "metadata": {
            "name": runner_name,
            "description": f"Test runner {runner_name}",
        },
        "spec": mock_manifest.spec,
    }
    mock_manifest.model_dump = Mock(return_value=mock_manifest.manifest)
    return mock_manifest


def create_mock_plugin(
    author: str,
    name: str,
    runner_components: list[tuple[str, Runner | None]],
    capabilities: dict | None = None,
    permissions: dict | None = None,
    mock_handler_responses: list[list[dict]] | None = None,
    status: RuntimeContainerStatus = RuntimeContainerStatus.INITIALIZED,
    enabled: bool = True,
):
    """Create a mock plugin container with Runner components.

    Args:
        author: Plugin author
        name: Plugin name
        runner_components: List of (runner_name, runner_instance) tuples
        capabilities: Optional capabilities dict
        mock_handler_responses: Optional list of response lists for each runner.
            Each element is a list of responses to yield for that runner.
    """
    plugin = Mock()
    plugin.manifest = Mock()
    plugin.manifest.metadata = Mock()
    plugin.manifest.metadata.author = author
    plugin.manifest.metadata.name = name
    plugin.manifest.metadata.version = "0.1.7"

    components = []
    for runner_name, runner_instance in runner_components:
        spec = {
            "config": [],
            "capabilities": capabilities or {},
            "permissions": permissions or {},
        }
        component = Mock()
        component.manifest = create_mock_component_manifest(runner_name, spec)
        component.component_instance = runner_instance
        components.append(component)

    plugin.components = components
    plugin.status = status
    plugin.enabled = enabled

    # Mock runtime plugin handler for forwarding
    if mock_handler_responses:

        async def mock_call_action_generator(action, data, timeout=300):
            runner_name = data.get("runner_name")
            # Find matching responses for this runner
            for idx, (rname, _) in enumerate(runner_components):
                if rname == runner_name and idx < len(mock_handler_responses):
                    for resp in mock_handler_responses[idx]:
                        yield resp  # Yield response data directly (matches real call_action_generator)
                    return
            # No matching responses found
            yield {
                "type": "run.failed",
                "data": {
                    "error": f"No mock responses for {runner_name}",
                    "code": "runner.mock_error",
                },
            }

        mock_handler = Mock()
        mock_handler.call_action_generator = mock_call_action_generator
        plugin._runtime_plugin_handler = mock_handler
    else:
        # Default: no handler (will cause handler_not_found error)
        plugin._runtime_plugin_handler = None

    return plugin


class RecordingRuntimeHandler:
    """Minimal runtime handler that records whether runner forwarding happens."""

    def __init__(self, responses: list[dict] | None = None):
        self.calls: list[tuple[typing.Any, dict, float]] = []
        self.responses = responses or [
            {"type": "run.completed", "data": {"finish_reason": "stop"}}
        ]

    async def call_action_generator(self, action, data, timeout=300):
        self.calls.append((action, data, timeout))
        for response in self.responses:
            yield response


def create_run_context() -> RunnerContext:
    """Create a valid RunnerContext for testing."""
    return RunnerContext(
        run_id="test_run",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(
            event_id="test_event",
            event_type="message.received",
            source="test",
        ),
        input=AgentInput(text="Hello"),
        delivery=DeliveryContext(surface="test"),
        resources=AgentResources(),
        runtime=AgentRuntimeContext(),
    )


class TestListRunners:
    """Test PluginManager.list_runners v1 protocol."""

    @pytest.mark.anyio
    async def test_single_plugin_single_runner(self):
        """Test listing a plugin with one runner."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)

        runner = MockRunner()
        plugin = create_mock_plugin("test-author", "test-plugin", [("default", runner)])
        mgr.plugins = [plugin]

        runners = await mgr.list_runners()

        assert len(runners) == 1
        assert runners[0]["plugin_author"] == "test-author"
        assert runners[0]["plugin_name"] == "test-plugin"
        assert runners[0]["plugin_version"] == "0.1.7"
        assert runners[0]["runner_name"] == "default"
        assert "protocol_version" not in runners[0]
        assert runners[0]["manifest"]["id"] == "plugin:test-author/test-plugin/default"
        assert runners[0]["manifest"]["capabilities"]["streaming"] is False
        assert runners[0]["manifest"]["permissions"]["models"] == []
        assert runners[0]["runner_description"] == {"en_US": "Test runner default"}
        assert runners[0]["capabilities"] == runners[0]["manifest"]["capabilities"]
        assert runners[0]["permissions"] == runners[0]["manifest"]["permissions"]
        assert runners[0]["config"] == runners[0]["manifest"]["config_schema"]

    @pytest.mark.anyio
    async def test_resume_extension_is_advertised_without_new_capability_fields(self):
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mgr = PluginManager(Mock(spec=RuntimeContext))
        plugin = create_mock_plugin(
            "test-author", "test-plugin", [("default", MockRunner())]
        )
        plugin.components[0].manifest.spec["resume"] = True
        mgr.plugins = [plugin]
        runners = await mgr.list_runners()
        assert runners[0]["manifest"]["metadata"]["supports_resume"] is True
        assert "resume" not in runners[0]["manifest"]["capabilities"]

    @pytest.mark.anyio
    async def test_single_plugin_multiple_runners(self):
        """Test listing a plugin with multiple runners (key feature of v1)."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)

        # Create plugin with multiple Runner components
        plugin = create_mock_plugin(
            "test-author",
            "multi-runner-plugin",
            [
                ("default", MockRunner()),
                ("streaming", StreamingRunner()),
                ("tool_based", MockRunner()),
            ],
            capabilities={"streaming": True, "tool_calling": True},
        )
        mgr.plugins = [plugin]

        runners = await mgr.list_runners()

        assert len(runners) == 3
        runner_names = [r["runner_name"] for r in runners]
        assert "default" in runner_names
        assert "streaming" in runner_names
        assert "tool_based" in runner_names

        # Discovery returns typed manifest plus extracted config.
        for runner in runners:
            assert "protocol_version" not in runner
            assert runner["manifest"]["capabilities"]["streaming"] is True
            assert runner["manifest"]["capabilities"]["tool_calling"] is True

    @pytest.mark.anyio
    async def test_include_plugins_filter(self):
        """Test include_plugins filtering."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)

        plugin1 = create_mock_plugin("author1", "plugin1", [("runner1", MockRunner())])
        plugin2 = create_mock_plugin("author2", "plugin2", [("runner2", MockRunner())])
        mgr.plugins = [plugin1, plugin2]

        # Only include plugin1
        runners = await mgr.list_runners(include_plugins=["author1/plugin1"])
        assert len(runners) == 1
        assert runners[0]["plugin_author"] == "author1"

        # Empty filter returns all
        runners = await mgr.list_runners()
        assert len(runners) == 2

    @pytest.mark.anyio
    async def test_skips_disabled_and_uninitialized_plugins(self):
        """Runner listing uses the same plugin lifecycle gate as event dispatch."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)
        mgr.plugins = [
            create_mock_plugin(
                "author",
                "ready",
                [("ready_runner", MockRunner())],
            ),
            create_mock_plugin(
                "author",
                "disabled",
                [("disabled_runner", MockRunner())],
                enabled=False,
            ),
            create_mock_plugin(
                "author",
                "mounted",
                [("mounted_runner", MockRunner())],
                status=RuntimeContainerStatus.MOUNTED,
            ),
        ]

        runners = await mgr.list_runners()

        assert [runner["plugin_name"] for runner in runners] == ["ready"]

    @pytest.mark.anyio
    async def test_uses_runner_class_defaults_when_manifest_omits_spec_details(self):
        """Python Runner declarations are reflected in LIST_RUNNERS."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)
        plugin = create_mock_plugin(
            "test-author",
            "class-declared-plugin",
            [("default", ClassDeclaredRunner())],
        )
        plugin.components[0].manifest = create_mock_component_manifest(
            "default",
            spec={},
        )
        mgr.plugins = [plugin]

        runners = await mgr.list_runners()

        assert len(runners) == 1
        assert runners[0]["manifest"]["capabilities"]["streaming"] is False
        assert runners[0]["manifest"]["permissions"]["models"] == []
        assert (
            runners[0]["manifest"]["config_schema"][0]["type"] == "llm-model-selector"
        )
        assert runners[0]["manifest"]["config_schema"][0]["name"] == "model"

    @pytest.mark.anyio
    async def test_skips_invalid_runner_manifest(self, caplog):
        """Invalid typed manifest data skips only that runner."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)
        plugin = create_mock_plugin(
            "test-author",
            "invalid-runner-plugin",
            [("valid", MockRunner()), ("invalid", MockRunner())],
        )
        plugin.components[1].manifest = create_mock_component_manifest(
            "invalid",
            spec={
                "config": [],
                "capabilities": {"event_context": True},
                "permissions": {},
            },
        )
        mgr.plugins = [plugin]

        runners = await mgr.list_runners()

        assert [runner["runner_name"] for runner in runners] == ["valid"]
        assert "Skipping invalid Runner manifest" in caplog.text


class TestRunAgent:
    """Test PluginManager.run_runner v1 protocol."""

    @pytest.mark.anyio
    async def test_run_runner_success_streaming(self):
        """Test successful run_runner with streaming output."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)

        # Create mock responses for streaming
        mock_responses = [
            {
                "type": "message.delta",
                "data": {"chunk": {"role": "assistant", "content": "Hello"}},
            },
            {
                "type": "message.delta",
                "data": {"chunk": {"role": "assistant", "content": " world"}},
            },
            {"type": "run.completed", "data": {"finish_reason": "stop"}},
        ]

        plugin = create_mock_plugin(
            "test-author",
            "test-plugin",
            [("streaming", None)],
            mock_handler_responses=[mock_responses],
        )
        mgr.plugins = [plugin]

        ctx = create_run_context()
        results = []
        async for result in mgr.run_runner(
            "test-author",
            "test-plugin",
            "streaming",
            ctx.model_dump(mode="json"),
        ):
            results.append(result)

        # Should have streaming chunks + run.completed
        assert len(results) >= 2
        assert results[-1]["type"] == "run.completed"
        assert [result["sequence"] for result in results] == [1, 2, 3]

    @pytest.mark.anyio
    async def test_run_runner_overwrites_runner_supplied_sequences(self):
        """Runtime owns result sequence numbers for forwarded runner streams."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)
        plugin = create_mock_plugin(
            "test-author",
            "test-plugin",
            [("presequenced", None)],
            mock_handler_responses=[
                [
                    {
                        "type": "message.completed",
                        "data": {
                            "message": {
                                "role": "assistant",
                                "content": "presequenced",
                            }
                        },
                        "sequence": 99,
                    },
                    {
                        "type": "run.completed",
                        "data": {"finish_reason": "stop"},
                        "sequence": 100,
                    },
                ]
            ],
        )
        mgr.plugins = [plugin]

        ctx = create_run_context()
        results = [
            result
            async for result in mgr.run_runner(
                "test-author",
                "test-plugin",
                "presequenced",
                ctx.model_dump(mode="json"),
            )
        ]

        assert [result["sequence"] for result in results] == [1, 2]

    @pytest.mark.anyio
    async def test_run_runner_plugin_not_found(self):
        """Test run_runner returns run.failed when plugin not found."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)
        mgr.plugins = []

        ctx = create_run_context()
        results = []
        async for result in mgr.run_runner(
            "unknown",
            "unknown-plugin",
            "default",
            ctx.model_dump(mode="json"),
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "run.failed"
        assert results[0]["data"]["code"] == "runner.plugin_not_found"

    @pytest.mark.anyio
    async def test_run_runner_not_found(self):
        """Test run_runner returns run.failed when runner not found."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)

        # Plugin exists but no matching runner
        plugin = create_mock_plugin(
            "test-author", "test-plugin", [("other_runner", MockRunner())]
        )
        mgr.plugins = [plugin]

        ctx = create_run_context()
        results = []
        async for result in mgr.run_runner(
            "test-author",
            "test-plugin",
            "default",  # Not found
            ctx.model_dump(mode="json"),
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "run.failed"
        assert results[0]["data"]["code"] == "runner.not_found"

    @pytest.mark.anyio
    async def test_run_runner_exception_converted_to_run_failed(self):
        """Test that runner exceptions are converted to run.failed (critical requirement)."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)

        # Create mock responses simulating an exception
        mock_responses = [
            {
                "type": "message.delta",
                "data": {"chunk": {"role": "assistant", "content": "Starting..."}},
            },
            {
                "type": "run.failed",
                "data": {
                    "error": "Intentional test failure",
                    "code": "runner.exception",
                },
            },
        ]

        plugin = create_mock_plugin(
            "test-author",
            "test-plugin",
            [("failing", None)],
            mock_handler_responses=[mock_responses],
        )
        mgr.plugins = [plugin]

        ctx = create_run_context()
        results = []
        async for result in mgr.run_runner(
            "test-author",
            "test-plugin",
            "failing",
            ctx.model_dump(mode="json"),
        ):
            results.append(result)

        # Must convert exception to run.failed, not raise
        assert len(results) >= 1
        assert results[-1]["type"] == "run.failed"
        assert results[-1]["data"]["code"] == "runner.exception"
        assert "Intentional test failure" in results[-1]["data"]["error"]

    @pytest.mark.anyio
    async def test_run_runner_context_validation_failure(self):
        """Test that invalid context produces run.failed when forwarded."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)

        # Create mock responses for context validation failure
        mock_responses = [
            {
                "type": "run.failed",
                "data": {
                    "error": "Context validation failed",
                    "code": "runner.context_invalid",
                },
            },
        ]

        plugin = create_mock_plugin(
            "test-author",
            "test-plugin",
            [("default", None)],
            mock_handler_responses=[mock_responses],
        )
        mgr.plugins = [plugin]

        # Invalid context (missing required fields)
        invalid_context = {"invalid": "data"}

        results = []
        async for result in mgr.run_runner(
            "test-author",
            "test-plugin",
            "default",
            invalid_context,
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "run.failed"
        assert results[0]["data"]["code"] == "runner.context_invalid"

    @pytest.mark.anyio
    async def test_run_runner_handler_not_found(self):
        """Test run_runner when plugin has no runtime handler."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)

        # Plugin without handler (default when no mock_handler_responses provided)
        plugin = create_mock_plugin("test-author", "test-plugin", [("default", None)])
        mgr.plugins = [plugin]

        ctx = create_run_context()
        results = []
        async for result in mgr.run_runner(
            "test-author",
            "test-plugin",
            "default",
            ctx.model_dump(mode="json"),
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "run.failed"
        assert results[0]["data"]["code"] == "runner.handler_not_found"

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        ("enabled", "status", "expected_code"),
        [
            (False, RuntimeContainerStatus.INITIALIZED, "runner.plugin_disabled"),
            (True, RuntimeContainerStatus.MOUNTED, "runner.plugin_not_initialized"),
        ],
    )
    async def test_run_runner_rejects_plugins_outside_ready_gate(
        self,
        enabled: bool,
        status: RuntimeContainerStatus,
        expected_code: str,
    ):
        """Disabled or uninitialized plugins are denied before handler forwarding."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)
        plugin = create_mock_plugin(
            "test-author",
            "test-plugin",
            [("default", MockRunner())],
            enabled=enabled,
            status=status,
        )
        runtime_handler = RecordingRuntimeHandler()
        plugin._runtime_plugin_handler = runtime_handler
        mgr.plugins = [plugin]

        ctx = create_run_context()
        results = []
        async for result in mgr.run_runner(
            "test-author",
            "test-plugin",
            "default",
            ctx.model_dump(mode="json"),
        ):
            results.append(result)

        assert runtime_handler.calls == []
        assert len(results) == 1
        assert results[0]["type"] == "run.failed"
        assert results[0]["data"]["code"] == expected_code

    @pytest.mark.anyio
    async def test_run_runner_not_initialized_forwarded(self):
        """Test run_runner when plugin handler returns not_initialized error."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)

        # Mock responses for not initialized error
        mock_responses = [
            {
                "type": "run.failed",
                "data": {
                    "error": "Runner default not initialized",
                    "code": "runner.not_initialized",
                },
            },
        ]

        plugin = create_mock_plugin(
            "test-author",
            "test-plugin",
            [("default", None)],
            mock_handler_responses=[mock_responses],
        )
        mgr.plugins = [plugin]

        ctx = create_run_context()
        results = []
        async for result in mgr.run_runner(
            "test-author",
            "test-plugin",
            "default",
            ctx.model_dump(mode="json"),
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "run.failed"
        assert results[0]["data"]["code"] == "runner.not_initialized"

    @pytest.mark.anyio
    async def test_run_runner_deadline_returns_timeout(self):
        """PluginManager enforces total runner deadline while forwarding."""
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mock_context = Mock(spec=RuntimeContext)
        mgr = PluginManager(mock_context)

        mock_responses = [
            {"type": "run.completed", "data": {"finish_reason": "stop"}},
        ]
        plugin = create_mock_plugin(
            "test-author",
            "test-plugin",
            [("default", None)],
            mock_handler_responses=[mock_responses],
        )
        mgr.plugins = [plugin]

        ctx = create_run_context()
        ctx.runtime.deadline_at = time.time() - 1

        results = []
        async for result in mgr.run_runner(
            "test-author",
            "test-plugin",
            "default",
            ctx.model_dump(mode="json"),
        ):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "run.failed"
        assert results[0]["data"]["code"] == "runner.timeout"
        assert results[0]["data"]["retryable"] is True

    @pytest.mark.anyio
    async def test_runtime_forwarding_waits_past_initial_deadline(self):
        from langbot_plugin.runtime.plugin.mgr import PluginManager
        from langbot_plugin.runtime.context import RuntimeContext

        mgr = PluginManager(Mock(spec=RuntimeContext))
        plugin = create_mock_plugin(
            "test-author",
            "test-plugin",
            [("default", None)],
            mock_handler_responses=[[{"type": "run.completed", "data": {}}]],
        )

        async def delayed_result(action, data, timeout=300):
            assert timeout is None
            await asyncio.sleep(0.05)
            yield {"type": "run.completed", "data": {"finish_reason": "stop"}}

        plugin._runtime_plugin_handler.call_action_generator = delayed_result
        mgr.plugins = [plugin]
        ctx = create_run_context()
        ctx.runtime.deadline_at = time.time() + 0.01

        results = [
            result
            async for result in mgr.run_runner(
                "test-author", "test-plugin", "default", ctx.model_dump(mode="json")
            )
        ]

        assert results[0]["type"] == "run.completed"


@pytest.mark.anyio
async def test_plugin_runtime_runner_deadline_cancels_runner_coroutine():
    """The plugin-process helper converts an expired runner coroutine to run.failed."""
    from langbot_plugin.cli.run.handler import _iter_runner_results_with_deadline

    ctx = create_run_context()
    ctx.runtime.deadline_at = time.time() + 0.01

    results = [
        result async for result in _iter_runner_results_with_deadline(SlowRunner(), ctx)
    ]

    assert len(results) == 1
    assert results[0].type.value == "run.failed"
    assert results[0].data["code"] == "runner.timeout"
    assert results[0].data["retryable"] is True
    assert results[0].sequence == 1


@pytest.mark.anyio
async def test_plugin_runtime_runner_results_get_sequence_numbers():
    """The plugin-process RUN_RUNNER helper assigns sequence to runner results."""
    from langbot_plugin.cli.run.handler import _iter_runner_results_with_deadline

    ctx = create_run_context()

    results = [
        result async for result in _iter_runner_results_with_deadline(MockRunner(), ctx)
    ]

    assert [result.sequence for result in results] == [1, 2]


@pytest.mark.anyio
async def test_plugin_runtime_runner_results_overwrite_sequence_numbers():
    """The plugin-process RUN_RUNNER helper owns result sequence numbers."""
    from langbot_plugin.cli.run.handler import _iter_runner_results_with_deadline

    ctx = create_run_context()

    results = [
        result
        async for result in _iter_runner_results_with_deadline(
            PresequencedRunner(), ctx
        )
    ]

    assert [result.sequence for result in results] == [1, 2]


@pytest.mark.anyio
async def test_plugin_runtime_runner_exception_includes_run_id():
    """The plugin-process RUN_RUNNER handler must convert runner exceptions to run.failed."""
    from langbot_plugin.cli.run.handler import PluginRuntimeHandler
    from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction

    async def initialize_plugin(_settings):
        return None

    handler = PluginRuntimeHandler(Mock(), initialize_plugin)
    component = Mock()
    component.manifest = create_mock_component_manifest("failing")
    component.component_instance = FailingRunner()
    handler.plugin_container = Mock(components=[component])

    run_runner = handler.actions[RuntimeToPluginAction.RUN_RUNNER.value]
    results = [
        response.data
        async for response in run_runner(
            {
                "runner_name": "failing",
                "context": create_run_context().model_dump(mode="json"),
            }
        )
    ]

    assert results[-1]["type"] == "run.failed"
    assert results[-1]["run_id"] == "test_run"
    assert results[-1]["data"]["code"] == "runner.exception"
    assert "Intentional test failure" in results[-1]["data"]["error"]
    assert [result["sequence"] for result in results] == [1, 2]


@pytest.mark.anyio
async def test_plugin_runtime_context_validation_returns_structured_run_failed():
    """RUN_RUNNER context validation failure must stay inside the runner stream."""
    from langbot_plugin.cli.run.handler import PluginRuntimeHandler
    from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction

    async def initialize_plugin(_settings):
        return None

    handler = PluginRuntimeHandler(Mock(), initialize_plugin)
    handler.plugin_container = Mock(components=[])

    run_runner = handler.actions[RuntimeToPluginAction.RUN_RUNNER.value]
    responses = [
        response
        async for response in run_runner(
            {
                "runner_name": "default",
                "context": {"run_id": "bad_run", "invalid": "data"},
            }
        )
    ]

    assert len(responses) == 1
    assert responses[0].code == 0
    assert responses[0].data["type"] == "run.failed"
    assert responses[0].data["run_id"] == "bad_run"
    assert responses[0].data["data"]["code"] == "runner.context_invalid"
    assert responses[0].data["sequence"] == 1


@pytest.mark.anyio
async def test_plugin_runtime_runner_not_found_returns_structured_run_failed():
    """RUN_RUNNER not-found must be a stream payload, not an ActionResponse signature error."""
    from langbot_plugin.cli.run.handler import PluginRuntimeHandler
    from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction

    async def initialize_plugin(_settings):
        return None

    handler = PluginRuntimeHandler(Mock(), initialize_plugin)
    component = Mock()
    component.manifest = create_mock_component_manifest("other")
    component.component_instance = MockRunner()
    handler.plugin_container = Mock(components=[component])

    run_runner = handler.actions[RuntimeToPluginAction.RUN_RUNNER.value]
    responses = [
        response
        async for response in run_runner(
            {
                "runner_name": "missing",
                "context": create_run_context().model_dump(mode="json"),
            }
        )
    ]

    assert len(responses) == 1
    assert responses[0].code == 0
    assert responses[0].data["type"] == "run.failed"
    assert responses[0].data["run_id"] == "test_run"
    assert responses[0].data["data"]["code"] == "runner.not_found"
    assert responses[0].data["sequence"] == 1


@pytest.mark.anyio
async def test_plugin_runtime_uninitialized_runner_returns_structured_run_failed():
    """RUN_RUNNER uninitialized branch must preserve runner.not_initialized."""
    from langbot_plugin.cli.run.handler import PluginRuntimeHandler
    from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction

    async def initialize_plugin(_settings):
        return None

    handler = PluginRuntimeHandler(Mock(), initialize_plugin)
    component = Mock()
    component.manifest = create_mock_component_manifest("default")
    component.component_instance = NoneComponent()
    handler.plugin_container = Mock(components=[component])

    run_runner = handler.actions[RuntimeToPluginAction.RUN_RUNNER.value]
    responses = [
        response
        async for response in run_runner(
            {
                "runner_name": "default",
                "context": create_run_context().model_dump(mode="json"),
            }
        )
    ]

    assert len(responses) == 1
    assert responses[0].code == 0
    assert responses[0].data["type"] == "run.failed"
    assert responses[0].data["run_id"] == "test_run"
    assert responses[0].data["data"]["code"] == "runner.not_initialized"
    assert responses[0].data["sequence"] == 1


@pytest.mark.anyio
async def test_dual_usage_runner_discovery_and_dispatch_share_one_identity():
    from langbot_plugin.runtime.plugin.runner_service import RunnerRuntimeService

    plugin = create_mock_plugin("test", "both", [("default", MockRunner())])
    plugin.components[0].manifest.spec.update(
        usages=["agent", "event"], events=["group.member_joined"]
    )
    plugin._runtime_plugin_handler = RecordingRuntimeHandler()
    service = RunnerRuntimeService(
        plugins=lambda: [plugin], find_plugin=lambda author, name: plugin
    )
    entries = await service.list_runners()
    assert len(entries) == 1
    assert entries[0]["manifest"]["id"] == "plugin:test/both/default"
    assert entries[0]["manifest"]["component_kind"] == "Runner"
    assert entries[0]["manifest"]["usages"] == ["agent", "event"]
    assert entries[0]["manifest"]["supported_event_patterns"] == ["group.member_joined"]
    ctx = create_run_context().model_dump(mode="json")
    results = [
        result async for result in service.run_runner("test", "both", "default", ctx)
    ]
    assert results[-1]["type"] == "run.completed"
    assert len(plugin._runtime_plugin_handler.calls) == 1


@pytest.mark.anyio
async def test_event_usage_requires_an_explicit_event_declaration():
    from langbot_plugin.runtime.plugin.runner_service import RunnerRuntimeService

    plugin = create_mock_plugin("test", "invalid", [("default", MockRunner())])
    plugin.components[0].manifest.spec.update(usages=["event"])
    service = RunnerRuntimeService(
        plugins=lambda: [plugin], find_plugin=lambda author, name: plugin
    )
    assert await service.list_runners() == []
