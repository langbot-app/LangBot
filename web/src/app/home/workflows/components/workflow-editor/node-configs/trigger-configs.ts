/**
 * Trigger Node Configurations
 * 
 * Defines configurations for all trigger node types:
 * - message_trigger: Triggered by incoming messages
 * - cron_trigger: Triggered by scheduled time
 * - webhook_trigger: Triggered by HTTP webhook calls
 * - event_trigger: Triggered by system events
 */

import { DynamicFormItemType } from '@/app/infra/entities/form/dynamic';
import { NodeConfigMeta, createOutput } from './types';

/**
 * Message Trigger Node
 * Triggers workflow when a message matches specified conditions
 */
export const messageTriggerConfig: NodeConfigMeta = {
  nodeType: 'message_trigger',
  label: {
    en_US: 'Message Trigger',
    zh_Hans: '消息触发',
  },
  description: {
    en_US: 'Trigger workflow when a message matches the specified conditions',
    zh_Hans: '当收到匹配指定条件的消息时触发工作流',
  },
  icon: 'MessageSquare',
  category: 'trigger',
  color: '#f59e0b',
  isEntryPoint: true,
  maxInstances: 1,
  inputs: [],
  outputs: [
    createOutput('message', 'object', {
      description: 'The received message object',
      label: { en_US: 'Message', zh_Hans: '消息' },
    }),
    createOutput('sender', 'object', {
      description: 'Message sender information',
      label: { en_US: 'Sender', zh_Hans: '发送者' },
    }),
    createOutput('context', 'object', {
      description: 'Message context information',
      label: { en_US: 'Context', zh_Hans: '上下文' },
    }),
  ],
  configSchema: [
    {
      id: 'match_type',
      name: 'match_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Match Type',
        zh_Hans: '匹配类型',
      },
      description: {
        en_US: 'How to match the incoming message',
        zh_Hans: '如何匹配收到的消息',
      },
      required: true,
      default: 'all',
      options: [
        { name: 'all', label: { en_US: 'All Messages', zh_Hans: '所有消息' } },
        { name: 'prefix', label: { en_US: 'Prefix Match', zh_Hans: '前缀匹配' } },
        { name: 'regex', label: { en_US: 'Regex Match', zh_Hans: '正则匹配' } },
        { name: 'contains', label: { en_US: 'Contains Keyword', zh_Hans: '包含关键词' } },
        { name: 'exact', label: { en_US: 'Exact Match', zh_Hans: '精确匹配' } },
      ],
    },
    {
      id: 'match_pattern',
      name: 'match_pattern',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Match Pattern',
        zh_Hans: '匹配模式',
      },
      description: {
        en_US: 'The pattern to match against the message (prefix, regex, keyword, or exact text)',
        zh_Hans: '用于匹配消息的模式（前缀、正则表达式、关键词或精确文本）',
      },
      required: false,
      default: '',
      show_if: {
        field: 'match_type',
        operator: 'neq',
        value: 'all',
      },
    },
    {
      id: 'ignore_bot_messages',
      name: 'ignore_bot_messages',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Ignore Bot Messages',
        zh_Hans: '忽略机器人消息',
      },
      description: {
        en_US: 'Do not trigger for messages sent by bots',
        zh_Hans: '不对机器人发送的消息触发',
      },
      required: false,
      default: true,
    },
  ],
  defaultConfig: {
    match_type: 'all',
    match_pattern: '',
    ignore_bot_messages: true,
  },
};

/**
 * Cron Trigger Node
 * Triggers workflow on a schedule
 */
