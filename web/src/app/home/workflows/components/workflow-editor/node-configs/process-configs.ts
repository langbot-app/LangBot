/**
 * Process Node Configurations
 * 
 * Defines configurations for general processing node types:
 * - text_template: Generate text using templates
 * - json_transform: Transform JSON data
 * - code_executor: Execute custom code
 * - data_aggregator: Aggregate data from multiple sources
 * - text_splitter: Split text into chunks
 */

import { DynamicFormItemType } from '@/app/infra/entities/form/dynamic';
import { NodeConfigMeta, createInput, createOutput } from './types';

/**
 * Text Template Node
 * Generates text using variable interpolation
 */
export const textTemplateConfig: NodeConfigMeta = {
  nodeType: 'text_template',
  label: {
    en_US: 'Text Template',
    zh_Hans: '文本模板',
  },
  description: {
    en_US: 'Generate text using templates with variable interpolation',
    zh_Hans: '使用带有变量插值的模板生成文本',
  },
  icon: 'FileText',
  category: 'process',
  color: '#3b82f6',
  inputs: [
    createInput('variables', 'object', {
      description: 'Variables to use in the template',
      label: { en_US: 'Variables', zh_Hans: '变量' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('text', 'string', {
      description: 'Generated text',
      label: { en_US: 'Text', zh_Hans: '文本' },
    }),
  ],
  configSchema: [
    {
      id: 'template',
      name: 'template',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Template',
        zh_Hans: '模板',
      },
      description: {
        en_US: 'Text template with variable placeholders (e.g., {{variable_name}})',
        zh_Hans: '带有变量占位符的文本模板（例如 {{variable_name}}）',
      },
      required: true,
      default: '',
    },
    {
      id: 'escape_html',
      name: 'escape_html',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Escape HTML',
        zh_Hans: '转义 HTML',
      },
      description: {
        en_US: 'Escape HTML characters in variable values',
        zh_Hans: '转义变量值中的 HTML 字符',
      },
      required: false,
      default: false,
    },
    {
      id: 'trim_whitespace',
      name: 'trim_whitespace',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Trim Whitespace',
        zh_Hans: '去除空白',
      },
      description: {
        en_US: 'Remove leading and trailing whitespace from output',
        zh_Hans: '去除输出的前后空白',
      },
      required: false,
      default: true,
    },
  ],
  defaultConfig: {
    template: '',
    escape_html: false,
    trim_whitespace: true,
  },
};

/**
 * JSON Transform Node
 * Transforms JSON data using JSONPath or JMESPath expressions
 */
export const jsonTransformConfig: NodeConfigMeta = {
  nodeType: 'json_transform',
  label: {
    en_US: 'JSON Transform',
    zh_Hans: 'JSON 转换',
  },
  description: {
    en_US: 'Transform JSON data using expressions or mappings',
    zh_Hans: '使用表达式或映射转换 JSON 数据',
  },
  icon: 'Braces',
  category: 'process',
  color: '#3b82f6',
  inputs: [
    createInput('input', 'object', {
      description: 'JSON data to transform',
      label: { en_US: 'Input', zh_Hans: '输入' },
    }),
  ],
  outputs: [
    createOutput('output', 'any', {
      description: 'Transformed data',
      label: { en_US: 'Output', zh_Hans: '输出' },
    }),
  ],
  configSchema: [
    {
      id: 'transform_type',
      name: 'transform_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Transform Type',
        zh_Hans: '转换类型',
      },
      description: {
        en_US: 'Method of transformation',
        zh_Hans: '转换方法',
      },
      required: true,
      default: 'jmespath',
      options: [
        { name: 'jmespath', label: { en_US: 'JMESPath Expression', zh_Hans: 'JMESPath 表达式' } },
        { name: 'jsonpath', label: { en_US: 'JSONPath Expression', zh_Hans: 'JSONPath 表达式' } },
        { name: 'mapping', label: { en_US: 'Field Mapping', zh_Hans: '字段映射' } },
      ],
    },
    {
      id: 'expression',
      name: 'expression',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Expression',
        zh_Hans: '表达式',
      },
      description: {
        en_US: 'JMESPath or JSONPath expression',
        zh_Hans: 'JMESPath 或 JSONPath 表达式',
      },
      required: true,
      default: '',
      show_if: {
        field: 'transform_type',
        operator: 'in',
        value: ['jmespath', 'jsonpath'],
      },
    },
    {
      id: 'mapping',
      name: 'mapping',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Field Mapping',
        zh_Hans: '字段映射',
      },
      description: {
        en_US: 'JSON object defining field mappings: {"output_field": "input.path.to.field"}',
        zh_Hans: '定义字段映射的 JSON 对象: {"output_field": "input.path.to.field"}',
      },
      required: true,
      default: '{}',
      show_if: {
        field: 'transform_type',
        operator: 'eq',
        value: 'mapping',
      },
    },
  ],
  defaultConfig: {
    transform_type: 'jmespath',
    expression: '',
    mapping: '{}',
  },
};

