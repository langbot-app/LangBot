import type {
  WorkflowNodeTypeMetadata,
  WorkflowPortDefinition,
} from '@/app/infra/entities/api';
import type { I18nObject } from '@/app/infra/entities/common';
import { getNodeConfig, type NodeConfigMeta } from './node-configs';

export const WORKFLOW_NODE_CATEGORIES = [
  'trigger',
  'process',
  'control',
  'action',
  'integration',
] as const;

const DEFAULT_INPUT_PORT: WorkflowPortDefinition = {
  name: 'input',
  type: 'any',
  label: 'workflows.nodeInputs.input',
};

const DEFAULT_OUTPUT_PORT: WorkflowPortDefinition = {
  name: 'output',
  type: 'any',
  label: 'workflows.nodeOutputs.output',
};

function ensurePortLabelKey(
  prefix: 'workflows.nodeInputs' | 'workflows.nodeOutputs',
  portName: string,
  label?: string | Record<string, string>,
): string {
  const key = `${prefix}.${portName}`;

  if (typeof label === 'string') {
    return label.startsWith(prefix) ? label : key;
  }

  if (label && typeof label === 'object') {
    const existing = Object.values(label).find(
      (value) => typeof value === 'string' && value.startsWith(prefix),
    );
    if (existing) return existing;
  }

  return key;
}

function normalizePort(
  prefix: 'workflows.nodeInputs' | 'workflows.nodeOutputs',
  port: WorkflowPortDefinition,
): WorkflowPortDefinition {
  return {
    ...port,
    label: ensurePortLabelKey(prefix, port.name, port.label),
  };
}

function toBackendI18nObject(
  value?: I18nObject,
): Record<string, string> | undefined {
  if (!value) return undefined;

  return {
    'en-US': value.en_US,
    en: value.en_US,
    'zh-Hans': value.zh_Hans,
    'zh-CN': value.zh_Hans,
  };
}

function toWorkflowPortDefinition(
  prefix: 'workflows.nodeInputs' | 'workflows.nodeOutputs',
  port: NodeConfigMeta['inputs'][number] | NodeConfigMeta['outputs'][number],
): WorkflowPortDefinition {
  return normalizePort(prefix, {
    name: port.name,
    type: port.type,
    label: `${prefix}.${port.name}`,
  });
}

function resolveNodeTypeCategory(type: string): string {
  if (type.includes('.')) {
    return type.split('.')[0];
  }
  return 'process';
}

function getLocalConfigVariants(type: string): string[] {
  const variants = new Set<string>([type]);

  if (type.includes('.')) {
    variants.add(type.split('.').slice(1).join('.'));
    variants.add(type.replace(/\./g, '_'));
  } else {
    for (const category of WORKFLOW_NODE_CATEGORIES) {
      variants.add(`${category}.${type}`);
    }
  }

  return [...variants];
}

export function getLocalNodeTypeMeta(
  type: string,
): WorkflowNodeTypeMetadata | null {
  let localConfig: NodeConfigMeta | undefined;

  for (const variant of getLocalConfigVariants(type)) {
    localConfig = getNodeConfig(variant);
    if (localConfig) break;
  }

  if (!localConfig) return null;

  return {
    type,
    category: localConfig.category,
    label: toBackendI18nObject(localConfig.label) ?? {},
    description: toBackendI18nObject(localConfig.description),
    icon: localConfig.icon,
    color: localConfig.color,
    config_schema: localConfig.configSchema,
    inputs: localConfig.inputs.map((input) =>
      toWorkflowPortDefinition('workflows.nodeInputs', input),
    ),
    outputs: localConfig.outputs.map((output) =>
      toWorkflowPortDefinition('workflows.nodeOutputs', output),
    ),
  };
}

export function normalizeWorkflowNodeTypeMeta(
  type: string,
  nodeType?: WorkflowNodeTypeMetadata | null,
): WorkflowNodeTypeMetadata {
  const localMeta = getLocalNodeTypeMeta(type);
  const category =
    nodeType?.category || localMeta?.category || resolveNodeTypeCategory(type);

  const inputs = nodeType?.inputs?.length
    ? nodeType.inputs.map((input) =>
        normalizePort('workflows.nodeInputs', input),
      )
    : localMeta?.inputs?.length
      ? localMeta.inputs
      : [DEFAULT_INPUT_PORT];

  const outputs = nodeType?.outputs?.length
    ? nodeType.outputs.map((output) =>
        normalizePort('workflows.nodeOutputs', output),
      )
    : localMeta?.outputs?.length
      ? localMeta.outputs
      : [DEFAULT_OUTPUT_PORT];

  const configSchema = nodeType?.config_schema?.length
    ? nodeType.config_schema
    : localMeta?.config_schema?.length
      ? localMeta.config_schema
      : [];

  return {
    type,
    category,
    label: nodeType?.label || localMeta?.label || {},
    description: nodeType?.description || localMeta?.description,
    icon: nodeType?.icon || localMeta?.icon,
    color: nodeType?.color || localMeta?.color,
    config_schema: configSchema,
    config_schema_source: nodeType?.config_schema_source,
    config_stages: nodeType?.config_stages,
    inputs,
    outputs,
  };
}
