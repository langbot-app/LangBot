/**
 * Control Node Configurations
 *
 * Defines configurations for flow control node types:
 * - condition: Conditional branching
 * - switch_case: Multi-way branching
 * - loop: Loop/iteration
 * - parallel: Parallel execution
 * - wait: Wait/delay
 * - end: End workflow
 */

import { DynamicFormItemType } from '@/app/infra/entities/form/dynamic';
import { NodeConfigMeta, createInput, createOutput } from './types';

/**
 * Condition Node
 * Conditional branching based on expression
 */
export const conditionConfig: NodeConfigMeta = {
  nodeType: 'condition',
  label: {
    en_US: 'Condition',
    zh_Hans: '条件分支',
  },
  description: {
    en_US: 'Branch workflow based on a condition',
    zh_Hans: '根据条件分支工作流',
  },
  icon: 'GitBranch',
  category: 'control',
  color: '#8b5cf6',
  inputs: [
    createInput('input', 'any', {
      description: 'Input data for condition evaluation',
      label: { en_US: 'Input', zh_Hans: '输入' },
    }),
  ],
  outputs: [
    createOutput('true', 'any', {
      description: 'Output when condition is true',
      label: { en_US: 'True', zh_Hans: '真' },
    }),
    createOutput('false', 'any', {
      description: 'Output when condition is false',
      label: { en_US: 'False', zh_Hans: '假' },
    }),
  ],
  configSchema: [
    {
      id: 'condition_type',
      name: 'condition_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Condition Type',
        zh_Hans: '条件类型',
      },
      description: {
        en_US: 'Type of condition to evaluate',
        zh_Hans: '要评估的条件类型',
      },
      required: true,
      default: 'expression',
      options: [
        {
          name: 'expression',
          label: { en_US: 'Expression', zh_Hans: '表达式' },
        },
        { name: 'comparison', label: { en_US: 'Comparison', zh_Hans: '比较' } },
        { name: 'exists', label: { en_US: 'Value Exists', zh_Hans: '值存在' } },
        {
          name: 'type_check',
          label: { en_US: 'Type Check', zh_Hans: '类型检查' },
        },
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
        en_US: 'JavaScript expression that evaluates to true/false',
        zh_Hans: '评估为 true/false 的 JavaScript 表达式',
      },
      required: true,
      default: '',
      show_if: {
        field: 'condition_type',
        operator: 'eq',
        value: 'expression',
      },
    },
    {
      id: 'left_value',
      name: 'left_value',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Left Value',
        zh_Hans: '左值',
      },
      description: {
        en_US: 'Left side of comparison (supports variable references)',
        zh_Hans: '比较的左侧（支持变量引用）',
      },
      required: true,
      default: '{{input}}',
      show_if: {
        field: 'condition_type',
        operator: 'in',
        value: ['comparison', 'exists', 'type_check'],
      },
    },
    {
      id: 'operator',
      name: 'operator',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Operator',
        zh_Hans: '运算符',
      },
      description: {
        en_US: 'Comparison operator',
        zh_Hans: '比较运算符',
      },
      required: true,
      default: 'eq',
      options: [
        { name: 'eq', label: { en_US: 'Equals (==)', zh_Hans: '等于 (==)' } },
        {
          name: 'neq',
          label: { en_US: 'Not Equals (!=)', zh_Hans: '不等于 (!=)' },
        },
        {
          name: 'gt',
          label: { en_US: 'Greater Than (>)', zh_Hans: '大于 (>)' },
        },
        {
          name: 'gte',
          label: { en_US: 'Greater or Equal (>=)', zh_Hans: '大于等于 (>=)' },
        },
        { name: 'lt', label: { en_US: 'Less Than (<)', zh_Hans: '小于 (<)' } },
        {
          name: 'lte',
          label: { en_US: 'Less or Equal (<=)', zh_Hans: '小于等于 (<=)' },
        },
        { name: 'contains', label: { en_US: 'Contains', zh_Hans: '包含' } },
        {
          name: 'starts_with',
          label: { en_US: 'Starts With', zh_Hans: '以...开头' },
        },
        {
          name: 'ends_with',
          label: { en_US: 'Ends With', zh_Hans: '以...结尾' },
        },
        {
          name: 'matches',
          label: { en_US: 'Matches Regex', zh_Hans: '匹配正则' },
        },
      ],
      show_if: {
        field: 'condition_type',
        operator: 'eq',
        value: 'comparison',
      },
    },
    {
      id: 'right_value',
      name: 'right_value',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Right Value',
        zh_Hans: '右值',
      },
      description: {
        en_US: 'Right side of comparison',
        zh_Hans: '比较的右侧',
      },
      required: true,
      default: '',
      show_if: {
        field: 'condition_type',
        operator: 'eq',
        value: 'comparison',
      },
    },
    {
      id: 'expected_type',
      name: 'expected_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Expected Type',
        zh_Hans: '期望类型',
      },
      description: {
        en_US: 'The type to check for',
        zh_Hans: '要检查的类型',
      },
      required: true,
      default: 'string',
      options: [
        { name: 'string', label: { en_US: 'String', zh_Hans: '字符串' } },
        { name: 'number', label: { en_US: 'Number', zh_Hans: '数字' } },
        { name: 'boolean', label: { en_US: 'Boolean', zh_Hans: '布尔' } },
        { name: 'object', label: { en_US: 'Object', zh_Hans: '对象' } },
        { name: 'array', label: { en_US: 'Array', zh_Hans: '数组' } },
        { name: 'null', label: { en_US: 'Null', zh_Hans: '空' } },
      ],
      show_if: {
        field: 'condition_type',
        operator: 'eq',
        value: 'type_check',
      },
    },
  ],
  defaultConfig: {
    condition_type: 'expression',
    expression: '',
    left_value: '{{input}}',
    operator: 'eq',
    right_value: '',
    expected_type: 'string',
  },
};