/**
 * Code Executor Node
 * Executes custom code (JavaScript/Python)
 */
export const codeExecutorConfig: NodeConfigMeta = {
  nodeType: 'code_executor',
  label: {
    en_US: 'Code Executor',
    zh_Hans: '代码执行',
  },
  description: {
    en_US: 'Execute custom code to process data',
    zh_Hans: '执行自定义代码处理数据',
  },
  icon: 'Code',
  category: 'process',
  color: '#3b82f6',
  inputs: [
    createInput('input', 'any', {
      description: 'Input data for the code',
      label: { en_US: 'Input', zh_Hans: '输入' },
    }),
  ],
  outputs: [
    createOutput('output', 'any', {
      description: 'Code execution result',
      label: { en_US: 'Output', zh_Hans: '输出' },
    }),
    createOutput('logs', 'array', {
      description: 'Console logs from code execution',
      label: { en_US: 'Logs', zh_Hans: '日志' },
    }),
  ],
  configSchema: [
    {
      id: 'language',
      name: 'language',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Language',
        zh_Hans: '语言',
      },
      description: {
        en_US: 'Programming language to use',
        zh_Hans: '要使用的编程语言',
      },
      required: true,
      default: 'javascript',
      options: [
        { name: 'javascript', label: { en_US: 'JavaScript', zh_Hans: 'JavaScript' } },
        { name: 'python', label: { en_US: 'Python', zh_Hans: 'Python' } },
      ],
    },
    {
      id: 'code',
      name: 'code',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Code',
        zh_Hans: '代码',
      },
      description: {
        en_US: 'Code to execute. Use `input` to access input data and return the result.',
        zh_Hans: '要执行的代码。使用 `input` 访问输入数据，并返回结果。',
      },
      required: true,
      default: '// Access input with: input\n// Return result with: return result;\n\nreturn input;',
    },
    {
      id: 'timeout',
      name: 'timeout',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Timeout (ms)',
        zh_Hans: '超时时间 (毫秒)',
      },
      description: {
        en_US: 'Maximum execution time in milliseconds',
        zh_Hans: '最大执行时间（毫秒）',
      },
      required: false,
      default: 5000,
    },
  ],
  defaultConfig: {
    language: 'javascript',
    code: '// Access input with: input\n// Return result with: return result;\n\nreturn input;',
    timeout: 5000,
  },
};

/**
 * Data Aggregator Node
 * Aggregates data from multiple inputs
 */
