"""Tests for the workflow execution engine."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from langbot.pkg.workflow.entities import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    ExecutionContext,
    ExecutionStatus,
    NodeStatus,
    MessageContext,
)
from langbot.pkg.workflow.executor import WorkflowExecutor, LoopExecutor
from langbot.pkg.workflow.node import WorkflowNode, NodePort
from langbot.pkg.workflow.registry import NodeTypeRegistry


# ── Test helpers ─────────────────────────────────────────────────────

class PassthroughNode(WorkflowNode):
    """Simple node that passes input to output."""
    type_name = "passthrough"
    category = "process"

    async def execute(self, inputs, context):
        return {"output": inputs.get("input", "default")}


class FailingNode(WorkflowNode):
    """Node that always fails."""
    type_name = "failing"
    category = "process"

    async def execute(self, inputs, context):
        raise RuntimeError("intentional failure")


class AccumulatorNode(WorkflowNode):
    """Node that appends its id to a context variable for tracking execution order."""
    type_name = "accumulator"
    category = "process"

    async def execute(self, inputs, context):
        order = context.variables.get("_exec_order", [])
        order.append(self.node_id)
        context.variables["_exec_order"] = order
        return {"output": self.node_id}


class ConditionTrueNode(WorkflowNode):
    """Node that outputs a truthy value."""
    type_name = "cond_true"
    category = "control"

    async def execute(self, inputs, context):
        return {"result": True}


def _make_registry(*node_classes) -> NodeTypeRegistry:
    """Create a fresh registry with given node classes."""
    reg = NodeTypeRegistry()
    for cls in node_classes:
        cat = getattr(cls, 'category', 'process')
        reg.register(f"{cat}.{cls.type_name}", cls)
    return reg


def _make_context(workflow_id="wf-test") -> ExecutionContext:
    return ExecutionContext(
        execution_id="exec-test",
        workflow_id=workflow_id,
    )


def _node(id: str, type: str, config=None) -> NodeDefinition:
    return NodeDefinition(id=id, type=type, config=config or {})


def _edge(id: str, src: str, tgt: str, condition=None) -> EdgeDefinition:
    return EdgeDefinition(
        id=id, source_node=src, target_node=tgt, condition=condition
    )


# ── Tests ────────────────────────────────────────────────────────────

class TestLinearWorkflow:
    """Test simple linear A → B → C workflows."""

    @pytest.mark.asyncio
    async def test_single_node(self):
        reg = _make_registry(PassthroughNode)
        executor = WorkflowExecutor()
        executor.registry = reg

        wf = WorkflowDefinition(
            uuid="wf-1", name="test",
            nodes=[_node("n1", "process.passthrough")],
            edges=[],
        )
        ctx = _make_context()
        result = await executor.execute(wf, ctx)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.node_states["n1"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_two_node_chain(self):
        reg = _make_registry(AccumulatorNode)
        executor = WorkflowExecutor()
        executor.registry = reg

        wf = WorkflowDefinition(
            uuid="wf-2", name="test",
            nodes=[
                _node("a", "process.accumulator"),
                _node("b", "process.accumulator"),
            ],
            edges=[_edge("e1", "a", "b")],
        )
        ctx = _make_context()
        result = await executor.execute(wf, ctx)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.variables["_exec_order"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_three_node_chain(self):
        reg = _make_registry(AccumulatorNode)
        executor = WorkflowExecutor()
        executor.registry = reg

        wf = WorkflowDefinition(
            uuid="wf-3", name="test",
            nodes=[
                _node("a", "process.accumulator"),
                _node("b", "process.accumulator"),
                _node("c", "process.accumulator"),
            ],
            edges=[
                _edge("e1", "a", "b"),
                _edge("e2", "b", "c"),
            ],
        )
        ctx = _make_context()
        result = await executor.execute(wf, ctx)

        assert result.status == ExecutionStatus.COMPLETED
        assert result.variables["_exec_order"] == ["a", "b", "c"]


class TestFailureHandling:
    """Test node failure and retry behavior."""

    @pytest.mark.asyncio
    async def test_failing_node_marks_failed(self):
        reg = _make_registry(FailingNode)
        executor = WorkflowExecutor()
        executor.registry = reg

        wf = WorkflowDefinition(
            uuid="wf-fail", name="test",
            nodes=[_node("n1", "process.failing")],
            edges=[],
            settings={"max_retries": 0},
        )
        ctx = _make_context()
        result = await executor.execute(wf, ctx)

        assert result.status == ExecutionStatus.FAILED
        assert result.node_states["n1"].status == NodeStatus.FAILED
        assert "intentional failure" in result.node_states["n1"].error

    @pytest.mark.asyncio
    async def test_failure_stops_downstream(self):
        reg = _make_registry(FailingNode, AccumulatorNode)
        executor = WorkflowExecutor()
        executor.registry = reg

        wf = WorkflowDefinition(
            uuid="wf-stop", name="test",
            nodes=[
                _node("a", "process.failing"),
                _node("b", "process.accumulator"),
            ],
            edges=[_edge("e1", "a", "b")],
            settings={"max_retries": 0},
        )
        ctx = _make_context()
        result = await executor.execute(wf, ctx)

        assert result.node_states["a"].status == NodeStatus.FAILED
        # b should not have been executed
        assert result.node_states["b"].status == NodeStatus.PENDING


class TestConditionalEdges:
    """Test edge condition evaluation."""

    @pytest.mark.asyncio
    async def test_true_condition_passes(self):
        reg = _make_registry(AccumulatorNode)
        executor = WorkflowExecutor()
        executor.registry = reg

        wf = WorkflowDefinition(
            uuid="wf-cond", name="test",
            nodes=[
                _node("a", "process.accumulator"),
                _node("b", "process.accumulator"),
            ],
            edges=[_edge("e1", "a", "b", condition="1 == 1")],
        )
        ctx = _make_context()
        result = await executor.execute(wf, ctx)

        assert result.variables["_exec_order"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_false_condition_skips(self):
        reg = _make_registry(AccumulatorNode)
        executor = WorkflowExecutor()
        executor.registry = reg

        wf = WorkflowDefinition(
            uuid="wf-cond2", name="test",
            nodes=[
                _node("a", "process.accumulator"),
                _node("b", "process.accumulator"),
            ],
            edges=[_edge("e1", "a", "b", condition="1 == 2")],
        )
        ctx = _make_context()
        result = await executor.execute(wf, ctx)

        # Only a should execute; b is skipped because condition is false
        assert result.variables["_exec_order"] == ["a"]


class TestDiamondGraph:
    """Test diamond-shaped DAG: A → B, A → C, B → D, C → D."""

    @pytest.mark.asyncio
    async def test_diamond_executes_all(self):
        """D should execute once (not be skipped as circular)."""
        reg = _make_registry(AccumulatorNode)
        executor = WorkflowExecutor()
        executor.registry = reg

        wf = WorkflowDefinition(
            uuid="wf-diamond", name="test",
            nodes=[
                _node("a", "process.accumulator"),
                _node("b", "process.accumulator"),
                _node("c", "process.accumulator"),
                _node("d", "process.accumulator"),
            ],
            edges=[
                _edge("e1", "a", "b"),
                _edge("e2", "a", "c"),
                _edge("e3", "b", "d"),
                _edge("e4", "c", "d"),
            ],
        )
        ctx = _make_context()
        result = await executor.execute(wf, ctx)

        assert result.status == ExecutionStatus.COMPLETED
        # All four nodes should complete
        for nid in ["a", "b", "c", "d"]:
            assert result.node_states[nid].status == NodeStatus.COMPLETED


class TestUnknownNodeType:
    """Test handling of unregistered node types."""

    @pytest.mark.asyncio
    async def test_unknown_type_fails(self):
        reg = _make_registry()  # empty registry
        executor = WorkflowExecutor()
        executor.registry = reg

        wf = WorkflowDefinition(
            uuid="wf-unk", name="test",
            nodes=[_node("n1", "process.nonexistent")],
            edges=[],
        )
        ctx = _make_context()
        result = await executor.execute(wf, ctx)

        assert result.node_states["n1"].status == NodeStatus.FAILED
        assert "Unknown node type" in result.node_states["n1"].error


class TestMessageContext:
    """Test that message context is available to nodes."""

    @pytest.mark.asyncio
    async def test_message_context_in_inputs(self):
        reg = _make_registry(PassthroughNode)
        executor = WorkflowExecutor()
        executor.registry = reg

        wf = WorkflowDefinition(
            uuid="wf-msg", name="test",
            nodes=[_node("n1", "process.passthrough")],
            edges=[],
        )
        ctx = _make_context()
        ctx.message_context = MessageContext(
            message_id="msg-1",
            message_content="hello world",
            sender_id="user-1",
        )
        result = await executor.execute(wf, ctx)

        assert result.status == ExecutionStatus.COMPLETED
        # message_content should be in the resolved inputs
        n1_inputs = result.node_states["n1"].inputs
        assert n1_inputs.get("message_content") == "hello world"


class TestExecutionHistory:
    """Test that execution steps are recorded."""

    @pytest.mark.asyncio
    async def test_history_recorded(self):
        reg = _make_registry(AccumulatorNode)
        executor = WorkflowExecutor()
        executor.registry = reg

        wf = WorkflowDefinition(
            uuid="wf-hist", name="test",
            nodes=[
                _node("a", "process.accumulator"),
                _node("b", "process.accumulator"),
            ],
            edges=[_edge("e1", "a", "b")],
        )
        ctx = _make_context()
        result = await executor.execute(wf, ctx)

        assert len(result.history) == 2
        assert result.history[0].node_id == "a"
        assert result.history[1].node_id == "b"
        assert result.history[0].status == "completed"
