"""Workflow debug execution support.

This module provides debugging capabilities for workflow execution, including:
- ExecutionLog: Structured log entries for execution tracking
- DebugExecutionState: State management for debug sessions (pause, resume, breakpoints)
- DebugWorkflowExecutor: Extended executor with step-by-step debugging support
"""

from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from .entities import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    ExecutionContext,
    ExecutionStatus,
    NodeState,
    NodeStatus,
)
from .executor import WorkflowExecutor

if TYPE_CHECKING:
    from ..core import app

logger = logging.getLogger(__name__)


class ExecutionLog:
    """Execution log entry"""

    def __init__(self, level: str, message: str, node_id: Optional[str] = None, data: Optional[dict] = None):
        self.id = str(uuid.uuid4())
        self.timestamp = datetime.now().isoformat()
        self.level = level
        self.message = message
        self.node_id = node_id
        self.data = data or {}

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'level': self.level,
            'message': self.message,
            'node_id': self.node_id,
            'data': self.data,
        }


class DebugExecutionState:
    """State for a debug execution"""

    def __init__(self, execution_id: str, breakpoints: list[str] = None):
        self.execution_id = execution_id
        self.status: str = 'running'
        self.is_paused: bool = False
        self.is_stopped: bool = False
        self.current_node_id: Optional[str] = None
        self.breakpoints: set[str] = set(breakpoints or [])
        self.logs: list[ExecutionLog] = []
        self.pending_logs: list[ExecutionLog] = []
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Initially not paused
        self._stop_event = asyncio.Event()

    def add_log(self, level: str, message: str, node_id: str = None, data: dict = None):
        """Add a log entry"""
        log = ExecutionLog(level, message, node_id, data)
        self.logs.append(log)
        self.pending_logs.append(log)
        logger.log(
            getattr(logging, level.upper(), logging.INFO),
            f'[Workflow Debug] {message}',
            extra={'node_id': node_id, 'data': data},
        )

    def get_pending_logs(self) -> list[dict]:
        """Get and clear pending logs"""
        logs = [log.to_dict() for log in self.pending_logs]
        self.pending_logs = []
        return logs

    def pause(self):
        """Pause execution"""
        self.is_paused = True
        self._pause_event.clear()
        self.add_log('info', 'Execution paused')

    def resume(self):
        """Resume execution"""
        self.is_paused = False
        self._pause_event.set()
        self.add_log('info', 'Execution resumed')

    def stop(self):
        """Stop execution"""
        self.is_stopped = True
        self.status = 'cancelled'
        self._stop_event.set()
        self._pause_event.set()  # Release any pause
        self.add_log('info', 'Execution stopped')

    async def wait_if_paused(self):
        """Wait if execution is paused"""
        if self.is_paused:
            self.add_log('info', 'Waiting for resume...')
            await self._pause_event.wait()

    def check_breakpoint(self, node_id: str) -> bool:
        """Check if there's a breakpoint at the given node"""
        return node_id in self.breakpoints