/**
 * Switch Case Node
 * Multi-way branching based on value
 */
export const switchCaseConfig: NodeConfigMeta = {
  nodeType: 'switch_case',
  label: {
    en_US: 'Switch',
    zh_Hans: '多路分支',
  },
  description: {
    en_US: 'Branch workflow based on multiple cases',
    zh_Hans: '根据多个条件分支工作流',
  },
  icon: 'GitFork',
  category: 'control',
  color: '#8b5cf6',
  inputs: [
    createInput('input', 'any', {
      description: 'Value to switch on',
      label: { en_US: 'Input', zh_Hans: '输入' },
    }),
  ],
  outputs: [
    createOutput('case_1', 'any', {
      description: 'Branch 1 output',
      label: { en_US: 'Branch 1', zh_Hans: '分支 1' },
    }),
    createOutput('case_2', 'any', {
      description: 'Branch 2 output',
      label: { en_US: 'Branch 2', zh_Hans: '分支 2' },
    }),
    createOutput('default', 'any', {
      description: 'Default branch output',
      label: { en_US: 'Default Branch', zh_Hans: '默认分支' },
    }),
  ],
  configSchema: [
    {
      id: 'switch_expression',
      name: 'switch_expression',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Switch Expression',
        zh_Hans: '开关表达式',
      },
      description: {
        en_US: 'Expression to evaluate for switching (e.g., {{input.type}})',
        zh_Hans: '用于切换的表达式（例如 {{input.type}}）',
      },
      required: true,
      default: '{{input}}',
    },
    {
      id: 'cases',
      name: 'cases',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Cases',
        zh_Hans: '情况',
      },
      description: {
        en_US:
          'Define cases as JSON array: [{"name": "case_1", "value": "value1"}, {"name": "case_2", "values": ["v1", "v2"]}]',
        zh_Hans:
          '使用 JSON 数组定义情况: [{"name": "case_1", "value": "value1"}, {"name": "case_2", "values": ["v1", "v2"]}]',
      },
      required: true,
      default:
        '[{"name": "case_1", "value": ""}, {"name": "case_2", "value": ""}]',
    },
    {
      id: 'case_sensitive',
      name: 'case_sensitive',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Case Sensitive',
        zh_Hans: '区分大小写',
      },
      description: {
        en_US: 'Whether string comparisons are case-sensitive',
        zh_Hans: '字符串比较是否区分大小写',
      },
      required: false,
      default: true,
    },
  ],
  defaultConfig: {
    switch_expression: '{{input}}',
    cases: '[{"name": "case_1", "value": ""}, {"name": "case_2", "value": ""}]',
    case_sensitive: true,
  },
};