export const dataAggregatorConfig: NodeConfigMeta = {
  nodeType: 'data_aggregator',
  label: {
    en_US: 'Data Aggregator',
    zh_Hans: '数据聚合',
  },
  description: {
    en_US: 'Aggregate and combine data from multiple sources',
    zh_Hans: '聚合和组合来自多个来源的数据',
  },
  icon: 'Layers',
  category: 'process',
  color: '#3b82f6',
  inputs: [
    createInput('items', 'array', {
      description: 'Array of items to aggregate',
      label: { en_US: 'Items', zh_Hans: '项目' },
    }),
  ],
  outputs: [
    createOutput('result', 'any', {
      description: 'Aggregated result',
      label: { en_US: 'Result', zh_Hans: '结果' },
    }),
    createOutput('count', 'number', {
      description: 'Number of items aggregated',
      label: { en_US: 'Count', zh_Hans: '数量' },
    }),
  ],
  configSchema: [
    {
      id: 'aggregation_type',
      name: 'aggregation_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Aggregation Type',
        zh_Hans: '聚合类型',
      },
      description: {
        en_US: 'How to aggregate the data',
        zh_Hans: '如何聚合数据',
      },
      required: true,
      default: 'array',
      options: [
        { name: 'array', label: { en_US: 'Collect to Array', zh_Hans: '收集为数组' } },
        { name: 'concat', label: { en_US: 'Concatenate Strings', zh_Hans: '连接字符串' } },
        { name: 'sum', label: { en_US: 'Sum Numbers', zh_Hans: '求和' } },
        { name: 'average', label: { en_US: 'Average Numbers', zh_Hans: '求平均' } },
        { name: 'min', label: { en_US: 'Minimum', zh_Hans: '最小值' } },
        { name: 'max', label: { en_US: 'Maximum', zh_Hans: '最大值' } },
        { name: 'merge', label: { en_US: 'Merge Objects', zh_Hans: '合并对象' } },
        { name: 'first', label: { en_US: 'First Item', zh_Hans: '第一项' } },
        { name: 'last', label: { en_US: 'Last Item', zh_Hans: '最后一项' } },
      ],
    },
    {
      id: 'separator',
      name: 'separator',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Separator',
        zh_Hans: '分隔符',
      },
      description: {
        en_US: 'Separator for string concatenation',
        zh_Hans: '字符串连接的分隔符',
      },
      required: false,
      default: '\n',
      show_if: {
        field: 'aggregation_type',
        operator: 'eq',
        value: 'concat',
      },
    },
    {
      id: 'field_path',
      name: 'field_path',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Field Path',
        zh_Hans: '字段路径',
      },
      description: {
        en_US: 'Path to the field to aggregate (for objects)',
        zh_Hans: '要聚合的字段路径（用于对象）',
      },
      required: false,
      default: '',
    },
  ],
  defaultConfig: {
    aggregation_type: 'array',
    separator: '\n',
    field_path: '',
  },
};

/**
 * Text Splitter Node
 * Splits text into chunks
 */
