"""Tests for workspace Application API tools and progressive disclosure."""

from __future__ import annotations

import asyncio
import hashlib
import types
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.resources import (
    AgentResources,
    ModelResource,
    ToolResource,
)
from langbot_plugin.api.entities.builtin.runner.result import (
    RunnerResultType,
)

from components.runner.default import DefaultRunner
from pkg.agent_core.langbot import LangBotToolExecutor
from pkg.agent_core.types import ToolCallRequest
from pkg.config import get_workspace_direct_threshold
from pkg.workspace_tools import (
    WorkspaceToolsManager,
    operation_id_to_tool_name,
    tool_name_to_operation_id,
)
from tests.test_runner import FakeRunnerAPIProxy, make_context


def _make_op(
    op_id: str,
    domain: str | None = None,
    summary: str = "",
    description: str = "",
    risk: str = "read",
    input_schema: dict[str, Any] | None = None,
) -> types.SimpleNamespace:
    d = domain or op_id.split(".")[0]
    return types.SimpleNamespace(
        id=op_id,
        domain=d,
        label={"zh_Hans": d, "en_US": d.capitalize()},
        summary=summary or f"Summary for {op_id}",
        description=description or f"Description for {op_id}",
        risk=risk,
        input_schema=input_schema or {"type": "object", "properties": {}},
    )


def _make_ctx(
    workspace_ops: list[Any] | None = None,
    tools: list[ToolResource] | None = None,
    config: dict[str, Any] | None = None,
    models: list[ModelResource] | None = None,
) -> RunnerContext:
    if models is None:
        models = [ModelResource(model_id="primary-model", model_name="Primary")]
    cfg = {
        "model": {"primary": "primary-model", "fallbacks": []},
        **(config or {}),
    }
    resources = AgentResources(
        models=models,
        tools=tools or [],
    )
    ctx = make_context(
        run_id="run-test-1",
        input_text="test question",
        config=cfg,
        resources=resources,
        delivery_supports_streaming=False,
    )
    if workspace_ops is not None:
        ctx.resources = types.SimpleNamespace(
            models=list(resources.models),
            tools=list(resources.tools),
            knowledge_bases=list(getattr(resources, "knowledge_bases", [])),
            skills=list(getattr(resources, "skills", [])),
            storage=getattr(resources, "storage", None),
            platform_capabilities=getattr(resources, "platform_capabilities", {}),
            workspace_operations=workspace_ops,
        )
    return ctx


# ==============================================================================
# 1. 授权列表为空时，不注册工具
# ==============================================================================


@pytest.mark.asyncio
async def test_empty_workspace_operations_registers_no_tools():
    ctx = _make_ctx(workspace_ops=[])
    api = Mock()
    api.workspace = Mock()
    api.workspace.list = AsyncMock(return_value={"operations": [], "domains": []})

    mgr = await WorkspaceToolsManager.discover(api, ctx)
    assert mgr.mode is None
    assert len(mgr.tools) == 0
    assert len(mgr.operations) == 0
    assert mgr.build_system_message() is None


# ==============================================================================
# 2. 3 个操作时为直接模式，20 个操作时为渐进模式 (及阈值可配置)
# ==============================================================================


@pytest.mark.asyncio
async def test_direct_mode_for_3_operations():
    ops = [
        _make_op("bot.list", summary="List bots"),
        _make_op("bot.create", summary="Create bot", risk="write"),
        _make_op("stats.basic", summary="Basic statistics"),
    ]
    ctx = _make_ctx(workspace_ops=ops)
    api = Mock()

    mgr = await WorkspaceToolsManager.discover(api, ctx)
    assert mgr.mode == "direct"
    assert len(mgr.tools) == 3
    tool_names = {t.name for t in mgr.tools}
    assert tool_names == {"ws_bot__list", "ws_bot__create", "ws_stats__basic"}
    # Direct mode does not register progressive meta tools
    assert "workspace_search" not in tool_names
    assert "workspace_describe" not in tool_names
    assert "workspace_call" not in tool_names
    # Direct mode adds no progressive system guidance
    assert mgr.build_system_message() is None


