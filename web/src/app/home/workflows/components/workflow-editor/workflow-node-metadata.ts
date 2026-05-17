import type {
  WorkflowNodeTypeMetadata,
  WorkflowPortDefinition,
} from '@/app/infra/entities/api';

export const WORKFLOW_NODE_CATEGORIES = [
  'trigger',
  'process',
  'control',
  'action',
  'integration',
  'misc',
] as const;

const DEFAULT_INPUT_PORT: WorkflowPortDefinition = {
  name: 'input',
  type: 'any',
  label: {
    en_US: 'Input',
    en: 'Input',
    'en-US': 'Input',
    zh_Hans: '输入',
    'zh-Hans': '输入',
    'zh-CN': '输入',
  },
};

const DEFAULT_OUTPUT_PORT: WorkflowPortDefinition = {
  name: 'output',
  type: 'any',
  label: {
    en_US: 'Output',
    en: 'Output',
    'en-US': 'Output',
    zh_Hans: '输出',
    'zh-Hans': '输出',
    'zh-CN': '输出',
  },
};

function resolveNodeTypeCategory(type: string): string {
  if (type.includes('.')) {
    return type.split('.')[0];
  }
  return 'process';
}

function normalizePort(
  port: WorkflowPortDefinition,
): WorkflowPortDefinition {
  return {
    ...port,
    type: port.type || 'any',
  };
}

export function normalizeWorkflowNodeTypeMeta(
  type: string,
  nodeType?: WorkflowNodeTypeMetadata | null,
): WorkflowNodeTypeMetadata {
  const category = nodeType?.category || resolveNodeTypeCategory(type);

  const inputs = nodeType?.inputs?.length
    ? nodeType.inputs.map(normalizePort)
    : [DEFAULT_INPUT_PORT];

  const outputs = nodeType?.outputs?.length
    ? nodeType.outputs.map(normalizePort)
    : [DEFAULT_OUTPUT_PORT];

  return {
    type,
    category,
    label: nodeType?.label || {},
    description: nodeType?.description,
    icon: nodeType?.icon,
    color: nodeType?.color,
    config_schema: nodeType?.config_schema || [],
    config_schema_source: nodeType?.config_schema_source,
    config_stages: nodeType?.config_stages,
    inputs,
    outputs,
  };
}
