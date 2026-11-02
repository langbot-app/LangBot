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
from ....entity.persistence.plugin import PluginSetting
from ....entity.persistence.pipeline import LegacyPipeline
from ....entity.persistence.rag import KnowledgeBase
from ....entity.persistence.mcp import MCPServer
from ....provider.tools.loaders.mcp_policy import require_stdio_mcp_enabled
from ....entity.persistence.model import LLMModel, EmbeddingModel, RerankModel
from ....i18n import t
from ....workspace.errors import WorkspaceNotFoundError
from .pipeline import default_stage_order
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource

from .scenario_format import (
    ScenarioDependency,
    ScenarioSelection,
    ScenarioInput,
    ScenarioMetadata,
    ScenarioPackage,
    ScenarioResource,
    parse_package,
    complete_pipeline_config,
    field_is_visible,
    project_config,
    read_path,
    scrub_nested,
)
from .tenant import require_workspace_uuid, scope_statement
from .workspace_limits import workspace_limits


MODELS = {
    'bot': Bot,
    'pipeline': LegacyPipeline,
    'agent': Agent,
    'event_processor': Agent,
    'knowledge_base': KnowledgeBase,
    'mcp_server': MCPServer,
}
FIELDS = {
    'mcp_server': {'name', 'mode', 'extra_args', 'readme', 'enable'},
    'knowledge_base': {
        'name',
        'description',
        'emoji',
        'knowledge_engine_plugin_id',
        'creation_settings',
        'retrieval_settings',
        'initialized',
    },
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

    async def export(self, context, bot_uuid, metadata=None, selection=None):
        selection = ScenarioSelection.model_validate(selection) if selection is not None else None
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
            if kind == 'knowledge_base':
                await self._project_knowledge(context, package, local_id, data)
            elif kind == 'mcp_server':
                self._project_mcp(package, local_id, data)
            else:
                await self._project_processor(context, package, local_id, kind, data, collect, selection)
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
        if selection is not None:
            selected = {
                'pipeline': set(selection.pipeline_uuids),
                'agent': set(selection.agent_uuids),
                'event_processor': set(selection.event_processor_uuids),
            }
            data['event_bindings'] = [
                route
                for route in data['event_bindings']
                if route['target_type'] == 'discard'
                or route['target_uuid'] in selected.get(route['target_type'], set())
            ]
            data['plugin_processors'] = [
                item for item in data['plugin_processors'] if item['processor_uuid'] in selected['event_processor']
            ]
        for index, binding in enumerate(data['event_bindings']):
            binding['id'] = f'route_{index}'
            if binding['target_type'] != 'discard':
                binding['target_uuid'] = await collect(binding['target_type'], binding['target_uuid'])
            binding['filters'] = scrub_nested(binding.get('filters', []))
        for subscription in data['plugin_processors']:
            subscription['processor_uuid'] = await collect('event_processor', subscription['processor_uuid'])
        if selection is not None:
            for kind, identifiers in (
                ('pipeline', selection.pipeline_uuids),
                ('agent', selection.agent_uuids),
                ('event_processor', selection.event_processor_uuids),
                ('knowledge_base', selection.knowledge_base_uuids),
                ('mcp_server', selection.mcp_server_uuids),
            ):
                for identifier in identifiers:
                    await collect(kind, identifier)
            if selection.plugin_ids:
                await self.ap.plugin_connector.require_workspace_context(context)
                installed = await self.ap.plugin_connector.list_plugins()
                available = {}
                for plugin in installed:
                    meta = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {})
                    available[f'{meta.get("author")}/{meta.get("name")}'] = meta
                for plugin_id in selection.plugin_ids:
                    if plugin_id not in available:
                        raise WorkspaceNotFoundError('Scenario plugin not found')
                    dependency = ScenarioDependency(
                        kind='plugin', id=plugin_id, plugin_id=plugin_id, version=available[plugin_id].get('version')
                    )
                    if dependency not in package.dependencies:
                        package.dependencies.append(dependency)
        if package.dependencies:
            await self.ap.plugin_connector.require_workspace_context(context)
            plugins = await self.ap.plugin_connector.list_plugins()
            for dependency in package.dependencies:
                plugin = next(
                    (
                        plugin
                        for plugin in plugins
                        if (
                            f'{plugin.get("manifest", {}).get("manifest", {}).get("metadata", {}).get("author")}/'
                            f'{plugin.get("manifest", {}).get("manifest", {}).get("metadata", {}).get("name")}'
                        )
                        == dependency.plugin_id
                    ),
                    None,
                )
                if plugin is None:
                    continue
                author, plugin_name = dependency.plugin_id.split('/', 1)
                result = await self.ap.persistence_mgr.execute_async(
                    scope_statement(
                        sa.select(PluginSetting.config).where(
                            PluginSetting.plugin_author == author, PluginSetting.plugin_name == plugin_name
                        ),
                        PluginSetting,
                        context,
                    )
                )
                stored = result.scalar()
                schema = plugin.get('manifest', {}).get('manifest', {}).get('spec', {}).get('config', [])
                dependency.config, _ = project_config(
                    stored if stored is not None else plugin.get('plugin_config', {}), schema, 'main', ['config']
                )
        package.resources.insert(0, ScenarioResource(id='main', kind='bot', data=data))
        return parse_package(package.model_dump()).model_dump()

    async def _project_processor(self, context, package, resource_id, kind, data, collect, selection):
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
        prefix = ['config', 'ai'] if kind == 'pipeline' else ['config']
        projected, inputs = project_config(
            source,
            descriptor.config_schema,
            resource_id,
            [*prefix, 'runner_config', runner_id],
        )
        for field in descriptor.config_schema:
            if 'knowledge' not in field.get('type', ''):
                continue
            references = source.get(field['name']) or []
            local_ids = [
                await collect('knowledge_base', ref)
                for ref in (references if isinstance(references, list) else [references])
                if selection is None or ref in selection.knowledge_base_uuids
            ]
            projected[field['name']] = (
                local_ids if isinstance(references, list) else (local_ids[0] if local_ids else '')
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
            plugin_ids = list(
                selection.plugin_ids if selection is not None else original_extensions.get('plugins') or []
            )
            if selection is None and original_extensions.get('enable_all_plugins'):
                await self.ap.plugin_connector.require_workspace_context(context)
                for plugin in await self.ap.plugin_connector.list_plugins():
                    metadata = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {})
                    plugin_ids.append(f'{metadata.get("author")}/{metadata.get("name")}')
            data['extensions_preferences']['plugins'] = list(dict.fromkeys(plugin_ids))
            for plugin_id in data['extensions_preferences']['plugins']:
                dependency = ScenarioDependency(kind='plugin', id=plugin_id, plugin_id=plugin_id)
                if dependency not in package.dependencies:
                    package.dependencies.append(dependency)
            mcp_ids = []
            if selection is not None:
                for identifier in selection.mcp_server_uuids:
                    mcp_ids.append(await collect('mcp_server', identifier))
            data['extensions_preferences']['mcp_servers'] = mcp_ids
            for field in ('mcp_resources', 'skills'):
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

    @staticmethod
    def _project_mcp(package, resource_id, data):
        data['enable'] = False
        package.inputs.append(
            ScenarioInput(resource=resource_id, path=['enable'], kind='configuration', label='Enable MCP server')
        )
        args = data.get('extra_args') or {}
        projected = scrub_nested(args)
        for section in ('env', 'headers'):
            if isinstance(projected.get(section), dict):
                for key in projected[section]:
                    projected[section][key] = ''
        data['extra_args'] = projected

        def missing(original, cleaned, path):
            if isinstance(original, dict) and isinstance(cleaned, dict):
                for key in cleaned:
                    missing(original.get(key), cleaned[key], [*path, key])
            elif original not in ('', None, [], {}) and cleaned in ('', None, [], {}):
                package.inputs.append(
                    ScenarioInput(resource=resource_id, path=path, kind='credential', label=str(path[-1]))
                )

        missing(args, projected, ['extra_args'])

    async def _project_knowledge(self, context, package, resource_id, data):
        data['initialized'] = False
        plugin_id = data['knowledge_engine_plugin_id']
        dependency = ScenarioDependency(kind='knowledge_plugin', id=plugin_id, plugin_id=plugin_id)
        if not any(item.kind == dependency.kind and item.id == dependency.id for item in package.dependencies):
            package.dependencies.append(dependency)
        for section, getter in (
            ('creation_settings', self.ap.knowledge_service.get_engine_creation_schema),
            ('retrieval_settings', self.ap.knowledge_service.get_engine_retrieval_schema),
        ):
            schema = await getter(context, plugin_id)
            fields = schema if isinstance(schema, list) else schema.get('schema', [])
            # Ordinary engine settings are portable; resource selectors and secrets
            # still use the normal projection and become recipient setup inputs.
            fields = [{**field, 'scenario_portable': True} for field in fields]
            values = data.get(section) or {}
            known = {field['name'] for field in fields}
            fields.extend({'name': name, 'scenario_portable': True} for name in values if name not in known)
            data[section], inputs = project_config(values, fields, resource_id, [section])
            package.inputs.extend(inputs)
        package.inputs.append(
            ScenarioInput(
                resource=resource_id,
                path=['initialized'],
                kind='configuration',
                label='Initialize empty knowledge base',
            )
        )

    async def _sanitize_plugin_config(self, context, dependency):
        if not dependency.config:
            return
        await self.ap.plugin_connector.require_workspace_context(context)
        author, name = dependency.plugin_id.split('/', 1)
        info = await self.ap.plugin_connector.get_plugin_info(author, name)
        if not info:
            raise ValueError('Scenario plugin configuration schema is unavailable')
        schema = info.get('manifest', {}).get('manifest', {}).get('spec', {}).get('config', [])
        dependency.config, _ = project_config(dependency.config, schema, 'main', ['config'])

    async def _install_dependencies(self, context, package):
        dependencies = await self._dependencies(context, package)
        pending = {}
        for item in dependencies:
            if item['status'] != 'missing':
                continue
            previous = pending.get(item['plugin_id'])
            if previous and previous['version'] and item['version'] and previous['version'] != item['version']:
                raise ValueError('Conflicting scenario plugin versions')
            if previous is None or item['version']:
                pending[item['plugin_id']] = item
        if not pending:
            return
        connector = self.ap.plugin_connector
        await connector.require_workspace_context(context)
        limits = await workspace_limits(self.ap, require_workspace_uuid(context))
        maximum = limits.get('max_extensions', -1)
        if maximum >= 0:
            installed = await connector.list_plugins()
            servers = await self.ap.mcp_service.get_mcp_servers(context)
            if (
                len(installed)
                + len(servers)
                + len(pending)
                + sum(item.kind == 'mcp_server' for item in package.resources)
                > maximum
            ):
                raise ValueError('Scenario exceeds max_extensions')
        for dependency in pending.values():
            parts = dependency['plugin_id'].split('/')
            if len(parts) != 2 or not all(parts):
                raise ValueError('Invalid scenario plugin ID')
            await connector.require_workspace_context(context)
            await connector.install_plugin(
                PluginInstallSource.MARKETPLACE,
                {
                    'plugin_author': parts[0],
                    'plugin_name': parts[1],
                    'plugin_version': dependency['version'],
                },
            )
            if dependency.get('config'):
                # Only newly installed plugins receive scene defaults. Existing
                # Workspace-wide configuration is never overwritten.
                config_dependency = ScenarioDependency.model_validate(
                    {key: value for key, value in dependency.items() if key != 'status'}
                )
                await self._sanitize_plugin_config(context, config_dependency)
                await connector.set_plugin_config(parts[0], parts[1], config_dependency.config)
        # Installation uses the same cache invalidation path as plugin management.
        remaining = await self._dependencies(context, package)
        if any(item['status'] == 'missing' for item in remaining):
            raise ValueError('Scenario plugin installation did not become ready')

    async def preview(self, context, document):
        package = parse_package(document)
        workspace = require_workspace_uuid(context)
        for dependency in package.dependencies:
            if dependency.config is not None:
                dependency.config = scrub_nested(dependency.config)
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
            elif resource.kind == 'mcp_server':
                if resource.data.get('mode') not in {'remote', 'http', 'sse', 'stdio'}:
                    raise ValueError('Invalid scenario MCP mode')
                require_stdio_mcp_enabled(self.ap, resource.data)
                self._project_mcp(package, resource.id, resource.data)
            elif resource.kind == 'knowledge_base':
                if not resource.data.get('knowledge_engine_plugin_id'):
                    raise ValueError('Scenario knowledge engine is required')
                if not any(
                    dep.kind == 'knowledge_plugin' and dep.plugin_id == resource.data['knowledge_engine_plugin_id']
                    for dep in package.dependencies
                ):
                    raise ValueError('Missing scenario knowledge engine dependency')
                for section in ('creation_settings', 'retrieval_settings'):
                    if not isinstance(resource.data.get(section, {}), dict):
                        raise ValueError('Invalid knowledge settings')
            elif resource.kind == 'pipeline':
                resource.data['config'] = complete_pipeline_config(resource.data.get('config'))
                RunnerConfigResolver.validate_pipeline_config(resource.data.get('config'))
            else:
                RunnerConfigResolver.validate_agent_config(resource.data.get('config'))
            if resource.kind not in {'bot', 'knowledge_base', 'mcp_server'}:
                config = resource.data['config']
                container = config.get('ai', {}) if resource.kind == 'pipeline' else config
                runner_id = container.get('runner', {}).get('id')
                if not runner_id:
                    raise ValueError('Scenario processor requires a Runner')
                if not any(dep.kind == 'runner' and dep.id == runner_id for dep in package.dependencies):
                    raise ValueError('Missing scenario Runner dependency declaration')
        limits = await workspace_limits(self.ap, workspace)
        for kind, limit_key in [
            ('bot', 'max_bots'),
            ('pipeline', 'max_pipelines'),
            ('knowledge_base', 'max_knowledge_bases'),
        ]:
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
        mcp_count = sum(item.kind == 'mcp_server' for item in package.resources)
        if mcp_count and limits.get('max_extensions', -1) >= 0:
            await self.ap.plugin_connector.require_workspace_context(context)
            installed = await self.ap.plugin_connector.list_plugins()
            servers = await self.ap.mcp_service.get_mcp_servers(context)
            if len(installed) + len(servers) + mcp_count > limits['max_extensions']:
                raise ValueError('Scenario exceeds max_extensions')
        return {'package': package.model_dump(), 'dependencies': await self._dependencies(context, package)}

    async def _dependencies(self, context, package):
        statuses = []
        installed = None
        seen = set()
        for dependency in package.dependencies:
            key = (dependency.kind, dependency.id)
            if key in seen:
                continue
            seen.add(key)
            status = 'configure'
            if dependency.kind == 'runner':
                try:
                    descriptor = await self.ap.runner_registry.get(context, dependency.id)
                except (ValueError, RunnerNotFoundError):
                    descriptor = None
                status = 'missing' if descriptor is None else 'ready'
                if descriptor and dependency.version and descriptor.plugin_version != dependency.version:
                    status = 'version_mismatch'
            else:
                if installed is None:
                    await self.ap.plugin_connector.require_workspace_context(context)
                    plugins = await self.ap.plugin_connector.list_plugins()
                    installed = {}
                    for plugin in plugins:
                        metadata = plugin.get('manifest', {}).get('manifest', {}).get('metadata', {})
                        installed[f'{metadata.get("author")}/{metadata.get("name")}'] = metadata.get('version')
                status = 'ready' if dependency.plugin_id in installed else 'missing'
                if status == 'ready' and dependency.version and installed[dependency.plugin_id] != dependency.version:
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
        # Network installation is outside the atomic resource-creation transaction.
        # Successful installations can be reused if creation fails or is retried.
        await self._install_dependencies(context, package)
        for dependency in package.dependencies:
            await self._sanitize_plugin_config(context, dependency)
        # Use installed engine schemas to sanitize uploaded secrets too.
        for resource in package.resources:
            if resource.kind == 'knowledge_base':
                await self._project_knowledge(context, package, resource.id, resource.data)
        package.inputs = list({(item.resource, tuple(item.path)): item for item in package.inputs}.values())
        async with self.ap.persistence_mgr.tenant_uow(workspace):
            if await self._record(context, request_id):
                return await self.status(context, request_id)
            # Persist a sanitized document, never credential values supplied in an
            # uploaded package. Exported templates already use these empty slots.
            by_id = {item.id: item for item in package.resources}
            for item in package.inputs:
                if item.kind != 'credential':
                    continue
                parent = read_path(by_id[item.resource].data, item.path[:-1])
                parent[item.path[-1]] = ''
            mapping = {item.id: str(uuid.uuid4()) for item in package.resources}
            mcp_names = {
                item.id: f'{item.data["name"]} ({mapping[item.id][:8]})'
                for item in package.resources
                if item.kind == 'mcp_server'
            }
            for item in package.resources:
                values = copy.deepcopy(item.data)
                values.update(uuid=mapping[item.id], workspace_uuid=workspace)
                if item.kind != 'mcp_server':
                    values.setdefault('description', '')
                if item.kind == 'bot':
                    values['enable'] = False
                    for route in values.get('event_bindings', []):
                        route['id'] = str(uuid.uuid4())
                        if route['target_type'] != 'discard':
                            route['target_uuid'] = mapping[route['target_uuid']]
                    for subscription in values.get('plugin_processors', []):
                        subscription['processor_uuid'] = mapping[subscription['processor_uuid']]
                elif item.kind == 'mcp_server':
                    values.update(name=mcp_names[item.id], enable=False)
                elif item.kind == 'knowledge_base':
                    values.update(collection_id=mapping[item.id], initialized=False, legacy_vector_collection=False)
                elif item.kind == 'pipeline':
                    values.update(
                        is_default=False,
                        stages=default_stage_order.copy(),
                        for_version=self.ap.ver_mgr.get_current_version(),
                    )
                else:
                    values['kind'] = item.kind
                    values['component_ref'] = values['config']['runner']['id']
                if item.kind == 'pipeline':
                    prefs = values.get('extensions_preferences') or {}
                    prefs['mcp_servers'] = [mcp_names.get(ref, ref) for ref in prefs.get('mcp_servers', [])]
                if item.kind in {'pipeline', 'agent', 'event_processor'}:
                    for requirement in package.inputs:
                        if requirement.resource != item.id or requirement.kind != 'knowledge':
                            continue
                        parent = read_path(values, requirement.path[:-1])
                        value = parent[requirement.path[-1]]
                        parent[requirement.path[-1]] = (
                            [mapping.get(ref, ref) for ref in value]
                            if isinstance(value, list)
                            else mapping.get(value, value)
                        )
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
                if item.path in (['initialized'], ['enable']):
                    ready = value is True
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
            elif resource.kind == 'mcp_server':
                pass
            elif resource.kind == 'knowledge_base':
                plugin_id = current['knowledge_engine_plugin_id']
                for section, getter in (
                    ('creation_settings', self.ap.knowledge_service.get_engine_creation_schema),
                    ('retrieval_settings', self.ap.knowledge_service.get_engine_retrieval_schema),
                ):
                    schema = await getter(context, plugin_id)
                    schemas.append(([section], schema if isinstance(schema, list) else schema.get('schema', [])))
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
                    field_path = (resource.id, tuple([*prefix, field['name']]))
                    if not field_is_visible(field, read_path(current, prefix)):
                        if field_path in known:
                            known[field_path]['required'] = False
                        continue
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
                            known[(resource.id, tuple(path))]['model_type'] = (
                                'embedding'
                                if 'embedding' in field_type
                                else 'rerank'
                                if 'rerank' in field_type
                                else 'llm'
                            )
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
                            'model_type': 'embedding'
                            if 'embedding' in field_type
                            else 'rerank'
                            if 'rerank' in field_type
                            else 'llm',
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
            model = (
                {'llm': LLMModel, 'embedding': EmbeddingModel, 'rerank': RerankModel}[item.get('model_type', 'llm')]
                if item['kind'] == 'model'
                else KnowledgeBase
            )
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
            if any(item['status'] != 'ready' for item in report['dependencies']):
                raise ValueError(t('Install compatible scenario Runner dependencies before enabling this bot.'))
            for resource in report['resources']:
                if resource['kind'] == 'pipeline':
                    pipeline = await self.ap.pipeline_service.get_pipeline(
                        context, resource['uuid'], include_secret=True
                    )
                    await self.ap.pipeline_mgr.load_pipeline(context, pipeline)
