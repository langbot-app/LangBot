"""Workspace-scoped scenario export, draft import and resumable setup reports."""

import copy
import json
import uuid

import sqlalchemy as sa

from ....agent.runner.config_resolver import RunnerConfigResolver
from ....agent.runner.errors import RunnerNotFoundError
from ....cloud.plan_policy import require_workspace_platform
from ....entity.persistence.agent import Agent
from ....entity.persistence.bot import Bot
from ....entity.persistence.metadata import WorkspaceMetadata
from ....entity.persistence.pipeline import LegacyPipeline
from ....entity.persistence.rag import KnowledgeBase
from ....entity.persistence.model import LLMModel
from ....i18n import t
from ....workspace.errors import WorkspaceNotFoundError
from .pipeline import default_stage_order
from .scenario_format import (
    ScenarioDependency,
    ScenarioInput,
    ScenarioMetadata,
    ScenarioPackage,
    ScenarioResource,
    parse_package,
    project_config,
    read_path,
    scrub_nested,
)
from .tenant import require_workspace_uuid, scope_statement
from .workspace_limits import workspace_limits


MODELS = {'bot': Bot, 'pipeline': LegacyPipeline, 'agent': Agent, 'event_processor': Agent}
FIELDS = {
    'bot': {'name', 'description', 'adapter', 'adapter_config', 'event_bindings', 'plugin_processors'},
    'pipeline': {'name', 'description', 'emoji', 'config', 'extensions_preferences'},
    'agent': {'name', 'description', 'emoji', 'config', 'supported_event_patterns', 'component_ref'},
    'event_processor': {'name', 'description', 'emoji', 'config', 'supported_event_patterns', 'component_ref'},
}
PREFIX = 'scenario_import:'