export const textSplitterConfig: NodeConfigMeta = {
  nodeType: 'text_splitter',
  label: {
    en_US: 'Text Splitter',
    zh_Hans: '文本分割',
  },
  description: {
    en_US: 'Split text into smaller chunks',
    zh_Hans: '将文本分割成较小的块',
  },
  icon: 'Scissors',
  category: 'process',
  color: '#3b82f6',
  inputs: [
    createInput('text', 'string', {
      description: 'Text to split',
      label: { en_US: 'Text', zh_Hans: '文本' },
    }),
  ],
  outputs: [
    createOutput('chunks', 'array', {
      description: 'Array of text chunks',
      label: { en_US: 'Chunks', zh_Hans: '块' },
    }),
    createOutput('count', 'number', {
      description: 'Number of chunks',
      label: { en_US: 'Count', zh_Hans: '数量' },
    }),
  ],
  configSchema: [
    {
      id: 'split_type',
      name: 'split_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Split Type',
        zh_Hans: '分割类型',
      },
      description: {
        en_US: 'How to split the text',
        zh_Hans: '如何分割文本',
      },
      required: true,
      default: 'separator',
      options: [
        { name: 'separator', label: { en_US: 'By Separator', zh_Hans: '按分隔符' } },
        { name: 'length', label: { en_US: 'By Length', zh_Hans: '按长度' } },
        { name: 'sentences', label: { en_US: 'By Sentences', zh_Hans: '按句子' } },
        { name: 'paragraphs', label: { en_US: 'By Paragraphs', zh_Hans: '按段落' } },
        { name: 'regex', label: { en_US: 'By Regex', zh_Hans: '按正则表达式' } },
      ],
    },
    {
      id: 'separator',
      name: 'separator',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Separator',
        zh_Hans: '分隔符',
      },
      description: {
        en_US: 'String to split on',
        zh_Hans: '用于分割的字符串',
      },
      required: false,
      default: '\n',
      show_if: {
        field: 'split_type',
        operator: 'eq',
        value: 'separator',
      },
    },
    {
      id: 'chunk_size',
      name: 'chunk_size',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Chunk Size',
        zh_Hans: '块大小',
      },
      description: {
        en_US: 'Maximum characters per chunk',
        zh_Hans: '每块的最大字符数',
      },
      required: false,
      default: 1000,
      show_if: {
        field: 'split_type',
        operator: 'eq',
        value: 'length',
      },
    },
    {
      id: 'chunk_overlap',
      name: 'chunk_overlap',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Chunk Overlap',
        zh_Hans: '块重叠',
      },
      description: {
        en_US: 'Number of characters to overlap between chunks',
        zh_Hans: '块之间重叠的字符数',
      },
      required: false,
      default: 100,
      show_if: {
        field: 'split_type',
        operator: 'eq',
        value: 'length',
      },
    },
    {
      id: 'regex_pattern',
      name: 'regex_pattern',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Regex Pattern',
        zh_Hans: '正则表达式模式',
      },
      description: {
        en_US: 'Regular expression pattern to split on',
        zh_Hans: '用于分割的正则表达式模式',
      },
      required: false,
      default: '',
      show_if: {
        field: 'split_type',
        operator: 'eq',
        value: 'regex',
      },
    },
    {
      id: 'remove_empty',
      name: 'remove_empty',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Remove Empty',
        zh_Hans: '移除空块',
      },
      description: {
        en_US: 'Remove empty chunks from result',
        zh_Hans: '从结果中移除空块',
      },
      required: false,
      default: true,
    },
  ],
  defaultConfig: {
    split_type: 'separator',
    separator: '\n',
    chunk_size: 1000,
    chunk_overlap: 100,
    regex_pattern: '',
    remove_empty: true,
  },
};

/**
 * Variable Assignment Node
 * Assigns values to workflow variables
 */
export const variableAssignmentConfig: NodeConfigMeta = {
  nodeType: 'variable_assignment',
  label: {
    en_US: 'Variable Assignment',
    zh_Hans: '变量赋值',
  },
  description: {
    en_US: 'Assign values to workflow variables',
    zh_Hans: '为工作流变量赋值',
  },
  icon: 'Variable',
  category: 'process',
  color: '#3b82f6',
  inputs: [
    createInput('value', 'any', {
      description: 'Value to assign',
      label: { en_US: 'Value', zh_Hans: '值' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('output', 'any', {
      description: 'The assigned value',
      label: { en_US: 'Output', zh_Hans: '输出' },
    }),
  ],
  configSchema: [
    {
      id: 'variable_name',
      name: 'variable_name',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Variable Name',
        zh_Hans: '变量名',
      },
      description: {
        en_US: 'Name of the variable to assign',
        zh_Hans: '要赋值的变量名',
      },
      required: true,
      default: '',
    },
    {
      id: 'value_type',
      name: 'value_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Value Type',
        zh_Hans: '值类型',
      },
      description: {
        en_US: 'Type of value to assign',
        zh_Hans: '要赋的值类型',
      },
      required: true,
      default: 'input',
      options: [
        { name: 'input', label: { en_US: 'From Input', zh_Hans: '来自输入' } },
        { name: 'static', label: { en_US: 'Static Value', zh_Hans: '静态值' } },
        { name: 'expression', label: { en_US: 'Expression', zh_Hans: '表达式' } },
      ],
    },
    {
      id: 'static_value',
      name: 'static_value',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Static Value',
        zh_Hans: '静态值',
      },
      description: {
        en_US: 'Value to assign (as JSON)',
        zh_Hans: '要赋的值（JSON 格式）',
      },
      required: false,
      default: '',
      show_if: {
        field: 'value_type',
        operator: 'eq',
        value: 'static',
      },
    },
    {
      id: 'expression',
      name: 'expression',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Expression',
        zh_Hans: '表达式',
      },
      description: {
        en_US: 'Expression to evaluate (e.g., {{input}} + 1)',
        zh_Hans: '要计算的表达式（例如 {{input}} + 1）',
      },
      required: false,
      default: '',
      show_if: {
        field: 'value_type',
        operator: 'eq',
        value: 'expression',
      },
    },
  ],
  defaultConfig: {
    variable_name: '',
    value_type: 'input',
    static_value: '',
    expression: '',
  },
};

