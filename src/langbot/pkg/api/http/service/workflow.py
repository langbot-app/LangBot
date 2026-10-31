"""Workflow service: Workspace-scoped CRUD and execution of workflow processors."""

from __future__ import annotations

import asyncio
import logging
import typing
import uuid
from datetime import datetime

import sqlalchemy

from ....core import app
from ....entity.persistence import workflow as persistence_workflow
from ....workflow.entities import (
    EdgeDefinition,
    ExecutionContext,
    MessageContext,
    NodeDefinition,
    Position,
    WorkflowDefinition,
    WorkflowSettings,
)
from ....workflow.executor import WorkflowExecutor
from ....workflow.protocol.enums import ExecutionStatus, NodeStatus
from ....workflow.registry import NodeTypeRegistry
from ....workflow.runtime import WorkflowRuntime, use_runtime
from ..context import ExecutionContext as WorkspaceExecutionContext
from .tenant import TenantContext, require_workspace_uuid, scope_statement

logger = logging.getLogger(__name__)

MAX_WORKFLOW_CALL_DEPTH = 8


class WorkflowExecutionFailedError(Exception):
    """Raised when a workflow execution finishes with failed status."""

    def __init__(self, execution_id: str, message: str) -> None:
        super().__init__(message)
        self.execution_id = execution_id
        self.message = message


