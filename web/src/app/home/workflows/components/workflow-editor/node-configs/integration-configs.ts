/**
 * Integration Node Configurations
 *
 * Defines configurations for integration node types:
 * - database_query: Query databases
 * - redis_operation: Redis operations
 * - mcp_tool: MCP tool invocation
 */

import { DynamicFormItemType } from '@/app/infra/entities/form/dynamic';
import { NodeConfigMeta, createInput, createOutput } from './types';

/**
 * Database Query Node
 * Executes database queries
 */
export const databaseQueryConfig: NodeConfigMeta = {
  nodeType: 'database_query',
  label: {
    en_US: 'Database Query',
    zh_Hans: '数据库查询',
  },
  description: {
    en_US: 'Execute database queries',
    zh_Hans: '执行数据库查询',
  },
  icon: 'Database',
  category: 'integration',
  color: '#ec4899',
  inputs: [
    createInput('parameters', 'object', {
      description: 'Query parameters',
      label: { en_US: 'Parameters', zh_Hans: '参数' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('results', 'array', {
      description: 'Query results',
      label: { en_US: 'Results', zh_Hans: '结果' },
    }),
    createOutput('row_count', 'number', {
      description: 'Number of rows affected/returned',
      label: { en_US: 'Row Count', zh_Hans: '行数' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether query was successful',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'connection_type',
      name: 'connection_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Database Type',
        zh_Hans: '数据库类型',
      },
      description: {
        en_US: 'Type of database to connect to',
        zh_Hans: '要连接的数据库类型',
      },
      required: true,
      default: 'postgresql',
      options: [
        {
          name: 'postgresql',
          label: { en_US: 'PostgreSQL', zh_Hans: 'PostgreSQL' },
        },
        { name: 'mysql', label: { en_US: 'MySQL', zh_Hans: 'MySQL' } },
        { name: 'sqlite', label: { en_US: 'SQLite', zh_Hans: 'SQLite' } },
      ],
    },
    {
      id: 'connection_string',
      name: 'connection_string',
      type: DynamicFormItemType.SECRET,
      label: {
        en_US: 'Connection String',
        zh_Hans: '连接字符串',
      },
      description: {
        en_US: 'Database connection string',
        zh_Hans: '数据库连接字符串',
      },
      required: true,
      default: '',
    },
    {
      id: 'query',
      name: 'query',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'SQL Query',
        zh_Hans: 'SQL 查询',
      },
      description: {
        en_US: 'SQL query to execute (use $1, $2, etc. for parameters)',
        zh_Hans: '要执行的 SQL 查询（使用 $1、$2 等作为参数占位符）',
      },
      required: true,
      default: '',
    },
    {
      id: 'query_type',
      name: 'query_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Query Type',
        zh_Hans: '查询类型',
      },
      description: {
        en_US: 'Type of query operation',
        zh_Hans: '查询操作的类型',
      },
      required: true,
      default: 'select',
      options: [
        { name: 'select', label: { en_US: 'SELECT', zh_Hans: 'SELECT' } },
        { name: 'insert', label: { en_US: 'INSERT', zh_Hans: 'INSERT' } },
        { name: 'update', label: { en_US: 'UPDATE', zh_Hans: 'UPDATE' } },
        { name: 'delete', label: { en_US: 'DELETE', zh_Hans: 'DELETE' } },
      ],
    },
    {
      id: 'timeout',
      name: 'timeout',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Timeout (seconds)',
        zh_Hans: '超时时间（秒）',
      },
      description: {
        en_US: 'Query timeout',
        zh_Hans: '查询超时时间',
      },
      required: false,
      default: 30,
    },
  ],
  defaultConfig: {
    connection_type: 'postgresql',
    connection_string: '',
    query: '',
    query_type: 'select',
    timeout: 30,
  },
};

/**
 * Redis Operation Node
 * Performs Redis operations
 */
export const redisOperationConfig: NodeConfigMeta = {
  nodeType: 'redis_operation',
  label: {
    en_US: 'Redis Operation',
    zh_Hans: 'Redis 操作',
  },
  description: {
    en_US: 'Perform Redis cache operations',
    zh_Hans: '执行 Redis 缓存操作',
  },
  icon: 'Server',
  category: 'integration',
  color: '#ec4899',
  inputs: [
    createInput('key', 'string', {
      description: 'Redis key',
      label: { en_US: 'Key', zh_Hans: '键' },
      required: false,
    }),
    createInput('value', 'any', {
      description: 'Value to store',
      label: { en_US: 'Value', zh_Hans: '值' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('result', 'any', {
      description: 'Operation result',
      label: { en_US: 'Result', zh_Hans: '结果' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether operation was successful',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'connection_url',
      name: 'connection_url',
      type: DynamicFormItemType.SECRET,
      label: {
        en_US: 'Redis URL',
        zh_Hans: 'Redis URL',
      },
      description: {
        en_US: 'Redis connection URL (e.g., redis://localhost:6379)',
        zh_Hans: 'Redis 连接 URL（例如 redis://localhost:6379）',
      },
      required: true,
      default: 'redis://localhost:6379',
    },
    {
      id: 'operation',
      name: 'operation',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Operation',
        zh_Hans: '操作',
      },
      description: {
        en_US: 'Redis operation to perform',
        zh_Hans: '要执行的 Redis 操作',
      },
      required: true,
      default: 'get',
      options: [
        { name: 'get', label: { en_US: 'GET', zh_Hans: 'GET' } },
        { name: 'set', label: { en_US: 'SET', zh_Hans: 'SET' } },
        { name: 'delete', label: { en_US: 'DELETE', zh_Hans: 'DELETE' } },
        { name: 'exists', label: { en_US: 'EXISTS', zh_Hans: 'EXISTS' } },
        { name: 'incr', label: { en_US: 'INCR', zh_Hans: 'INCR' } },
        { name: 'decr', label: { en_US: 'DECR', zh_Hans: 'DECR' } },
        { name: 'hget', label: { en_US: 'HGET', zh_Hans: 'HGET' } },
        { name: 'hset', label: { en_US: 'HSET', zh_Hans: 'HSET' } },
        { name: 'lpush', label: { en_US: 'LPUSH', zh_Hans: 'LPUSH' } },
        { name: 'rpush', label: { en_US: 'RPUSH', zh_Hans: 'RPUSH' } },
        { name: 'lpop', label: { en_US: 'LPOP', zh_Hans: 'LPOP' } },
        { name: 'rpop', label: { en_US: 'RPOP', zh_Hans: 'RPOP' } },
      ],
    },
    {
      id: 'key_template',
      name: 'key_template',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Key Template',
        zh_Hans: '键模板',
      },
      description: {
        en_US: 'Redis key (supports variable interpolation)',
        zh_Hans: 'Redis 键（支持变量插值）',
      },
      required: false,
      default: '',
    },
    {
      id: 'hash_field',
      name: 'hash_field',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Hash Field',
        zh_Hans: '哈希字段',
      },
      description: {
        en_US: 'Field name for hash operations',
        zh_Hans: '哈希操作的字段名',
      },
      required: false,
      default: '',
      show_if: {
        field: 'operation',
        operator: 'in',
        value: ['hget', 'hset'],
      },
    },
    {
      id: 'ttl',
      name: 'ttl',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'TTL (seconds)',
        zh_Hans: 'TTL（秒）',
      },
      description: {
        en_US: 'Time to live for SET operations (0 = no expiry)',
        zh_Hans: 'SET 操作的过期时间（0 = 不过期）',
      },
      required: false,
      default: 0,
      show_if: {
        field: 'operation',
        operator: 'eq',
        value: 'set',
      },
    },
  ],
  defaultConfig: {
    connection_url: 'redis://localhost:6379',
    operation: 'get',
    key_template: '',
    hash_field: '',
    ttl: 0,
  },
};

/**
 * MCP Tool Node
 * Invokes MCP (Model Context Protocol) tools
 */
export const mcpToolConfig: NodeConfigMeta = {
  nodeType: 'mcp_tool',
  label: {
    en_US: 'MCP Tool',
    zh_Hans: 'MCP 工具',
  },
  description: {
    en_US: 'Invoke an MCP (Model Context Protocol) tool',
    zh_Hans: '调用 MCP（模型上下文协议）工具',
  },
  icon: 'Wrench',
  category: 'integration',
  color: '#ec4899',
  inputs: [
    createInput('arguments', 'object', {
      description: 'Tool arguments',
      label: { en_US: 'Arguments', zh_Hans: '参数' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('result', 'any', {
      description: 'Tool execution result',
      label: { en_US: 'Result', zh_Hans: '结果' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether tool call was successful',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
    createOutput('error', 'string', {
      description: 'Error message if failed',
      label: { en_US: 'Error', zh_Hans: '错误' },
    }),
  ],
  configSchema: [
    {
      id: 'server_name',
      name: 'server_name',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'MCP Server',
        zh_Hans: 'MCP 服务器',
      },
      description: {
        en_US: 'Name of the MCP server',
        zh_Hans: 'MCP 服务器名称',
      },
      required: true,
      default: '',
    },
    {
      id: 'tool_name',
      name: 'tool_name',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Tool Name',
        zh_Hans: '工具名称',
      },
      description: {
        en_US: 'Name of the MCP tool to invoke',
        zh_Hans: '要调用的 MCP 工具名称',
      },
      required: true,
      default: '',
    },
    {
      id: 'arguments_template',
      name: 'arguments_template',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Arguments Template',
        zh_Hans: '参数模板',
      },
      description: {
        en_US:
          'Tool arguments as JSON (supports variable interpolation). Leave empty to use input.',
        zh_Hans: '工具参数（JSON 格式，支持变量插值）。留空则使用输入。',
      },
      required: false,
      default: '',
    },
    {
      id: 'timeout',
      name: 'timeout',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Timeout (seconds)',
        zh_Hans: '超时时间（秒）',
      },
      description: {
        en_US: 'Maximum execution time',
        zh_Hans: '最大执行时间',
      },
      required: false,
      default: 30,
    },
  ],
  defaultConfig: {
    server_name: '',
    tool_name: '',
    arguments_template: '',
    timeout: 30,
  },
};

/**
 * Memory Store Node
 * Store and retrieve from workflow memory
 */
export const memoryStoreConfig: NodeConfigMeta = {
  nodeType: 'memory_store',
  label: {
    en_US: 'Memory Store',
    zh_Hans: '记忆存储',
  },
  description: {
    en_US: 'Store and retrieve data from workflow memory',
    zh_Hans: '从工作流记忆中存储和检索数据',
  },
  icon: 'HardDrive',
  category: 'integration',
  color: '#ec4899',
  inputs: [
    createInput('value', 'any', {
      description: 'Value to store',
      label: { en_US: 'Value', zh_Hans: '值' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('result', 'any', {
      description: 'Retrieved or stored value',
      label: { en_US: 'Result', zh_Hans: '结果' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether operation was successful',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'operation',
      name: 'operation',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Operation',
        zh_Hans: '操作',
      },
      description: {
        en_US: 'Memory operation to perform',
        zh_Hans: '要执行的记忆操作',
      },
      required: true,
      default: 'get',
      options: [
        { name: 'get', label: { en_US: 'Get', zh_Hans: '获取' } },
        { name: 'set', label: { en_US: 'Set', zh_Hans: '设置' } },
        { name: 'delete', label: { en_US: 'Delete', zh_Hans: '删除' } },
        { name: 'append', label: { en_US: 'Append', zh_Hans: '追加' } },
        { name: 'list', label: { en_US: 'List All', zh_Hans: '列出全部' } },
      ],
    },
    {
      id: 'key',
      name: 'key',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Key',
        zh_Hans: '键',
      },
      description: {
        en_US: 'Memory key (supports variable interpolation)',
        zh_Hans: '记忆键（支持变量插值）',
      },
      required: true,
      default: '',
      show_if: {
        field: 'operation',
        operator: 'neq',
        value: 'list',
      },
    },
    {
      id: 'scope',
      name: 'scope',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Scope',
        zh_Hans: '作用域',
      },
      description: {
        en_US: 'Scope of the memory storage',
        zh_Hans: '记忆存储的作用域',
      },
      required: true,
      default: 'execution',
      options: [
        { name: 'execution', label: { en_US: 'Execution', zh_Hans: '执行' } },
        { name: 'workflow', label: { en_US: 'Workflow', zh_Hans: '工作流' } },
        { name: 'session', label: { en_US: 'Session', zh_Hans: '会话' } },
        { name: 'user', label: { en_US: 'User', zh_Hans: '用户' } },
        { name: 'global', label: { en_US: 'Global', zh_Hans: '全局' } },
      ],
    },
    {
      id: 'ttl',
      name: 'ttl',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'TTL (seconds)',
        zh_Hans: 'TTL（秒）',
      },
      description: {
        en_US: 'Time to live (0 = no expiry)',
        zh_Hans: '过期时间（0 = 不过期）',
      },
      required: false,
      default: 0,
      show_if: {
        field: 'operation',
        operator: 'eq',
        value: 'set',
      },
    },
  ],
  defaultConfig: {
    operation: 'get',
    key: '',
    scope: 'execution',
    ttl: 0,
  },
};

/**
 * Dify Workflow Node
 * Calls Dify platform workflow
 */
export const difyWorkflowConfig: NodeConfigMeta = {
  nodeType: 'dify_workflow',
  label: { en_US: 'Dify Workflow', zh_Hans: 'Dify 工作流' },
  description: {
    en_US: 'Call a Dify platform workflow',
    zh_Hans: '调用 Dify 平台工作流',
  },
  icon: 'Bot',
  category: 'integration',
  color: '#ec4899',
  inputs: [
    createInput('input', 'any', {
      description: 'Input data',
      label: { en_US: 'Input', zh_Hans: '输入' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('result', 'any', {
      description: 'Workflow result',
      label: { en_US: 'Result', zh_Hans: '结果' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether call was successful',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'base-url',
      name: 'base-url',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'Base URL', zh_Hans: 'Base URL' },
      description: { en_US: 'Dify API base URL', zh_Hans: 'Dify API 基础 URL' },
      required: true,
      default: '',
    },
    {
      id: 'api-key',
      name: 'api-key',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'API Key', zh_Hans: 'API Key' },
      description: { en_US: 'Dify API key', zh_Hans: 'Dify API 密钥' },
      required: true,
      default: '',
    },
    {
      id: 'app-type',
      name: 'app-type',
      type: DynamicFormItemType.SELECT,
      label: { en_US: 'App Type', zh_Hans: '应用类型' },
      description: { en_US: 'Dify application type', zh_Hans: 'Dify 应用类型' },
      required: true,
      default: 'workflow',
      options: [
        { name: 'workflow', label: { en_US: 'Workflow', zh_Hans: '工作流' } },
        { name: 'chatbot', label: { en_US: 'Chatbot', zh_Hans: '聊天机器人' } },
      ],
    },
    {
      id: 'timeout',
      name: 'timeout',
      type: DynamicFormItemType.INT,
      label: { en_US: 'Timeout (seconds)', zh_Hans: '超时时间（秒）' },
      description: { en_US: 'Request timeout', zh_Hans: '请求超时时间' },
      required: false,
      default: 60,
    },
  ],
  defaultConfig: {
    'base-url': '',
    'api-key': '',
    'app-type': 'workflow',
    timeout: 60,
  },
};

/**
 * Dify Knowledge Query Node
 */
export const difyKnowledgeQueryConfig: NodeConfigMeta = {
  nodeType: 'dify_knowledge_query',
  label: { en_US: 'Dify Knowledge Query', zh_Hans: 'Dify 知识库查询' },
  description: {
    en_US: 'Query Dify knowledge base',
    zh_Hans: '查询 Dify 知识库',
  },
  icon: 'Search',
  category: 'integration',
  color: '#ec4899',
  inputs: [
    createInput('query', 'string', {
      description: 'Search query',
      label: { en_US: 'Query', zh_Hans: '查询' },
    }),
  ],
  outputs: [
    createOutput('results', 'array', {
      description: 'Search results',
      label: { en_US: 'Results', zh_Hans: '结果' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether query was successful',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'base-url',
      name: 'base-url',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'Base URL', zh_Hans: 'Base URL' },
      description: { en_US: 'Dify API base URL', zh_Hans: 'Dify API 基础 URL' },
      required: true,
      default: '',
    },
    {
      id: 'api-key',
      name: 'api-key',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'API Key', zh_Hans: 'API Key' },
      description: { en_US: 'Dify API key', zh_Hans: 'Dify API 密钥' },
      required: true,
      default: '',
    },
    {
      id: 'dataset_id',
      name: 'dataset_id',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'Dataset ID', zh_Hans: '数据集 ID' },
      description: { en_US: 'Dify dataset ID', zh_Hans: 'Dify 数据集 ID' },
      required: true,
      default: '',
    },
    {
      id: 'top_k',
      name: 'top_k',
      type: DynamicFormItemType.INT,
      label: { en_US: 'Top K', zh_Hans: 'Top K' },
      description: {
        en_US: 'Number of results to return',
        zh_Hans: '返回结果数量',
      },
      required: false,
      default: 5,
    },
  ],
  defaultConfig: { 'base-url': '', 'api-key': '', dataset_id: '', top_k: 5 },
};

/**
 * N8n Workflow Node
 */
export const n8nWorkflowConfig: NodeConfigMeta = {
  nodeType: 'n8n_workflow',
  label: { en_US: 'N8n Workflow', zh_Hans: 'n8n 工作流' },
  description: {
    en_US: 'Call an n8n workflow via webhook',
    zh_Hans: '通过 webhook 调用 n8n 工作流',
  },
  icon: 'Settings',
  category: 'integration',
  color: '#ec4899',
  inputs: [
    createInput('input', 'any', {
      description: 'Input data',
      label: { en_US: 'Input', zh_Hans: '输入' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('result', 'any', {
      description: 'Workflow result',
      label: { en_US: 'Result', zh_Hans: '结果' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether call was successful',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'webhook-url',
      name: 'webhook-url',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'Webhook URL', zh_Hans: 'Webhook URL' },
      description: { en_US: 'N8n webhook URL', zh_Hans: 'n8n Webhook URL' },
      required: true,
      default: '',
    },
    {
      id: 'timeout',
      name: 'timeout',
      type: DynamicFormItemType.INT,
      label: { en_US: 'Timeout (seconds)', zh_Hans: '超时时间（秒）' },
      description: { en_US: 'Request timeout', zh_Hans: '请求超时时间' },
      required: false,
      default: 60,
    },
  ],
  defaultConfig: { 'webhook-url': '', timeout: 60 },
};

/**
 * Langflow Flow Node
 */
export const langflowFlowConfig: NodeConfigMeta = {
  nodeType: 'langflow_flow',
  label: { en_US: 'Langflow Flow', zh_Hans: 'Langflow 流程' },
  description: { en_US: 'Call a Langflow flow', zh_Hans: '调用 Langflow 流程' },
  icon: 'Workflow',
  category: 'integration',
  color: '#ec4899',
  inputs: [
    createInput('input', 'any', {
      description: 'Input data',
      label: { en_US: 'Input', zh_Hans: '输入' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('result', 'any', {
      description: 'Flow result',
      label: { en_US: 'Result', zh_Hans: '结果' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether call was successful',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'base-url',
      name: 'base-url',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'Base URL', zh_Hans: 'Base URL' },
      description: {
        en_US: 'Langflow API base URL',
        zh_Hans: 'Langflow API 基础 URL',
      },
      required: true,
      default: '',
    },
    {
      id: 'flow-id',
      name: 'flow-id',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'Flow ID', zh_Hans: '流程 ID' },
      description: { en_US: 'Langflow flow ID', zh_Hans: 'Langflow 流程 ID' },
      required: true,
      default: '',
    },
    {
      id: 'api-key',
      name: 'api-key',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'API Key', zh_Hans: 'API Key' },
      description: {
        en_US: 'Langflow API key (optional)',
        zh_Hans: 'Langflow API 密钥（可选）',
      },
      required: false,
      default: '',
    },
    {
      id: 'timeout',
      name: 'timeout',
      type: DynamicFormItemType.INT,
      label: { en_US: 'Timeout (seconds)', zh_Hans: '超时时间（秒）' },
      description: { en_US: 'Request timeout', zh_Hans: '请求超时时间' },
      required: false,
      default: 60,
    },
  ],
  defaultConfig: { 'base-url': '', 'flow-id': '', 'api-key': '', timeout: 60 },
};

/**
 * Coze Bot Node
 */
export const cozeBotConfig: NodeConfigMeta = {
  nodeType: 'coze_bot',
  label: { en_US: 'Coze Bot', zh_Hans: 'Coze Bot' },
  description: { en_US: 'Call a Coze Bot', zh_Hans: '调用扣子 Bot' },
  icon: 'Bot',
  category: 'integration',
  color: '#ec4899',
  inputs: [
    createInput('message', 'string', {
      description: 'Message to send',
      label: { en_US: 'Message', zh_Hans: '消息' },
    }),
  ],
  outputs: [
    createOutput('result', 'any', {
      description: 'Bot response',
      label: { en_US: 'Result', zh_Hans: '结果' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether call was successful',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'api-base',
      name: 'api-base',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'API Base URL', zh_Hans: 'API 基础 URL' },
      description: { en_US: 'Coze API base URL', zh_Hans: 'Coze API 基础 URL' },
      required: true,
      default: 'https://api.coze.com',
    },
    {
      id: 'bot-id',
      name: 'bot-id',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'Bot ID', zh_Hans: 'Bot ID' },
      description: { en_US: 'Coze Bot ID', zh_Hans: 'Coze Bot ID' },
      required: true,
      default: '',
    },
    {
      id: 'api-key',
      name: 'api-key',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'API Key', zh_Hans: 'API Key' },
      description: { en_US: 'Coze API key', zh_Hans: 'Coze API 密钥' },
      required: true,
      default: '',
    },
    {
      id: 'timeout',
      name: 'timeout',
      type: DynamicFormItemType.INT,
      label: { en_US: 'Timeout (seconds)', zh_Hans: '超时时间（秒）' },
      description: { en_US: 'Request timeout', zh_Hans: '请求超时时间' },
      required: false,
      default: 60,
    },
  ],
  defaultConfig: {
    'api-base': 'https://api.coze.com',
    'bot-id': '',
    'api-key': '',
    timeout: 60,
  },
};

/**
 * All integration node configurations
 */
export const integrationConfigs: NodeConfigMeta[] = [
  difyWorkflowConfig,
  difyKnowledgeQueryConfig,
  n8nWorkflowConfig,
  langflowFlowConfig,
  cozeBotConfig,
  databaseQueryConfig,
  redisOperationConfig,
  mcpToolConfig,
  memoryStoreConfig,
];

/**
 * Get integration config by type
 */
export function getIntegrationConfig(
  nodeType: string,
): NodeConfigMeta | undefined {
  return integrationConfigs.find((config) => config.nodeType === nodeType);
}