/**
 * Loop Node
 * Iterates over items or until condition
 */
export const loopConfig: NodeConfigMeta = {
  nodeType: 'loop',
  label: {
    en_US: 'Loop',
    zh_Hans: '循环',
  },
  description: {
    en_US: 'Iterate over items or repeat until condition',
    zh_Hans: '遍历项目或重复直到满足条件',
  },
  icon: 'Repeat',
  category: 'control',
  color: '#8b5cf6',
  inputs: [
    createInput('items', 'array', {
      description: 'Items to iterate over (for each loop)',
      label: { en_US: 'Items', zh_Hans: '项目' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('item', 'any', {
      description: 'Current item in iteration',
      label: { en_US: 'Item', zh_Hans: '当前项' },
    }),
    createOutput('index', 'number', {
      description: 'Current iteration index',
      label: { en_US: 'Index', zh_Hans: '索引' },
    }),
    createOutput('completed', 'any', {
      description: 'Output after loop completes',
      label: { en_US: 'Completed', zh_Hans: '完成' },
    }),
  ],
  configSchema: [
    {
      id: 'loop_type',
      name: 'loop_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Loop Type',
        zh_Hans: '循环类型',
      },
      description: {
        en_US: 'Type of loop to execute',
        zh_Hans: '要执行的循环类型',
      },
      required: true,
      default: 'foreach',
      options: [
        { name: 'foreach', label: { en_US: 'For Each', zh_Hans: '逐项遍历' } },
        { name: 'while', label: { en_US: 'While', zh_Hans: '条件循环' } },
        { name: 'count', label: { en_US: 'Count', zh_Hans: '计数' } },
      ],
    },
    {
      id: 'max_iterations',
      name: 'max_iterations',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Max Iterations',
        zh_Hans: '最大迭代次数',
      },
      description: {
        en_US: 'Maximum number of iterations (safety limit)',
        zh_Hans: '最大迭代次数（安全限制）',
      },
      required: false,
      default: 100,
    },
    {
      id: 'count',
      name: 'count',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Count',
        zh_Hans: '计数',
      },
      description: {
        en_US: 'Number of times to iterate',
        zh_Hans: '迭代次数',
      },
      required: true,
      default: 10,
      show_if: {
        field: 'loop_type',
        operator: 'eq',
        value: 'count',
      },
    },
    {
      id: 'while_condition',
      name: 'while_condition',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'While Condition',
        zh_Hans: 'While 条件',
      },
      description: {
        en_US: 'Condition expression to continue looping',
        zh_Hans: '继续循环的条件表达式',
      },
      required: true,
      default: '',
      show_if: {
        field: 'loop_type',
        operator: 'eq',
        value: 'while',
      },
    },
    {
      id: 'parallel',
      name: 'parallel',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Parallel Execution',
        zh_Hans: '并行执行',
      },
      description: {
        en_US: 'Execute iterations in parallel',
        zh_Hans: '并行执行迭代',
      },
      required: false,
      default: false,
      show_if: {
        field: 'loop_type',
        operator: 'eq',
        value: 'foreach',
      },
    },
    {
      id: 'parallel_limit',
      name: 'parallel_limit',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Parallel Limit',
        zh_Hans: '并行限制',
      },
      description: {
        en_US: 'Maximum number of parallel executions',
        zh_Hans: '最大并行执行数',
      },
      required: false,
      default: 5,
      show_if: {
        field: 'parallel',
        operator: 'eq',
        value: true,
      },
    },
  ],
  defaultConfig: {
    loop_type: 'foreach',
    max_iterations: 100,
    count: 10,
    while_condition: '',
    parallel: false,
    parallel_limit: 5,
  },
};

/**
 * Parallel Node
 * Execute multiple branches in parallel
 */
