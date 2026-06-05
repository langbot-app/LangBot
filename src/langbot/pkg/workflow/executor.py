"""Workflow execution engine.

This module contains the core workflow execution logic:
- WorkflowExecutor: Main execution engine with control flow handling
- ParallelExecutor: Parallel branch execution
- LoopExecutor: Loop/iterator execution

Debug execution support has been moved to the ``debug`` module.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

import sqlalchemy

from .entities import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    ExecutionContext,
    ExecutionStatus,
    NodeState,
    NodeStatus,
    ExecutionStep,
)
from ..entity.persistence import workflow as persistence_workflow
from .registry import NodeTypeRegistry
from .safe_eval import safe_eval_with_vars

if TYPE_CHECKING:
    from ..core import app

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """
    Workflow execution engine.
    Handles the execution of workflow definitions with proper control flow.
    """

    def __init__(self, ap: Optional['app.Application'] = None):
        self.ap = ap
        self.registry = NodeTypeRegistry.instance()
        self._edges: list[EdgeDefinition] = []

    async def execute(
        self, workflow: WorkflowDefinition, context: ExecutionContext, start_node_id: Optional[str] = None
    ) -> ExecutionContext:
        """
        Execute a workflow.

        Args:
            workflow: Workflow definition
            context: Execution context
            start_node_id: Optional starting node (for resumption)

        Returns:
            Updated execution context
        """
        context.status = ExecutionStatus.RUNNING
        context.start_time = datetime.now()

        try:
            # Build execution graph
            node_map = {node.id: node for node in workflow.nodes}
            edge_map = self._build_edge_map(workflow.edges)
            self._edges = workflow.edges

            # Initialize node states
            for node in workflow.nodes:
                if node.id not in context.node_states:
                    context.node_states[node.id] = NodeState(node_id=node.id, node_type=node.type, status=NodeStatus.PENDING)

            # Find start node(s)
            if start_node_id:
                start_nodes = [node_map[start_node_id]]
            else:
                start_nodes = self._find_start_nodes(workflow.nodes, workflow.edges)

            if not start_nodes:
                raise ValueError('No start nodes found in workflow')

            # Execute from start nodes
            for start_node in start_nodes:
                await self._execute_from_node(
                    start_node, node_map, edge_map, context, workflow.settings.max_retries, path=set()
                )

            # Check final status
            all_completed = all(
                state.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED) for state in context.node_states.values()
            )

            if all_completed:
                context.status = ExecutionStatus.COMPLETED
            else:
                # Some nodes might still be waiting
                has_failed = any(state.status == NodeStatus.FAILED for state in context.node_states.values())
                if has_failed:
                    context.status = ExecutionStatus.FAILED

        except Exception as e:
            context.status = ExecutionStatus.FAILED
            context.error = str(e)
            logger.error(
                'Workflow execution failed',
                exc_info=True,
                extra={
                    'workflow_id': workflow.uuid,
                    'execution_id': context.execution_id,
                    'node_states': {
                        node_id: {
                            'status': state.status.value if state.status else None,
                            'error': state.error,
                        }
                        for node_id, state in context.node_states.items()
                    },
                },
            )

            # Note: Frontend panel logging has been removed.
            # A new solution will be implemented separately.

        finally:
            context.end_time = datetime.now()

            # Note: Frontend panel logging has been removed.
            # A new solution will be implemented separately.

        return context

    async def _execute_from_node(
        self,
        node: NodeDefinition,
        node_map: dict[str, NodeDefinition],
        edge_map: dict[str, list[EdgeDefinition]],
        context: ExecutionContext,
        max_retries: int = 3,
        path: set[str] | None = None,
    ):
        """Execute workflow starting from a specific node"""

        # Initialize path set for cycle detection (path-based, not global visited)
        if path is None:
            path = set()

        # Check for circular dependency on the *current path* only
        # This correctly allows diamond shapes (A→B, A→C, B→D, C→D)
        if node.id in path:
            logger.warning(f'Circular dependency detected at node: {node.id}')
            context.node_states[node.id].status = NodeStatus.SKIPPED
            context.node_states[node.id].error = 'Circular dependency detected'
            context.node_states[node.id].end_time = datetime.now()
            await self._persist_node_execution(node, context.node_states[node.id], context)
            return

        # Add node to current path
        path.add(node.id)

        # Check if node should be skipped
        if await self._should_skip_node(node, context):
            existing_state = context.node_states[node.id]
            if existing_state.status == NodeStatus.SKIPPED:
                existing_state.end_time = existing_state.end_time or datetime.now()
                await self._persist_node_execution(node, existing_state, context)
            path.discard(node.id)
            return

        # Execute current node
        await self._execute_node(node, context, max_retries)

        # If node failed and we should stop on error, return
        if context.node_states[node.id].status == NodeStatus.FAILED:
            path.discard(node.id)
            return

        node_state = context.node_states[node.id]
        node_type_name = node.type.split('.')[-1] if '.' in node.type else node.type

        # ── Control flow integration ────────────────────────────────
        # For loop / iterator nodes: run the LoopExecutor over
        # downstream body nodes for each item, then continue to the
        # "completed" output edge.
        if node_type_name in ('loop', 'iterator'):
            items = node_state.outputs.get('_items') or []
            if not items:
                # iterator: items come from inputs
                items = node_state.inputs.get('items', node_state.inputs.get('array', []))
                if not isinstance(items, list):
                    items = [items] if items else []
            max_iter = int(node.config.get('max_iterations', 100))
            items = items[:max_iter]

            # Collect downstream "body" nodes (connected via edges)
            outgoing_edges = edge_map.get(node.id, [])
            body_nodes = []
            for edge in outgoing_edges:
                target = node_map.get(edge.target_node)
                if target:
                    body_nodes.append(target)

            if body_nodes and items:
                loop_exec = LoopExecutor(self)
                results = await loop_exec.execute_loop(items, body_nodes, context, max_iter)
                node_state.outputs['results'] = results
                node_state.outputs['completed'] = True
            else:
                node_state.outputs['results'] = []
                node_state.outputs['completed'] = True

            path.discard(node.id)
            return  # body nodes already executed by LoopExecutor

        # For parallel nodes: run downstream branches concurrently
        if node_type_name == 'parallel':
            outgoing_edges = edge_map.get(node.id, [])
            branch_nodes = []
            for edge in outgoing_edges:
                target = node_map.get(edge.target_node)
                if target:
                    branch_nodes.append([target])

            if branch_nodes:
                par_exec = ParallelExecutor(self)
                results = await par_exec.execute_parallel(branch_nodes, context)
                node_state.outputs['results'] = results

            path.discard(node.id)
            return  # branch nodes already executed by ParallelExecutor

        # ── Standard edge-based continuation ────────────────────────
        # Get outgoing edges
        outgoing_edges = edge_map.get(node.id, [])

        # Execute next nodes based on edge conditions
        for edge in outgoing_edges:
            target_node = node_map.get(edge.target_node)
            if not target_node:
                continue

            # Check edge condition
            if edge.condition:
                condition_met = await self._evaluate_condition(edge.condition, context)
                if not condition_met:
                    continue

            # Check if all inputs are ready
            if await self._inputs_ready(target_node, edge_map, context):
                await self._execute_from_node(target_node, node_map, edge_map, context, max_retries, path)

        # Remove node from path when backtracking (allows diamond revisit)
        path.discard(node.id)

    async def _execute_node(self, node: NodeDefinition, context: ExecutionContext, max_retries: int = 3):
        """Execute a single node with retry logic"""

        node_state = context.node_states[node.id]
        node_state.status = NodeStatus.RUNNING
        node_state.start_time = datetime.now()

        # Get node instance (pass ap for access to services)
        node_instance = self.registry.create_instance(node.type, node.id, node.config, ap=self.ap)

        if not node_instance:
            node_state.status = NodeStatus.FAILED
            node_state.error = f'Unknown node type: {node.type}'
            node_state.end_time = datetime.now()
            self._record_execution_step(node, node_state, context)
            await self._persist_node_execution(node, node_state, context)
            return

        # Resolve inputs
        inputs = await self._resolve_inputs(node, context)
        node_state.inputs = inputs

        # Validate inputs
        validation_errors = await node_instance.validate_inputs(inputs)
        if validation_errors:
            node_state.status = NodeStatus.FAILED
            node_state.error = '; '.join(validation_errors)
            node_state.end_time = datetime.now()
            self._record_execution_step(node, node_state, context)
            await self._persist_node_execution(node, node_state, context)
            return

        # Check if node supports streaming (has execute_stream method and stream config is enabled)
        use_streaming = hasattr(node_instance, 'execute_stream') and node.config.get('stream', False)

        # Execute with retries
        for attempt in range(max_retries + 1):
            try:
                if use_streaming:
                    # Streaming execution with aggregation and timeout
                    aggregated_response = ''
                    try:
                        async with asyncio.timeout(300):  # 5 minute timeout for streaming
                            async for chunk in node_instance.execute_stream(inputs, context):
                                if chunk:
                                    aggregated_response += chunk
                    except asyncio.TimeoutError:
                        logger.warning(f'Node {node.id} ({node.type}) streaming timed out, falling back to non-streaming')
                        use_streaming = False
                        outputs = await node_instance.execute(inputs, context)
                    else:
                        # Get response from context if set by execute_stream, otherwise use aggregated
                        final_response = context.variables.pop('_last_llm_response', aggregated_response)
                        outputs = {'response': final_response, 'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}}
                        logger.info(f'Node {node.id} ({node.type}) streaming completed, response length: {len(final_response)}')
                else:
                    outputs = await node_instance.execute(inputs, context)
                node_state.outputs = outputs
                node_state.status = NodeStatus.COMPLETED
                node_state.end_time = datetime.now()
                break
            except Exception as e:
                node_state.retry_count = attempt + 1
                logger.error(
                    f'Node {node.id} ({node.type}) execution failed (attempt {attempt + 1}/{max_retries + 1}): {e}',
                    exc_info=True,
                    extra={
                        'node_id': node.id,
                        'node_type': node.type,
                        'attempt': attempt + 1,
                        'max_retries': max_retries,
                        'execution_id': context.execution_id,
                    },
                )

                if attempt < max_retries:
                    await asyncio.sleep(1)  # Brief delay before retry
                else:
                    node_state.status = NodeStatus.FAILED
                    node_state.error = str(e)
                    node_state.end_time = datetime.now()
                    logger.error(
                        f'Node {node.id} ({node.type}) permanently failed after {max_retries + 1} attempts',
                        extra={
                            'node_id': node.id,
                            'node_type': node.type,
                            'error': str(e),
                            'execution_id': context.execution_id,
                        },
                    )

        self._record_execution_step(node, node_state, context)
        await self._persist_node_execution(node, node_state, context)

    async def _resolve_inputs(self, node: NodeDefinition, context: ExecutionContext) -> dict[str, Any]:
        """Resolve input values for a node from connected nodes and context"""
        inputs = {}

        # Get inputs from context variables
        if 'message' in context.variables:
            inputs['message'] = context.variables['message']

        # Get inputs from message context
        if context.message_context:
            inputs['message'] = context.message_context.message_content
            inputs['message_content'] = context.message_context.message_content
            inputs['sender_id'] = context.message_context.sender_id
            inputs['platform'] = context.message_context.platform
        else:
            logger.warning(
                f'[_resolve_inputs] node={node.id} ({node.type}): message_context is None!',
                extra={
                    'node_id': node.id,
                    'node_type': node.type,
                    'execution_id': context.execution_id,
                    'variables_keys': list(context.variables.keys()) if context.variables else [],
                },
            )

        # Log current inputs state after message_context processing
        logger.debug(
            f'[_resolve_inputs] node={node.id} after message_context: {list(inputs.keys())}',
        )

        # Get inputs from node config that reference other nodes
        for key, value in node.config.items():
            if isinstance(value, str) and value.startswith('{{') and value.endswith('}}'):
                resolved = await self._resolve_expression(value[2:-2], context)
                inputs[key] = resolved
            else:
                inputs[key] = value

        # Get inputs from connected upstream nodes via edges
        # Build a reverse map: for each incoming edge to this node, find the
        # source node and the specific source/target port.
        for edge in self._edges:
            if edge.target_node != node.id:
                continue
            source_state = context.node_states.get(edge.source_node)
            if not source_state or source_state.status != NodeStatus.COMPLETED:
                continue
            target_port = edge.target_port or 'input'
            source_port = edge.source_port or 'output'
            # Map the source node's output port value to this node's input port
            if source_port in source_state.outputs:
                inputs[target_port] = source_state.outputs[source_port]
            elif 'output' in source_state.outputs:
                # Fallback: if exact port not found, try generic 'output'
                inputs[target_port] = source_state.outputs['output']
            elif source_state.outputs:
                # Last resort: use the first available output
                inputs[target_port] = next(iter(source_state.outputs.values()))

        # Smart input mapping: if a node needs 'message' but received a different
        # port name (e.g., 'content' from llm_call), copy the value to 'message'.
        # This handles edge connection mismatches where the sender uses a different
        # port name than what the receiver expects.
        if 'message' not in inputs or inputs.get('message') is None:
            for fallback_key in ('content', 'response', 'input', 'output', 'result', 'text'):
                if fallback_key in inputs and inputs[fallback_key] is not None:
                    inputs['message'] = inputs[fallback_key]
                    logger.debug(
                        f'[_resolve_inputs] node={node.id}: mapped {fallback_key} -> message',
                    )
                    break

        logger.debug(
            f'[_resolve_inputs] node={node.id} final inputs keys: {list(inputs.keys())}, message={repr(inputs.get("message", "<missing>")[:100] if isinstance(inputs.get("message"), str) else inputs.get("message"))}',
        )
        return inputs

    async def _resolve_expression(self, expression: str, context: ExecutionContext) -> Any:
        """Resolve a variable expression like 'nodes.node1.outputs.text'"""
        parts = expression.strip().split('.')

        if not parts:
            return None

        if parts[0] == 'nodes' and len(parts) >= 4:
            # nodes.node_id.outputs.output_name
            node_id = parts[1]
            if parts[2] == 'outputs' and node_id in context.node_states:
                output_name = '.'.join(parts[3:])
                return context.node_states[node_id].outputs.get(output_name)

        elif parts[0] == 'variables':
            # variables.var_name
            var_name = '.'.join(parts[1:])
            return context.variables.get(var_name)

        elif parts[0] == 'conversation_variables':
            # conversation_variables.var_name
            var_name = '.'.join(parts[1:])
            return context.conversation_variables.get(var_name)

        elif parts[0] == 'message':
            # message.content, message.sender_id, etc.
            if context.message_context:
                attr = parts[1] if len(parts) > 1 else None
                if attr == 'content':
                    return context.message_context.message_content
                elif attr == 'sender_id':
                    return context.message_context.sender_id
                elif attr == 'platform':
                    return context.message_context.platform
                elif attr == 'conversation_id':
                    return context.message_context.conversation_id

        return None

    async def _evaluate_condition(self, condition: str, context: ExecutionContext) -> bool:
        """Evaluate a condition expression safely.

        Any ``{{ ... }}`` references are resolved against the execution context
        and bound as **variables** that are passed to :func:`safe_eval_with_vars`.
        Values are never string-concatenated into the expression, which avoids
        broken parsing (e.g. values containing quotes) and any injection risk
        from non-literal value types (lists, dicts, etc.).
        """
        variables: dict[str, Any] = {}
        try:
            # Resolve variable references in condition into bound variables.
            if '{{' in condition:
                pattern = r'\{\{([^}]+)\}\}'

                placeholders: dict[str, str] = {}
                placeholder_idx = 0

                def replace_with_placeholder(match: re.Match[str]) -> str:
                    nonlocal placeholder_idx
                    var_expr = match.group(1)
                    placeholder = f'__ph{placeholder_idx}__'
                    placeholders[placeholder] = var_expr
                    placeholder_idx += 1
                    return placeholder

                condition = re.sub(pattern, replace_with_placeholder, condition)

                # Resolve each placeholder and bind it as a variable, so the
                # actual value (of any type) is passed through unchanged.
                for placeholder, var_expr in placeholders.items():
                    variables[placeholder] = await self._resolve_expression(var_expr, context)

            # Safe expression evaluation with bound variables (AST whitelist).
            result = safe_eval_with_vars(condition, variables)
            return bool(result)

        except Exception as e:
            logger.warning(f'Condition evaluation failed: {condition} - {e}')
            return False

    async def _should_skip_node(self, node: NodeDefinition, context: ExecutionContext) -> bool:
        """Check if a node should be skipped"""
        state = context.node_states.get(node.id)
        if state and state.status in (NodeStatus.COMPLETED, NodeStatus.RUNNING, NodeStatus.SKIPPED):
            return True
        return False

    async def _inputs_ready(
        self, node: NodeDefinition, edge_map: dict[str, list[EdgeDefinition]], context: ExecutionContext
    ) -> bool:
        """Check if all inputs for a node are ready"""
        # Find all edges that connect to this node
        incoming_nodes = set()
        for source_id, edges in edge_map.items():
            for edge in edges:
                if edge.target_node == node.id:
                    incoming_nodes.add(source_id)

        # Check if all incoming nodes have completed
        for source_id in incoming_nodes:
            state = context.node_states.get(source_id)
            if not state or state.status not in (NodeStatus.COMPLETED, NodeStatus.SKIPPED):
                return False

        return True

    def _find_start_nodes(self, nodes: list[NodeDefinition], edges: list[EdgeDefinition]) -> list[NodeDefinition]:
        """Find nodes that have no incoming edges (start nodes)"""
        target_nodes = {edge.target_node for edge in edges}
        start_nodes = [node for node in nodes if node.id not in target_nodes]

        # Also check for trigger nodes
        trigger_types = {'message_trigger', 'cron_trigger', 'webhook_trigger', 'event_trigger'}
        for node in nodes:
            if node.type in trigger_types and node not in start_nodes:
                start_nodes.insert(0, node)

        return start_nodes

    def _build_edge_map(self, edges: list[EdgeDefinition]) -> dict[str, list[EdgeDefinition]]:
        """Build a map of source node ID to outgoing edges"""
        edge_map: dict[str, list[EdgeDefinition]] = {}
        for edge in edges:
            if edge.source_node not in edge_map:
                edge_map[edge.source_node] = []
            edge_map[edge.source_node].append(edge)
        return edge_map

    def _record_execution_step(self, node: NodeDefinition, node_state: NodeState, context: ExecutionContext):
        """Record an execution step in the history"""
        duration_ms = 0
        if node_state.start_time and node_state.end_time:
            duration_ms = int((node_state.end_time - node_state.start_time).total_seconds() * 1000)

        step = ExecutionStep(
            step_id=f"step_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(),
            node_id=node.id,
            node_type=node.type,
            status=node_state.status,
            duration_ms=duration_ms,
            error=node_state.error,
            inputs=node_state.inputs,
            outputs=node_state.outputs,
        )
        context.history.append(step)

    async def _persist_node_execution(
        self,
        node: NodeDefinition,
        node_state: NodeState,
        context: ExecutionContext,
    ):
        """Persist node execution state for execution detail and logs."""
        if not self.ap:
            return

        values = {
            'execution_uuid': context.execution_id,
            'node_id': node.id,
            'node_type': node.type,
            'status': node_state.status.value,
            'inputs': node_state.inputs,
            'outputs': node_state.outputs,
            'start_time': node_state.start_time,
            'end_time': node_state.end_time,
            'error': node_state.error,
            'retry_count': node_state.retry_count,
        }

        existing_query = sqlalchemy.select(persistence_workflow.WorkflowNodeExecution).where(
            persistence_workflow.WorkflowNodeExecution.execution_uuid == context.execution_id,
            persistence_workflow.WorkflowNodeExecution.node_id == node.id,
        )
        existing_result = await self.ap.persistence_mgr.execute_async(existing_query)
        existing = existing_result.first()

        if existing is None:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_workflow.WorkflowNodeExecution).values(**values)
            )
        else:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_workflow.WorkflowNodeExecution)
                .where(persistence_workflow.WorkflowNodeExecution.id == existing.id)
                .values(**values)
            )


class ParallelExecutor:
    """Execute multiple branches in parallel"""

    def __init__(self, executor: WorkflowExecutor):
        self.executor = executor

    async def execute_parallel(
        self, branches: list[list[NodeDefinition]], context: ExecutionContext
    ) -> list[dict[str, Any]]:
        """
        Execute multiple branches in parallel.

        Args:
            branches: List of node sequences to execute in parallel
            context: Execution context

        Returns:
            List of results from each branch
        """
        tasks = []
        for branch in branches:
            task = self._execute_branch(branch, context)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for index, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f'Parallel branch {index} failed: {result}',
                    exc_info=result,
                    extra={'branch_index': index, 'execution_id': context.execution_id},
                )
                processed_results.append({'error': str(result)})
            else:
                processed_results.append(result)

        return processed_results

    async def _execute_branch(self, nodes: list[NodeDefinition], context: ExecutionContext) -> dict[str, Any]:
        """Execute a single branch"""
        # Create a copy of context for this branch
        branch_outputs = {}

        for node in nodes:
            await self.executor._execute_node(node, context, max_retries=3)
            state = context.node_states.get(node.id)
            if state and state.status == NodeStatus.COMPLETED:
                branch_outputs[node.id] = state.outputs
            elif state and state.status == NodeStatus.FAILED:
                branch_outputs['error'] = state.error
                break

        return branch_outputs


class LoopExecutor:
    """Execute loop iterations"""

    def __init__(self, executor: WorkflowExecutor):
        self.executor = executor

    async def execute_loop(
        self, items: list[Any], loop_body: list[NodeDefinition], context: ExecutionContext, max_iterations: int = 100
    ) -> list[dict[str, Any]]:
        """
        Execute a loop over items.

        Args:
            items: Items to iterate over
            loop_body: Nodes to execute for each item
            context: Execution context
            max_iterations: Maximum number of iterations

        Returns:
            List of results from each iteration
        """
        results = []

        for i, item in enumerate(items[:max_iterations]):
            # Set loop variables
            context.variables['loop_item'] = item
            context.variables['loop_index'] = i
            context.variables['loop_is_first'] = i == 0
            context.variables['loop_is_last'] = i == len(items) - 1

            iteration_result = {}

            for node in loop_body:
                # Reset node state for this iteration
                context.node_states[node.id] = NodeState(node_id=node.id, node_type=node.type, status=NodeStatus.PENDING)

                await self.executor._execute_node(node, context, max_retries=3)

                state = context.node_states.get(node.id)
                if state:
                    iteration_result[node.id] = state.outputs

                    # Check for break condition
                    if state.outputs.get('break', False):
                        results.append(iteration_result)
                        return results

            results.append(iteration_result)

        # Clean up loop variables
        context.variables.pop('loop_item', None)
        context.variables.pop('loop_index', None)
        context.variables.pop('loop_is_first', None)
        context.variables.pop('loop_is_last', None)

        return results