@pytest.mark.asyncio
async def test_progressive_mode_for_20_operations():
    ops = [_make_op(f"domain_{i}.action_{i}") for i in range(20)]
    ctx = _make_ctx(workspace_ops=ops)
    api = Mock()

    mgr = await WorkspaceToolsManager.discover(api, ctx)
    assert mgr.mode == "progressive"
    assert len(mgr.tools) == 3
    tool_names = {t.name for t in mgr.tools}
    assert tool_names == {"workspace_search", "workspace_describe", "workspace_call"}

    # Progressive mode injects domain overview and guidance into system prompt
    msg = mgr.build_system_message()
    assert msg is not None
    assert msg.role == "system"
    assert "先 search → describe → call" in msg.content
    assert "Available workspace capability domains:" in msg.content


@pytest.mark.asyncio
async def test_configurable_threshold():
    ops = [_make_op(f"bot.action_{i}") for i in range(5)]
    # Default threshold is 8 -> direct mode
    ctx_default = _make_ctx(workspace_ops=ops)
    mgr_default = await WorkspaceToolsManager.discover(Mock(), ctx_default)
    assert mgr_default.mode == "direct"

    # Configured threshold = 3 -> switches to progressive mode
    ctx_custom = _make_ctx(workspace_ops=ops, config={"workspace-direct-threshold": 3})
    assert get_workspace_direct_threshold(ctx_custom.config) == 3
    mgr_custom = await WorkspaceToolsManager.discover(Mock(), ctx_custom)
    assert mgr_custom.mode == "progressive"


# ==============================================================================
# 3. 工具名可以正确还原为操作 ID
# ==============================================================================


def test_tool_name_bidirectional_mapping():
    cases = [
        ("bot.list", "ws_bot__list"),
        ("stats.basic", "ws_stats__basic"),
        ("pipeline.extensions.update", "ws_pipeline__extensions__update"),
        ("monitoring.metrics.query", "ws_monitoring__metrics__query"),
        ("knowledge.documents.chunks.list", "ws_knowledge__documents__chunks__list"),
    ]
    for op_id, expected_tool_name in cases:
        tool_name = operation_id_to_tool_name(op_id)
        assert tool_name == expected_tool_name
        assert len(tool_name) <= 64
        reversed_op_id = tool_name_to_operation_id(tool_name)
        assert reversed_op_id == op_id


# ==============================================================================
# 4. search 和 describe 只能看到授权列表里的操作
# ==============================================================================


@pytest.mark.asyncio
async def test_search_and_describe_isolated_to_authorized():
    ops = [
        _make_op("bot.list", domain="bot", summary="List chat bots", risk="read"),
        _make_op("bot.create", domain="bot", summary="Create a new bot", risk="write"),
        _make_op("stats.basic", domain="stats", summary="Basic metrics and counts", risk="read"),
    ]
    ctx = _make_ctx(workspace_ops=ops, config={"workspace-direct-threshold": 1})  # force progressive
    mgr = await WorkspaceToolsManager.discover(Mock(), ctx)
    assert mgr.mode == "progressive"

    # Search by keyword in authorized operations
    search_res = mgr.execute_search(query="bot")
    assert len(search_res) == 2
    assert {r["id"] for r in search_res} == {"bot.list", "bot.create"}
    assert all(set(r.keys()) == {"id", "summary", "risk"} for r in search_res)

    # Search for an unauthorized domain/operation returns empty
    search_unauthorized = mgr.execute_search(query="pipeline")
    assert search_unauthorized == []

    # Describe authorized operation
    desc_ok = mgr.execute_describe("bot.list")
    assert desc_ok["id"] == "bot.list"
    assert "description" in desc_ok
    assert desc_ok["risk"] == "read"
    assert "input_schema" in desc_ok

    # Describe unauthorized operation returns error
    desc_err = mgr.execute_describe("pipeline.update")
    assert "error" in desc_err
    assert "not found or not authorized" in desc_err["error"]


# ==============================================================================
# 5. call 能把参数正确透传给 SDK (直接模式与渐进模式)
# ==============================================================================


@pytest.mark.asyncio
async def test_direct_mode_call_passthrough():
    ops = [_make_op("bot.list", input_schema={"type": "object", "properties": {"limit": {"type": "integer"}}})]
    ctx = _make_ctx(workspace_ops=ops)
    api = Mock()
    api.workspace = Mock()
    api.workspace.call = AsyncMock(return_value={"ok": True, "result": {"items": ["b1", "b2"]}})

    mgr = await WorkspaceToolsManager.discover(api, ctx)
    res = await mgr.execute(api, "ws_bot__list", {"limit": 10})

    assert res["ok"] is True
    assert res["result"] == {"items": ["b1", "b2"]}
    api.workspace.call.assert_awaited_once_with("bot.list", limit=10)