export const parallelConfig: NodeConfigMeta = {
  nodeType: 'parallel',
  label: {
    en_US: 'Parallel',
    zh_Hans: '并行执行',
  },
  description: {
    en_US: 'Execute multiple branches in parallel',
    zh_Hans: '并行执行多个分支',
  },
  icon: 'GitMerge',
  category: 'control',
  color: '#8b5cf6',
  inputs: [
    createInput('input', 'any', {
      description: 'Input data for all branches',
      label: { en_US: 'Input', zh_Hans: '输入' },
    }),
  ],
  outputs: [
    createOutput('branch_1', 'any', {
      description: 'Branch 1 output',
      label: { en_US: 'Branch 1', zh_Hans: '分支 1' },
    }),
    createOutput('branch_2', 'any', {
      description: 'Branch 2 output',
      label: { en_US: 'Branch 2', zh_Hans: '分支 2' },
    }),
    createOutput('results', 'object', {
      description: 'Combined results from all branches',
      label: { en_US: 'Results', zh_Hans: '结果' },
    }),
  ],
  configSchema: [
    {
      id: 'branches',
      name: 'branches',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Branches',
        zh_Hans: '分支',
      },
      description: {
        en_US:
          'Define branches as JSON array: [{"name": "branch_1"}, {"name": "branch_2"}]',
        zh_Hans:
          '使用 JSON 数组定义分支: [{"name": "branch_1"}, {"name": "branch_2"}]',
      },
      required: true,
      default: '[{"name": "branch_1"}, {"name": "branch_2"}]',
    },
    {
      id: 'wait_for_all',
      name: 'wait_for_all',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Wait for All',
        zh_Hans: '等待全部完成',
      },
      description: {
        en_US: 'Wait for all branches to complete before continuing',
        zh_Hans: '等待所有分支完成后再继续',
      },
      required: false,
      default: true,
    },
    {
      id: 'fail_fast',
      name: 'fail_fast',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Fail Fast',
        zh_Hans: '快速失败',
      },
      description: {
        en_US: 'Stop all branches if any one fails',
        zh_Hans: '如果任何一个分支失败则停止所有分支',
      },
      required: false,
      default: false,
    },
  ],
  defaultConfig: {
    branches: '[{"name": "branch_1"}, {"name": "branch_2"}]',
    wait_for_all: true,
    fail_fast: false,
  },
};

/**
 * Wait Node
 * Pause workflow execution
 */
export const waitConfig: NodeConfigMeta = {
  nodeType: 'wait',
  label: {
    en_US: 'Wait',
    zh_Hans: '等待',
  },
  description: {
    en_US: 'Pause workflow execution for a specified duration or condition',
    zh_Hans: '暂停工作流执行指定的时间或等待条件满足',
  },
  icon: 'Clock',
  category: 'control',
  color: '#8b5cf6',
  inputs: [
    createInput('input', 'any', {
      description: 'Input to pass through',
      label: { en_US: 'Input', zh_Hans: '输入' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('output', 'any', {
      description: 'Passed through input',
      label: { en_US: 'Output', zh_Hans: '输出' },
    }),
  ],
  configSchema: [
    {
      id: 'wait_type',
      name: 'wait_type',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Wait Type',
        zh_Hans: '等待类型',
      },
      description: {
        en_US: 'Type of wait operation',
        zh_Hans: '等待操作的类型',
      },
      required: true,
      default: 'duration',
      options: [
        { name: 'duration', label: { en_US: 'Duration', zh_Hans: '时长' } },
        { name: 'until', label: { en_US: 'Until Time', zh_Hans: '直到时间' } },
      ],
    },
    {
      id: 'duration',
      name: 'duration',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Duration (seconds)',
        zh_Hans: '时长（秒）',
      },
      description: {
        en_US: 'Number of seconds to wait',
        zh_Hans: '等待的秒数',
      },
      required: true,
      default: 5,
      show_if: {
        field: 'wait_type',
        operator: 'eq',
        value: 'duration',
      },
    },
    {
      id: 'until_time',
      name: 'until_time',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Until Time',
        zh_Hans: '直到时间',
      },
      description: {
        en_US: 'Wait until this time (ISO 8601 format or expression)',
        zh_Hans: '等待直到此时间（ISO 8601 格式或表达式）',
      },
      required: true,
      default: '',
      show_if: {
        field: 'wait_type',
        operator: 'eq',
        value: 'until',
      },
    },
  ],
  defaultConfig: {
    wait_type: 'duration',
    duration: 5,
    until_time: '',
  },
};

/**
 * End Node
 * Terminates workflow execution
 */