/**
 * Data Transform Node
 * Transform and extract data using templates or JSONPath
 */
export const dataTransformConfig: NodeConfigMeta = {
  nodeType: 'data_transform',
  label: {
    en_US: 'Data Transform',
    zh_Hans: '数据转换',
  },
  description: {
    en_US: 'Transform and extract data using templates or JSONPath',
    zh_Hans: '使用模板或 JSONPath 转换和提取数据',
  },
  icon: 'RefreshCw',
  category: 'process',
  color: '#3b82f6',
  inputs: [
    createInput('data', 'any', {
      description: 'Input data',
      label: { en_US: 'Data', zh_Hans: '数据' },
      required: true,
    }),
  ],
  outputs: [
    createOutput('result', 'any', {
      description: 'Transform result',
      label: { en_US: 'Result', zh_Hans: '结果' },
    }),
  ],
  configSchema: [
    {
      id: 'transform_type',
      name: 'transform_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Transform Type',
        zh_Hans: '转换类型',
      },
      description: {
        en_US: 'Type of transformation to perform',
        zh_Hans: '要执行的转换类型',
      },
      required: true,
      default: 'template',
      options: [
        { name: 'template', label: { en_US: 'Template', zh_Hans: '模板' } },
        { name: 'jsonpath', label: { en_US: 'JSONPath', zh_Hans: 'JSONPath' } },
        { name: 'jmespath', label: { en_US: 'JMESPath', zh_Hans: 'JMESPath' } },
        { name: 'expression', label: { en_US: 'Expression', zh_Hans: '表达式' } },
      ],
    },
    {
      id: 'template',
      name: 'template',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Template',
        zh_Hans: '模板',
      },
      description: {
        en_US: 'Template with {{variable}} syntax',
        zh_Hans: '支持 {{variable}} 语法的模板',
      },
      required: false,
      default: '',
      show_if: {
        field: 'transform_type',
        operator: 'eq',
        value: 'template',
      },
    },
    {
      id: 'expression',
      name: 'expression',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Expression',
        zh_Hans: '表达式',
      },
      description: {
        en_US: 'JSONPath/JMESPath expression',
        zh_Hans: 'JSONPath/JMESPath 表达式',
      },
      required: false,
      default: '',
      show_if: {
        field: 'transform_type',
        operator: 'in',
        value: ['jsonpath', 'jmespath', 'expression'],
      },
    },
  ],
  defaultConfig: {
    transform_type: 'template',
    template: '',
    expression: '',
  },
};

/**
 * All process node configurations
 */
export const processConfigs: NodeConfigMeta[] = [
  textTemplateConfig,
  jsonTransformConfig,
  codeExecutorConfig,
  dataAggregatorConfig,
  textSplitterConfig,
  variableAssignmentConfig,
  dataTransformConfig,
];

/**
 * Get process config by type
 */
export function getProcessConfig(nodeType: string): NodeConfigMeta | undefined {
  return processConfigs.find((config) => config.nodeType === nodeType);
}
