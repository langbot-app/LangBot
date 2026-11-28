"""Workflow service: Workspace-scoped CRUD and execution of workflow processors."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy

from ....entity.persistence import workflow as persistence_workflow
from ....entity.persistence.bot import Bot
from ....entity.persistence.agent import Agent
from ....entity.persistence.pipeline import LegacyPipeline
from ....workflow.graph import CATALOG, validate
from ....workflow.tree import execute_tree
from ....workflow.triggers import validate_triggers
from ....workflow.memory import RunMemory
from ....workflow.runtime import WorkflowRuntime
from ....entity.persistence.model import ASRModel, LLMModel, TTSModel
from ....storage.media import MediaCache
from .tenant import TenantContext, require_workspace_uuid, scope_statement

BASIC_STEPS = tuple(CATALOG)


def initial_graph():
    return {'nodes': [{'id': 'start', 'type': 'start', 'name': 'Start', 'config': {}}], 'edges': []}


def payload(value):
    return json.dumps(MediaCache.redact_inline_images(value), ensure_ascii=False)


class WorkflowExecutionFailedError(Exception):
    """Raised when a workflow execution finishes with failed status."""

    def __init__(self, execution_id: str, message: str) -> None:
        super().__init__(message)
        self.execution_id = execution_id
        self.message = message


class WorkflowService:
    """Workflow processors owned by a Workspace."""

    DEFAULT_MAX_EXECUTION_TIME = 300

    def __init__(self, ap) -> None:
        self.ap = ap

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
        return [
            {
                **{key: getattr(row, key) for key in ('uuid', 'name', 'description', 'emoji', 'is_enabled')},
                'updated_at': row.updated_at.isoformat(),
                'step_count': len(row.graph.get('nodes', []))
                if isinstance(row.graph, dict) and isinstance(row.graph.get('nodes'), list)
                else 0,
            }
            for row in result.all()
        ]

    async def workflows_with_trigger(self, context, kind: str) -> list[dict]:
        """Enabled workflows of the Workspace that declare a trigger of ``kind``."""
        model = persistence_workflow.Workflow
        rows = await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.select(model).where(model.is_enabled.is_(True)), model, context)
        )
        workflows = []
        for row in rows.all():
            triggers = row.triggers if isinstance(row.triggers, list) else []
            if any(isinstance(item, dict) and item.get('type') == kind for item in triggers):
                workflows.append(self.ap.persistence_mgr.serialize_model(model, row, masked_columns=['workspace_uuid']))
        return workflows

    async def command_workflows(self, context) -> list[dict]:
        return await self.workflows_with_trigger(context, 'command')

    async def get_workflow(self, context: TenantContext, workflow_uuid: str) -> dict | None:
        model = persistence_workflow.Workflow
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.select(model).where(model.uuid == workflow_uuid), model, context)
        )
        row = result.first()
        return (
            None
            if row is None
            else self.ap.persistence_mgr.serialize_model(model, row, masked_columns=['workspace_uuid'])
        )

    async def create_workflow(self, context: TenantContext, workflow_data: dict) -> str:
        workspace_uuid = require_workspace_uuid(context)
        from .workspace_limits import workspace_limits

        limitation = await workspace_limits(self.ap, workspace_uuid)
        max_workflows = limitation.get('max_workflows', -1)
        if max_workflows >= 0 and len(await self.get_workflows(context)) >= max_workflows:
            raise ValueError(f'Maximum number of workflows ({max_workflows}) reached')

        workflow_uuid = str(uuid.uuid4())
        values = self.definition_values(workflow_data)
        values.setdefault('graph', initial_graph())
        values.setdefault('name', 'New Workflow')
        values.setdefault('emoji', '🔄')
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_workflow.Workflow).values(
                **values, uuid=workflow_uuid, workspace_uuid=workspace_uuid
            )
        )
        return workflow_uuid

    @staticmethod
    def definition_values(data):
        values = {
            key: data[key]
            for key in ('name', 'description', 'emoji', 'graph', 'triggers', 'timezone', 'is_enabled')
            if key in data
        }
        if 'graph' in values and not isinstance(values['graph'], dict):
            raise ValueError('graph must be an object')
        if 'triggers' in values:
            validate_triggers(values['triggers'])
        if 'timezone' in values:
            try:
                ZoneInfo(values['timezone'])
            except (TypeError, ValueError, ZoneInfoNotFoundError) as exc:
                raise ValueError('Unknown workflow timezone') from exc
        return values

    async def update_workflow(self, context, workflow_uuid, workflow_data):
        if await self.get_workflow(context, workflow_uuid) is None:
            raise ValueError('Workflow not found')
        values = self.definition_values(workflow_data)
        if values:
            model = persistence_workflow.Workflow
            await self.ap.persistence_mgr.execute_async(
                scope_statement(sqlalchemy.update(model).where(model.uuid == workflow_uuid), model, context).values(
                    **values
                )
            )

    async def delete_workflow(self, context: TenantContext, workflow_uuid: str) -> None:
        result = await self.ap.persistence_mgr.execute_async(scope_statement(sqlalchemy.select(Bot), Bot, context))
        for bot in result.all():
            if any(
                binding.get('target_type') == 'workflow' and binding.get('target_uuid') == workflow_uuid
                for binding in (bot.event_bindings or [])
            ):
                raise ValueError(f'Workflow is referenced by bot {bot.name}')
        executions = scope_statement(
            sqlalchemy.select(persistence_workflow.WorkflowExecution.uuid).where(
                persistence_workflow.WorkflowExecution.workflow_uuid == workflow_uuid
            ),
            persistence_workflow.WorkflowExecution,
            context,
        )
        node_model = persistence_workflow.WorkflowExecutionStep
        await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.delete(node_model).where(node_model.execution_uuid.in_(executions)), node_model, context
            )
        )
        for model in (persistence_workflow.WorkflowMemory, persistence_workflow.WorkflowExecution):
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
                'graph': original['graph'],
                'triggers': original['triggers'],
                'timezone': original['timezone'],
            },
        )

    async def validate_graph(self, context, graph):
        nodes = graph.get('nodes', []) if isinstance(graph, dict) else []
        nodes = [node for node in nodes if isinstance(node, dict)] if isinstance(nodes, list) else []
        model_ids = set()
        kinds = {node.get('type') for node in nodes}
        for model, used_by in (
            (LLMModel, {'llm', 'classify', 'extract'}),
            (TTSModel, {'tts'}),
            (ASRModel, {'asr'}),
        ):
            if kinds & used_by:
                model_ids.update(
                    (
                        await self.ap.persistence_mgr.execute_async(
                            scope_statement(sqlalchemy.select(model.uuid), model, context)
                        )
                    ).scalars()
                )
        targets = set()
        if any(node.get('type') == 'handoff' for node in nodes):
            for kind, model in (
                ('agent', Agent),
                ('chat', LegacyPipeline),
                ('workflow', persistence_workflow.Workflow),
            ):
                ids = await self.ap.persistence_mgr.execute_async(
                    scope_statement(sqlalchemy.select(model.uuid), model, context)
                )
                targets.update((kind, ident) for ident in ids.scalars())
        issues = validate(graph, models=model_ids, targets=targets)
        for node in nodes:
            if node.get('type') == 'code' and not self._box_available():
                issues.append(
                    {'node_id': node.get('id'), 'field': 'type', 'code': 'box_unavailable', 'severity': 'error'}
                )
            if node.get('type') not in BASIC_STEPS:
                issues.append(
                    {'node_id': node.get('id'), 'field': 'type', 'code': 'unsupported_type', 'severity': 'error'}
                )
        return issues

    async def workflow_response(self, context, workflow_uuid):
        workflow = await self.get_workflow(context, workflow_uuid)
        if workflow is None:
            raise ValueError('Workflow not found')
        return {'workflow': workflow, 'issues': await self.validate_graph(context, workflow['graph'])}

    async def _recent_history(self, context, workflow_uuid, session_id):
        executions = persistence_workflow.WorkflowExecution
        steps = persistence_workflow.WorkflowExecutionStep
        db = self.ap.persistence_mgr.execute_async
        recent = (
            await db(
                scope_statement(
                    sqlalchemy.select(executions.uuid, executions.input_text).where(
                        executions.workflow_uuid == workflow_uuid,
                        executions.session_id == session_id,
                        executions.bot_uuid == context.bot_uuid,
                        executions.status == 'completed',
                        executions.trigger != 'test',
                    ),
                    executions,
                    context,
                )
                .order_by(executions.started_at.desc(), executions.uuid.desc())
                .limit(10)
            )
        ).all()
        replies = {}
        if recent:
            rows = await db(
                scope_statement(
                    sqlalchemy.select(steps.execution_uuid, steps.inputs).where(
                        steps.execution_uuid.in_([row.uuid for row in recent]),
                        steps.node_type == 'reply',
                        steps.status == 'completed',
                    ),
                    steps,
                    context,
                ).order_by(steps.seq)
            )
            for row in rows:
                config = json.loads(row.inputs)
                replies[row.execution_uuid] = ''.join(
                    part.get('text', '') for part in config.get('content', []) if part.get('type') == 'text'
                ) or config.get('text', '')
        history = []
        for row in reversed(recent):
            history.append({'role': 'user', 'content': row.input_text})
            if replies.get(row.uuid):
                history.append({'role': 'assistant', 'content': replies[row.uuid]})
        return history

    async def execute_workflow(
        self,
        execution_context,
        workflow_uuid,
        *,
        trigger_type,
        message_context,
        session_id,
        runtime=None,
        graph=None,
        trigger_data=None,
        user_id=None,
    ):
        workspace = require_workspace_uuid(execution_context)
        workflow = await self.get_workflow(execution_context, workflow_uuid)
        if workflow is None:
            raise ValueError('Workflow not found')
        graph = workflow['graph'] if graph is None else graph
        execution_uuid = str(uuid.uuid4())
        runtime = runtime or WorkflowRuntime(execution_context)
        runtime.session_id = session_id
        message = {
            key: getattr(message_context, key)
            for key in ('sender_id', 'sender_name', 'group_id', 'platform', 'is_group')
        }
        message.update(
            text=message_context.message_content,
            trigger=trigger_type if trigger_type not in ('test', 'workflow') else 'message',
            bot_uuid=execution_context.bot_uuid or '',
            args=(trigger_data or {}).get('args', {}) if trigger_type in ('command', 'test') else {},
            payload=(trigger_data or {}).get('payload', {}) if trigger_type == 'webhook' else {},
            target=(trigger_data or {}).get('target', {}) if trigger_type == 'schedule' else {},
            event=trigger_data if trigger_type == 'event' else {},
            images=[],
            voice=None,
        )
        chain = (trigger_data or {}).get('message_chain', [])
        if chain:
            chain = await self.ap.storage_mgr.media_cache.externalize_chain_dump(chain)
            message['images'] = [part['url'] for part in chain if part.get('type') == 'Image' and part.get('url')]
            message['voice'] = next(
                (part['url'] for part in chain if part.get('type') == 'Voice' and part.get('url')), None
            )
        model = persistence_workflow.WorkflowExecution
        db = self.ap.persistence_mgr.execute_async
        await db(
            sqlalchemy.insert(model).values(
                uuid=execution_uuid,
                workflow_uuid=workflow_uuid,
                workspace_uuid=workspace,
                trigger=trigger_type,
                bot_uuid=execution_context.bot_uuid,
                session_id=session_id,
                input_text=message['text'],
                status='running',
                started_at=datetime.now(),
            )
        )
        error = None
        try:
            issues = await self.validate_graph(execution_context, graph)
            rejected = next((issue for issue in issues if issue['severity'] == 'error'), None)
            if rejected:
                error = ': '.join(str(rejected[key]) for key in ('node_id', 'field', 'code') if rejected.get(key))
            else:
                memory = RunMemory(
                    self.ap.persistence_mgr,
                    workspace,
                    workflow_uuid,
                    message['platform'],
                    message['sender_id'],
                    message['group_id'],
                    test=runtime.test,
                )
                await memory.load()
                steps, error = await execute_tree(
                    graph,
                    message,
                    ap=self.ap,
                    runtime=runtime,
                    memory=memory.values,
                    save_memory=memory.write,
                    history=await self._recent_history(execution_context, workflow_uuid, session_id)
                    if not runtime.test
                    and any(
                        node['type'] == 'llm' and node['config'].get('use_history', True) for node in graph['nodes']
                    )
                    else [],
                    models=None,
                    targets=None,
                    issues=issues,
                    now=datetime.now(ZoneInfo(workflow['timezone'])),
                )
                for step in steps:
                    await db(
                        sqlalchemy.insert(persistence_workflow.WorkflowExecutionStep).values(
                            **{**step, 'inputs': payload(step['inputs']), 'outputs': payload(step['outputs'])},
                            execution_uuid=execution_uuid,
                            workspace_uuid=workspace,
                        )
                    )
                if runtime.handoff and runtime.depth >= 8:
                    raise ValueError('Workflow handoff depth exceeds 8')
                if runtime.handoff:
                    handoff = runtime.handoff
                    model_type = {
                        'chat': LegacyPipeline,
                        'workflow': persistence_workflow.Workflow,
                        'agent': Agent,
                    }.get(handoff['target_type'])
                    if model_type is None:
                        raise ValueError('Unsupported handoff target')
                    name = (
                        await db(
                            scope_statement(
                                sqlalchemy.select(model_type.name).where(model_type.uuid == handoff['target_uuid']),
                                model_type,
                                execution_context,
                            )
                        )
                    ).scalar_one_or_none()
                    if name is None:
                        raise ValueError('Handoff target not found')
                    handoff['name'] = name
                    if runtime.dispatch is not None:
                        await runtime.dispatch(handoff)
        except Exception as exc:
            error = str(exc) or type(exc).__name__
        await db(
            scope_statement(
                sqlalchemy.update(model).where(model.uuid == execution_uuid), model, execution_context
            ).values(
                status='failed' if error else 'completed',
                error=error,
                handoff=runtime.handoff,
                finished_at=datetime.now(),
            )
        )
        if error:
            raise WorkflowExecutionFailedError(execution_uuid, error)
        return execution_uuid, runtime

    async def get_node_types(self):
        return [
            {
                'type': kind,
                **CATALOG[kind],
                **(
                    {'available': False, 'reason': 'box_unavailable'}
                    if kind == 'code' and not self._box_available()
                    else {'available': True}
                ),
            }
            for kind in BASIC_STEPS
        ]

    def _box_available(self):
        return bool(getattr(getattr(self.ap, 'box_service', None), 'available', False))

    def _serialize_execution(self, row, model=persistence_workflow.WorkflowExecution):
        data = self.ap.persistence_mgr.serialize_model(model, row, masked_columns=['workspace_uuid'])
        data['duration_ms'] = (
            round((row.finished_at - row.started_at).total_seconds() * 1000) if row.finished_at else None
        )
        if model is persistence_workflow.WorkflowExecutionStep:
            for key in ('inputs', 'outputs'):
                data[key] = json.loads(data[key])
        return data

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
            .order_by(model.started_at.desc())
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

        node_model = persistence_workflow.WorkflowExecutionStep
        node_rows = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(node_model).where(node_model.execution_uuid == execution_uuid), node_model, context
            ).order_by(node_model.seq.asc())
        )
        data['steps'] = [self._serialize_execution(item, node_model) for item in node_rows.all()]
        return data