export const endConfig: NodeConfigMeta = {
  nodeType: 'end',
  label: {
    en_US: 'End',
    zh_Hans: '结束',
  },
  description: {
    en_US: 'End the workflow execution',
    zh_Hans: '结束工作流执行',
  },
  icon: 'CircleStop',
  category: 'control',
  color: '#8b5cf6',
  inputs: [
    createInput('input', 'any', {
      description: 'Final output data',
      label: { en_US: 'Input', zh_Hans: '输入' },
      required: false,
    }),
  ],
  outputs: [],
  configSchema: [
    {
      id: 'status',
      name: 'status',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'End Status',
        zh_Hans: '结束状态',
      },
      description: {
        en_US: 'Status to report when workflow ends',
        zh_Hans: '工作流结束时报告的状态',
      },
      required: true,
      default: 'success',
      options: [
        { name: 'success', label: { en_US: 'Success', zh_Hans: '成功' } },
        { name: 'failed', label: { en_US: 'Failed', zh_Hans: '失败' } },
        { name: 'cancelled', label: { en_US: 'Cancelled', zh_Hans: '取消' } },
      ],
    },
    {
      id: 'message',
      name: 'message',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Message',
        zh_Hans: '消息',
      },
      description: {
        en_US: 'Optional message to include with the end status',
        zh_Hans: '与结束状态一起包含的可选消息',
      },
      required: false,
      default: '',
    },
  ],
  defaultConfig: {
    status: 'success',
    message: '',
  },
};

/**
 * Iterator Node
 * Iterates over array items one by one
 */
export const iteratorConfig: NodeConfigMeta = {
  nodeType: 'iterator',
  label: {
    en_US: 'Iterator',
    zh_Hans: '迭代器',
  },
  description: {
    en_US: 'Iterate over array elements one by one',
    zh_Hans: '逐个遍历数组元素',
  },
  icon: 'Repeat',
  category: 'control',
  color: '#8b5cf6',
  inputs: [
    createInput('items', 'array', {
      description: 'Array to iterate over',
      label: { en_US: 'Items', zh_Hans: '项目' },
    }),
  ],
  outputs: [
    createOutput('item', 'any', {
      description: 'Current item',
      label: { en_US: 'Item', zh_Hans: '当前项' },
    }),
    createOutput('index', 'number', {
      description: 'Current index',
      label: { en_US: 'Index', zh_Hans: '索引' },
    }),
    createOutput('is_first', 'boolean', {
      description: 'Whether this is the first item',
      label: { en_US: 'Is First', zh_Hans: '是否第一个' },
    }),
    createOutput('is_last', 'boolean', {
      description: 'Whether this is the last item',
      label: { en_US: 'Is Last', zh_Hans: '是否最后一个' },
    }),
    createOutput('completed', 'any', {
      description: 'Output after iteration completes',
      label: { en_US: 'Completed', zh_Hans: '完成' },
    }),
  ],
  configSchema: [
    {
      id: 'parallel',
      name: 'parallel',
      type: DynamicFormItemType.BOOLEAN,
      label: { en_US: 'Parallel Processing', zh_Hans: '并行处理' },
      description: {
        en_US: 'Process items in parallel',
        zh_Hans: '并行处理项目',
      },
      required: false,
      default: false,
    },
    {
      id: 'max_concurrency',
      name: 'max_concurrency',
      type: DynamicFormItemType.INT,
      label: { en_US: 'Max Concurrency', zh_Hans: '最大并发数' },
      description: {
        en_US: 'Maximum number of concurrent iterations',
        zh_Hans: '最大并发迭代数',
      },
      required: false,
      default: 5,
      show_if: { field: 'parallel', operator: 'eq', value: true },
    },
    {
      id: 'max_iterations',
      name: 'max_iterations',
      type: DynamicFormItemType.INT,
      label: { en_US: 'Max Iterations', zh_Hans: '最大迭代次数' },
      description: {
        en_US: 'Safety limit on iterations',
        zh_Hans: '迭代次数安全限制',
      },
      required: false,
      default: 1000,
    },
  ],
  defaultConfig: { parallel: false, max_concurrency: 5, max_iterations: 1000 },
};

/**
 * Merge Node
 * Merges multiple branches back together
 */
