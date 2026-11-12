"""Member permission ceilings for plugin installation capabilities."""

from ..authz import Permission
from langbot_plugin.entities.io.actions.enums import (
    PluginToRuntimeAction as PluginAction,
    RuntimeToLangBotAction as RuntimeAction,
)

CAPABILITY_PERMISSIONS: dict[str, frozenset[Permission]] = {
    'langbot.info': frozenset({Permission.RESOURCE_VIEW}),
    'bot.read': frozenset({Permission.RESOURCE_VIEW}),
    'bot.message.send': frozenset({Permission.RUNTIME_OPERATE}),
    'bot.platform_api': frozenset({Permission.RUNTIME_OPERATE, Permission.RESOURCE_MANAGE}),
    'models.read': frozenset({Permission.RESOURCE_VIEW}),
    'models.invoke': frozenset({Permission.RUNTIME_OPERATE}),
    'storage.plugin': frozenset({Permission.RESOURCE_MANAGE}),
    'storage.workspace': frozenset({Permission.RESOURCE_MANAGE}),
    'knowledge.read': frozenset({Permission.RESOURCE_VIEW}),
    'knowledge.vector': frozenset({Permission.RESOURCE_MANAGE}),
    'knowledge.parser': frozenset({Permission.RUNTIME_OPERATE}),
    'config.read': frozenset({Permission.RESOURCE_VIEW}),
    'plugin_tools': frozenset({Permission.RUNTIME_OPERATE}),
    'mcp': frozenset({Permission.RUNTIME_OPERATE}),
    'sandbox': frozenset({Permission.RUNTIME_OPERATE}),
    'plugin.read': frozenset({Permission.RESOURCE_VIEW}),
}

LEGACY_CAPABILITIES = frozenset(
    {
        'langbot.info',
        'bot.read',
        'bot.message.send',
        'bot.platform_api',
        'models.read',
        'models.invoke',
        'storage.plugin',
        'storage.workspace',
        'knowledge.read',
        'knowledge.vector',
        'knowledge.parser',
        'config.read',
        'plugin_tools',
        'mcp',
        'sandbox',
        'plugin.read',
    }
)

DANGEROUS_CAPABILITIES = frozenset({'bot.platform_api', 'mcp', 'sandbox'})

CAPABILITY_ACTIONS = {
    'langbot.info': (PluginAction.GET_LANGBOT_VERSION,),
    'bot.read': (PluginAction.GET_BOTS, PluginAction.GET_BOT_INFO),
    'bot.message.send': (PluginAction.SEND_MESSAGE,),
    'bot.platform_api': (PluginAction.CALL_PLATFORM_API,),
    'models.read': (PluginAction.GET_LLM_MODELS,),
    'models.invoke': (
        PluginAction.INVOKE_LLM,
        PluginAction.INVOKE_LLM_STREAM,
        PluginAction.COUNT_TOKENS,
        PluginAction.INVOKE_EMBEDDING,
        PluginAction.INVOKE_RERANK,
    ),
    'storage.plugin': (
        PluginAction.GET_PLUGIN_STORAGE,
        PluginAction.SET_PLUGIN_STORAGE,
        PluginAction.DELETE_PLUGIN_STORAGE,
        PluginAction.GET_PLUGIN_STORAGE_KEYS,
    ),
    'storage.workspace': (
        PluginAction.GET_WORKSPACE_STORAGE,
        PluginAction.SET_WORKSPACE_STORAGE,
        PluginAction.DELETE_WORKSPACE_STORAGE,
        PluginAction.GET_WORKSPACE_STORAGE_KEYS,
    ),
    'knowledge.read': (
        PluginAction.LIST_KNOWLEDGE_BASES,
        PluginAction.LIST_PIPELINE_KNOWLEDGE_BASES,
        PluginAction.RETRIEVE_KNOWLEDGE,
        PluginAction.RETRIEVE_KNOWLEDGE_BASE,
        PluginAction.GET_KNOWLEDEGE_FILE_STREAM,
    ),
    'knowledge.vector': (
        PluginAction.VECTOR_UPSERT,
        PluginAction.VECTOR_SEARCH,
        PluginAction.VECTOR_DELETE,
        PluginAction.VECTOR_LIST,
    ),
    'knowledge.parser': (PluginAction.LIST_PARSERS, PluginAction.INVOKE_PARSER),
    'config.read': (PluginAction.GET_CONFIG_FILE,),
    'plugin_tools': (PluginAction.LIST_TOOLS, PluginAction.GET_TOOL_DETAIL, PluginAction.CALL_TOOL),
    'mcp': (),
    'sandbox': (PluginAction.GET_BOX_STATUS, PluginAction.LIST_BOXES, PluginAction.ACQUIRE_BOX),
    'plugin.read': (PluginAction.LIST_PLUGINS_MANIFEST, PluginAction.LIST_COMMANDS),
}

