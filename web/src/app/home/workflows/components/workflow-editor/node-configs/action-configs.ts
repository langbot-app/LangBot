/**
 * Action Node Configurations
 *
 * Defines configurations for action node types:
 * - send_message: Send a message
 * - http_request: Make HTTP requests
 * - bot_invoke: Invoke another bot
 * - workflow_invoke: Invoke another workflow
 * - notification: Send notifications
 */

import { DynamicFormItemType } from '@/app/infra/entities/form/dynamic';
import { NodeConfigMeta, createInput, createOutput } from './types';

/**
 * Send Message Node
 * Sends a message to a chat or user
 */
export const sendMessageConfig: NodeConfigMeta = {
  nodeType: 'send_message',
  label: {
    en_US: 'Send Message',
    zh_Hans: '发送消息',
  },
  description: {
    en_US: 'Send a message to a chat or user',
    zh_Hans: '向聊天或用户发送消息',
  },
  icon: 'Send',
  category: 'action',
  color: '#10b981',
  inputs: [
    createInput('content', 'string', {
      description: 'Message content to send',
      label: { en_US: 'Content', zh_Hans: '内容' },
      required: false,
    }),
    createInput('context', 'object', {
      description: 'Message context (for reply)',
      label: { en_US: 'Context', zh_Hans: '上下文' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('message_id', 'string', {
      description: 'ID of the sent message',
      label: { en_US: 'Message ID', zh_Hans: '消息 ID' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether the message was sent successfully',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'message_type',
      name: 'message_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Message Type',
        zh_Hans: '消息类型',
      },
      description: {
        en_US: 'Type of message to send',
        zh_Hans: '要发送的消息类型',
      },
      required: true,
      default: 'text',
      options: [
        { name: 'text', label: { en_US: 'Text', zh_Hans: '文本' } },
        {
          name: 'markdown',
          label: { en_US: 'Markdown', zh_Hans: 'Markdown 文本' },
        },
        { name: 'image', label: { en_US: 'Image', zh_Hans: '图片' } },
        { name: 'file', label: { en_US: 'File', zh_Hans: '文件' } },
        { name: 'card', label: { en_US: 'Card', zh_Hans: '卡片' } },
      ],
    },
    {
      id: 'content_template',
      name: 'content_template',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Content Template',
        zh_Hans: '内容模板',
      },
      description: {
        en_US:
          'Message content template (supports variables). Leave empty to use input.',
        zh_Hans: '消息内容模板（支持变量）。留空则使用输入。',
      },
      required: false,
      default: '',
    },
    {
      id: 'reply_to_original',
      name: 'reply_to_original',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Reply to Original',
        zh_Hans: '回复原消息',
      },
      description: {
        en_US: 'Reply to the original message that triggered the workflow',
        zh_Hans: '回复触发工作流的原始消息',
      },
      required: false,
      default: true,
    },
    {
      id: 'at_sender',
      name: 'at_sender',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: '@ Sender',
        zh_Hans: '@ 发送者',
      },
      description: {
        en_US: 'Mention the original sender in the reply',
        zh_Hans: '在回复中提及原始发送者',
      },
      required: false,
      default: false,
    },
  ],
  defaultConfig: {
    message_type: 'text',
    content_template: '',
    reply_to_original: true,
    at_sender: false,
  },
};

/**
 * HTTP Request Node
 * Makes HTTP requests to external APIs
 */
export const httpRequestConfig: NodeConfigMeta = {
  nodeType: 'http_request',
  label: {
    en_US: 'HTTP Request',
    zh_Hans: 'HTTP 请求',
  },
  description: {
    en_US: 'Make HTTP requests to external APIs',
    zh_Hans: '向外部 API 发送 HTTP 请求',
  },
  icon: 'Globe',
  category: 'action',
  color: '#10b981',
  inputs: [
    createInput('body', 'any', {
      description: 'Request body data',
      label: { en_US: 'Body', zh_Hans: '请求体' },
      required: false,
    }),
    createInput('variables', 'object', {
      description: 'Variables for URL/header templates',
      label: { en_US: 'Variables', zh_Hans: '变量' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('response', 'any', {
      description: 'Response body',
      label: { en_US: 'Response', zh_Hans: '响应' },
    }),
    createOutput('status_code', 'number', {
      description: 'HTTP status code',
      label: { en_US: 'Status Code', zh_Hans: '状态码' },
    }),
    createOutput('headers', 'object', {
      description: 'Response headers',
      label: { en_US: 'Headers', zh_Hans: '响应头' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether request was successful (2xx)',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'method',
      name: 'method',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Method',
        zh_Hans: '方法',
      },
      description: {
        en_US: 'HTTP method',
        zh_Hans: 'HTTP 方法',
      },
      required: true,
      default: 'GET',
      options: [
        { name: 'GET', label: { en_US: 'GET', zh_Hans: 'GET' } },
        { name: 'POST', label: { en_US: 'POST', zh_Hans: 'POST' } },
        { name: 'PUT', label: { en_US: 'PUT', zh_Hans: 'PUT' } },
        { name: 'PATCH', label: { en_US: 'PATCH', zh_Hans: 'PATCH' } },
        { name: 'DELETE', label: { en_US: 'DELETE', zh_Hans: 'DELETE' } },
      ],
    },
    {
      id: 'url',
      name: 'url',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'URL',
        zh_Hans: 'URL',
      },
      description: {
        en_US: 'Request URL (supports variable interpolation)',
        zh_Hans: '请求 URL（支持变量插值）',
      },
      required: true,
      default: '',
    },
    {
      id: 'headers',
      name: 'headers',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Headers',
        zh_Hans: '请求头',
      },
      description: {
        en_US: 'Request headers as JSON object',
        zh_Hans: '请求头（JSON 对象格式）',
      },
      required: false,
      default: '{}',
    },
    {
      id: 'body_type',
      name: 'body_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Body Type',
        zh_Hans: '请求体类型',
      },
      description: {
        en_US: 'Type of request body',
        zh_Hans: '请求体的类型',
      },
      required: false,
      default: 'json',
      options: [
        { name: 'none', label: { en_US: 'None', zh_Hans: '无' } },
        { name: 'json', label: { en_US: 'JSON', zh_Hans: 'JSON' } },
        { name: 'form', label: { en_US: 'Form Data', zh_Hans: '表单数据' } },
        { name: 'raw', label: { en_US: 'Raw', zh_Hans: '原始' } },
      ],
      show_if: {
        field: 'method',
        operator: 'in',
        value: ['POST', 'PUT', 'PATCH'],
      },
    },
    {
      id: 'body_template',
      name: 'body_template',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Body Template',
        zh_Hans: '请求体模板',
      },
      description: {
        en_US:
          'Request body template (supports variables). Leave empty to use input.',
        zh_Hans: '请求体模板（支持变量）。留空则使用输入。',
      },
      required: false,
      default: '',
      show_if: {
        field: 'body_type',
        operator: 'in',
        value: ['json', 'form', 'raw'],
      },
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
    {
      id: 'retry_count',
      name: 'retry_count',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Retry Count',
        zh_Hans: '重试次数',
      },
      description: {
        en_US: 'Number of retries on failure',
        zh_Hans: '失败时的重试次数',
      },
      required: false,
      default: 0,
    },
    {
      id: 'ignore_ssl',
      name: 'ignore_ssl',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Ignore SSL Errors',
        zh_Hans: '忽略 SSL 错误',
      },
      description: {
        en_US: 'Ignore SSL certificate verification errors',
        zh_Hans: '忽略 SSL 证书验证错误',
      },
      required: false,
      default: false,
    },
  ],
  defaultConfig: {
    method: 'GET',
    url: '',
    headers: '{}',
    body_type: 'json',
    body_template: '',
    timeout: 30,
    retry_count: 0,
    ignore_ssl: false,
  },
};