@pytest.mark.asyncio
async def test_progressive_mode_call_passthrough():
    ops = [_make_op(f"op_{i}.action") for i in range(10)]
    target_op = ops[0].id
    ctx = _make_ctx(workspace_ops=ops)
    api = Mock()
    api.workspace = Mock()
    api.workspace.call = AsyncMock(return_value={"ok": True, "result": {"status": "created"}})

    mgr = await WorkspaceToolsManager.discover(api, ctx)

    # Calling via workspace_call with nested arguments
    res = await mgr.execute(
        api,
        "workspace_call",
        {"operation_id": target_op, "arguments": {"name": "test_bot"}},
    )
    assert res["ok"] is True
    api.workspace.call.assert_awaited_once_with(target_op, name="test_bot")

    # Calling an unauthorized operation is blocked locally
    res_unauth = await mgr.execute(
        api,
        "workspace_call",
        {"operation_id": "unauthorized.dangerous.delete", "arguments": {}},
    )
    assert res_unauth["ok"] is False
    assert res_unauth["error"]["code"] == "not_authorized"


# ==============================================================================
# 6. 结果超长时被截断并给出提示
# ==============================================================================


@pytest.mark.asyncio
async def test_large_result_truncated_with_hint():
    ops = [_make_op("stats.large")]
    ctx = _make_ctx(workspace_ops=ops)
    api = Mock()
    api.workspace = Mock()
    # Massive payload > 20000 chars
    huge_payload = {"ok": True, "data": "X" * 30000}
    api.workspace.call = AsyncMock(return_value=huge_payload)

    mgr = await WorkspaceToolsManager.discover(api, ctx)
    res = await mgr.execute(api, "ws_stats__large", {}, max_result_chars=1000)

    assert res["ok"] is True
    assert res["truncated"] is True
    assert "preview" in res
    assert "hint" in res
    assert "分页或过滤参数缩小结果" in res["hint"]


# ==============================================================================
# 7. 与原有工具同名时，以原有工具为准，并记录 warning
# ==============================================================================


@pytest.mark.asyncio
async def test_tool_name_conflict_resolution(caplog):
    ops = [_make_op("bot.list")]  # direct name: ws_bot__list
    ctx = _make_ctx(workspace_ops=ops)
    api = Mock()

    mgr = await WorkspaceToolsManager.discover(api, ctx)
    assert len(mgr.tools) == 1
    assert mgr.tools[0].name == "ws_bot__list"

    # Suppose host already has a tool named ws_bot__list
    existing_tools = {"ws_bot__list", "bash", "grep"}
    with caplog.at_level("WARNING"):
        mgr.resolve_conflicts(existing_tools)

    # Workspace tool should be dropped
    assert len(mgr.tools) == 0
    assert any("conflicts with existing tool" in rec.message for rec in caplog.records)


# ==============================================================================
# 8. SDK 不支持时，自动降级为原有行为
# ==============================================================================


@pytest.mark.asyncio
async def test_sdk_unsupported_graceful_degradation():
    ctx = _make_ctx(workspace_ops=None)
    # API has no workspace attribute at all
    api_without_workspace = Mock(spec=[])

    mgr = await WorkspaceToolsManager.discover(api_without_workspace, ctx)
    assert mgr.mode is None
    assert len(mgr.tools) == 0
    assert mgr.build_system_message() is None


# ==============================================================================
# 9. ok: false 时把错误原样返回给模型，不重试写操作
# ==============================================================================


@pytest.mark.asyncio
async def test_ok_false_returned_verbatim():
    ops = [_make_op("bot.delete", risk="dangerous")]
    ctx = _make_ctx(workspace_ops=ops)
    api = Mock()
    api.workspace = Mock()
    api.workspace.call = AsyncMock(
        return_value={
            "ok": False,
            "error": {"code": "not_found", "message": "Bot does not exist"},
        }
    )

    mgr = await WorkspaceToolsManager.discover(api, ctx)
    res = await mgr.execute(api, "ws_bot__delete", {"uuid": "b-999"})

    assert res["ok"] is False
    assert res["error"]["code"] == "not_found"
    assert res["error"]["message"] == "Bot does not exist"


# ==============================================================================
# 10. LangBotToolExecutor 调度 workspace tools 验证
# ==============================================================================