class DebugWorkflowExecutor(WorkflowExecutor):
    """
    Debug-enabled workflow executor with step-by-step execution support.
    Extends WorkflowExecutor with debugging capabilities.
    """

    # Class-level storage for active debug sessions
    _debug_states: dict[str, DebugExecutionState] = {}

    def __init__(self, ap: Optional['app.Application'] = None):
        super().__init__(ap)

    @classmethod
    def get_debug_state(cls, execution_id: str) -> Optional[DebugExecutionState]:
        """Get debug state for an execution"""
        return cls._debug_states.get(execution_id)

    @classmethod
    def create_debug_state(cls, execution_id: str, breakpoints: list[str] = None) -> DebugExecutionState:
        """Create a new debug state"""
        state = DebugExecutionState(execution_id, breakpoints)
        cls._debug_states[execution_id] = state
        return state

    @classmethod
    def remove_debug_state(cls, execution_id: str):
        """Remove debug state for an execution"""
        cls._debug_states.pop(execution_id, None)

    async def execute_debug(
        self,
        workflow: WorkflowDefinition,
        context: ExecutionContext,
        debug_state: DebugExecutionState,
    ) -> ExecutionContext:
        """
        Execute a workflow in debug mode.

        Args:
            workflow: Workflow definition
            context: Execution context
            debug_state: Debug execution state

        Returns:
            Updated execution context
        """
        context.status = ExecutionStatus.RUNNING
        context.start_time = datetime.now()
        debug_state.add_log('info', f'Starting debug execution for workflow: {workflow.name}')

        try:
            # Build execution graph
            node_map = {node.id: node for node in workflow.nodes}
            edge_map = self._build_edge_map(workflow.edges)
            self._edges = workflow.edges

            # Initialize node states
            for node in workflow.nodes:
                if node.id not in context.node_states:
                    context.node_states[node.id] = NodeState(node_id=node.id)

            # Find start node(s)
            start_nodes = self._find_start_nodes(workflow.nodes, workflow.edges)

            if not start_nodes:
                raise ValueError('No start nodes found in workflow')

            debug_state.add_log('info', f'Found {len(start_nodes)} start node(s)')

            # Execute from start nodes
            for start_node in start_nodes:
                if debug_state.is_stopped:
                    break

                await self._execute_debug_from_node(
                    start_node, node_map, edge_map, context, debug_state, workflow.settings.max_retries
                )

            # Set final status
            if debug_state.is_stopped:
                context.status = ExecutionStatus.CANCELLED
                debug_state.status = 'cancelled'
            else:
                all_completed = all(
                    state.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED) for state in context.node_states.values()
                )

                if all_completed:
                    context.status = ExecutionStatus.COMPLETED
                    debug_state.status = 'completed'
                    debug_state.add_log('info', 'Workflow execution completed successfully')
                else:
                    has_failed = any(state.status == NodeStatus.FAILED for state in context.node_states.values())
                    if has_failed:
                        context.status = ExecutionStatus.FAILED
                        debug_state.status = 'error'

        except Exception as e:
            context.status = ExecutionStatus.FAILED
            context.error = str(e)
            debug_state.status = 'error'
            debug_state.add_log('error', f'Workflow execution failed: {e}', data={'traceback': traceback.format_exc()})
            logger.error(f'Debug workflow execution failed: {e}\n{traceback.format_exc()}')

        finally:
            context.end_time = datetime.now()

        return context

    async def _execute_debug_from_node(
        self,
        node: NodeDefinition,
        node_map: dict[str, NodeDefinition],
        edge_map: dict[str, list[EdgeDefinition]],
        context: ExecutionContext,
        debug_state: DebugExecutionState,
        max_retries: int = 3,
    ):
        """Execute workflow from a node with debug support"""

        # Check if stopped
        if debug_state.is_stopped:
            return

        # Wait if paused
        await debug_state.wait_if_paused()

        # Check if should skip
        if await self._should_skip_node(node, context):
            if context.node_states[node.id].status == NodeStatus.SKIPPED:
                debug_state.add_log('info', f'Skipping node: {node.id}', node_id=node.id)
            return

        # Check breakpoint
        if debug_state.check_breakpoint(node.id):
            debug_state.add_log('info', f'Hit breakpoint at node: {node.id}', node_id=node.id)
            debug_state.pause()
            await debug_state.wait_if_paused()

        # Update current node
        debug_state.current_node_id = node.id
        debug_state.add_log('info', f'Executing node: {node.id} ({node.type})', node_id=node.id)

        # Execute node
        await self._execute_debug_node(node, context, debug_state, max_retries)

        # Check if stopped or failed
        if debug_state.is_stopped:
            return
        if context.node_states[node.id].status == NodeStatus.FAILED:
            return

        # Get outgoing edges
        outgoing_edges = edge_map.get(node.id, [])

        # Execute next nodes
        for edge in outgoing_edges:
            if debug_state.is_stopped:
                break

            target_node = node_map.get(edge.target_node)
            if not target_node:
                continue

            # Check edge condition
            if edge.condition:
                condition_met = await self._evaluate_condition(edge.condition, context)
                if not condition_met:
                    debug_state.add_log('debug', f'Edge condition not met: {edge.condition}', node_id=node.id)
                    continue

            # Check if all inputs are ready
            if await self._inputs_ready(target_node, edge_map, context):
                await self._execute_debug_from_node(target_node, node_map, edge_map, context, debug_state, max_retries)

    async def _execute_debug_node(
        self, node: NodeDefinition, context: ExecutionContext, debug_state: DebugExecutionState, max_retries: int = 3
    ):
        """Execute a single node with debug logging"""

        node_state = context.node_states[node.id]
        node_state.status = NodeStatus.RUNNING
        node_state.start_time = datetime.now()

        # Get node instance (pass ap for access to services)
        node_instance = self.registry.create_instance(node.type, node.id, node.config, ap=self.ap)

        if not node_instance:
            node_state.status = NodeStatus.FAILED
            node_state.error = f'Unknown node type: {node.type}'
            node_state.end_time = datetime.now()
            debug_state.add_log('error', f'Unknown node type: {node.type}', node_id=node.id)
            self._record_execution_step(node, node_state, context)
            await self._persist_node_execution(node, node_state, context)
            return

        # Resolve inputs
        inputs = await self._resolve_inputs(node, context)
        node_state.inputs = inputs
        debug_state.add_log(
            'debug', 'Node inputs resolved', node_id=node.id, data={'inputs': self._safe_serialize(inputs)}
        )

        # Validate inputs
        validation_errors = await node_instance.validate_inputs(inputs)
        if validation_errors:
            node_state.status = NodeStatus.FAILED
            node_state.error = '; '.join(validation_errors)
            node_state.end_time = datetime.now()
            debug_state.add_log('error', f'Input validation failed: {node_state.error}', node_id=node.id)
            self._record_execution_step(node, node_state, context)
            await self._persist_node_execution(node, node_state, context)
            return

        # Execute with retries
        for attempt in range(max_retries + 1):
            if debug_state.is_stopped:
                node_state.status = NodeStatus.FAILED
                node_state.error = 'Execution stopped'
                node_state.end_time = datetime.now()
                break

            try:
                outputs = await node_instance.execute(inputs, context)
                node_state.outputs = outputs
                node_state.status = NodeStatus.COMPLETED
                node_state.end_time = datetime.now()

                duration_ms = int((node_state.end_time - node_state.start_time).total_seconds() * 1000)
                debug_state.add_log(
                    'info',
                    f'Node completed in {duration_ms}ms',
                    node_id=node.id,
                    data={'outputs': self._safe_serialize(outputs), 'duration_ms': duration_ms},
                )
                break

            except Exception as e:
                node_state.retry_count = attempt + 1
                debug_state.add_log(
                    'warning', f'Node execution failed (attempt {attempt + 1}/{max_retries + 1}): {e}', node_id=node.id
                )

                if attempt < max_retries:
                    await asyncio.sleep(1)
                else:
                    node_state.status = NodeStatus.FAILED
                    node_state.error = str(e)
                    node_state.end_time = datetime.now()
                    debug_state.add_log(
                        'error',
                        f'Node failed after {max_retries + 1} attempts: {e}',
                        node_id=node.id,
                        data={'error': str(e), 'traceback': traceback.format_exc()},
                    )

        self._record_execution_step(node, node_state, context)
        await self._persist_node_execution(node, node_state, context)

    async def step_execute(
        self,
        workflow: WorkflowDefinition,
        context: ExecutionContext,
        debug_state: DebugExecutionState,
    ) -> dict:
        """
        Execute one step (one node) in debug mode.

        Returns:
            Dict with node_id, node_state, and completed status
        """
        # Find next node to execute
        next_node = self._find_next_executable_node(workflow, context)

        if not next_node:
            debug_state.status = 'completed'
            return {'completed': True}

        # Execute single node
        debug_state.current_node_id = next_node.id
        await self._execute_debug_node(next_node, context, debug_state, workflow.settings.max_retries)

        node_state = context.node_states.get(next_node.id)

        # Check if workflow is complete
        all_done = all(
            state.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED, NodeStatus.FAILED)
            for state in context.node_states.values()
        )

        if all_done:
            debug_state.status = 'completed'
            context.status = ExecutionStatus.COMPLETED

        return {
            'node_id': next_node.id,
            'node_state': {
                'status': node_state.status.value if node_state else 'unknown',
                'inputs': self._safe_serialize(node_state.inputs) if node_state else {},
                'outputs': self._safe_serialize(node_state.outputs) if node_state else {},
                'error': node_state.error if node_state else None,
            },
            'completed': all_done,
        }

    def _find_next_executable_node(
        self, workflow: WorkflowDefinition, context: ExecutionContext
    ) -> Optional[NodeDefinition]:
        """Find the next node that can be executed"""
        edge_map = self._build_edge_map(workflow.edges)

        for node in workflow.nodes:
            state = context.node_states.get(node.id)

            # Skip completed, running, or failed nodes
            if state and state.status in (
                NodeStatus.COMPLETED,
                NodeStatus.RUNNING,
                NodeStatus.FAILED,
                NodeStatus.SKIPPED,
            ):
                continue

            # Check if this node's inputs are ready
            incoming_nodes = set()
            for source_id, edges in edge_map.items():
                for edge in edges:
                    if edge.target_node == node.id:
                        incoming_nodes.add(source_id)

            # If no incoming nodes, it's a start node
            if not incoming_nodes:
                return node

            # Check if all incoming nodes are done
            all_incoming_done = True
            for source_id in incoming_nodes:
                source_state = context.node_states.get(source_id)
                if not source_state or source_state.status not in (NodeStatus.COMPLETED, NodeStatus.SKIPPED):
                    all_incoming_done = False
                    break

            if all_incoming_done:
                return node

        return None

    def _safe_serialize(self, data: Any) -> Any:
        """Safely serialize data for logging"""
        if data is None:
            return None
        if isinstance(data, (str, int, float, bool)):
            return data
        if isinstance(data, (list, tuple)):
            return [self._safe_serialize(item) for item in data[:100]]  # Limit list size
        if isinstance(data, dict):
            result = {}
            for key, value in list(data.items())[:50]:  # Limit dict size
                result[str(key)] = self._safe_serialize(value)
            return result
        # For complex objects, try to convert to string
        try:
            return str(data)[:1000]  # Limit string length
        except Exception:
            return '<non-serializable>'

    def get_execution_state(self, context: ExecutionContext, debug_state: DebugExecutionState) -> dict:
        """Get current execution state for API response"""
        node_states = {}
        for node_id, state in context.node_states.items():
            node_states[node_id] = {
                'status': state.status.value,
                'inputs': self._safe_serialize(state.inputs),
                'outputs': self._safe_serialize(state.outputs),
                'error': state.error,
                'startTime': state.start_time.isoformat() if state.start_time else None,
                'endTime': state.end_time.isoformat() if state.end_time else None,
                'duration': int((state.end_time - state.start_time).total_seconds() * 1000)
                if state.start_time and state.end_time
                else None,
            }

        return {
            'status': debug_state.status,
            'current_node_id': debug_state.current_node_id,
            'node_states': node_states,
            'new_logs': debug_state.get_pending_logs(),
            'error': context.error,
        }