export const cronTriggerConfig: NodeConfigMeta = {
  nodeType: 'cron_trigger',
  label: {
    en_US: 'Scheduled Trigger',
    zh_Hans: '定时触发',
  },
  description: {
    en_US: 'Trigger workflow on a scheduled time using cron expression',
    zh_Hans: '使用 Cron 表达式按计划时间触发工作流',
  },
  icon: 'Clock',
  category: 'trigger',
  color: '#f59e0b',
  isEntryPoint: true,
  inputs: [],
  outputs: [
    createOutput('trigger_time', 'datetime', {
      description: 'The time when the trigger fired',
      label: { en_US: 'Trigger Time', zh_Hans: '触发时间' },
    }),
    createOutput('context', 'object', {
      description: 'Trigger context information',
      label: { en_US: 'Context', zh_Hans: '上下文' },
    }),
  ],
  configSchema: [
    {
      id: 'cron_expression',
      name: 'cron_expression',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Cron Expression',
        zh_Hans: 'Cron 表达式',
      },
      description: {
        en_US: 'Standard cron expression (e.g., "0 9 * * *" for 9 AM daily)',
        zh_Hans: '标准 Cron 表达式（例如 "0 9 * * *" 表示每天上午 9 点）',
      },
      required: true,
      default: '0 9 * * *',
    },
    {
      id: 'timezone',
      name: 'timezone',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Timezone',
        zh_Hans: '时区',
      },
      description: {
        en_US: 'Timezone for the cron schedule',
        zh_Hans: 'Cron 计划的时区',
      },
      required: true,
      default: 'Asia/Shanghai',
      options: [
        { name: 'UTC', label: { en_US: 'UTC', zh_Hans: 'UTC' } },
        { name: 'Asia/Shanghai', label: { en_US: 'Asia/Shanghai (UTC+8)', zh_Hans: '亚洲/上海 (UTC+8)' } },
        { name: 'Asia/Tokyo', label: { en_US: 'Asia/Tokyo (UTC+9)', zh_Hans: '亚洲/东京 (UTC+9)' } },
        { name: 'America/New_York', label: { en_US: 'America/New_York (EST)', zh_Hans: '美国/纽约 (EST)' } },
        { name: 'America/Los_Angeles', label: { en_US: 'America/Los_Angeles (PST)', zh_Hans: '美国/洛杉矶 (PST)' } },
        { name: 'Europe/London', label: { en_US: 'Europe/London (GMT)', zh_Hans: '欧洲/伦敦 (GMT)' } },
        { name: 'Europe/Berlin', label: { en_US: 'Europe/Berlin (CET)', zh_Hans: '欧洲/柏林 (CET)' } },
      ],
    },
    {
      id: 'description',
      name: 'description',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Description',
        zh_Hans: '描述',
      },
      description: {
        en_US: 'Optional description for this scheduled trigger',
        zh_Hans: '此定时触发器的可选描述',
      },
      required: false,
      default: '',
    },
    {
      id: 'enabled',
      name: 'enabled',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Enabled',
        zh_Hans: '启用',
      },
      description: {
        en_US: 'Whether this scheduled trigger is active',
        zh_Hans: '此定时触发器是否激活',
      },
      required: false,
      default: true,
    },
  ],
  defaultConfig: {
    cron_expression: '0 9 * * *',
    timezone: 'Asia/Shanghai',
    description: '',
    enabled: true,
  },
};

/**
 * Webhook Trigger Node
 * Triggers workflow via HTTP webhook
 */
export const webhookTriggerConfig: NodeConfigMeta = {
  nodeType: 'webhook_trigger',
  label: {
    en_US: 'Webhook Trigger',
    zh_Hans: 'Webhook 触发',
  },
  description: {
    en_US: 'Trigger workflow when an HTTP request is received at the webhook URL',
    zh_Hans: '当在 Webhook URL 收到 HTTP 请求时触发工作流',
  },
  icon: 'Webhook',
  category: 'trigger',
  color: '#f59e0b',
  isEntryPoint: true,
  inputs: [],
  outputs: [
    createOutput('body', 'object', {
      description: 'Request body data',
      label: { en_US: 'Body', zh_Hans: '请求体' },
    }),
    createOutput('headers', 'object', {
      description: 'Request headers',
      label: { en_US: 'Headers', zh_Hans: '请求头' },
    }),
    createOutput('query', 'object', {
      description: 'Query parameters',
      label: { en_US: 'Query', zh_Hans: '查询参数' },
    }),
    createOutput('method', 'string', {
      description: 'HTTP method',
      label: { en_US: 'Method', zh_Hans: 'HTTP 方法' },
    }),
  ],
  configSchema: [
    {
      id: 'webhook_path',
      name: 'webhook_path',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Webhook Path',
        zh_Hans: 'Webhook 路径',
      },
      description: {
        en_US: 'Unique path for this webhook (e.g., "my-workflow")',
        zh_Hans: '此 Webhook 的唯一路径（例如 "my-workflow"）',
      },
      required: true,
      default: '',
    },
    {
      id: 'auth_type',
      name: 'auth_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Authentication',
        zh_Hans: '认证方式',
      },
      description: {
        en_US: 'How to authenticate incoming webhook requests',
        zh_Hans: '如何验证传入的 Webhook 请求',
      },
      required: true,
      default: 'none',
      options: [
        { name: 'none', label: { en_US: 'None', zh_Hans: '无' } },
        { name: 'token', label: { en_US: 'Bearer Token', zh_Hans: 'Bearer 令牌' } },
        { name: 'signature', label: { en_US: 'Signature', zh_Hans: '签名验证' } },
        { name: 'basic', label: { en_US: 'Basic Auth', zh_Hans: '基本认证' } },
      ],
    },
    {
      id: 'auth_token',
      name: 'auth_token',
      type: DynamicFormItemType.SECRET,
      label: {
        en_US: 'Auth Token',
        zh_Hans: '认证令牌',
      },
      description: {
        en_US: 'Token or secret for authentication',
        zh_Hans: '用于认证的令牌或密钥',
      },
      required: true,
      default: '',
      show_if: {
        field: 'auth_type',
        operator: 'in',
        value: ['token', 'signature', 'basic'],
      },
    },
    {
      id: 'content_type',
      name: 'content_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Content Type',
        zh_Hans: '内容类型',
      },
      description: {
        en_US: 'Expected Content-Type of the request',
        zh_Hans: '请求预期的 Content-Type',
      },
      required: false,
      default: 'application/json',
      options: [
        { name: 'application/json', label: { en_US: 'application/json', zh_Hans: 'JSON' } },
        { name: 'application/x-www-form-urlencoded', label: { en_US: 'application/x-www-form-urlencoded', zh_Hans: '表单编码' } },
        { name: 'multipart/form-data', label: { en_US: 'multipart/form-data', zh_Hans: '表单数据' } },
        { name: 'text/plain', label: { en_US: 'text/plain', zh_Hans: '纯文本' } },
      ],
    },
    {
      id: 'validation',
      name: 'validation',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Validation Rules',
        zh_Hans: '验证规则',
      },
      description: {
        en_US: 'JSON validation rules for request body (optional)',
        zh_Hans: '请求体的 JSON 验证规则（可选）',
      },
      required: false,
      default: '{}',
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
        en_US: 'Request timeout in seconds',
        zh_Hans: '请求超时时间（秒）',
      },
      required: false,
      default: 30,
    },
  ],
  defaultConfig: {
    webhook_path: '',
    auth_type: 'none',
    auth_token: '',
    content_type: 'application/json',
    validation: '{}',
    timeout: 30,
  },
};