ACTION_CAPABILITIES = {
    action.value: capability for capability, actions in CAPABILITY_ACTIONS.items() for action in actions
}

BINARY_STORAGE_ACTIONS = frozenset(
    action.value
    for action in (
        RuntimeAction.GET_BINARY_STORAGE,
        RuntimeAction.SET_BINARY_STORAGE,
        RuntimeAction.DELETE_BINARY_STORAGE,
        RuntimeAction.GET_BINARY_STORAGE_KEYS,
    )
)

CONTEXT_ACTIONS = frozenset(
    action.value
    for action in (
        PluginAction.REPLY_MESSAGE,
        PluginAction.GET_BOT_UUID,
        PluginAction.SET_QUERY_VAR,
        PluginAction.GET_QUERY_VAR,
        PluginAction.GET_QUERY_VARS,
        PluginAction.CREATE_NEW_CONVERSATION,
        PluginAction.REPLY_STREAM,
        PluginAction.REQUEST_INTERACTION,
        PluginAction.BIND_BOX,
        PluginAction.IMPORT_BOX_ATTACHMENTS,
        PluginAction.READ_INPUT_ATTACHMENT,
        PluginAction.EXPORT_BOX_FILES,
        PluginAction.GET_PROMPT,
        PluginAction.HISTORY_PAGE,
        PluginAction.HISTORY_SEARCH,
        PluginAction.EVENT_GET,
        PluginAction.EVENT_PAGE,
        PluginAction.STEERING_PULL,
        PluginAction.STATE_GET,
        PluginAction.STATE_SET,
        PluginAction.STATE_DELETE,
        PluginAction.STATE_LIST,
        PluginAction.RUN_GET,
        PluginAction.RUN_LIST,
        PluginAction.RUN_EVENTS_PAGE,
        PluginAction.RUN_CANCEL,
        PluginAction.RUN_APPEND_RESULT,
        PluginAction.RUN_FINALIZE,
        PluginAction.RUN_CLAIM,
        PluginAction.RUN_RENEW_CLAIM,
        PluginAction.RUN_RELEASE_CLAIM,
        PluginAction.RUNNER_LIST,
        PluginAction.RUNTIME_REGISTER,
        PluginAction.RUNTIME_HEARTBEAT,
        PluginAction.RUNTIME_LIST,
        PluginAction.RUNTIME_RECONCILE,
        PluginAction.RUN_STATS,
        PluginAction.RUNTIME_STATS,
        PluginAction.RUNNER_STATS,
    )
) | {
    # Core registers these actions before the paired SDK enums are published.
    'steering_ack',
    'run_retry',
    'run_resume',
    'run_cancel_ack',
}

APPLICATION_ACTIONS = frozenset(
    action.value
    for action in (
        PluginAction.LIST_APPLICATION_OPERATIONS,
        PluginAction.CALL_APPLICATION_OPERATION,
    )
)
