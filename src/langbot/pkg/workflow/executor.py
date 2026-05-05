"""Workflow execution engine"""
from __future__ import annotations

import ast
import asyncio
import logging
import operator
import traceback
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

if TYPE_CHECKING:
    from ..core import app

logger = logging.getLogger(__name__)


class ExecutionLog:
    """Execution log entry"""
    
    def __init__(
        self,
        level: str,
        message: str,
        node_id: Optional[str] = None,
        data: Optional[dict] = None
    ):
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
            f"[Workflow Debug] {message}",
            extra={'node_id': node_id, 'data': data}
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


# ─── Safe expression evaluator (replaces eval()) ─────────────────────
# Uses Python's ast module to whitelist only comparison / boolean / arithmetic
# operations.  No function calls, attribute access, or subscript injection.

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Not: operator.not_,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def _safe_eval(expr: str) -> Any:
    """Evaluate a simple expression safely via AST whitelist.

    Supports: literals, comparisons (==, !=, <, >, <=, >=, in, not in, is, is not),
    boolean logic (and, or, not), arithmetic (+, -, *, /, //, %, **), and
    string operations (contains via ``in``).

    Raises ``ValueError`` on any disallowed construct (function calls,
    attribute access, imports, etc.).
    """
    tree = ast.parse(expr.strip(), mode='eval')
    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> Any:
    # Literals: numbers, strings, True/False/None
    if isinstance(node, ast.Constant):
        return node.value

    # Unary operators: -x, +x, not x
    if isinstance(node, ast.UnaryOp):
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported unary op: {type(node.op).__name__}")
        return op_fn(_eval_node(node.operand))

    # Binary operators: x + y, x * y, etc.
    if isinstance(node, ast.BinOp):
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported binary op: {type(node.op).__name__}")
        return op_fn(_eval_node(node.left), _eval_node(node.right))

    # Comparisons: x == y, x > y, x in y, etc.  (chained)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            op_fn = _SAFE_OPS.get(type(op))
            if op_fn is None:
                raise ValueError(f"Unsupported comparison: {type(op).__name__}")
            right = _eval_node(comparator)
            if not op_fn(left, right):
                return False
            left = right
        return True

    # Boolean operators: x and y, x or y
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval_node(v) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_eval_node(v) for v in node.values)

    # Ternary: x if cond else y
    if isinstance(node, ast.IfExp):
        return _eval_node(node.body) if _eval_node(node.test) else _eval_node(node.orelse)

    # Tuples / Lists (used in "x in [1,2,3]")
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval_node(e) for e in node.elts]

    # Name lookup – only allow None, True, False
    if isinstance(node, ast.Name):
        if node.id == 'None':
            return None
        if node.id == 'True':
            return True
        if node.id == 'False':
            return False
        raise ValueError(f"Unsupported variable reference: {node.id}")

    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


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
        self, 
        workflow: WorkflowDefinition, 
        context: ExecutionContext,
        start_node_id: Optional[str] = None
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
                    context.node_states[node.id] = NodeState(node_id=node.id)
            
            # Find start node(s)
            if start_node_id:
                start_nodes = [node_map[start_node_id]]
            else:
                start_nodes = self._find_start_nodes(workflow.nodes, workflow.edges)
            
            if not start_nodes:
                raise ValueError("No start nodes found in workflow")
            
            # Execute from start nodes
            for start_node in start_nodes:
                await self._execute_from_node(
                    start_node,
                    node_map,
                    edge_map,
                    context,
                    workflow.settings.max_retries,
                    path=set()
                )
            
            # Check final status
            all_completed = all(
                state.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED)
                for state in context.node_states.values()
            )
            
            if all_completed:
                context.status = ExecutionStatus.COMPLETED
            else:
                # Some nodes might still be waiting
                has_failed = any(
                    state.status == NodeStatus.FAILED
                    for state in context.node_states.values()
                )
                if has_failed:
                    context.status = ExecutionStatus.FAILED
                    
        except Exception as e:
            context.status = ExecutionStatus.FAILED
            context.error = str(e)
            logger.error(
                "Workflow execution failed",
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
            
        finally:
            context.end_time = datetime.now()
        
        return context
    
    async def _execute_from_node(
        self,
        node: NodeDefinition,
        node_map: dict[str, NodeDefinition],
        edge_map: dict[str, list[EdgeDefinition]],
        context: ExecutionContext,
        max_retries: int = 3,
        path: set[str] | None = None
    ):
        """Execute workflow starting from a specific node"""
        
        # Initialize path set for cycle detection (path-based, not global visited)
        if path is None:
            path = set()
        
        # Check for circular dependency on the *current path* only
        # This correctly allows diamond shapes (A→B, A→C, B→D, C→D)
        if node.id in path:
            logger.warning(f"Circular dependency detected at node: {node.id}")
            context.node_states[node.id].status = NodeStatus.SKIPPED
            context.node_states[node.id].error = "Circular dependency detected"
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
                await self._execute_from_node(
                    target_node,
                    node_map,
                    edge_map,
                    context,
                    max_retries,
                    path
                )
        
        # Remove node from path when backtracking (allows diamond revisit)
        path.discard(node.id)
    
    async def _execute_node(
        self, 
        node: NodeDefinition, 
        context: ExecutionContext,
        max_retries: int = 3
    ):
        """Execute a single node with retry logic"""
        
        node_state = context.node_states[node.id]
        node_state.status = NodeStatus.RUNNING
        node_state.start_time = datetime.now()
        
        # Get node instance (pass ap for access to services)
        node_instance = self.registry.create_instance(node.type, node.id, node.config, ap=self.ap)
        
        if not node_instance:
            node_state.status = NodeStatus.FAILED
            node_state.error = f"Unknown node type: {node.type}"
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
            node_state.error = "; ".join(validation_errors)
            node_state.end_time = datetime.now()
            self._record_execution_step(node, node_state, context)
            await self._persist_node_execution(node, node_state, context)
            return
        
        # Execute with retries
        for attempt in range(max_retries + 1):
            try:
                outputs = await node_instance.execute(inputs, context)
                node_state.outputs = outputs
                node_state.status = NodeStatus.COMPLETED
                node_state.end_time = datetime.now()
                break
            except Exception as e:
                node_state.retry_count = attempt + 1
                logger.error(
                    f"Node {node.id} ({node.type}) execution failed (attempt {attempt + 1}/{max_retries + 1}): {e}",
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
                        f"Node {node.id} ({node.type}) permanently failed after {max_retries + 1} attempts",
                        extra={
                            'node_id': node.id,
                            'node_type': node.type,
                            'error': str(e),
                            'execution_id': context.execution_id,
                        },
                    )
        
        self._record_execution_step(node, node_state, context)
        await self._persist_node_execution(node, node_state, context)
    
    async def _resolve_inputs(
        self, 
        node: NodeDefinition, 
        context: ExecutionContext
    ) -> dict[str, Any]:
        """Resolve input values for a node from connected nodes and context"""
        inputs = {}
        
        # Get inputs from context variables
        if 'message' in context.variables:
            inputs['message'] = context.variables['message']
        
        # Get inputs from message context
        if context.message_context:
            inputs['message_content'] = context.message_context.message_content
            inputs['sender_id'] = context.message_context.sender_id
            inputs['platform'] = context.message_context.platform
        
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
        """Evaluate a condition expression safely using AST whitelist"""
        try:
            # Resolve variable references in condition
            if '{{' in condition:
                import re
                pattern = r'\{\{([^}]+)\}\}'
                
                # First pass: replace all variable references with placeholders
                placeholders = {}
                placeholder_idx = 0
                
                def replace_with_placeholder(match):
                    nonlocal placeholder_idx
                    var_expr = match.group(1)
                    placeholder = f'__PH{placeholder_idx}__'
                    placeholders[placeholder] = var_expr
                    placeholder_idx += 1
                    return placeholder
                
                condition_with_placeholders = re.sub(pattern, replace_with_placeholder, condition)
                
                # Second pass: resolve each placeholder asynchronously
                for placeholder, var_expr in placeholders.items():
                    value = await self._resolve_expression(var_expr, context)
                    if isinstance(value, str):
                        condition_with_placeholders = condition_with_placeholders.replace(
                            placeholder, f'"{value}"'
                        )
                    elif value is None:
                        condition_with_placeholders = condition_with_placeholders.replace(
                            placeholder, 'None'
                        )
                    else:
                        condition_with_placeholders = condition_with_placeholders.replace(
                            placeholder, str(value)
                        )
                
                condition = condition_with_placeholders
            
            # Safe expression evaluation using AST whitelist
            result = _safe_eval(condition)
            return bool(result)
            
        except Exception as e:
            logger.warning(f"Condition evaluation failed: {condition} - {e}")
            return False
    
    async def _should_skip_node(self, node: NodeDefinition, context: ExecutionContext) -> bool:
        """Check if a node should be skipped"""
        state = context.node_states.get(node.id)
        if state and state.status in (NodeStatus.COMPLETED, NodeStatus.RUNNING, NodeStatus.SKIPPED):
            return True
        return False
    
    async def _inputs_ready(
        self, 
        node: NodeDefinition,
        edge_map: dict[str, list[EdgeDefinition]],
        context: ExecutionContext
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
    
    def _find_start_nodes(
        self, 
        nodes: list[NodeDefinition], 
        edges: list[EdgeDefinition]
    ) -> list[NodeDefinition]:
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
    
    def _record_execution_step(
        self, 
        node: NodeDefinition, 
        node_state: NodeState, 
        context: ExecutionContext
    ):
        """Record an execution step in the history"""
        duration_ms = 0
        if node_state.start_time and node_state.end_time:
            duration_ms = int((node_state.end_time - node_state.start_time).total_seconds() * 1000)
        
        step = ExecutionStep(
            timestamp=datetime.now(),
            node_id=node.id,
            node_type=node.type,
            status=node_state.status.value,
            inputs=node_state.inputs,
            outputs=node_state.outputs,
            duration_ms=duration_ms,
            error=node_state.error
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
        self,
        branches: list[list[NodeDefinition]],
        context: ExecutionContext
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
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({'error': str(result)})
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _execute_branch(
        self, 
        nodes: list[NodeDefinition], 
        context: ExecutionContext
    ) -> dict[str, Any]:
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
        self,
        items: list[Any],
        loop_body: list[NodeDefinition],
        context: ExecutionContext,
        max_iterations: int = 100
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
                context.node_states[node.id] = NodeState(node_id=node.id)
                
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
                raise ValueError("No start nodes found in workflow")
            
            debug_state.add_log('info', f'Found {len(start_nodes)} start node(s)')
            
            # Execute from start nodes
            for start_node in start_nodes:
                if debug_state.is_stopped:
                    break
                    
                await self._execute_debug_from_node(
                    start_node,
                    node_map,
                    edge_map,
                    context,
                    debug_state,
                    workflow.settings.max_retries
                )
            
            # Set final status
            if debug_state.is_stopped:
                context.status = ExecutionStatus.CANCELLED
                debug_state.status = 'cancelled'
            else:
                all_completed = all(
                    state.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED)
                    for state in context.node_states.values()
                )
                
                if all_completed:
                    context.status = ExecutionStatus.COMPLETED
                    debug_state.status = 'completed'
                    debug_state.add_log('info', 'Workflow execution completed successfully')
                else:
                    has_failed = any(
                        state.status == NodeStatus.FAILED
                        for state in context.node_states.values()
                    )
                    if has_failed:
                        context.status = ExecutionStatus.FAILED
                        debug_state.status = 'error'
                        
        except Exception as e:
            context.status = ExecutionStatus.FAILED
            context.error = str(e)
            debug_state.status = 'error'
            debug_state.add_log('error', f'Workflow execution failed: {e}', data={'traceback': traceback.format_exc()})
            logger.error(f"Debug workflow execution failed: {e}\n{traceback.format_exc()}")
            
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
        max_retries: int = 3
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
                    debug_state.add_log(
                        'debug',
                        f'Edge condition not met: {edge.condition}',
                        node_id=node.id
                    )
                    continue
            
            # Check if all inputs are ready
            if await self._inputs_ready(target_node, edge_map, context):
                await self._execute_debug_from_node(
                    target_node,
                    node_map,
                    edge_map,
                    context,
                    debug_state,
                    max_retries
                )
    
    async def _execute_debug_node(
        self,
        node: NodeDefinition,
        context: ExecutionContext,
        debug_state: DebugExecutionState,
        max_retries: int = 3
    ):
        """Execute a single node with debug logging"""
        
        node_state = context.node_states[node.id]
        node_state.status = NodeStatus.RUNNING
        node_state.start_time = datetime.now()
        
        # Get node instance (pass ap for access to services)
        node_instance = self.registry.create_instance(node.type, node.id, node.config, ap=self.ap)
        
        if not node_instance:
            node_state.status = NodeStatus.FAILED
            node_state.error = f"Unknown node type: {node.type}"
            node_state.end_time = datetime.now()
            debug_state.add_log('error', f'Unknown node type: {node.type}', node_id=node.id)
            self._record_execution_step(node, node_state, context)
            await self._persist_node_execution(node, node_state, context)
            return
        
        # Resolve inputs
        inputs = await self._resolve_inputs(node, context)
        node_state.inputs = inputs
        debug_state.add_log(
            'debug',
            f'Node inputs resolved',
            node_id=node.id,
            data={'inputs': self._safe_serialize(inputs)}
        )
        
        # Validate inputs
        validation_errors = await node_instance.validate_inputs(inputs)
        if validation_errors:
            node_state.status = NodeStatus.FAILED
            node_state.error = "; ".join(validation_errors)
            node_state.end_time = datetime.now()
            debug_state.add_log(
                'error',
                f'Input validation failed: {node_state.error}',
                node_id=node.id
            )
            self._record_execution_step(node, node_state, context)
            await self._persist_node_execution(node, node_state, context)
            return
        
        # Execute with retries
        for attempt in range(max_retries + 1):
            if debug_state.is_stopped:
                node_state.status = NodeStatus.FAILED
                node_state.error = "Execution stopped"
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
                    data={'outputs': self._safe_serialize(outputs), 'duration_ms': duration_ms}
                )
                break
                
            except Exception as e:
                node_state.retry_count = attempt + 1
                debug_state.add_log(
                    'warning',
                    f'Node execution failed (attempt {attempt + 1}/{max_retries + 1}): {e}',
                    node_id=node.id
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
                        data={'error': str(e), 'traceback': traceback.format_exc()}
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
        node_map = {node.id: node for node in workflow.nodes}
        edge_map = self._build_edge_map(workflow.edges)
        
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
        self,
        workflow: WorkflowDefinition,
        context: ExecutionContext
    ) -> Optional[NodeDefinition]:
        """Find the next node that can be executed"""
        edge_map = self._build_edge_map(workflow.edges)
        
        for node in workflow.nodes:
            state = context.node_states.get(node.id)
            
            # Skip completed, running, or failed nodes
            if state and state.status in (NodeStatus.COMPLETED, NodeStatus.RUNNING, NodeStatus.FAILED, NodeStatus.SKIPPED):
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
            return "<non-serializable>"
    
    def get_execution_state(
        self,
        context: ExecutionContext,
        debug_state: DebugExecutionState
    ) -> dict:
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
                    if state.start_time and state.end_time else None,
            }
        
        return {
            'status': debug_state.status,
            'current_node_id': debug_state.current_node_id,
            'node_states': node_states,
            'new_logs': debug_state.get_pending_logs(),
            'error': context.error,
        }
