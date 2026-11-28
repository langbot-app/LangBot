import sqlalchemy as sa

from ..agent.runner import config_schema
from ..agent.runner.config_resolver import RunnerConfigResolver
from ..agent.runner.context_reset import reset_conversation
from ..agent.runner.descriptor import is_local_agent
from ..agent.runner.errors import RunnerNotFoundError
from ..agent.runner.query_entry_adapter import QueryEntryAdapter
from ..agent.runner.transcript_store import TranscriptStore
from ..agent.runner.resource_policy import ResourcePolicyProjector
from ..entity.persistence.monitoring import MonitoringLLMCall, MonitoringSession
from ..i18n import language, t
from ..persistence.session_summary_contract import conversation_scope
from ..platform.command_registration import descriptions
from ..utils import constants
from .catalog import DESCRIPTIONS
from .permissions import builtin_settings, can_run


async def _help(bot, event, settings, is_admin):
    prefix = settings.get('prefixes', ['/'])[0]
    lines = []
    seen = set()
    for name, description in DESCRIPTIONS.items():
        config = builtin_settings(settings, name)
        if config['enabled']:
            seen.add(name)
            if name == 'new':
                seen.add('reset')
            if can_run(config['permission'], is_admin):
                lines.append(f'{prefix}{name} — {t(description)}')
    for owner, _, manifest in await bot._effective_plugin_commands(event, settings.get('processors', [])):
        name = manifest.metadata.name
        if name in seen:
            continue
        seen.add(name)
        if can_run(settings.get('plugin_permissions', {}).get(f'{owner}/{name}', 'everyone'), is_admin):
            localized = descriptions(manifest)
            lines.append(f'{prefix}{name} — {localized.get(language.get()) or localized.get("en_US", name)}')
    return '\n'.join(lines)