/**
 * Bot Invoke Node
 * Invokes another bot to handle a task
 */
export const botInvokeConfig: NodeConfigMeta = {
  nodeType: 'bot_invoke',
  label: {
    en_US: 'Invoke Bot',
    zh_Hans: '调用机器人',
  },
  description: {
    en_US: 'Invoke another bot to process the input',
    zh_Hans: '调用另一个机器人处理输入',
  },
  icon: 'Bot',
  category: 'action',
  color: '#10b981',
  inputs: [
    createInput('message', 'string', {
      description: 'Message to send to the bot',
      label: { en_US: 'Message', zh_Hans: '消息' },
    }),
    createInput('context', 'object', {
      description: 'Additional context',
      label: { en_US: 'Context', zh_Hans: '上下文' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('response', 'string', {
      description: 'Bot response',
      label: { en_US: 'Response', zh_Hans: '响应' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether invocation was successful',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'bot',
      name: 'bot',
      type: DynamicFormItemType.BOT_SELECTOR,
      label: {
        en_US: 'Bot',
        zh_Hans: '机器人',
      },
      description: {
        en_US: 'Select the bot to invoke',
        zh_Hans: '选择要调用的机器人',
      },
      required: true,
      default: '',
    },
    {
      id: 'wait_for_response',
      name: 'wait_for_response',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Wait for Response',
        zh_Hans: '等待响应',
      },
      description: {
        en_US: 'Wait for the bot to respond before continuing',
        zh_Hans: '等待机器人响应后再继续',
      },
      required: false,
      default: true,
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
        en_US: 'Maximum time to wait for response',
        zh_Hans: '等待响应的最大时间',
      },
      required: false,
      default: 60,
      show_if: {
        field: 'wait_for_response',
        operator: 'eq',
        value: true,
      },
    },
  ],
  defaultConfig: {
    bot: '',
    wait_for_response: true,
    timeout: 60,
  },
};

/**
 * Workflow Invoke Node
 * Invokes another workflow
 */
export const workflowInvokeConfig: NodeConfigMeta = {
  nodeType: 'workflow_invoke',
  label: {
    en_US: 'Invoke Workflow',
    zh_Hans: '调用工作流',
  },
  description: {
    en_US: 'Invoke another workflow as a sub-workflow',
    zh_Hans: '调用另一个工作流作为子工作流',
  },
  icon: 'Workflow',
  category: 'action',
  color: '#10b981',
  inputs: [
    createInput('input', 'any', {
      description: 'Input data for the workflow',
      label: { en_US: 'Input', zh_Hans: '输入' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('output', 'any', {
      description: 'Workflow output',
      label: { en_US: 'Output', zh_Hans: '输出' },
    }),
    createOutput('status', 'string', {
      description: 'Workflow execution status',
      label: { en_US: 'Status', zh_Hans: '状态' },
    }),
    createOutput('execution_id', 'string', {
      description: 'Workflow execution ID',
      label: { en_US: 'Execution ID', zh_Hans: '执行 ID' },
    }),
  ],
  configSchema: [
    {
      id: 'workflow_id',
      name: 'workflow_id',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Workflow ID',
        zh_Hans: '工作流 ID',
      },
      description: {
        en_US: 'ID of the workflow to invoke',
        zh_Hans: '要调用的工作流 ID',
      },
      required: true,
      default: '',
    },
    {
      id: 'wait_for_completion',
      name: 'wait_for_completion',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Wait for Completion',
        zh_Hans: '等待完成',
      },
      description: {
        en_US: 'Wait for the workflow to complete before continuing',
        zh_Hans: '等待工作流完成后再继续',
      },
      required: false,
      default: true,
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
        en_US: 'Maximum time to wait for workflow completion',
        zh_Hans: '等待工作流完成的最大时间',
      },
      required: false,
      default: 300,
      show_if: {
        field: 'wait_for_completion',
        operator: 'eq',
        value: true,
      },
    },
    {
      id: 'pass_context',
      name: 'pass_context',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Pass Context',
        zh_Hans: '传递上下文',
      },
      description: {
        en_US: 'Pass the current workflow context to the sub-workflow',
        zh_Hans: '将当前工作流上下文传递给子工作流',
      },
      required: false,
      default: false,
    },
  ],
  defaultConfig: {
    workflow_id: '',
    wait_for_completion: true,
    timeout: 300,
    pass_context: false,
  },
};

/**
 * Notification Node
 * Sends notifications via various channels
 */
export const notificationConfig: NodeConfigMeta = {
  nodeType: 'notification',
  label: {
    en_US: 'Notification',
    zh_Hans: '通知',
  },
  description: {
    en_US: 'Send notifications via various channels',
    zh_Hans: '通过各种渠道发送通知',
  },
  icon: 'Bell',
  category: 'action',
  color: '#10b981',
  inputs: [
    createInput('content', 'string', {
      description: 'Notification content',
      label: { en_US: 'Content', zh_Hans: '内容' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('success', 'boolean', {
      description: 'Whether notification was sent',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
    createOutput('notification_id', 'string', {
      description: 'ID of the sent notification',
      label: { en_US: 'Notification ID', zh_Hans: '通知 ID' },
    }),
  ],
  configSchema: [
    {
      id: 'channel',
      name: 'channel',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Channel',
        zh_Hans: '渠道',
      },
      description: {
        en_US: 'Notification channel',
        zh_Hans: '通知渠道',
      },
      required: true,
      default: 'webhook',
      options: [
        { name: 'webhook', label: { en_US: 'Webhook', zh_Hans: 'Webhook' } },
        { name: 'email', label: { en_US: 'Email', zh_Hans: '邮件' } },
        { name: 'dingtalk', label: { en_US: 'DingTalk', zh_Hans: '钉钉' } },
        { name: 'feishu', label: { en_US: 'Feishu', zh_Hans: '飞书' } },
        {
          name: 'wechat_work',
          label: { en_US: 'WeChat Work', zh_Hans: '企业微信' },
        },
      ],
    },
    {
      id: 'title',
      name: 'title',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Title',
        zh_Hans: '标题',
      },
      description: {
        en_US: 'Notification title',
        zh_Hans: '通知标题',
      },
      required: false,
      default: '',
    },
    {
      id: 'content_template',
      name: 'content_template',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Content Template',
        zh_Hans: '内容模板',
      },
      description: {
        en_US: 'Notification content (supports variables)',
        zh_Hans: '通知内容（支持变量）',
      },
      required: false,
      default: '',
    },
    {
      id: 'webhook_url',
      name: 'webhook_url',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Webhook URL',
        zh_Hans: 'Webhook URL',
      },
      description: {
        en_US: 'URL for webhook notifications',
        zh_Hans: 'Webhook 通知的 URL',
      },
      required: true,
      default: '',
      show_if: {
        field: 'channel',
        operator: 'in',
        value: ['webhook', 'dingtalk', 'feishu', 'wechat_work'],
      },
    },
    {
      id: 'recipients',
      name: 'recipients',
      type: DynamicFormItemType.STRING_ARRAY,
      label: {
        en_US: 'Recipients',
        zh_Hans: '接收者',
      },
      description: {
        en_US: 'Email recipients or user IDs',
        zh_Hans: '邮件接收者或用户 ID',
      },
      required: true,
      default: [],
      show_if: {
        field: 'channel',
        operator: 'eq',
        value: 'email',
      },
    },
  ],
  defaultConfig: {
    channel: 'webhook',
    title: '',
    content_template: '',
    webhook_url: '',
    recipients: [],
  },
};

/**
 * Reply Message Node
 * Replies to the message that triggered the workflow
 */
export const replyMessageConfig: NodeConfigMeta = {
  nodeType: 'reply_message',
  label: {
    en_US: 'Reply Message',
    zh_Hans: '回复消息',
  },
  description: {
    en_US: 'Reply to the message that triggered the workflow',
    zh_Hans: '回复触发工作流的消息',
  },
  icon: 'MessageCircle',
  category: 'action',
  color: '#10b981',
  inputs: [
    createInput('content', 'string', {
      description: 'Reply content',
      label: { en_US: 'Content', zh_Hans: '内容' },
      required: false,
    }),
    createInput('context', 'object', {
      description: 'Message context (from trigger)',
      label: { en_US: 'Context', zh_Hans: '上下文' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('message_id', 'string', {
      description: 'ID of the sent reply',
      label: { en_US: 'Message ID', zh_Hans: '消息 ID' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether the reply was sent successfully',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'reply_mode',
      name: 'reply_mode',
      type: DynamicFormItemType.SELECT,
      label: { en_US: 'Reply Mode', zh_Hans: '回复模式' },
      description: {
        en_US: 'How to reply to the original message',
        zh_Hans: '如何回复原始消息',
      },
      required: true,
      default: 'reply',
      options: [
        { name: 'reply', label: { en_US: 'Quote Reply', zh_Hans: '引用回复' } },
        {
          name: 'direct',
          label: { en_US: 'Direct Message', zh_Hans: '直接消息' },
        },
      ],
    },
    {
      id: 'message_template',
      name: 'message_template',
      type: DynamicFormItemType.TEXT,
      label: { en_US: 'Message Template', zh_Hans: '消息模板' },
      description: {
        en_US:
          'Reply content template (supports {{variable}} interpolation). Leave empty to use input.',
        zh_Hans: '回复内容模板（支持 {{variable}} 插值）。留空则使用输入。',
      },
      required: false,
      default: '',
    },
    {
      id: 'long_text_processing',
      name: 'long_text_processing',
      type: DynamicFormItemType.SELECT,
      label: { en_US: 'Long Text Processing', zh_Hans: '长文本处理' },
      description: {
        en_US: 'How to handle long text that exceeds platform limits',
        zh_Hans: '如何处理超出平台限制的长文本',
      },
      required: false,
      default: 'truncate',
      options: [
        { name: 'truncate', label: { en_US: 'Truncate', zh_Hans: '截断' } },
        {
          name: 'split',
          label: {
            en_US: 'Split into multiple messages',
            zh_Hans: '拆分为多条消息',
          },
        },
        {
          name: 'forward',
          label: { en_US: 'Forward as file', zh_Hans: '转发为文件' },
        },
      ],
    },
  ],
  defaultConfig: {
    reply_mode: 'reply',
    message_template: '',
    long_text_processing: 'truncate',
  },
};

/**
 * Store Data Node
 * Stores data to persistent storage
 */
export const storeDataConfig: NodeConfigMeta = {
  nodeType: 'store_data',
  label: {
    en_US: 'Store Data',
    zh_Hans: '存储数据',
  },
  description: {
    en_US: 'Store data to persistent storage',
    zh_Hans: '将数据存储到持久化存储',
  },
  icon: 'Database',
  category: 'action',
  color: '#10b981',
  inputs: [
    createInput('value', 'any', {
      description: 'Value to store',
      label: { en_US: 'Value', zh_Hans: '值' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('success', 'boolean', {
      description: 'Whether storage was successful',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'storage_type',
      name: 'storage_type',
      type: DynamicFormItemType.SELECT,
      label: { en_US: 'Storage Type', zh_Hans: '存储类型' },
      description: {
        en_US: 'Type of storage to use',
        zh_Hans: '要使用的存储类型',
      },
      required: true,
      default: 'variable',
      options: [
        {
          name: 'variable',
          label: { en_US: 'Workflow Variable', zh_Hans: '工作流变量' },
        },
        {
          name: 'session',
          label: { en_US: 'Session Storage', zh_Hans: '会话存储' },
        },
        {
          name: 'persistent',
          label: { en_US: 'Persistent Storage', zh_Hans: '持久化存储' },
        },
      ],
    },
    {
      id: 'key',
      name: 'key',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'Key', zh_Hans: '键' },
      description: {
        en_US: 'Storage key (supports variable interpolation)',
        zh_Hans: '存储键（支持变量插值）',
      },
      required: true,
      default: '',
    },
    {
      id: 'ttl',
      name: 'ttl',
      type: DynamicFormItemType.INT,
      label: { en_US: 'TTL (seconds)', zh_Hans: 'TTL（秒）' },
      description: {
        en_US: 'Time to live (0 = no expiry)',
        zh_Hans: '过期时间（0 = 不过期）',
      },
      required: false,
      default: 0,
    },
  ],
  defaultConfig: { storage_type: 'variable', key: '', ttl: 0 },
};

/**
 * Call Pipeline Node
 * Invokes an existing Pipeline
 */
export const callPipelineConfig: NodeConfigMeta = {
  nodeType: 'call_pipeline',
  label: {
    en_US: 'Call Pipeline',
    zh_Hans: '调用 Pipeline',
  },
  description: {
    en_US: 'Invoke an existing Pipeline for processing',
    zh_Hans: '调用现有的 Pipeline 进行处理',
  },
  icon: 'Workflow',
  category: 'action',
  color: '#10b981',
  inputs: [
    createInput('input', 'any', {
      description: 'Input data for the pipeline',
      label: { en_US: 'Input', zh_Hans: '输入' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('response', 'string', {
      description: 'Pipeline response',
      label: { en_US: 'Response', zh_Hans: '响应' },
    }),
    createOutput('result', 'object', {
      description: 'Pipeline execution result',
      label: { en_US: 'Result', zh_Hans: '结果' },
    }),
  ],
  configSchema: [
    {
      id: 'pipeline_uuid',
      name: 'pipeline_uuid',
      type: DynamicFormItemType.PIPELINE_SELECTOR,
      label: { en_US: 'Pipeline', zh_Hans: '流水线' },
      description: {
        en_US: 'Select the pipeline to invoke',
        zh_Hans: '选择要调用的流水线',
      },
      required: true,
      default: '',
    },
    {
      id: 'inherit_context',
      name: 'inherit_context',
      type: DynamicFormItemType.BOOLEAN,
      label: { en_US: 'Inherit Context', zh_Hans: '继承上下文' },
      description: {
        en_US: 'Pass the current workflow context to the pipeline',
        zh_Hans: '将当前工作流上下文传递给 Pipeline',
      },
      required: false,
      default: true,
    },
    {
      id: 'timeout',
      name: 'timeout',
      type: DynamicFormItemType.INT,
      label: { en_US: 'Timeout (seconds)', zh_Hans: '超时时间（秒）' },
      description: { en_US: 'Maximum execution time', zh_Hans: '最大执行时间' },
      required: false,
      default: 60,
    },
  ],
  defaultConfig: { pipeline_uuid: '', inherit_context: true, timeout: 60 },
};

/**
 * Set Variable Node
 * Sets a context variable
 */
export const setVariableConfig: NodeConfigMeta = {
  nodeType: 'set_variable',
  label: {
    en_US: 'Set Variable',
    zh_Hans: '设置变量',
  },
  description: {
    en_US: 'Set a context variable value',
    zh_Hans: '设置上下文变量值',
  },
  icon: 'Variable',
  category: 'action',
  color: '#10b981',
  inputs: [
    createInput('value', 'any', {
      description: 'Value to set',
      label: { en_US: 'Value', zh_Hans: '值' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('output', 'any', {
      description: 'The set value',
      label: { en_US: 'Output', zh_Hans: '输出' },
    }),
  ],
  configSchema: [
    {
      id: 'variable_name',
      name: 'variable_name',
      type: DynamicFormItemType.STRING,
      label: { en_US: 'Variable Name', zh_Hans: '变量名' },
      description: {
        en_US: 'Name of the variable to set',
        zh_Hans: '要设置的变量名',
      },
      required: true,
      default: '',
    },
    {
      id: 'variable_scope',
      name: 'variable_scope',
      type: DynamicFormItemType.SELECT,
      label: { en_US: 'Variable Scope', zh_Hans: '变量作用域' },
      description: { en_US: 'Scope of the variable', zh_Hans: '变量的作用域' },
      required: true,
      default: 'workflow',
      options: [
        { name: 'workflow', label: { en_US: 'Workflow', zh_Hans: '工作流' } },
        { name: 'session', label: { en_US: 'Session', zh_Hans: '会话' } },
        { name: 'global', label: { en_US: 'Global', zh_Hans: '全局' } },
      ],
    },
    {
      id: 'value_template',
      name: 'value_template',
      type: DynamicFormItemType.TEXT,
      label: { en_US: 'Value Template', zh_Hans: '值模板' },
      description: {
        en_US:
          'Value template (supports {{variable}} interpolation). Leave empty to use input.',
        zh_Hans: '值模板（支持 {{variable}} 插值）。留空则使用输入。',
      },
      required: false,
      default: '',
    },
  ],
  defaultConfig: {
    variable_name: '',
    variable_scope: 'workflow',
    value_template: '',
  },
};

/**
 * Opening Statement Node
 * Provides conversation opener and suggested questions
 */
export const openingStatementConfig: NodeConfigMeta = {
  nodeType: 'opening_statement',
  label: {
    en_US: 'Opening Statement',
    zh_Hans: '对话开场白',
  },
  description: {
    en_US: 'Provide conversation opener and suggested questions',
    zh_Hans: '提供对话开场白和建议问题',
  },
  icon: 'MessageSquarePlus',
  category: 'action',
  color: '#10b981',
  inputs: [],
  outputs: [
    createOutput('statement', 'string', {
      description: 'The opening statement text',
      label: { en_US: 'Statement', zh_Hans: '开场白' },
    }),
    createOutput('suggestions', 'array', {
      description: 'Suggested questions',
      label: { en_US: 'Suggestions', zh_Hans: '建议问题' },
    }),
  ],
  configSchema: [
    {
      id: 'statement',
      name: 'statement',
      type: DynamicFormItemType.TEXT,
      label: { en_US: 'Opening Statement', zh_Hans: '开场白' },
      description: {
        en_US: 'The opening statement to display',
        zh_Hans: '要显示的开场白',
      },
      required: true,
      default: '',
    },
    {
      id: 'suggested_questions',
      name: 'suggested_questions',
      type: DynamicFormItemType.STRING_ARRAY,
      label: { en_US: 'Suggested Questions', zh_Hans: '建议问题' },
      description: {
        en_US: 'List of suggested questions for the user',
        zh_Hans: '给用户的建议问题列表',
      },
      required: false,
      default: [],
    },
    {
      id: 'show_suggestions',
      name: 'show_suggestions',
      type: DynamicFormItemType.BOOLEAN,
      label: { en_US: 'Show Suggestions', zh_Hans: '显示建议' },
      description: {
        en_US: 'Whether to show suggested questions',
        zh_Hans: '是否显示建议问题',
      },
      required: false,
      default: true,
    },
  ],
  defaultConfig: {
    statement: '',
    suggested_questions: [],
    show_suggestions: true,
  },
};

/**
 * All action node configurations
 */
export const actionConfigs: NodeConfigMeta[] = [
  sendMessageConfig,
  replyMessageConfig,
  httpRequestConfig,
  storeDataConfig,
  callPipelineConfig,
  setVariableConfig,
  openingStatementConfig,
  botInvokeConfig,
  workflowInvokeConfig,
  notificationConfig,
];

/**
 * Get action config by type
 */
export function getActionConfig(nodeType: string): NodeConfigMeta | undefined {
  return actionConfigs.find((config) => config.nodeType === nodeType);
}