class WorkflowService:
    """Workflow processors owned by a Workspace."""

    DEFAULT_MAX_EXECUTION_TIME = 300

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self.registry = NodeTypeRegistry.instance()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def get_workflows(
        self,
        context: TenantContext,
        sort_by: str = 'created_at',
        sort_order: str = 'DESC',
    ) -> list[dict]:
        model = persistence_workflow.Workflow
        column = {'updated_at': model.updated_at, 'name': model.name}.get(sort_by, model.created_at)
        statement = scope_statement(sqlalchemy.select(model), model, context).order_by(
            column.asc() if sort_order == 'ASC' else column.desc()
        )
        result = await self.ap.persistence_mgr.execute_async(statement)
        return [self._serialize_workflow(row) for row in result.all()]

    async def get_workflow(self, context: TenantContext, workflow_uuid: str) -> dict | None:
        model = persistence_workflow.Workflow
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.select(model).where(model.uuid == workflow_uuid), model, context)
        )
        row = result.first()
        return None if row is None else self._serialize_workflow(row)

    async def create_workflow(self, context: TenantContext, workflow_data: dict) -> str:
        workspace_uuid = require_workspace_uuid(context)
        from .workspace_limits import workspace_limits

        limitation = await workspace_limits(self.ap, workspace_uuid)
        max_workflows = limitation.get('max_workflows', -1)
        if max_workflows >= 0 and len(await self.get_workflows(context)) >= max_workflows:
            raise ValueError(f'Maximum number of workflows ({max_workflows}) reached')

        definition = self._definition_from_payload(workflow_data, {})
        self._validate_workflow_definition(definition)

        workflow_uuid = str(uuid.uuid4())
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_workflow.Workflow).values(
                uuid=workflow_uuid,
                workspace_uuid=workspace_uuid,
                name=workflow_data.get('name') or 'New Workflow',
                description=workflow_data.get('description', ''),
                emoji=workflow_data.get('emoji') or '🔄',
                version=1,
                is_enabled=bool(workflow_data.get('is_enabled', True)),
                definition=definition,
            )
        )
        return workflow_uuid

    async def update_workflow(self, context: TenantContext, workflow_uuid: str, workflow_data: dict) -> None:
        workspace_uuid = require_workspace_uuid(context)
        current = await self.get_workflow(context, workflow_uuid)
        if current is None:
            raise ValueError(f'Workflow {workflow_uuid} not found')

        values: dict[str, typing.Any] = {
            key: workflow_data[key] for key in ('name', 'description', 'emoji', 'is_enabled') if key in workflow_data
        }

        if any(key in workflow_data for key in ('definition', 'nodes', 'edges', 'variables', 'settings')):
            definition = self._definition_from_payload(workflow_data, current.get('definition') or {})
            self._validate_workflow_definition(definition)
            if definition != current.get('definition'):
                await self._save_version_history(
                    workspace_uuid, workflow_uuid, current['version'], current.get('definition') or {}
                )
                values['definition'] = definition
                values['version'] = current['version'] + 1

        if not values:
            return

        model = persistence_workflow.Workflow
        await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.update(model).where(model.uuid == workflow_uuid), model, context).values(
                **values
            )
        )

    async def delete_workflow(self, context: TenantContext, workflow_uuid: str) -> None:
        for model in (persistence_workflow.WorkflowVersion, persistence_workflow.WorkflowExecution):
            await self.ap.persistence_mgr.execute_async(
                scope_statement(sqlalchemy.delete(model).where(model.workflow_uuid == workflow_uuid), model, context)
            )
        model = persistence_workflow.Workflow
        await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.delete(model).where(model.uuid == workflow_uuid), model, context)
        )

    async def copy_workflow(self, context: TenantContext, workflow_uuid: str) -> str:
        original = await self.get_workflow(context, workflow_uuid)
        if original is None:
            raise ValueError(f'Workflow {workflow_uuid} not found')
        return await self.create_workflow(
            context,
            {
                'name': f'{original["name"]} (Copy)',
                'description': original.get('description', ''),
                'emoji': original.get('emoji'),
                'is_enabled': False,
                'definition': original.get('definition') or {},
            },
        )

    async def get_versions(self, context: TenantContext, workflow_uuid: str) -> list[dict]:
        model = persistence_workflow.WorkflowVersion
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(model).where(model.workflow_uuid == workflow_uuid), model, context
            ).order_by(model.version.desc())
        )
        return [self.ap.persistence_mgr.serialize_model(model, row) for row in result.all()]

    async def rollback_to_version(self, context: TenantContext, workflow_uuid: str, version: int) -> None:
        model = persistence_workflow.WorkflowVersion
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(model).where(model.workflow_uuid == workflow_uuid, model.version == version),
                model,
                context,
            )
        )
        row = result.first()
        if row is None:
            raise ValueError(f'Version {version} not found for workflow {workflow_uuid}')
        await self.update_workflow(context, workflow_uuid, {'definition': row.definition})

    async def _save_version_history(
        self, workspace_uuid: str, workflow_uuid: str, version: int, definition: dict
    ) -> None:
        model = persistence_workflow.WorkflowVersion
        existing = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(model.id).where(model.workflow_uuid == workflow_uuid, model.version == version),
                model,
                workspace_uuid,
            )
        )
        if existing.first() is not None:
            return
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(model).values(
                workspace_uuid=workspace_uuid,
                workflow_uuid=workflow_uuid,
                version=version,
                definition=definition,
            )
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute_workflow(
        self,
        execution_context: WorkspaceExecutionContext,
        workflow_uuid: str,
        *,
        trigger_type: str,
        trigger_data: dict | None = None,
        message_context: MessageContext | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        runtime: WorkflowRuntime | None = None,
    ) -> tuple[str, WorkflowRuntime]:
        """Run a workflow to completion and return its execution UUID and runtime.

        ``runtime`` carries the live delivery channel; when omitted the
        execution only collects replies (manual runs from the WebUI).
        """
        workspace_uuid = require_workspace_uuid(execution_context)
        workflow_dict = await self.get_workflow(execution_context, workflow_uuid)
        if workflow_dict is None:
            raise ValueError(f'Workflow {workflow_uuid} not found')
        if runtime is None:
            runtime = WorkflowRuntime(execution_context=execution_context)
        if runtime.depth > MAX_WORKFLOW_CALL_DEPTH:
            raise ValueError(f'Workflow call depth exceeds {MAX_WORKFLOW_CALL_DEPTH}')

        workflow = self._build_definition(workflow_dict)
        execution_uuid = str(uuid.uuid4())
        execution_model = persistence_workflow.WorkflowExecution
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(execution_model).values(
                uuid=execution_uuid,
                workspace_uuid=workspace_uuid,
                workflow_uuid=workflow_uuid,
                workflow_version=workflow.version,
                status=ExecutionStatus.RUNNING.value,
                trigger_type=trigger_type,
                trigger_data=trigger_data or {},
                bot_uuid=execution_context.bot_uuid,
                variables={},
                start_time=datetime.now(),
            )
        )

        context = ExecutionContext(
            execution_id=execution_uuid,
            workflow_id=workflow_uuid,
            workflow_version=workflow.version,
            trigger_type=trigger_type,
            trigger_data=trigger_data or {},
            session_id=session_id,
            user_id=user_id,
            bot_id=execution_context.bot_uuid,
            message_context=message_context,
        )
        context.variables.update(workflow.variables)
        context.variables['_workflow_name'] = workflow.name

        status = ExecutionStatus.FAILED
        error: str | None = None
        try:
            with use_runtime(runtime):
                # A fresh executor per run: the executor keeps per-run graph state.
                context = await asyncio.wait_for(
                    WorkflowExecutor(self.ap).execute(workflow, context),
                    timeout=workflow.settings.max_execution_time or self.DEFAULT_MAX_EXECUTION_TIME,
                )
            status = context.status
            error = context.error
            if status == ExecutionStatus.FAILED and not error:
                error = next(
                    (
                        state.error
                        for state in context.node_states.values()
                        if state.status == NodeStatus.FAILED and state.error
                    ),
                    'Workflow execution failed',
                )
        except asyncio.TimeoutError:
            status = ExecutionStatus.CANCELLED
            error = f'Workflow execution timed out after {workflow.settings.max_execution_time} seconds'
        except Exception as exc:
            logger.exception('Workflow execution %s crashed', execution_uuid)
            error = str(exc)
        finally:
            await self.ap.persistence_mgr.execute_async(
                scope_statement(
                    sqlalchemy.update(execution_model).where(execution_model.uuid == execution_uuid),
                    execution_model,
                    workspace_uuid,
                ).values(
                    status=status.value,
                    end_time=datetime.now(),
                    error=error,
                    variables=_json_safe(context.variables),
                )
            )

        if status != ExecutionStatus.COMPLETED:
            raise WorkflowExecutionFailedError(execution_uuid, error or 'Workflow execution failed')
        return execution_uuid, runtime

    async def get_executions(
        self,
        context: TenantContext,
        workflow_uuid: str,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> dict:
        model = persistence_workflow.WorkflowExecution
        filters = [model.workflow_uuid == workflow_uuid]
        if status:
            filters.append(model.status == status)

        count = await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.select(sqlalchemy.func.count(model.uuid)).where(*filters), model, context)
        )
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.select(model).where(*filters), model, context)
            .order_by(model.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return {
            'executions': [self._serialize_execution(row) for row in result.all()],
            'total': count.scalar() or 0,
        }

    async def get_execution(self, context: TenantContext, workflow_uuid: str, execution_uuid: str) -> dict | None:
        model = persistence_workflow.WorkflowExecution
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(model).where(model.uuid == execution_uuid, model.workflow_uuid == workflow_uuid),
                model,
                context,
            )
        )
        row = result.first()
        if row is None:
            return None
        data = self._serialize_execution(row)

        node_model = persistence_workflow.WorkflowNodeExecution
        node_rows = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(node_model).where(node_model.execution_uuid == execution_uuid), node_model, context
            ).order_by(node_model.id.asc())
        )
        data['node_executions'] = [self._serialize_execution(item, node_model) for item in node_rows.all()]
        return data

    async def get_workflow_stats(self, context: TenantContext, workflow_uuid: str) -> dict:
        model = persistence_workflow.WorkflowExecution
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(model.status, sqlalchemy.func.count(model.uuid))
                .where(model.workflow_uuid == workflow_uuid)
                .group_by(model.status),
                model,
                context,
            )
        )
        counts = {row[0]: int(row[1]) for row in result.all()}
        total = sum(counts.values())

        # Portable duration average: computed in Python over a bounded window.
        durations = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(model.start_time, model.end_time, model.created_at)
                .where(model.workflow_uuid == workflow_uuid)
                .order_by(model.created_at.desc())
                .limit(200),
                model,
                context,
            )
        )
        rows = durations.all()
        finished = [(row[1] - row[0]).total_seconds() for row in rows if row[0] and row[1]]
        return {
            'total_executions': total,
            'successful_executions': counts.get(ExecutionStatus.COMPLETED.value, 0),
            'failed_executions': counts.get(ExecutionStatus.FAILED.value, 0),
            'running_executions': counts.get(ExecutionStatus.RUNNING.value, 0),
            'cancelled_executions': counts.get(ExecutionStatus.CANCELLED.value, 0),
            'success_rate': round(counts.get(ExecutionStatus.COMPLETED.value, 0) / total, 4) if total else 0.0,
            'average_duration_ms': round(sum(finished) / len(finished) * 1000, 2) if finished else 0,
            'last_execution_time': rows[0][2] if rows else None,
        }

    # ------------------------------------------------------------------
    # Node type metadata
    # ------------------------------------------------------------------

    async def get_node_types(self) -> list[dict]:
        return self.registry.list_all()

    async def get_node_categories(self) -> list[dict]:
        categories = self.registry.get_categories()
        ordered = ['trigger', 'process', 'control', 'action', 'misc']
        return [{'name': name, 'order': order} for order, name in enumerate(ordered) if name in categories]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _definition_from_payload(payload: dict, current: dict) -> dict:
        """Accept either a full ``definition`` or top-level editor fields."""
        definition = dict(payload.get('definition') or current or {})
        for key in ('nodes', 'edges', 'variables', 'settings'):
            if key in payload:
                definition[key] = payload[key]
        definition.setdefault('nodes', [])
        definition.setdefault('edges', [])
        definition.setdefault('variables', {})
        return definition

    @staticmethod
    def _build_definition(workflow_dict: dict) -> WorkflowDefinition:
        definition = workflow_dict.get('definition') or {}
        settings = definition.get('settings')
        return WorkflowDefinition(
            uuid=workflow_dict['uuid'],
            name=workflow_dict.get('name', ''),
            description=workflow_dict.get('description') or '',
            version=workflow_dict.get('version', 1),
            nodes=[
                NodeDefinition(
                    id=node.get('id', ''),
                    type=node.get('type', ''),
                    name=node.get('name', ''),
                    position=Position(**(node.get('position') or {'x': 0, 'y': 0})),
                    config=node.get('config') or {},
                )
                for node in definition.get('nodes', [])
            ],
            edges=[
                EdgeDefinition(
                    id=edge.get('id', ''),
                    source_node=edge.get('source_node') or edge.get('source', ''),
                    source_port=edge.get('source_port') or edge.get('sourceHandle') or 'output',
                    target_node=edge.get('target_node') or edge.get('target', ''),
                    target_port=edge.get('target_port') or edge.get('targetHandle') or 'input',
                    edge_type=edge.get('edge_type') or (edge.get('data') or {}).get('edgeType') or 'legacy',
                    condition=edge.get('condition') or (edge.get('data') or {}).get('condition'),
                )
                for edge in definition.get('edges', [])
            ],
            variables=definition.get('variables') or {},
            settings=WorkflowSettings(**settings) if isinstance(settings, dict) else WorkflowSettings(),
        )

    def _serialize_workflow(self, row: typing.Any) -> dict:
        result = self.ap.persistence_mgr.serialize_model(persistence_workflow.Workflow, row)
        definition = result.get('definition') if isinstance(result.get('definition'), dict) else {}
        result['nodes'] = definition.get('nodes', [])
        result['edges'] = definition.get('edges', [])
        result['variables'] = definition.get('variables', {})
        return result

    def _serialize_execution(
        self, row: typing.Any, model: typing.Any = persistence_workflow.WorkflowExecution
    ) -> dict:
        data = self.ap.persistence_mgr.serialize_model(model, row)
        data['started_at'] = data.get('start_time')
        data['completed_at'] = data.get('end_time')
        return data

    @staticmethod
    def _edge_type(edge: dict) -> str:
        edge_type = edge.get('edge_type') or (edge.get('data') or {}).get('edgeType')
        return edge_type if edge_type in {'control', 'data', 'legacy'} else 'legacy'

    @classmethod
    def _has_control_path(cls, source: str, target: str, edges: list[dict]) -> bool:
        if not source or not target or source == target:
            return False
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            if cls._edge_type(edge) == 'data':
                continue
            edge_source = edge.get('source_node') or edge.get('source', '')
            edge_target = edge.get('target_node') or edge.get('target', '')
            if edge_source and edge_target:
                adjacency.setdefault(edge_source, []).append(edge_target)
        visited: set[str] = set()
        stack = list(adjacency.get(source, []))
        while stack:
            current = stack.pop()
            if current == target:
                return True
            if current not in visited:
                visited.add(current)
                stack.extend(adjacency.get(current, []))
        return False

    def _validate_workflow_definition(self, definition: dict) -> None:
        if not isinstance(definition.get('nodes'), list):
            raise ValueError('Workflow definition nodes must be a list')
        edges = definition.get('edges')
        if not isinstance(edges, list):
            raise ValueError('Workflow definition edges must be a list')
        for edge in edges:
            if not isinstance(edge, dict) or self._edge_type(edge) != 'data':
                continue
            source = edge.get('source_node') or edge.get('source', '')
            target = edge.get('target_node') or edge.get('target', '')
            if not self._has_control_path(source, target, edges):
                raise ValueError(
                    'Invalid data edge: data outputs can only connect from a node '
                    'that appears earlier in the control flow to a later node input'
                )


def _json_safe(value: typing.Any) -> typing.Any:
    """Drop values that cannot be stored in a JSON column."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