@pytest.mark.asyncio
async def test_tool_executor_handles_workspace_tools():
    ops = [_make_op("bot.list")]
    ctx = _make_ctx(workspace_ops=ops)
    api = Mock()
    api.workspace = Mock()
    api.workspace.call = AsyncMock(return_value={"ok": True, "result": ["bot-1"]})

    mgr = await WorkspaceToolsManager.discover(api, ctx)
    executor = LangBotToolExecutor(
        api=api,
        allowed_tools={"ws_bot__list"},
        max_result_chars=20000,
        workspace_manager=mgr,
    )

    prep = executor.prepare(
        ToolCallRequest(
            id="call-1",
            name="ws_bot__list",
            arguments='{"limit": 5}',
        )
    )
    outcome = await executor.execute(prep)

    assert outcome.error is None
    assert outcome.result == {"ok": True, "result": ["bot-1"]}
    assert outcome.message is not None
    assert outcome.message.role == "tool"
    assert "bot-1" in outcome.message.content


# ==============================================================================
# 11. 追踪与可观测性（_TracedRunAPI 队列事件）
# ==============================================================================


@pytest.mark.asyncio
async def test_tool_executor_emits_traced_run_api_events():
    """Verify that when api is wrapped by _TracedRunAPI (having _results queue and _run_id),
    executing a workspace tool emits tool_call_started and tool_call_completed events to the queue.
    """
    ops = [_make_op("bot.list", summary="List bots")]
    ctx = _make_ctx(workspace_ops=ops)
    api = Mock()
    api.workspace = Mock()
    api.workspace.call = AsyncMock(return_value={"ok": True, "result": ["bot-1"]})

    # Simulate _TracedRunAPI wrapper probe
    results_queue = asyncio.Queue()
    api._results = results_queue
    api._run_id = "test-run-trace-123"

    mgr = await WorkspaceToolsManager.discover(api, ctx)
    executor = LangBotToolExecutor(
        api=api,
        allowed_tools={"ws_bot__list"},
        max_result_chars=20000,
        workspace_manager=mgr,
    )

    prep = executor.prepare(
        ToolCallRequest(
            id="call-trace-1",
            name="ws_bot__list",
            arguments='{"limit": 5}',
        )
    )
    outcome = await executor.execute(prep)
    assert outcome.error is None

    # Verify queue received 2 events (started and completed)
    assert results_queue.qsize() == 2
    started = await results_queue.get()
    completed = await results_queue.get()

    assert started.type == RunnerResultType.TOOL_CALL_STARTED
    assert started.run_id == "test-run-trace-123"
    assert started.data["tool_name"] == "ws_bot__list"
    assert started.data["parameters"] == {"limit": 5}

    assert completed.type == RunnerResultType.TOOL_CALL_COMPLETED
    assert completed.run_id == "test-run-trace-123"
    assert completed.data["tool_name"] == "ws_bot__list"
    assert completed.data["result"] == {"ok": True, "result": ["bot-1"]}


# ==============================================================================
# 12. 超长操作名哈希后缀与保留参数校验
# ==============================================================================


def test_long_operation_id_hashing():
    """Verify operation ID > 64 chars uses a stable 8-char SHA256 suffix bounded <= 64."""
    very_long_op = "pipeline.very_long_domain_name.subdomain_action_that_exceeds_sixty_four_characters_easily"
    tool_name = operation_id_to_tool_name(very_long_op)
    assert len(tool_name) <= 64
    assert tool_name.startswith("ws_")
    expected_digest = hashlib.sha256(very_long_op.encode("utf-8")).hexdigest()[:8]
    assert tool_name.endswith(expected_digest)


@pytest.mark.asyncio
async def test_reserved_argument_conflict_check():
    """Verify that passing 'operation_id' or '_timeout' inside arguments returns invalid_argument error."""
    ops = [_make_op("bot.list")]
    ctx = _make_ctx(workspace_ops=ops)
    api = Mock()
    api.workspace = Mock()

    mgr = await WorkspaceToolsManager.discover(api, ctx)
    res = await mgr.execute(api, "ws_bot__list", {"operation_id": "malicious", "limit": 1})
    assert res["ok"] is False
    assert res["error"]["code"] == "invalid_argument"
    assert "reserved parameter" in res["error"]["message"]