async def execute_builtin(bot, event, adapter, name, text, query, session, is_admin):
    settings = bot.bot_entity.command_settings or {}
    route = getattr(event, '_selected_route', None) or {}
    kind = route.get('target_type')
    target = route.get('target_uuid')
    context = bot.execution_context
    ap = bot.ap
    unsupported = t('This processor does not support this command')
    if name == 'help':
        return await _help(bot, event, settings, is_admin)
    if name == 'version':
        return f'LangBot {constants.semantic_version}'
    launcher = f'{query.launcher_type.value}_{query.launcher_id}'
    if name == 'whoami':
        return t(
            'Sender: {sender}\nSession: {session}\nSet administrators in Session Monitoring.',
            sender=f'person_{event.sender.id}',
            session=launcher,
        )
    if name == 'plugins':
        selected = query._listener_plugins
        plugins = await ap.plugin_connector.list_plugins()
        installed = [item['manifest']['manifest']['metadata'] for item in plugins if item.get('enabled', True)]
        names = [f'{item["author"]}/{item["name"]}' for item in installed]
        return '\n'.join(names if selected is None else [item for item in selected if item in names]) or '—'

    if name not in ('usage', 'status') and (not target or kind not in ('agent', 'pipeline', 'event_processor')):
        return t('No processor handles this message')
    pipeline = None
    agent = None
    binding = None
    runner_id = None
    runner_config = {}
    if kind == 'pipeline':
        pipeline = await ap.pipeline_mgr.get_pipeline_by_uuid(context, target)
        if pipeline:
            config = pipeline.pipeline_entity.config
            await ap.message_policy_mgr.bind_query(query, config)
            runner_id = RunnerConfigResolver.resolve_runner_id(config)
            runner_config = RunnerConfigResolver.resolve_runner_config(config, runner_id) if runner_id else {}
    elif kind == 'agent':
        agent = await ap.agent_service.get_agent(context, target)
        binding = bot._agent_product_to_binding(agent, route, event.type, query.bot_uuid) if agent else None
        if binding:
            runner_id, runner_config = binding.runner_id, binding.runner_config
    session = await ap.sess_mgr.get_session(query) if pipeline else session
    query.session = session
    envelope = bot._eba_event_to_agent_envelope(event, adapter) if binding else None
    scope = envelope.conversation_id if envelope else conversation_scope(query)
    if name in ('status', 'usage'):
        async with ap.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
            count = (
                await uow.execute(
                    sa.select(MonitoringSession.message_count).where(
                        MonitoringSession.workspace_uuid == context.workspace_uuid,
                        MonitoringSession.bot_id == query.bot_uuid,
                        MonitoringSession.session_id == scope,
                    )
                )
            ).scalar() or 0
            if name == 'usage':
                tokens = (
                    await uow.execute(
                        sa.select(sa.func.sum(MonitoringLLMCall.total_tokens)).where(
                            MonitoringLLMCall.workspace_uuid == context.workspace_uuid,
                            MonitoringLLMCall.bot_id == query.bot_uuid,
                            MonitoringLLMCall.session_id == scope,
                        )
                    )
                ).scalar() or 0
                return t('Messages: {count} · Tokens: {tokens}', count=count, tokens=tokens)
    if name == 'new' and (pipeline or binding):
        await reset_conversation(ap, query, envelope.conversation_id if envelope else None)
        return t('New conversation started')
    if name in ('retry', 'undo') and pipeline and runner_id:
        if not is_local_agent(await ap.runner_registry.get(context, runner_id, pipeline.bound_plugins)):
            return unsupported
        conversation = QueryEntryAdapter._build_conversation_context(query)
        previous = await TranscriptStore(ap.persistence_mgr.get_db_engine()).pop_last_turn(
            conversation.conversation_id,
            query.bot_uuid,
            context.workspace_uuid,
            getattr(conversation, 'thread_id', None),
            require_text=name == 'retry',
        )
        if previous is None:
            return unsupported
        if name == 'retry':
            chain = previous.get_content_platform_message_chain()
            source = query.message_event.model_copy(update={'message_chain': chain})
            await ap.query_pool.add_query(
                bot_uuid=query.bot_uuid,
                launcher_type=query.launcher_type,
                launcher_id=query.launcher_id,
                sender_id=query.sender_id,
                message_event=source,
                message_chain=chain,
                adapter=adapter,
                pipeline_uuid=target,
                routed_by_rule=True,
                execution_context=context,
                route_id=route.get('id'),
            )
        return t('Regenerating reply') if name == 'retry' else t('Last turn removed')
    if name == 'stop' and (pipeline or binding):
        if pipeline and not runner_id:
            return t('No active reply')
        if binding:
            stopped = await ap.agent_run_orchestrator.cancel_active_from_event(envelope, runner_id, is_admin)
        else:
            stopped = await ap.agent_run_orchestrator.cancel_active_from_query(query, allow_other_actors=is_admin)
        return t('Reply stopped') if stopped else t('No active reply')
    if name in ('status', 'model'):
        try:
            descriptor = await ap.runner_registry.get(context, runner_id) if runner_id else None
        except RunnerNotFoundError:
            descriptor = None
        model_uuid, _ = config_schema.extract_model_selection(descriptor, runner_config)
        if pipeline and is_local_agent(descriptor):
            model_uuid = getattr(session, '_command_model_uuid', None) or model_uuid
        models = ap.model_mgr.runtime_llm_models_for_workspace(context.workspace_uuid)
        model = models.get(model_uuid)
        model_name = model.model_entity.name if model else '—'
        if name == 'status':
            processor = pipeline.pipeline_entity.name if pipeline else (agent or {}).get('name', '—')
            return t(
                'Bot: {bot}\nRoute: {route}\nProcessor: {processor}\nModel: {model}\nSession: {session}\nMessages: {count}',
                bot=bot.bot_entity.name,
                route=route.get('description') or route.get('id') or '—',
                processor=f'{processor} ({kind or "—"})',
                model=model_name,
                session=launcher,
                count=count,
            )
        args = text.split(maxsplit=1)
        if len(args) == 1:
            return model_name
        if pipeline and is_local_agent(descriptor) and config_schema.uses_host_models(descriptor):
            for candidate in models.values():
                if candidate.model_entity.name == args[1]:
                    session._command_model_uuid = candidate.model_entity.uuid
                    return t('Switched to {model} for this session', model=candidate.model_entity.name)
            return t('model not found')
    if name == 'tools' and (pipeline or binding):
        catalog = await ap.tool_mgr.get_resolved_tool_catalog(
            context, getattr(pipeline, 'bound_plugins', None), getattr(pipeline, 'bound_mcp_servers', None)
        )
        policy = (
            binding.resource_policy
            if binding
            else ResourcePolicyProjector.from_runner_config(
                runner_config,
                resolved_tool_names=ResourcePolicyProjector.extract_tool_names(catalog),
                allowed_workspace_operations=pipeline.workspace_operations,
            )
        )
        return (
            '\n'.join(ResourcePolicyProjector.extract_tool_names(ResourcePolicyProjector.filter_tools(catalog, policy)))
            or '—'
        )
    return unsupported
