"""Explicit, tenant-scoped migration. Preview never contacts plugin runtimes.

The task handle is process-local. Original snapshots and pending activation are
persistent; a refreshed preview is required after observation loss or restart.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import json
import math
import time
import secrets
import sys
import uuid

from langbot_plugin.runtime.plugin.mgr import PluginInstallSource

import httpx
import sqlalchemy as sa

from ..authz import Permission, permissions_for_role, require_permission
from ..context import ExecutionContext, PrincipalType, RequestContext
from ....agent.runner.config_resolver import RunnerConfigResolver
from ....agent.runner import config_schema
from ....agent.runner.resource_builder import AgentResourceBuilder
from ....agent.runner.resource_policy import ResourcePolicyProjector
from ....entity.persistence.model import LLMModel, RerankModel, EmbeddingModel
from ....entity.persistence.rag import KnowledgeBase
from ....entity.persistence.mcp import MCPServer
from ....core.taskmgr import TaskContext
from ....entity.persistence.pipeline import LegacyPipeline
from ....entity.persistence.agent_interaction import AgentInteraction
from ....persistence.pipeline_admission import lock_pipeline_admission
from ....entity.persistence.pipeline_migration import PipelineMigrationSnapshot
from ....entity.persistence.plugin import PluginSetting
from ....entity.persistence.user import User
from ....entity.persistence.workspace import Workspace, WorkspaceMembership, WorkspaceExecutionState
from ....plugin.errors import (
    PluginRuntimeNotConnectedError,
    MarketplacePluginVersionNotFoundError,
    PluginInstallationFailedError,
)
from ....pipeline.legacy_config_migration import PLANNER_VERSION, plan_legacy_pipeline


class MigrationInstallContext(TaskContext):
    """Publish only structured installer progress, never upstream logs or URLs."""

    ACTIONS = {
        'downloading plugin package': 'downloading',
        'validating plugin package': 'validating',
        'preparing plugin installation': 'preparing',
        'installing plugin dependencies': 'installing_deps',
        'waiting for plugin initialization': 'activating',
        'refreshing plugin components': 'refreshing',
        'plugin installed': 'done',
    }
    METRICS = ('progress_percent', 'download_current', 'download_total', 'download_speed', 'deps_total')

    def __init__(self, target):
        super().__init__()
        self.progress = {
            **target,
            'status': 'installing',
            'stage': 'checking',
            'code': None,
            'started_at': time.time(),
            'finished_at': None,
            'steps': [],
        }
        self._step('checking')

    def _step(self, stage):
        steps = self.progress['steps']
        if steps and steps[-1]['stage'] == stage:
            return
        now = time.time()
        if steps:
            steps[-1]['finished_at'] = now
        steps.append({'stage': stage, 'started_at': now, 'finished_at': None})
        self.progress['stage'] = stage

    def set_current_action(self, action):
        super().set_current_action(action)
        stage = self.ACTIONS.get(action)
        if stage:
            self._step(stage)
        self.publish()

    def publish(self):
        for key in self.METRICS:
            value = self.metadata.get(key)
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                self.progress[key] = min(value, 100) if key == 'progress_percent' else value
        self.progress['updated_at'] = time.time()

    def finish(self, code=None):
        self.publish()
        self.progress.update(status='failed' if code else 'completed', code=code, finished_at=time.time())
        self.progress['steps'][-1]['finished_at'] = self.progress['finished_at']
        if not code:
            self.progress['progress_percent'] = 100

    async def observe(self):
        while True:
            self.publish()
            await asyncio.sleep(0.2)


class MigrationError(ValueError):
    """Only constant, credential-free codes cross the API/task boundary."""

    def __init__(self, code: str, status_code: int = 409):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, MigrationError):
        return exc.code
    if isinstance(exc, PluginRuntimeNotConnectedError):
        return 'plugin_runtime_unavailable'
    return 'migration_failed'


def validate_execute_request(body) -> list[dict]:
    if not isinstance(body, dict) or set(body) != {'confirmed', 'items'} or body['confirmed'] is not True:
        raise MigrationError('confirmation_required', 400)
    items = body['items']
    if not isinstance(items, list) or not 1 <= len(items) <= 50:
        raise MigrationError('invalid_selection', 400)
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {'pipeline_uuid', 'preview_token'}:
            raise MigrationError('invalid_selection', 400)
        for key, maximum in [('pipeline_uuid', 255), ('preview_token', 256)]:
            value = item[key]
            if not isinstance(value, str) or not value.strip() or len(value) > maximum or value != value.strip():
                raise MigrationError('invalid_selection', 400)
        if item['pipeline_uuid'] in seen:
            raise MigrationError('invalid_selection', 400)
        seen.add(item['pipeline_uuid'])
    return copy.deepcopy(items)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)


def _fingerprint(row):
    # SQL timestamps are neither monotonic revisions nor portable CAS values.
    return hashlib.sha256(
        _json(
            {k: v for k, v in row.items() if not k.startswith('_') and k not in ('created_at', 'updated_at')}
        ).encode()
    ).hexdigest()


class PipelineMigrationService:
    def __init__(self, ap):
        self.ap = ap
        self.pm = ap.persistence_mgr
        # Loss of this process key only invalidates previews, never snapshots.
        self._token_key = secrets.token_bytes(32)
        self._all_tasks: set[str] = set()

    async def _binding(self, ctx, session=None):
        binding = await self.ap.workspace_service.get_execution_binding(
            ctx.workspace_uuid, expected_generation=ctx.placement_generation, session=session
        )
        if binding.instance_uuid != ctx.instance_uuid:
            raise MigrationError('placement_changed')

    async def _authorize(self, ctx, session=None):
        require_permission(ctx, Permission.RESOURCE_MANAGE)
        if ctx.principal.principal_type != PrincipalType.ACCOUNT or not ctx.account_uuid:
            raise MigrationError('authorization_changed', 403)
        status = (await self.pm.execute_async(sa.select(User.status).where(User.uuid == ctx.account_uuid))).scalar()
        if status != 'active':
            raise MigrationError('authorization_changed', 403)
        access = await self.ap.workspace_collaboration_service.resolve_account_workspace(
            ctx.account_uuid, ctx.workspace_uuid, session=session
        )
        if (
            access.workspace.uuid != ctx.workspace_uuid
            or access.membership.uuid != ctx.workspace.membership_uuid
            or access.membership.projection_revision != ctx.workspace.membership_revision
            or Permission.RESOURCE_MANAGE.value not in permissions_for_role(access.membership.role)
            or access.execution.instance_uuid != ctx.instance_uuid
            or access.execution.placement_generation != ctx.placement_generation
        ):
            raise MigrationError('authorization_changed', 403)
        await self._binding(ctx, session)

    async def _rows(self, ctx, pipeline_uuid=None):
        # Read DB-native text for JSON CAS: never compare PostgreSQL JSON using =,
        # and never assume Python's JSON whitespace/key order matches stored text.
        table = LegacyPipeline.__table__
        stmt = sa.select(
            table,
            *[sa.cast(table.c[k], sa.Text).label('_raw_' + k) for k in ('config', 'stages', 'extensions_preferences')],
        )
        stmt = stmt.where(table.c.workspace_uuid == ctx.workspace_uuid)
        if pipeline_uuid is not None:
            stmt = stmt.where(table.c.uuid == pipeline_uuid)
        return [dict(r._mapping) for r in (await self.pm.execute_async(stmt.order_by(table.c.uuid))).all()]

    async def _plugin(self, ctx, plan):
        target = plan.get('target_plugin')
        if not target:
            return None
        t = PluginSetting.__table__
        row = (
            await self.pm.execute_async(
                sa.select(
                    t.c.enabled, t.c.installation_uuid, t.c.artifact_digest, t.c.runtime_revision, t.c.install_info
                ).where(
                    t.c.workspace_uuid == ctx.workspace_uuid,
                    t.c.plugin_author == target['author'],
                    t.c.plugin_name == target['name'],
                )
            )
        ).first()
        return dict(row._mapping) if row else None

    def _native_interactions(self, ctx, pipeline_uuid):
        """Inspect the old in-process cache without importing/pruning it.

        Native forms have no durable handoff to the plugin runner. Operators
        must finish them in the original runtime before migrating; never infer
        completion from the cache TTL or submit/cancel a form here.
        """
        module = sys.modules.get('langbot.pkg.provider.runners.difysvapi')
        if module is None:
            return []
        cache = getattr(module, '_PENDING_FORMS', None)
        if not isinstance(cache, dict):
            return ['unavailable']
        observed = []
        for key, forms in cache.items():
            if not isinstance(key, tuple) or len(key) != 8:
                if forms:
                    observed.append('unscoped')
                continue
            instance, workspace, _, _, pipeline, *_ = key
            # Inspect ownership before touching any form contents. Empty scope
            # cannot prove this is another tenant; block without disclosing it.
            if instance and instance != ctx.instance_uuid or workspace and workspace != ctx.workspace_uuid:
                continue
            if pipeline and pipeline != pipeline_uuid:
                continue
            if forms:
                observed.append(hashlib.sha256(_json(key).encode()).hexdigest())
        return sorted(observed)

    async def _interaction_state(self, ctx, pipeline_uuid):
        """Read only correlation/status, never request/submission/token data.

        The real table has workspace_id (not workspace_uuid), and no instance
        column. Execution placement is verified by the caller; processor_id is
        the globally unique pipeline UUID. NULL ownership on that exact UUID
        is uncertainty, not permission to query other Workspaces.
        """
        if self.pm.get_db_engine().dialect.name not in {'sqlite', 'postgresql'}:
            return {'boundary': 'unavailable'}, True
        t = AgentInteraction.__table__
        try:
            records = (
                await self.pm.execute_async(
                    sa.select(t.c.id, t.c.status, t.c.updated_at, t.c.workspace_id)
                    .where(
                        t.c.processor_type == 'pipeline',
                        t.c.processor_id == pipeline_uuid,
                        sa.or_(
                            t.c.workspace_id == ctx.workspace_uuid, t.c.workspace_id.is_(None), t.c.workspace_id == ''
                        ),
                    )
                    .order_by(t.c.id)
                )
            ).all()
            durable = [tuple(r) for r in records]
            blocked = any(r.status not in {'submitted', 'cancelled', 'expired', 'delivery_failed'} for r in records)
        except Exception:
            # Missing schema, permissions, or a failed store must not be treated
            # as an empty store. No original diagnostic crosses the API.
            durable, blocked = ['unavailable'], True
        native = self._native_interactions(ctx, pipeline_uuid)
        return {'durable': durable, 'native': native}, blocked or bool(native)

    async def _plan(self, ctx, row):
        plan = plan_legacy_pipeline(row['config'], row['extensions_preferences'])
        pending = None
        if plan['state'] == 'already_current':
            t = PipelineMigrationSnapshot.__table__
            snapshots = (
                await self.pm.execute_async(
                    sa.select(t).where(
                        t.c.workspace_uuid == ctx.workspace_uuid,
                        t.c.pipeline_uuid == row['uuid'],
                        t.c.state == 'activation_pending',
                        t.c.target_fingerprint == _fingerprint(row),
                        t.c.planner_version == str(PLANNER_VERSION),
                    )
                )
            ).all()
            if snapshots:
                pending = dict(snapshots[0]._mapping)
                source = pending['source_snapshot']
                plan = plan_legacy_pipeline(source['config'], source['extensions_preferences'])
                candidate = {**row, 'config': plan.get('config')}
                if plan['state'] != 'ready' or _fingerprint(candidate) != _fingerprint(row):
                    raise MigrationError('planner_changed')
        facts = await self._plugin(ctx, plan)
        state = 'activation_pending' if pending else plan['state']
        blockers = list(plan['blockers'])
        if state in ('ready', 'activation_pending'):
            if facts is None:
                state = 'needs_plugin'
                blockers.append({'code': 'plugin_missing'})
            elif facts['enabled'] is not True:
                state = 'blocked'
                blockers.append({'code': 'plugin_disabled'})
        if plan['state'] == 'ready':
            observation, interaction_blocked = await self._interaction_state(ctx, row['uuid'])
            plan['_interaction_state'] = observation
            if interaction_blocked:
                state = 'blocked'
                blockers.append({'code': 'runtime.pending_interaction'})
        return plan, facts, pending, state, blockers

    def _token(self, ctx, row, plan, facts, pending):
        claim = [
            ctx.instance_uuid,
            ctx.workspace_uuid,
            ctx.placement_generation,
            ctx.account_uuid,
            ctx.workspace.membership_uuid,
            ctx.workspace.membership_revision,
            str(PLANNER_VERSION),
            _fingerprint(row),
            plan,
            facts,
            pending['uuid'] if pending else None,
        ]
        # An authenticated opaque digest discloses neither credentials nor configs.
        return hmac.new(self._token_key, _json(claim).encode(), hashlib.sha256).hexdigest()

    async def preview(self, ctx: RequestContext):
        require_permission(ctx, Permission.RESOURCE_VIEW)
        async with self.pm.tenant_scope(ctx.workspace_uuid):
            await self._binding(ctx)
            items = []
            for row in await self._rows(ctx):
                plan, facts, pending, state, blockers = await self._plan(ctx, row)
                item = {
                    k: copy.deepcopy(plan[k])
                    for k in ('legacy_runner', 'target_runner_id', 'target_plugin', 'changed_paths', 'warnings')
                }
                item.update(
                    pipeline_uuid=row['uuid'],
                    name=row['name'],
                    state=state,
                    blockers=blockers,
                    preview_token=self._token(ctx, row, plan, facts, pending)
                    if state in ('ready', 'activation_pending')
                    else None,
                )
                items.append(item)
            return {
                'planner_version': str(PLANNER_VERSION),
                'workspace_uuid': ctx.workspace_uuid,
                'items': items,
                'total': len(items),
            }

    async def _selected(self, ctx, selection, *, data_only=False):
        rows = await self._rows(ctx, selection['pipeline_uuid'])
        if not rows:
            raise MigrationError('pipeline_not_found', 404)
        row = rows[0]
        plan, facts, pending, state, blockers = await self._plan(ctx, row)
        token = self._token(ctx, row, plan, facts, pending)
        if not hmac.compare_digest(token, selection['preview_token']):
            raise MigrationError('preview_stale')
        if state not in ('ready', 'activation_pending') and not (
            data_only
            and plan['state'] == 'ready'
            and all(b['code'] in ('plugin_missing', 'plugin_disabled') for b in blockers)
        ):
            raise MigrationError('migration_blocked')
        return row, plan, facts, pending

    async def execute(self, ctx: RequestContext, body):
        require_permission(ctx, Permission.RESOURCE_MANAGE)
        if isinstance(body, dict) and body.get('all') is True:
            if (
                set(body) != {'confirmed', 'all', 'install_plugins'}
                or body['confirmed'] is not True
                or not isinstance(body['install_plugins'], bool)
            ):
                raise MigrationError('confirmation_required', 400)
            return await self._execute_all(ctx, install_plugins=body['install_plugins'])
        items = validate_execute_request(body)
        async with self.pm.tenant_scope(ctx.workspace_uuid):
            await self._authorize(ctx)
            # Preflight the entire selection before creating tasks or contacting runtimes.
            for selection in items:
                await self._selected(ctx, selection)
        task_context = TaskContext.new()
        task_context.metadata = {
            'kind': 'pipeline_migration',
            'results': [{'pipeline_uuid': i['pipeline_uuid'], 'state': 'pending', 'code': None} for i in items],
        }
        task = self.ap.task_mgr.create_user_task(
            self._run(ctx, ExecutionContext.from_request(ctx), items, task_context),
            kind='pipeline_migration',
            name='pipeline_migration',
            context=task_context,
            instance_uuid=ctx.instance_uuid,
            workspace_uuid=ctx.workspace_uuid,
            placement_generation=ctx.placement_generation,
        )
        return {'task_id': task.id}

    async def _execute_all(self, ctx, *, install_plugins):
        # Capture all sources on admission. Plugin installation must not silently
        # include later edits or pipelines created while the task is running.
        if ctx.workspace_uuid in self._all_tasks:
            raise MigrationError('migration_running')
        self._all_tasks.add(ctx.workspace_uuid)
        try:
            async with self.pm.tenant_scope(ctx.workspace_uuid):
                await self._authorize(ctx)
                sources = []
                for row in await self._rows(ctx):
                    _, _, _, state, _ = await self._plan(ctx, row)
                    if state not in ('already_current', 'not_legacy'):
                        sources.append(row)
            if not sources:
                raise MigrationError('nothing_to_migrate')
            task_context = TaskContext.new()
            task_context.metadata = {
                'kind': 'pipeline_migration',
                'phase': 'installing' if install_plugins else 'migrating',
                'installations': [],
                'results': [{'pipeline_uuid': row['uuid'], 'state': 'pending', 'code': None} for row in sources],
            }
            task = self.ap.task_mgr.create_user_task(
                self._run_all(
                    ctx, ExecutionContext.from_request(ctx), sources, task_context, install_plugins=install_plugins
                ),
                kind='pipeline_migration',
                name='pipeline_migration',
                context=task_context,
                instance_uuid=ctx.instance_uuid,
                workspace_uuid=ctx.workspace_uuid,
                placement_generation=ctx.placement_generation,
            )
            return {'task_id': task.id, 'pipeline_uuids': [row['uuid'] for row in sources]}
        except BaseException:
            self._all_tasks.discard(ctx.workspace_uuid)
            raise

    async def _run_all(self, ctx, execution, sources, task_context, *, install_plugins):
        installed = {}
        try:
            async with self.pm.tenant_scope(execution.workspace_uuid):
                for source, result in zip(sources, task_context.metadata['results']):
                    if result['state'] != 'pending':
                        continue
                    try:
                        await self._authorize(ctx)
                        current = await self._rows(ctx, source['uuid'])
                        if not current or _fingerprint(current[0]) != _fingerprint(source):
                            raise MigrationError('preview_stale')
                        plan, facts, pending, state, blockers = await self._plan(ctx, current[0])
                        hard_blockers = [b for b in blockers if b['code'] not in ('plugin_missing', 'plugin_disabled')]
                        if hard_blockers:
                            raise MigrationError(hard_blockers[0]['code'])
                        if state in ('already_current', 'not_legacy'):
                            result.update(state='already_current', code=None)
                            continue
                        target = plan.get('target_plugin')
                        if not target:
                            raise MigrationError('migration_blocked')
                        if not install_plugins:
                            selection = {
                                'pipeline_uuid': source['uuid'],
                                'preview_token': self._token(ctx, current[0], plan, facts, pending),
                            }
                            await self._run(ctx, execution, [selection], task_context, results=[result], data_only=True)
                            continue
                        key = (target['author'], target['name'], target['version'])
                        if key not in installed:
                            runners = await self.ap.runner_registry.list_runners(
                                execution, use_cache=False, usage='agent'
                            )
                            descriptor = next((r for r in runners if r.id == plan['target_runner_id']), None)
                            ready = (
                                facts
                                and facts['enabled']
                                and descriptor
                                and descriptor.plugin_version == target['version']
                            )
                            if not ready:
                                task_context.metadata['phase'] = 'installing'
                                install_context = MigrationInstallContext(target)
                                task_context.metadata['installations'].append(install_context.progress)
                                observer = asyncio.create_task(install_context.observe())
                                install_code = 'operation_cancelled'
                                try:
                                    await self._authorize(ctx)
                                    await self.ap.plugin_connector.require_workspace_context(execution)
                                    await self.ap.plugin_connector.install_plugin(
                                        PluginInstallSource.MARKETPLACE,
                                        {
                                            'plugin_author': target['author'],
                                            'plugin_name': target['name'],
                                            'plugin_version': target['version'],
                                        },
                                        task_context=install_context,
                                    )
                                    install_code = None
                                except PluginRuntimeNotConnectedError:
                                    install_code = 'plugin_runtime_unavailable'
                                except MarketplacePluginVersionNotFoundError:
                                    install_code = 'plugin_version_unavailable'
                                except httpx.TimeoutException:
                                    install_code = 'plugin_download_timeout'
                                except httpx.HTTPStatusError as exc:
                                    install_code = (
                                        'plugin_version_unavailable'
                                        if exc.response.status_code == 404
                                        else 'plugin_marketplace_unavailable'
                                    )
                                except httpx.RequestError:
                                    install_code = 'plugin_download_failed'
                                except PluginInstallationFailedError as exc:
                                    install_code = {
                                        'dependency_prepare_failed': 'dependency_prepare_failed',
                                        'worker_launch_failed': 'plugin_launch_failed',
                                    }.get(exc.error_code, 'plugin_install_failed')
                                except Exception:
                                    install_code = 'plugin_install_failed'
                                finally:
                                    observer.cancel()
                                    try:
                                        await observer
                                    except asyncio.CancelledError:
                                        pass
                                    install_context.finish(install_code)
                                installed[key] = install_code
                            else:
                                installed[key] = None
                        if installed[key]:
                            raise MigrationError(installed[key])
                        await self._authorize(ctx)
                        current = await self._rows(ctx, source['uuid'])
                        if not current or _fingerprint(current[0]) != _fingerprint(source):
                            raise MigrationError('preview_stale')
                        plan, facts, pending, state, blockers = await self._plan(ctx, current[0])
                        if state not in ('ready', 'activation_pending'):
                            raise MigrationError(blockers[0]['code'] if blockers else 'migration_blocked')
                        selection = {
                            'pipeline_uuid': source['uuid'],
                            'preview_token': self._token(ctx, current[0], plan, facts, pending),
                        }
                        task_context.metadata['phase'] = 'migrating'
                        await self._run(ctx, execution, [selection], task_context, results=[result])
                    except Exception as exc:
                        result.update(
                            state='blocked' if isinstance(exc, MigrationError) else 'failed',
                            code=_failure_code(exc),
                        )
                    if any(
                        r['code'] in ('operation_cancelled', 'commit_outcome_unknown')
                        for r in task_context.metadata['results']
                    ):
                        break
        finally:
            for result in task_context.metadata['results']:
                if result['state'] == 'pending':
                    result.update(state='failed', code='operation_cancelled')
            task_context.metadata['phase'] = 'finished'
            self._all_tasks.discard(ctx.workspace_uuid)
        return task_context.metadata

    async def _verify_runtime(self, execution, plan):
        runners = await self.ap.runner_registry.list_runners(execution, use_cache=False, usage='agent')
        descriptor = next((r for r in runners if r.id == plan['target_runner_id']), None)
        if descriptor is None or 'agent' not in descriptor.usages:
            raise MigrationError('runner_unavailable')
        if descriptor.plugin_version != plan['target_plugin']['version']:
            raise MigrationError('plugin_version_incompatible')
        config = plan['config']
        RunnerConfigResolver.validate_pipeline_config(config)
        runner_config = config['ai']['runner_config'][plan['target_runner_id']]
        schema = {item['name']: item for item in descriptor.config_schema}
        # Host fields have their own scope/capability checks below; plugin
        # schema defaults must never implicitly authorize a foreign resource.
        host_fields = {
            'enable-all-tools': 'boolean',
            'tools': 'array',
            'knowledge-bases': 'knowledge-base-multi-selector',
            'mcp-resources': 'array',
            'mcp-resource-agent-read-enabled': 'boolean',
        }
        for name, value in runner_config.items():
            field = schema.get(name)
            if field is None and name in host_fields:
                field = {'type': host_fields[name]}
            if field is None:
                raise MigrationError('runner_schema_incompatible')
            if value is None and field.get('nullable') is True:
                continue
            kind = config_schema.normalize_schema_item_type(field.get('type'))
            valid = (
                (
                    kind
                    in (
                        'string',
                        'text',
                        'password',
                        'secret',
                        'select',
                        'llm-model-selector',
                        'embedding-model-selector',
                        'rerank-model-selector',
                    )
                    and isinstance(value, str)
                )
                or (kind == 'boolean' and type(value) is bool)
                or (kind in ('integer', 'int') and type(value) is int)
                or (kind in ('float', 'number') and type(value) in (int, float))
                or (
                    kind
                    in (
                        'array',
                        'multi-select',
                        'knowledge-base-selector',
                        'knowledge-base-multi-selector',
                        'prompt-editor',
                    )
                    and isinstance(value, list)
                )
                or (kind in ('object', 'json') and type(value) is dict)
                or (kind == 'array[string]' and type(value) is list and all(type(v) is str for v in value))
                or (
                    kind == 'model-fallback-selector'
                    and (
                        isinstance(value, str)
                        or isinstance(value, dict)
                        and set(value) <= {'primary', 'fallbacks', 'reasoning'}
                        and isinstance(value.get('primary'), str)
                        and isinstance(value.get('fallbacks', []), list)
                        and all(isinstance(v, str) for v in value.get('fallbacks', []))
                        and isinstance(value.get('reasoning', {}), dict)
                    )
                )
            )
            if not valid:
                raise MigrationError('runner_schema_incompatible')
            if kind == 'select' and field.get('options') and field.get('allow_custom') is not True:
                if value not in [o.get('value', o.get('name')) for o in field['options']]:
                    raise MigrationError('runner_schema_incompatible')
        if any(
            f.get('required') and name not in runner_config and f.get('default') is None for name, f in schema.items()
        ):
            raise MigrationError('runner_schema_incompatible')
        await self._verify_resources(execution, descriptor, runner_config)
        return _json(
            [
                descriptor.id,
                descriptor.plugin_version,
                descriptor.usages,
                descriptor.config_schema,
                getattr(descriptor, 'capabilities', None),
                getattr(descriptor, 'permissions', None),
            ]
        )

    async def _verify_resources(self, execution, descriptor, runner_config):
        """Fail closed on references the scoped Host cannot authorize.

        This runs only on explicit execution, outside the mutation transaction.
        Resource use is still reauthorized by the Host on every eventual run.
        """

        async def require_row(model, identifier, *, column=None):
            column = model.uuid if column is None else column
            found = (
                await self.pm.execute_async(
                    sa.select(model.uuid).where(
                        model.workspace_uuid == execution.workspace_uuid,
                        column == identifier,
                    )
                )
            ).first()
            if found is None:
                raise MigrationError('runner_resource_unavailable')

        permissions = getattr(descriptor, 'permissions', None)
        for model_type, model_uuid in config_schema.iter_config_model_refs(descriptor, runner_config):
            allowed = set(getattr(permissions, 'models', []))
            if not (allowed & ({'rerank'} if model_type == 'rerank' else {'invoke', 'stream'})):
                raise MigrationError('runner_resource_unavailable')
            await require_row(RerankModel if model_type == 'rerank' else LLMModel, model_uuid)
        for field in config_schema.iter_schema_items(descriptor, {'embedding-model-selector'}):
            value = runner_config.get(field['name'])
            if value and value not in config_schema.NONE_SENTINELS:
                await require_row(EmbeddingModel, value)

        kb_ids = runner_config.get('knowledge-bases', [])
        if not isinstance(kb_ids, list) or any(not isinstance(v, str) or not v for v in kb_ids):
            raise MigrationError('runner_resource_unavailable')
        if kb_ids:
            if not config_schema.uses_host_knowledge_bases(descriptor) or 'retrieve' not in getattr(
                permissions, 'knowledge_bases', []
            ):
                raise MigrationError('runner_resource_unavailable')
            for kb_id in kb_ids:
                await require_row(KnowledgeBase, kb_id)

        tool_names = runner_config.get('tools', [])
        if not isinstance(tool_names, list) or any(not isinstance(v, str) or not v for v in tool_names):
            raise MigrationError('runner_resource_unavailable')
        tool_grant = (
            runner_config.get('enable-all-tools', False)
            or tool_names
            or runner_config.get('mcp-resource-agent-read-enabled', False)
        )
        if tool_grant:
            if not config_schema.uses_host_tools(descriptor) or 'call' not in getattr(permissions, 'tools', []):
                raise MigrationError('runner_resource_unavailable')
            policy = ResourcePolicyProjector.from_runner_config(runner_config)
            tools = await AgentResourceBuilder(self.ap)._build_tools_from_binding(
                execution,
                permissions,
                policy,
                descriptor,
                runner_config,
            )
            if not set(tool_names) <= {tool['tool_name'] for tool in tools}:
                raise MigrationError('runner_resource_unavailable')

        for attachment in runner_config.get('mcp-resources', []):
            if not isinstance(attachment, dict):
                raise MigrationError('runner_resource_unavailable')
            identifier = attachment.get('server_uuid') or attachment.get('server_id')
            name = attachment.get('server_name')
            if identifier:
                await require_row(MCPServer, identifier)
            elif name:
                await require_row(MCPServer, name, column=MCPServer.name)
            else:
                raise MigrationError('runner_resource_unavailable')

    async def _lock(self, ctx, pipeline_uuid, session):
        # Every pending producer shares this row and revalidates its captured
        # configuration/conversation authority after acquiring admission.
        if self.pm.get_db_engine().dialect.name not in {'sqlite', 'postgresql'}:
            raise MigrationError('runtime.pending_interaction')
        await lock_pipeline_admission(session, ctx.workspace_uuid, pipeline_uuid)
        # Hold revocable directory rows through commit (no network in this UoW).
        await session.execute(sa.select(User.uuid).where(User.uuid == ctx.account_uuid).with_for_update())
        for model, condition in [
            (Workspace, Workspace.uuid == ctx.workspace_uuid),
            (WorkspaceExecutionState, WorkspaceExecutionState.workspace_uuid == ctx.workspace_uuid),
            (
                WorkspaceMembership,
                sa.and_(
                    WorkspaceMembership.workspace_uuid == ctx.workspace_uuid,
                    WorkspaceMembership.account_uuid == ctx.account_uuid,
                ),
            ),
            (PluginSetting, PluginSetting.workspace_uuid == ctx.workspace_uuid),
        ]:
            await session.execute(sa.select(model.__table__).where(condition).with_for_update())

    async def _commit(self, ctx, selection, expected_facts, candidate, *, data_only=False):
        async with self.pm.tenant_uow(ctx.workspace_uuid) as uow:
            await self._lock(ctx, selection['pipeline_uuid'], uow.session)
            await self._authorize(ctx, uow.session)
            row, plan, facts, pending = await self._selected(ctx, selection, data_only=data_only)
            if facts != expected_facts:
                raise MigrationError('plugin_changed')
            if pending:
                return pending['uuid'], pending['target_fingerprint']
            target = {**row, 'config': candidate['config']}
            t = LegacyPipeline.__table__
            cas = [t.c.workspace_uuid == ctx.workspace_uuid, t.c.uuid == row['uuid']]
            for key in ('config', 'stages', 'extensions_preferences'):
                cas.append(sa.cast(t.c[key], sa.Text) == row['_raw_' + key])
            result = await self.pm.execute_async(sa.update(t).where(*cas).values(config=candidate['config']))
            if result.rowcount != 1:
                raise MigrationError('preview_stale')
            snapshot_uuid = str(uuid.uuid4())
            target_fingerprint = _fingerprint(target)
            await self.pm.execute_async(
                sa.insert(PipelineMigrationSnapshot).values(
                    uuid=snapshot_uuid,
                    workspace_uuid=ctx.workspace_uuid,
                    pipeline_uuid=row['uuid'],
                    source_fingerprint=_fingerprint(row),
                    target_fingerprint=target_fingerprint,
                    source_snapshot=json.loads(_json({k: v for k, v in row.items() if not k.startswith('_')})),
                    planner_version=str(PLANNER_VERSION),
                    state='activation_pending',
                )
            )
            if self._native_interactions(ctx, row['uuid']):
                raise MigrationError('runtime.pending_interaction')
        return snapshot_uuid, target_fingerprint

    async def _activate(self, ctx, selection, snapshot_uuid, target_fingerprint, candidate, plan, expected_facts):
        # Re-read the committed target under a short lock before synchronous
        # publication. A later editor must never be replaced by our old candidate.
        async with self.pm.tenant_uow(ctx.workspace_uuid) as uow:
            await self._lock(ctx, selection['pipeline_uuid'], uow.session)
            await self._authorize(ctx, uow.session)
            rows = await self._rows(ctx, selection['pipeline_uuid'])
            if not rows or _fingerprint(rows[0]) != target_fingerprint:
                raise MigrationError('activation_source_changed')
            if await self._plugin(ctx, plan) != expected_facts:
                raise MigrationError('plugin_changed')
            _, interaction_blocked = await self._interaction_state(ctx, selection['pipeline_uuid'])
            if interaction_blocked:
                raise MigrationError('runtime.pending_interaction')
            # Native cache inspection above is the last await before publication
            # and session invalidation; no native producer can interleave here.
            self.ap.pipeline_mgr.publish_pipeline(candidate)
            for session in self.ap.sess_mgr.session_list:
                conversation = session.using_conversation
                if (
                    conversation is not None
                    and conversation.pipeline_uuid == selection['pipeline_uuid']
                    and getattr(session, 'workspace_uuid', None) == ctx.workspace_uuid
                ):
                    session.using_conversation = None
            t = PipelineMigrationSnapshot.__table__
            await self.pm.execute_async(
                sa.update(t)
                .where(t.c.workspace_uuid == ctx.workspace_uuid, t.c.uuid == snapshot_uuid)
                .values(state='active')
            )

    async def _run(self, ctx, execution, items, task_context, results=None, *, data_only=False):
        async with self.pm.tenant_scope(execution.workspace_uuid):
            for selection, result in zip(items, results if results is not None else task_context.metadata['results']):
                committed = False
                commit_attempted = False
                try:
                    await self._authorize(ctx)
                    row, plan, facts, pending = await self._selected(ctx, selection, data_only=data_only)
                    runtime_schema = None if data_only else await self._verify_runtime(execution, plan)
                    RunnerConfigResolver.validate_pipeline_config(plan['config'])
                    candidate_entity = {k: copy.deepcopy(v) for k, v in row.items() if not k.startswith('_')}
                    candidate_entity['config'] = copy.deepcopy(plan['config'])
                    runtime = await self.ap.pipeline_mgr.prepare_pipeline(execution, copy.deepcopy(candidate_entity))
                    if not data_only and await self._verify_runtime(execution, plan) != runtime_schema:
                        raise MigrationError('runner_schema_changed')
                    # Runtime awaits are over. Recheck authorization/source/plugin
                    # facts under database locks, then atomically journal and CAS.
                    commit_attempted = True
                    snapshot_uuid, target_fingerprint = await self._commit(
                        ctx, selection, facts, candidate_entity, **({'data_only': True} if data_only else {})
                    )
                    committed = True
                    await self._activate(ctx, selection, snapshot_uuid, target_fingerprint, runtime, plan, facts)
                    result.update(state='migrated', code='data_only' if data_only else None)
                except (Exception, asyncio.CancelledError) as exc:
                    cancelled = isinstance(exc, asyncio.CancelledError)
                    reconciliation_cancel = None
                    code = 'operation_cancelled' if cancelled else _failure_code(exc)
                    if commit_attempted and not committed and not isinstance(exc, MigrationError):
                        # A commit can succeed while acknowledgement/connection
                        # cleanup fails, including cancellation. Make one read
                        # after the UoW has unwound, in this task's tenant scope;
                        # never shield/retry through another cancellation.
                        try:
                            t = PipelineMigrationSnapshot.__table__
                            conditions = [
                                t.c.workspace_uuid == ctx.workspace_uuid,
                                t.c.pipeline_uuid == selection['pipeline_uuid'],
                                t.c.source_fingerprint
                                == (pending['source_fingerprint'] if pending else _fingerprint(row)),
                                t.c.target_fingerprint == _fingerprint(candidate_entity),
                                t.c.planner_version == str(PLANNER_VERSION),
                            ]
                            if pending:
                                # A retry starts from the target, not the legacy
                                # source. Only the original snapshot proves this
                                # durable migration; an unrelated journal cannot.
                                conditions.extend(
                                    [
                                        t.c.uuid == pending['uuid'],
                                        t.c.target_fingerprint == pending['target_fingerprint'],
                                    ]
                                )
                            found = (await self.pm.execute_async(sa.select(t.c.uuid).where(*conditions))).first()
                            committed = found is not None
                        except asyncio.CancelledError as cancel_exc:
                            reconciliation_cancel = cancel_exc
                            cancelled = True
                            code = 'commit_outcome_unknown'
                        except Exception:
                            code = 'commit_outcome_unknown'
                    state = (
                        # Unknown is deliberately recovery-needed, not a claim
                        # of rollback or proof that a snapshot was committed.
                        'activation_pending'
                        if committed or code == 'commit_outcome_unknown'
                        else 'stale'
                        if code == 'preview_stale'
                        else 'blocked'
                        if isinstance(exc, MigrationError)
                        else 'failed'
                    )
                    result.update(state=state, code=code)
                    if cancelled:
                        for unstarted in task_context.metadata['results']:
                            if unstarted['state'] == 'pending':
                                unstarted.update(state='failed', code='operation_cancelled')
                        if reconciliation_cancel is not None:
                            # Preserve cancellation propagation during recovery,
                            # but record safe outcomes before leaving the task.
                            raise reconciliation_cancel
                        return task_context.metadata
                    # Never attach the original exception, traceback or plugin
                    # diagnostic to TaskContext: upstream errors can contain keys.
            return task_context.metadata
