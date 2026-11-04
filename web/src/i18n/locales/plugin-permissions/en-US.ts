export default {
  managerRequired:
    'Managing plugin permissions requires resource.manage. Only accounts can confirm grants; API keys can only revoke existing grants.',
  title: 'Plugin permissions',
  undeclared: 'Undeclared permissions',
  compatibilityWarning:
    'This plugin does not declare permissions. Confirmation grants all 16 legacy plugin API capabilities; individual grants can be revoked afterward. No workspace Application API operations are granted.',
  pending: 'Permission confirmation required',
  saved: 'Permissions saved',
  failed: 'Unable to update permissions',
  retry: 'Retry',
  revoke: 'Revoke',
  dangerous: 'Dangerous',
  sendsMessages: 'Sends bot messages',
  requires: 'Requires {{permissions}}',
  review: 'Review permissions',
  confirm: 'Confirm grants',
  confirmDescription:
    'Grant the selected permissions to this plugin installation. Dangerous permissions and bot messaging are highlighted.',
  grantInPlugin: 'Grant this operation in plugin permissions first',
  workspaceOperations: 'Workspace operations',
  capabilities: 'Plugin capabilities',
  granted: 'Granted',
  grantedCount: '{{granted}} of {{total}} granted',
  empty: 'This plugin does not request any permissions.',
  pendingCount: 'Waiting for confirmation: {{count}}',
  highlighted: 'Requires attention',
  grantSummary: '{{count}} permissions will be granted',
  capability: {
    langbot_info: {
      label: 'LangBot version',
      description: 'Read the LangBot version',
    },
    bot_read: {
      label: 'Read bots',
      description: 'List bots and read bot details',
    },
    bot_message_send: {
      label: 'Send bot messages',
      description: 'Send messages through Workspace bots',
    },
    bot_platform_api: {
      label: 'Platform API',
      description: 'Call raw IM platform APIs through a bot',
    },
    models_read: {
      label: 'Read models',
      description: 'List configured models',
    },
    models_invoke: {
      label: 'Invoke models',
      description: 'Call LLM, embedding and rerank models',
    },
    storage_plugin: {
      label: 'Plugin storage',
      description: "Read and write this plugin's own storage",
    },
    storage_workspace: {
      label: 'Workspace storage',
      description: 'Read and write storage shared across the Workspace',
    },
    knowledge_read: {
      label: 'Read knowledge',
      description: 'List and retrieve knowledge bases',
    },
    knowledge_vector: {
      label: 'Vector store',
      description: 'Write, search and delete vectors',
    },
    knowledge_parser: {
      label: 'Document parsers',
      description: 'List and invoke document parsers',
    },
    config_read: {
      label: 'Read config files',
      description: 'Read uploaded plugin config files',
    },
    plugin_tools: {
      label: 'Plugin tools',
      description: 'List and call tools of other plugins',
    },
    mcp: { label: 'MCP', description: 'Call MCP tools and read MCP resources' },
    sandbox: {
      label: 'Sandbox',
      description: 'Acquire and run code in a Box sandbox',
    },
    plugin_read: {
      label: 'Read plugins',
      description: 'List installed plugins and commands',
    },
  },
};