class ScenarioPackService:
    def __init__(self, ap):
        self.ap = ap

    async def _row(self, context, kind, resource_uuid):
        model = MODELS[kind]
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sa.select(model).where(model.uuid == resource_uuid),
                model,
                context,
            )
        )
        row = result.first()
        if row is None:
            raise WorkspaceNotFoundError('Scenario resource not found')
        return self.ap.persistence_mgr.serialize_model(model, row)

    async def export(self, context, bot_uuid, metadata=None):
        bot = await self._row(context, 'bot', bot_uuid)
        package = ScenarioPackage.model_construct(
            format='langbot-scenario',
            format_version=1,
            metadata=ScenarioMetadata.model_validate(metadata or {'name': bot['name']}),
            resources=[],
            inputs=[],
            dependencies=[],
        )
        mapped = {('bot', bot_uuid): 'main'}

        async def collect(kind, source_uuid):
            key = (kind, source_uuid)
            if key in mapped:
                return mapped[key]
            local_id = f'resource_{len(mapped)}'
            mapped[key] = local_id
            row = await self._row(context, kind, source_uuid)
            data = {field: copy.deepcopy(row[field]) for field in FIELDS[kind] if field in row}
            await self._project_processor(context, package, local_id, kind, data)
            package.resources.append(ScenarioResource(id=local_id, kind=kind, data=data))
            return local_id

        data = {field: copy.deepcopy(bot[field]) for field in FIELDS['bot']}
        component = self.ap.bot_service._get_adapter_component(bot['adapter'])
        if component is None:
            raise ValueError('Unsupported scenario adapter')
        data['adapter_config'], inputs = project_config(
            data['adapter_config'],
            component.spec.get('config', []),
            'main',
            ['adapter_config'],
            platform=True,
        )
        package.inputs.extend(inputs)
        for index, binding in enumerate(data['event_bindings']):
            binding['id'] = f'route_{index}'
            if binding['target_type'] != 'discard':
                binding['target_uuid'] = await collect(binding['target_type'], binding['target_uuid'])
            if binding.get('filters'):
                binding['filters'] = []
                # Disabled until the importer explicitly restores deployment-specific routing.
                binding['enabled'] = False
                package.inputs.append(
                    ScenarioInput(
                        resource='main',
                        path=['event_bindings', index, 'filters'],
                        kind='configuration',
                        label='Route filters',
                        required=True,
                    )
                )
        for subscription in data['plugin_processors']:
            subscription['processor_uuid'] = await collect('event_processor', subscription['processor_uuid'])
        package.resources.insert(0, ScenarioResource(id='main', kind='bot', data=data))
        return parse_package(package.model_dump()).model_dump()

    async def _project_processor(self, context, package, resource_id, kind, data):
        config = data['config']
        container = config.get('ai', {}) if kind == 'pipeline' else config
        runner_id = container.get('runner', {}).get('id', '')
        if not runner_id:
            raise ValueError('Configure a Runner before exporting this scenario')
        descriptor = await self.ap.runner_registry.get(context, runner_id)
        if descriptor is None:
            raise ValueError('Scenario Runner is not installed')
        dependency = ScenarioDependency(
            kind='runner',
            id=runner_id,
            plugin_id=descriptor.get_plugin_id(),
            version=descriptor.plugin_version,
        )
        if dependency not in package.dependencies:
            package.dependencies.append(dependency)
        source = container.get('runner_config', {}).get(runner_id, {})
        for field in descriptor.config_schema:
            if 'knowledge' not in field.get('type', ''):
                continue
            references = source.get(field['name']) or []
            for kb_uuid in references if isinstance(references, list) else [references]:
                result = await self.ap.persistence_mgr.execute_async(
                    scope_statement(
                        sa.select(KnowledgeBase.knowledge_engine_plugin_id).where(KnowledgeBase.uuid == kb_uuid),
                        KnowledgeBase,
                        context,
                    )
                )
                plugin_id = result.scalar()
                if plugin_id:
                    dep = ScenarioDependency(kind='knowledge_plugin', id=plugin_id, plugin_id=plugin_id)
                    if dep not in package.dependencies:
                        package.dependencies.append(dep)
        prefix = ['config', 'ai'] if kind == 'pipeline' else ['config']
        projected, inputs = project_config(
            source,
            descriptor.config_schema,
            resource_id,
            [*prefix, 'runner_config', runner_id],
        )
        package.inputs.extend(inputs)
        # Do not carry inactive Runner configurations or Host resource grants across Workspaces.
        container.clear()
        container.update(runner={'id': runner_id, 'expire-time': 0}, runner_config={runner_id: projected})
        if kind == 'pipeline':
            original_extensions = data.get('extensions_preferences') or {}
            metadata = await self.ap.pipeline_service.get_pipeline_metadata(context)
            sections = {section['name']: section for section in metadata}
            for section_name in list(config):
                if section_name == 'ai':
                    continue
                section = config[section_name]
                stages = {stage['name']: stage for stage in sections.get(section_name, {}).get('stages', [])}
                for stage_name, values in list(section.items()):
                    projected, inputs = project_config(
                        values,
                        stages.get(stage_name, {}).get('config', []),
                        resource_id,
                        ['config', section_name, stage_name],
                    )
                    section[stage_name] = projected
                    package.inputs.extend(inputs)
            data['extensions_preferences'] = {
                'enable_all_plugins': False,
                'enable_all_mcp_servers': False,
                'plugins': [],
                'mcp_servers': [],
                'mcp_resources': [],
                'mcp_resource_agent_read_enabled': False,
                'enable_all_skills': False,
                'skills': [],
            }
            for field in ('plugins', 'mcp_servers', 'mcp_resources', 'skills'):
                if original_extensions.get(field):
                    package.inputs.append(
                        ScenarioInput(
                            resource=resource_id,
                            path=['extensions_preferences', field],
                            kind='extensions',
                            label=field,
                            required=True,
                        )
                    )

    async def preview(self, context, document):
        package = parse_package(document)
        workspace = require_workspace_uuid(context)
        for resource in package.resources:
            resource.data = scrub_nested(resource.data)
            if set(resource.data) - FIELDS[resource.kind]:
                raise ValueError('Unsupported scenario resource field')
            if not isinstance(resource.data.get('name'), str) or not resource.data['name'].strip():
                raise ValueError('Scenario resource name is required')
            if resource.kind == 'bot':
                if self.ap.bot_service._get_adapter_component(resource.data.get('adapter')) is None:
                    raise ValueError('Unsupported scenario adapter')
                if not isinstance(resource.data.get('adapter_config'), dict):
                    raise ValueError('Invalid adapter configuration')
                for route in resource.data.get('event_bindings', []):
                    if not isinstance(route.get('event_pattern'), str) or not route['event_pattern']:
                        raise ValueError('Scenario route event_pattern is required')
                component = self.ap.bot_service._get_adapter_component(resource.data['adapter'])
                for field in component.spec.get('config', []):
                    if field.get('type') in {'password', 'secret'} or field.get('secret'):
                        resource.data['adapter_config'][field['name']] = ''
                await require_workspace_platform(self.ap, workspace, resource.data['adapter'])
            elif resource.kind == 'pipeline':
                RunnerConfigResolver.validate_pipeline_config(resource.data.get('config'))
            else:
                RunnerConfigResolver.validate_agent_config(resource.data.get('config'))
            if resource.kind != 'bot':
                config = resource.data['config']
                container = config.get('ai', {}) if resource.kind == 'pipeline' else config
                runner_id = container.get('runner', {}).get('id')
                if not runner_id:
                    raise ValueError('Scenario processor requires a Runner')
                if not any(dep.kind == 'runner' and dep.id == runner_id for dep in package.dependencies):
                    raise ValueError('Missing scenario Runner dependency declaration')
        limits = await workspace_limits(self.ap, workspace)
        for kind, limit_key in [('bot', 'max_bots'), ('pipeline', 'max_pipelines')]:
            limit = limits.get(limit_key, -1)
            if limit >= 0:
                model = MODELS[kind]
                result = await self.ap.persistence_mgr.execute_async(
                    scope_statement(
                        sa.select(sa.func.count()).select_from(model),
                        model,
                        context,
                    )
                )
                if result.scalar() + sum(item.kind == kind for item in package.resources) > limit:
                    raise ValueError(f'Scenario exceeds {limit_key}')
        return {'package': package.model_dump(), 'dependencies': await self._dependencies(context, package)}

    async def _dependencies(self, context, package):
        statuses = []
        for dependency in package.dependencies:
            status = 'configure'
            if dependency.kind == 'runner':
                try:
                    descriptor = await self.ap.runner_registry.get(context, dependency.id)
                except (ValueError, RunnerNotFoundError):
                    descriptor = None
                status = 'missing' if descriptor is None else 'ready'
                if descriptor and dependency.version and descriptor.plugin_version != dependency.version:
                    status = 'version_mismatch'
            statuses.append({**dependency.model_dump(), 'status': status})
        return statuses

    async def import_package(self, context, document, request_id):
        request_id = str(uuid.UUID(request_id))
        workspace = require_workspace_uuid(context)
        async with self.ap.persistence_mgr.tenant_uow(workspace):
            existing = await self._record(context, request_id)
            if existing:
                return await self.status(context, request_id)
            preview = await self.preview(context, document)
            package = parse_package(preview['package'])
            # Persist a sanitized document, never credential values supplied in an
            # uploaded package. Exported templates already use these empty slots.
            by_id = {item.id: item for item in package.resources}
            for item in package.inputs:
                if item.kind != 'credential':
                    continue
                parent = read_path(by_id[item.resource].data, item.path[:-1])
                parent[item.path[-1]] = ''
            mapping = {item.id: str(uuid.uuid4()) for item in package.resources}
            for item in package.resources:
                values = copy.deepcopy(item.data)
                values.update(uuid=mapping[item.id], workspace_uuid=workspace)
                values.setdefault('description', '')
                if item.kind == 'bot':
                    values['enable'] = False
                    for route in values.get('event_bindings', []):
                        route['id'] = str(uuid.uuid4())
                        if route['target_type'] != 'discard':
                            route['target_uuid'] = mapping[route['target_uuid']]
                    for subscription in values.get('plugin_processors', []):
                        subscription['processor_uuid'] = mapping[subscription['processor_uuid']]
                elif item.kind == 'pipeline':
                    values.update(
                        is_default=False,
                        stages=default_stage_order.copy(),
                        for_version=self.ap.ver_mgr.get_current_version(),
                    )
                else:
                    values['kind'] = item.kind
                    values['component_ref'] = values['config']['runner']['id']
                await self.ap.persistence_mgr.execute_async(sa.insert(MODELS[item.kind]).values(**values))
            record = {'package': package.model_dump(), 'mapping': mapping}
            await self.ap.persistence_mgr.execute_async(
                sa.insert(WorkspaceMetadata).values(
                    workspace_uuid=workspace,
                    key=PREFIX + request_id,
                    value=json.dumps(record),
                )
            )
        return await self.status(context, request_id)

    async def _record(self, context, import_id):
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sa.select(WorkspaceMetadata.value).where(WorkspaceMetadata.key == PREFIX + import_id),
                WorkspaceMetadata,
                context,
            )
        )
        value = result.scalar()
        return json.loads(value) if value else None

    async def status(self, context, import_id):
        record = await self._record(context, import_id)
        if record is None:
            raise WorkspaceNotFoundError('Scenario import not found')
        package = parse_package(record['package'])
        resources = {}
        for resource in package.resources:
            try:
                resources[resource.id] = await self._row(context, resource.kind, record['mapping'][resource.id])
            except WorkspaceNotFoundError:
                resources[resource.id] = {}
        inputs = []
        for item in package.inputs:
            try:
                value = read_path(resources[item.resource], item.path)
                if item.kind == 'model' and isinstance(value, dict):
                    value = value.get('primary')
                ready = value not in ('', None, [], {}, '***')
            except ValueError:
                ready = False
            inputs.append({**item.model_dump(), 'status': 'ready' if ready else 'missing'})
        # Recompute required fields from trusted installed schemas; uploaded inputs
        # are helpful author hints, never the authority for activation readiness.
        known = {(item['resource'], tuple(item['path'])): item for item in inputs}
        for resource in package.resources:
            current = resources[resource.id]
            if not current:
                inputs.append(
                    {
                        'resource': resource.id,
                        'path': ['config'],
                        'kind': 'configuration',
                        'label': resource.data['name'],
                        'required': True,
                        'status': 'missing',
                    }
                )
                continue
            schemas = []
            if resource.kind == 'bot':
                component = self.ap.bot_service._get_adapter_component(current.get('adapter'))
                if component:
                    schemas.append((['adapter_config'], component.spec.get('config', [])))
            else:
                prefix = ['config', 'ai'] if resource.kind == 'pipeline' else ['config']
                try:
                    container = read_path(current, prefix)
                    runner_id = container['runner']['id']
                    descriptor = await self.ap.runner_registry.get(context, runner_id)
                    if descriptor:
                        schemas.append(([*prefix, 'runner_config', runner_id], descriptor.config_schema))
                except (ValueError, KeyError, RunnerNotFoundError):
                    pass
            for prefix, schema in schemas:
                for field in schema:
                    if not field.get('required') or field.get('type') == 'webhook-url':
                        continue
                    path = [*prefix, field['name']]
                    field_type = field.get('type', '')
                    kind = (
                        'model'
                        if 'model' in field_type
                        else 'knowledge'
                        if 'knowledge' in field_type
                        else 'configuration'
                    )
                    if (resource.id, tuple(path)) in known:
                        known[(resource.id, tuple(path))]['required'] = True
                        if kind != 'configuration':
                            known[(resource.id, tuple(path))]['kind'] = kind
                        continue
                    try:
                        value = read_path(current, path)
                        ready = value not in ('', None, [], {}, '***')
                    except ValueError:
                        ready = False
                    inputs.append(
                        {
                            'resource': resource.id,
                            'path': path,
                            'kind': kind,
                            'label': field.get('label') or field['name'],
                            'required': True,
                            'status': 'ready' if ready else 'missing',
                        }
                    )
        for item in inputs:
            if item['kind'] not in {'model', 'knowledge'} or item['status'] != 'ready':
                continue
            value = read_path(resources[item['resource']], item['path'])
            if item['kind'] == 'model' and isinstance(value, dict):
                value = [value.get('primary'), *value.get('fallbacks', [])]
            references = value if isinstance(value, list) else [value]
            model = LLMModel if item['kind'] == 'model' else KnowledgeBase
            for reference in references:
                if not isinstance(reference, str) or not reference:
                    item['status'] = 'missing'
                    break
                result = await self.ap.persistence_mgr.execute_async(
                    scope_statement(
                        sa.select(model.uuid).where(model.uuid == reference),
                        model,
                        context,
                    )
                )
                if result.scalar() is None:
                    item['status'] = 'missing'
                    break
        return {
            'id': import_id,
            'metadata': package.metadata.model_dump(),
            'resources': [
                {'id': item.id, 'kind': item.kind, 'uuid': record['mapping'][item.id], 'name': item.data['name']}
                for item in package.resources
            ],
            'inputs': inputs,
            'dependencies': await self._dependencies(context, package),
        }

    async def list_imports(self, context):
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sa.select(WorkspaceMetadata.key).where(WorkspaceMetadata.key.startswith(PREFIX)),
                WorkspaceMetadata,
                context,
            )
        )
        return [await self.status(context, row[0][len(PREFIX) :]) for row in result.all()]

    async def check_enable(self, context, bot_uuid):
        """Keep imported bots disabled until their persisted requirements are satisfied."""
        for report in await self.list_imports(context):
            if not any(item['kind'] == 'bot' and item['uuid'] == bot_uuid for item in report['resources']):
                continue
            if any(item['required'] and item['status'] != 'ready' for item in report['inputs']):
                raise ValueError(t('Complete the scenario setup checklist before enabling this bot.'))
            if any(item['kind'] == 'runner' and item['status'] != 'ready' for item in report['dependencies']):
                raise ValueError(t('Install compatible scenario Runner dependencies before enabling this bot.'))
            for resource in report['resources']:
                if resource['kind'] == 'pipeline':
                    pipeline = await self.ap.pipeline_service.get_pipeline(
                        context, resource['uuid'], include_secret=True
                    )
                    await self.ap.pipeline_mgr.load_pipeline(context, pipeline)
