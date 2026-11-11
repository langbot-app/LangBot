from __future__ import annotations

from enum import Enum


class ActionType(Enum):
    pass


class CommonAction(ActionType):
    """The common action."""

    PING = "__ping"
    HEARTBEAT = "__heartbeat"
    FILE_CHUNK = "__file_chunk"
    CANCEL_ACTION = "__cancel_action"
    STREAM_ACK = "__stream_ack"


class PluginToRuntimeAction(ActionType):
    """The action from plugin to runtime."""

    REGISTER_PLUGIN = "register_plugin"

    # ========== APIs for plugin code ==========

    """Query-based APIs"""
    REPLY_MESSAGE = "reply_message"
    GET_BOT_UUID = "get_bot_uuid"
    SET_QUERY_VAR = "set_query_var"
    GET_QUERY_VAR = "get_query_var"
    GET_QUERY_VARS = "get_query_vars"
    CREATE_NEW_CONVERSATION = "create_new_conversation"

    """LangBot APIs"""
    GET_LANGBOT_VERSION = "get_langbot_version"

    GET_BOX_STATUS = "get_box_status"
    LIST_BOXES = "list_boxes"
    ACQUIRE_BOX = "acquire_box"
    BIND_BOX = "bind_box"
    IMPORT_BOX_ATTACHMENTS = "import_box_attachments"
    READ_INPUT_ATTACHMENT = "read_input_attachment"
    EXPORT_BOX_FILES = "export_box_files"

    GET_BOTS = "get_bots"
    GET_BOT_INFO = "get_bot_info"
    SEND_MESSAGE = "send_message"
    REPLY_STREAM = "reply_stream"
    CALL_PLATFORM_API = "call_platform_api"
    REQUEST_INTERACTION = "request_interaction"

    GET_LLM_MODELS = "get_llm_models"
    # GET_LLM_MODEL_INFO = "get_llm_model_info"
    COUNT_TOKENS = "count_tokens"
    INVOKE_LLM = "invoke_llm"
    INVOKE_LLM_STREAM = "invoke_llm_stream"

    SET_PLUGIN_STORAGE = "set_plugin_storage"
    GET_PLUGIN_STORAGE = "get_plugin_storage"
    GET_PLUGIN_STORAGE_KEYS = "get_plugin_storage_keys"
    DELETE_PLUGIN_STORAGE = "delete_plugin_storage"

    SET_WORKSPACE_STORAGE = "set_workspace_storage"
    GET_WORKSPACE_STORAGE = "get_workspace_storage"
    GET_WORKSPACE_STORAGE_KEYS = "get_workspace_storage_keys"
    DELETE_WORKSPACE_STORAGE = "delete_workspace_storage"

    GET_CONFIG_FILE = "get_config_file"

    LIST_PLUGINS_MANIFEST = "list_plugins_manifest"
    LIST_COMMANDS = "list_commands"
    LIST_TOOLS = "list_tools"
    GET_TOOL_DETAIL = "get_tool_detail"
    CALL_TOOL = "call_tool"

    INVOKE_EMBEDDING = "invoke_embedding"
    INVOKE_RERANK = "invoke_rerank"
    VECTOR_UPSERT = "vector_upsert"
    VECTOR_SEARCH = "vector_search"
    VECTOR_DELETE = "vector_delete"
    VECTOR_LIST = "vector_list"
    # TODO: Keep the legacy misspelled enum member for now. Renaming this
    # member is unrelated to the Runner branch and should be handled in
    # a separate compatibility cleanup.
    GET_KNOWLEDEGE_FILE_STREAM = "get_knowledge_file_stream"

    LIST_PARSERS = "list_parsers"
    INVOKE_PARSER = "invoke_parser"

    """Knowledge Base APIs (global, unrestricted)"""
    LIST_KNOWLEDGE_BASES = "list_knowledge_bases"
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"

    """Knowledge Base Query APIs (query-based, pipeline-scoped)"""
    LIST_PIPELINE_KNOWLEDGE_BASES = "list_pipeline_knowledge_bases"
    RETRIEVE_KNOWLEDGE_BASE = "retrieve_knowledge_base"

    """Agent History/Event APIs (run-scoped, requires run_id authorization)"""
    GET_PROMPT = "get_prompt"
    HISTORY_PAGE = "history_page"
    HISTORY_SEARCH = "history_search"
    EVENT_GET = "event_get"
    EVENT_PAGE = "event_page"
    STEERING_PULL = "steering_pull"

    """Agent Run Ledger APIs (run-scoped, requires run_id authorization)"""
    RUN_GET = "run_get"
    RUN_LIST = "run_list"
    RUN_EVENTS_PAGE = "run_events_page"
    RUN_CANCEL = "run_cancel"
    RUN_APPEND_RESULT = "run_append_result"
    RUN_FINALIZE = "run_finalize"
    RUN_CLAIM = "run_claim"
    RUN_RENEW_CLAIM = "run_renew_claim"
    RUN_RELEASE_CLAIM = "run_release_claim"
    RUNNER_LIST = "runner_list"

    """Agent Runtime Registry APIs (Host control-plane scoped)"""
    RUNTIME_REGISTER = "runtime_register"
    RUNTIME_HEARTBEAT = "runtime_heartbeat"
    RUNTIME_LIST = "runtime_list"
    RUNTIME_RECONCILE = "runtime_reconcile"

    """Agent Run Statistics APIs (Host control-plane scoped, admin-only)"""
    RUN_STATS = "run_stats"
    RUNTIME_STATS = "runtime_stats"
    RUNNER_STATS = "runner_stats"

    """Agent State APIs (run-scoped, requires run_id authorization)"""
    STATE_GET = "state_get"
    STATE_SET = "state_set"
    STATE_DELETE = "state_delete"
    STATE_LIST = "state_list"

    """Application API Operations (run-scoped)"""
    LIST_APPLICATION_OPERATIONS = "list_application_operations"
    CALL_APPLICATION_OPERATION = "call_application_operation"


