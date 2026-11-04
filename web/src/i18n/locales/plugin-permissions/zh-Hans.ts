export default {
  managerRequired:
    '管理插件权限需要 resource.manage 权限。仅账户可确认授权，API Key 只能撤销已有授权。',
  title: '插件权限',
  undeclared: '未声明权限',
  compatibilityWarning:
    '该插件未声明权限。确认时必须授予全部 16 项旧版插件 API 权限，确认后可逐项撤销；不包含任何工作区 Application API 操作。',
  pending: '需要确认插件权限',
  saved: '权限已保存',
  failed: '无法更新权限',
  retry: '重试',
  revoke: '撤销',
  dangerous: '危险操作',
  sendsMessages: '可发送机器人消息',
  requires: '需要 {{permissions}}',
  review: '审阅权限',
  confirm: '确认授予',
  confirmDescription:
    '向此插件安装授予选中的权限。危险权限和机器人发消息能力已单独标出。',
  grantInPlugin: '需先在插件权限中授予此操作',
  workspaceOperations: '工作区操作',
  capabilities: '插件能力',
  granted: '已授予',
  grantedCount: '已授予 {{granted}} / {{total}} 项',
  empty: '该插件未申请任何权限。',
  pendingCount: '{{count}} 个插件等待确认权限',
  highlighted: '需留意',
  grantSummary: '将授予 {{count}} 项权限',
  capability: {
    langbot_info: { label: 'LangBot 版本', description: '读取 LangBot 版本' },
    bot_read: { label: '读取机器人', description: '列出机器人并读取详情' },
    bot_message_send: {
      label: '发送机器人消息',
      description: '通过工作区机器人发送消息',
    },
    bot_platform_api: {
      label: '平台 API',
      description: '通过机器人调用 IM 平台原生 API',
    },
    models_read: { label: '读取模型', description: '列出已配置的模型' },
    models_invoke: {
      label: '调用模型',
      description: '调用对话、嵌入和重排序模型',
    },
    storage_plugin: { label: '插件存储', description: '读写插件自身的存储' },
    storage_workspace: {
      label: '工作区存储',
      description: '读写工作区内共享的存储',
    },
    knowledge_read: { label: '读取知识库', description: '列出并检索知识库' },
    knowledge_vector: { label: '向量库', description: '写入、搜索和删除向量' },
    knowledge_parser: {
      label: '文档解析器',
      description: '列出并调用文档解析器',
    },
    config_read: {
      label: '读取配置文件',
      description: '读取上传的插件配置文件',
    },
    plugin_tools: {
      label: '插件工具',
      description: '列出并调用其他插件的工具',
    },
    mcp: { label: 'MCP', description: '调用 MCP 工具、读取 MCP 资源' },
    sandbox: { label: '沙盒', description: '申请 Box 沙盒并执行代码' },
    plugin_read: { label: '读取插件', description: '列出已安装的插件和命令' },
  },
};