export const mergeConfig: NodeConfigMeta = {
  nodeType: 'merge',
  label: {
    en_US: 'Merge',
    zh_Hans: '合并',
  },
  description: {
    en_US: 'Merge multiple branches back together',
    zh_Hans: '将多个分支合并在一起',
  },
  icon: 'GitMerge',
  category: 'control',
  color: '#8b5cf6',
  inputs: [
    createInput('branch_1', 'any', {
      description: 'Input from branch 1',
      label: { en_US: 'Branch 1', zh_Hans: '分支 1' },
      required: false,
    }),
    createInput('branch_2', 'any', {
      description: 'Input from branch 2',
      label: { en_US: 'Branch 2', zh_Hans: '分支 2' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('output', 'any', {
      description: 'Merged output',
      label: { en_US: 'Output', zh_Hans: '输出' },
    }),
  ],
  configSchema: [
    {
      id: 'merge_strategy',
      name: 'merge_strategy',
      type: DynamicFormItemType.SELECT,
      label: { en_US: 'Merge Strategy', zh_Hans: '合并策略' },
      description: {
        en_US: 'How to merge inputs from branches',
        zh_Hans: '如何合并分支输入',
      },
      required: true,
      default: 'wait_all',
      options: [
        {
          name: 'wait_all',
          label: { en_US: 'Wait for All', zh_Hans: '等待全部' },
        },
        {
          name: 'first_completed',
          label: { en_US: 'First Completed', zh_Hans: '第一个完成' },
        },
        {
          name: 'combine',
          label: { en_US: 'Combine to Object', zh_Hans: '合并为对象' },
        },
        {
          name: 'array',
          label: { en_US: 'Collect to Array', zh_Hans: '收集为数组' },
        },
      ],
    },
  ],
  defaultConfig: { merge_strategy: 'wait_all' },
};

/**
 * Variable Aggregator Node
 * Aggregates variable outputs from multiple branches
 */
export const variableAggregatorConfig: NodeConfigMeta = {
  nodeType: 'variable_aggregator',
  label: {
    en_US: 'Variable Aggregator',
    zh_Hans: '变量聚合器',
  },
  description: {
    en_US: 'Aggregate variable outputs from multiple branches',
    zh_Hans: '聚合多个分支的变量输出',
  },
  icon: 'GitMerge',
  category: 'control',
  color: '#8b5cf6',
  inputs: [
    createInput('input', 'any', {
      description: 'Input data',
      label: { en_US: 'Input', zh_Hans: '输入' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('output', 'any', {
      description: 'Aggregated output',
      label: { en_US: 'Output', zh_Hans: '输出' },
    }),
  ],
  configSchema: [
    {
      id: 'variable_mappings',
      name: 'variable_mappings',
      type: DynamicFormItemType.TEXT,
      label: { en_US: 'Variable Mappings', zh_Hans: '变量映射' },
      description: {
        en_US:
          'JSON mapping of output variables: {"out_key": "{{nodes.xxx.value}}"}',
        zh_Hans: 'JSON 格式的输出变量映射: {"out_key": "{{nodes.xxx.value}}"}',
      },
      required: true,
      default: '{}',
    },
    {
      id: 'aggregation_mode',
      name: 'aggregation_mode',
      type: DynamicFormItemType.SELECT,
      label: { en_US: 'Aggregation Mode', zh_Hans: '聚合模式' },
      description: {
        en_US: 'How to aggregate the variables',
        zh_Hans: '如何聚合变量',
      },
      required: true,
      default: 'merge',
      options: [
        {
          name: 'merge',
          label: { en_US: 'Merge Objects', zh_Hans: '合并对象' },
        },
        {
          name: 'array',
          label: { en_US: 'Collect to Array', zh_Hans: '收集为数组' },
        },
        {
          name: 'first',
          label: { en_US: 'First Non-null', zh_Hans: '第一个非空' },
        },
      ],
    },
  ],
  defaultConfig: { variable_mappings: '{}', aggregation_mode: 'merge' },
};

/**
 * All control node configurations
 */
export const controlConfigs: NodeConfigMeta[] = [
  conditionConfig,
  switchCaseConfig,
  loopConfig,
  iteratorConfig,
  parallelConfig,
  waitConfig,
  mergeConfig,
  variableAggregatorConfig,
  endConfig,
];

/**
 * Get control config by type
 */
export function getControlConfig(nodeType: string): NodeConfigMeta | undefined {
  return controlConfigs.find((config) => config.nodeType === nodeType);
}