class RuntimeToPluginAction(ActionType):
    """The action from runtime to plugin."""

    INITIALIZE_PLUGIN = "initialize_plugin"
    ATTACH_PLUGIN_SLOT = "attach_plugin_slot"
    DETACH_PLUGIN_SLOT = "detach_plugin_slot"
    GET_PLUGIN_SLOT_CONTAINER = "get_plugin_slot_container"
    GET_PLUGIN_CONTAINER = "get_plugin_container"
    GET_PLUGIN_ICON = "get_plugin_icon"
    GET_PLUGIN_README = "get_plugin_readme"
    GET_PLUGIN_ASSETS_FILE = "get_plugin_assets_file"
    EMIT_EVENT = "emit_event"
    PLUGIN_DIAGNOSTIC = "plugin_diagnostic"
    CALL_TOOL = "call_tool"
    EXECUTE_COMMAND = "execute_command"
    SHUTDOWN = "shutdown"

    # Runner actions
    RUN_RUNNER = "run_runner"

    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
    INGEST_DOCUMENT = "ingest_document"
    DELETE_DOCUMENT = "delete_document"
    ON_KB_CREATE = "on_kb_create"
    ON_KB_DELETE = "on_kb_delete"
    GET_RAG_CAPABILITIES = "get_rag_capabilities"

    PARSE_DOCUMENT = "parse_document"

    PAGE_API = "page_api"

    # Plugin source packaging / GitHub synchronisation, used by the
    # "upload a debug plugin to LangBot Space" flow. The plugin process owns
    # its working directory, so it builds the package and performs git work
    # on behalf of the Runtime.
    BUILD_PLUGIN_PACKAGE = "build_plugin_package"
    GIT_SYNC_PLUGIN = "git_sync_plugin"


class LangBotToRuntimeAction(ActionType):
    """The action from langbot to runtime."""

    LIST_PLUGINS = "list_plugins"
    GET_PLUGIN_INFO = "get_plugin_info"
    GET_PLUGIN_ICON = "get_plugin_icon"
    GET_PLUGIN_README = "get_plugin_readme"
    GET_PLUGIN_LOGS = "get_plugin_logs"
    GET_PLUGIN_ASSETS_FILE = "get_plugin_assets_file"
    INSTALL_PLUGIN = "install_plugin"
    RESTART_PLUGIN = "restart_plugin"
    DELETE_PLUGIN = "delete_plugin"
    UPGRADE_PLUGIN = "upgrade_plugin"
    EMIT_EVENT = "emit_event"
    PLUGIN_DIAGNOSTIC = "plugin_diagnostic"
    LIST_TOOLS = "list_tools"
    CALL_TOOL = "call_tool"
    LIST_COMMANDS = "list_commands"
    EXECUTE_COMMAND = "execute_command"

    # KnowledgeEngine retrieval action
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"

    # Runner actions
    LIST_RUNNERS = "list_runners"
    RUN_RUNNER = "run_runner"

    # Knowledge Engine actions (LangBot -> Runtime -> Plugin)
    LIST_KNOWLEDGE_ENGINES = "list_knowledge_engines"
    RAG_INGEST_DOCUMENT = "rag_ingest_document"
    RAG_DELETE_DOCUMENT = "rag_delete_document"
    RAG_ON_KB_CREATE = "rag_on_kb_create"
    RAG_ON_KB_DELETE = "rag_on_kb_delete"
    GET_RAG_CREATION_SETTINGS_SCHEMA = "get_rag_creation_settings_schema"
    GET_RAG_RETRIEVAL_SETTINGS_SCHEMA = "get_rag_retrieval_settings_schema"

    # Parser actions (LangBot -> Runtime -> Plugin)
    LIST_PARSERS = "list_parsers"
    PARSE_DOCUMENT = "parse_document"

    # Debug info
    GET_DEBUG_INFO = "get_debug_info"

    # Instance-scoped Runtime filesystem diagnostics. The Host only exposes
    # this in its single-Workspace maintenance surface.
    GET_STORAGE_ANALYSIS = "get_storage_analysis"

    # Runtime configuration pushed by LangBot at connection init (e.g. the
    # marketplace / cloud service URL), so the runtime does not rely on its own
    # env/default.
    SET_RUNTIME_CONFIG = "set_runtime_config"

    # Multi-tenant desired-state protocol. Reconcile is instance-scoped;
    # apply/remove carry one complete InstallationBinding envelope.
    RECONCILE_PLUGIN_INSTALLATIONS = "reconcile_plugin_installations"
    APPLY_PLUGIN_INSTALLATION = "apply_plugin_installation"
    REMOVE_PLUGIN_INSTALLATION = "remove_plugin_installation"

    # Page API
    PAGE_API = "page_api"

    # Plugin source packaging / GitHub synchronisation for the upload flow.
    BUILD_PLUGIN_PACKAGE = "build_plugin_package"
    GIT_SYNC_PLUGIN = "git_sync_plugin"


class RuntimeToLangBotAction(ActionType):
    """The action from runtime to langbot."""

    INITIALIZE_PLUGIN_SETTINGS = "initialize_plugin_settings"
    GET_PLUGIN_SETTINGS = "get_plugin_settings"

    SET_BINARY_STORAGE = "set_binary_storage"
    GET_BINARY_STORAGE = "get_binary_storage"
    GET_BINARY_STORAGE_KEYS = "get_binary_storage_keys"
    DELETE_BINARY_STORAGE = "delete_binary_storage"

    GET_CONFIG_FILE = "get_config_file"