@pytest.mark.asyncio
async def test_sdk_0719_graceful_degradation_without_workspace_attr():
    """Verify that when running on 0.7.19 where resources has no workspace_operations
    and api has no workspace attribute, discovery gracefully returns mode=None and 0 tools."""
    api_0719 = Mock(spec=["call_tool", "get_allowed_tools"])
    ctx_0719 = make_context(
        run_id="run-0719",
        input_text="hello",
        resources=AgentResources(
            models=[ModelResource(model_id="primary", model_name="Primary")],
            tools=[],
        ),
    )
    if hasattr(ctx_0719.resources, "workspace_operations"):
        delattr(ctx_0719.resources, "workspace_operations")

    mgr = await WorkspaceToolsManager.discover(api_0719, ctx_0719)
    assert mgr.mode is None
    assert len(mgr.tools) == 0
    assert mgr.build_system_message() is None


# ==============================================================================
# 13. 端到端本地运行记录：直接模式与渐进模式（真实 Core Catalog 元数据）
# ==============================================================================


@pytest.mark.asyncio
async def test_e2e_direct_mode_agent_run():
    """Simulated local agent run in direct mode with real Core catalog metadata."""
    ops = [
        _make_op(
            "bot.list",
            summary="List all configured chat bots in the workspace.",
            description=(
                "Retrieve all configured chat bots in the workspace with basic settings, "
                "adapter types, and pipeline bindings. Set include_secret=True to include credentials."
            ),
            risk="read",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "include_secret": {"type": "boolean"},
                },
            },
        ),
        _make_op(
            "stats.basic",
            summary="Get workspace overview counters for bots, models, and pipelines.",
            description="Retrieve aggregate workspace statistics including total bot count, active pipelines, configured models, and knowledge bases.",
            risk="read",
        ),
    ]
    ctx = _make_ctx(workspace_ops=ops)

    api = FakeRunnerAPIProxy(
        models=[ModelResource(model_id="primary-model", model_name="Primary")],
        tools=[],
    )
    api.get_prompt = AsyncMock(return_value=[{"role": "system", "content": "You are a test assistant."}])
    api.workspace = Mock()
    api.workspace.call = AsyncMock(
        return_value={"ok": True, "result": [{"id": "bot-1", "name": "SupportBot"}, {"id": "bot-2", "name": "DocsBot"}]}
    )

    turn_1_msg = Message(
        role="assistant",
        content="I will check the bots.",
        tool_calls=[
            {
                "id": "call-bot-list-1",
                "type": "function",
                "function": {"name": "ws_bot__list", "arguments": '{"limit": 10}'},
            }
        ],
    )
    turn_2_msg = Message(
        role="assistant",
        content="There are 2 bots in this workspace:\n1. SupportBot (ID: bot-1)\n2. DocsBot (ID: bot-2)",
    )

    call_count = 0

    async def mock_invoke(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return turn_1_msg
        return turn_2_msg

    api.invoke_llm = AsyncMock(side_effect=mock_invoke)
    if hasattr(api, "invoke_llm_with_usage"):
        delattr(api, "invoke_llm_with_usage")

    runner = DefaultRunner()
    runner.get_run_api = lambda _c: api
    results = []
    async for item in runner.run(ctx):
        results.append(item)

    tool_started = [r for r in results if r.type == RunnerResultType.TOOL_CALL_STARTED]
    tool_completed = [r for r in results if r.type == RunnerResultType.TOOL_CALL_COMPLETED]
    msg_completed = [r for r in results if r.type == RunnerResultType.MESSAGE_COMPLETED]
    run_completed = [r for r in results if r.type == RunnerResultType.RUN_COMPLETED]

    assert len(tool_started) == 1
    assert tool_started[0].data["tool_name"] == "ws_bot__list"
    assert tool_started[0].data["parameters"] == {"limit": 10}

    assert len(tool_completed) == 1
    assert tool_completed[0].data["tool_name"] == "ws_bot__list"

    assert len(msg_completed) == 1
    assert "SupportBot" in msg_completed[0].data["message"]["content"]
    assert len(run_completed) == 1


@pytest.mark.asyncio
async def test_e2e_progressive_mode_agent_run():
    """Simulated local agent run in progressive mode with real Core catalog metadata."""
    ops = [
        _make_op(
            "pipeline.copy",
            domain="pipeline",
            summary="Duplicate an existing pipeline to create a new copy.",
            description="Clone an existing pipeline definition under a new identifier. Prerequisites: Call pipeline.list to obtain source pipeline_uuid. Side effect: Creates duplicate pipeline.",
            risk="write",
            input_schema={
                "type": "object",
                "properties": {
                    "pipeline_uuid": {"type": "string"},
                    "new_name": {"type": "string"},
                },
                "required": ["pipeline_uuid"],
            },
        ),
        _make_op(
            "pipeline.delete",
            domain="pipeline",
            summary="Permanently delete a pipeline from the workspace.",
            description="Delete a processing pipeline and disconnect it from associated bots. Prerequisites: Call pipeline.list to obtain pipeline_uuid. Side effect: Irreversible removal of pipeline.",
            risk="dangerous",
            input_schema={
                "type": "object",
                "properties": {
                    "pipeline_uuid": {"type": "string"},
                },
                "required": ["pipeline_uuid"],
            },
        ),
        _make_op("pipeline.list", summary="List all processing pipelines in the workspace.", risk="read"),
        _make_op("pipeline.get", summary="Get pipeline details and flow configuration.", risk="read"),
        _make_op("pipeline.create", summary="Create a new processing pipeline.", risk="write"),
        _make_op("bot.list", summary="List all configured chat bots.", risk="read"),
        _make_op("bot.create", summary="Create a new bot.", risk="write"),
        _make_op("bot.delete", summary="Delete a bot from the workspace.", risk="dangerous"),
        _make_op("knowledge.list", summary="List all knowledge bases.", risk="read"),
        _make_op("model.llm.list", summary="List configured language models.", risk="read"),
    ]
    ctx = _make_ctx(workspace_ops=ops)

    api = FakeRunnerAPIProxy(
        models=[ModelResource(model_id="primary-model", model_name="Primary")],
        tools=[],
    )
    api.get_prompt = AsyncMock(return_value=[{"role": "system", "content": "You are a test assistant."}])
    api.workspace = Mock()

    async def mock_call(operation_id, **arguments):
        if operation_id == "pipeline.copy":
            return {"ok": True, "result": {"pipeline_uuid": "pipe-copy-uuid", "name": "pipe-prod-copy"}}
        elif operation_id == "pipeline.delete":
            return {"ok": True, "result": {"deleted": True}}
        return {"ok": True}

    api.workspace.call = AsyncMock(side_effect=mock_call)

    # 4-turn progressive execution:
    turn_1 = Message(
        role="assistant",
        content="Searching operations...",
        tool_calls=[
            {
                "id": "c-1",
                "type": "function",
                "function": {"name": "workspace_search", "arguments": '{"query": "copy", "domain": "pipeline"}'},
            }
        ],
    )
    turn_2 = Message(
        role="assistant",
        content="Describing schema...",
        tool_calls=[
            {
                "id": "c-2",
                "type": "function",
                "function": {"name": "workspace_describe", "arguments": '{"operation_id": "pipeline.copy"}'},
            }
        ],
    )
    turn_3 = Message(
        role="assistant",
        content="Calling operation...",
        tool_calls=[
            {
                "id": "c-3",
                "type": "function",
                "function": {
                    "name": "workspace_call",
                    "arguments": '{"operation_id": "pipeline.copy", "arguments": {"pipeline_uuid": "pipe-prod-uuid", "new_name": "pipe-prod-copy"}}',
                },
            }
        ],
    )
    turn_4 = Message(
        role="assistant",
        content="Pipeline copy created successfully: pipe-prod-copy (UUID: pipe-copy-uuid).",
    )

    turns = [turn_1, turn_2, turn_3, turn_4]
    turn_idx = 0

    async def mock_invoke(**kwargs):
        nonlocal turn_idx
        idx = min(turn_idx, len(turns) - 1)
        turn_idx += 1
        return turns[idx]

    api.invoke_llm = AsyncMock(side_effect=mock_invoke)
    if hasattr(api, "invoke_llm_with_usage"):
        delattr(api, "invoke_llm_with_usage")

    runner = DefaultRunner()
    runner.get_run_api = lambda _c: api
    results = []
    async for item in runner.run(ctx):
        results.append(item)

    tool_started = [r for r in results if r.type == RunnerResultType.TOOL_CALL_STARTED]
    tool_completed = [r for r in results if r.type == RunnerResultType.TOOL_CALL_COMPLETED]
    msg_completed = [r for r in results if r.type == RunnerResultType.MESSAGE_COMPLETED]
    run_completed = [r for r in results if r.type == RunnerResultType.RUN_COMPLETED]

    called_tool_names = [t.data["tool_name"] for t in tool_started]
    assert called_tool_names == ["workspace_search", "workspace_describe", "workspace_call"]
    assert len(tool_completed) == 3
    assert len(msg_completed) == 1
    assert "pipe-copy-uuid" in msg_completed[0].data["message"]["content"]
    assert len(run_completed) == 1