/**
 * Event Trigger Node
 * Triggers workflow on system events
 */
export const eventTriggerConfig: NodeConfigMeta = {
  nodeType: 'event_trigger',
  label: {
    en_US: 'Event Trigger',
    zh_Hans: '事件触发',
  },
  description: {
    en_US: 'Trigger workflow when a system event occurs',
    zh_Hans: '当系统事件发生时触发工作流',
  },
  icon: 'Zap',
  category: 'trigger',
  color: '#f59e0b',
  isEntryPoint: true,
  inputs: [],
  outputs: [
    createOutput('event', 'object', {
      description: 'The event data',
      label: { en_US: 'Event', zh_Hans: '事件' },
    }),
    createOutput('event_type', 'string', {
      description: 'Type of the event',
      label: { en_US: 'Event Type', zh_Hans: '事件类型' },
    }),
    createOutput('context', 'object', {
      description: 'Event context information',
      label: { en_US: 'Context', zh_Hans: '上下文' },
    }),
  ],
  configSchema: [
    {
      id: 'event_type',
      name: 'event_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Event Type',
        zh_Hans: '事件类型',
      },
      description: {
        en_US: 'The type of system event to listen for',
        zh_Hans: '要监听的系统事件类型',
      },
      required: true,
      default: 'member_join',
      options: [
        { name: 'member_join', label: { en_US: 'Member Join', zh_Hans: '成员加入' } },
        { name: 'member_leave', label: { en_US: 'Member Leave', zh_Hans: '成员离开' } },
        { name: 'message_recall', label: { en_US: 'Message Recall', zh_Hans: '消息撤回' } },
        { name: 'group_created', label: { en_US: 'Group Created', zh_Hans: '群组创建' } },
        { name: 'group_disbanded', label: { en_US: 'Group Disbanded', zh_Hans: '群组解散' } },
        { name: 'bot_added', label: { en_US: 'Bot Added to Group', zh_Hans: '机器人被添加到群' } },
        { name: 'bot_removed', label: { en_US: 'Bot Removed from Group', zh_Hans: '机器人被移出群' } },
        { name: 'friend_request', label: { en_US: 'Friend Request', zh_Hans: '好友请求' } },
        { name: 'group_request', label: { en_US: 'Group Join Request', zh_Hans: '入群请求' } },
      ],
    },
  ],
  defaultConfig: {
    event_type: 'member_join',
  },
};

/**
 * All trigger node configurations
 */
export const triggerConfigs: NodeConfigMeta[] = [
  messageTriggerConfig,
  cronTriggerConfig,
  webhookTriggerConfig,
  eventTriggerConfig,
];

/**
 * Get trigger config by type
 */
export function getTriggerConfig(nodeType: string): NodeConfigMeta | undefined {
  return triggerConfigs.find((config) => config.nodeType === nodeType);
}
