/**
 * Node Configurations Index
 *
 * This module exports all node configuration metadata and provides
 * utility functions for accessing node configurations.
 */

// Types
export * from './types';

// Trigger Nodes
export {
  triggerConfigs,
  getTriggerConfig,
  messageTriggerConfig,
  cronTriggerConfig,
  webhookTriggerConfig,
  eventTriggerConfig,
} from './trigger-configs';

// AI Nodes
export {
  aiConfigs,
  getAIConfig,
  llmCallConfig,
  questionClassifierConfig,
  parameterExtractorConfig,
  knowledgeRetrievalConfig,
  textEmbeddingConfig,
  intentRecognitionConfig,
} from './ai-configs';

// Process Nodes
export {
  processConfigs,
  getProcessConfig,
  textTemplateConfig,
  jsonTransformConfig,
  codeExecutorConfig,
  dataAggregatorConfig,
  textSplitterConfig,
  variableAssignmentConfig,
  dataTransformConfig,
} from './process-configs';

// Control Nodes
export {
  controlConfigs,
  getControlConfig,
  conditionConfig,
  switchCaseConfig,
  loopConfig,
  iteratorConfig,
  parallelConfig,
  waitConfig,
  mergeConfig,
  variableAggregatorConfig,
  endConfig,
} from './control-configs';

// Action Nodes
export {
  actionConfigs,
  getActionConfig,
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
} from './action-configs';

// Integration Nodes
export {
  integrationConfigs,
  getIntegrationConfig,
  difyWorkflowConfig,
  difyKnowledgeQueryConfig,
  n8nWorkflowConfig,
  langflowFlowConfig,
  cozeBotConfig,
  databaseQueryConfig,
  redisOperationConfig,
  mcpToolConfig,
  memoryStoreConfig,
} from './integration-configs';

import { NodeConfigMeta, NodeConfigRegistry } from './types';
import { triggerConfigs } from './trigger-configs';
import { aiConfigs } from './ai-configs';
import { processConfigs } from './process-configs';
import { controlConfigs } from './control-configs';
import { actionConfigs } from './action-configs';
import { integrationConfigs } from './integration-configs';
import { NodeCategory } from '@/app/infra/entities/workflow';

/**
 * All node configurations combined
 */
export const allNodeConfigs: NodeConfigMeta[] = [
  ...triggerConfigs,
  ...aiConfigs,
  ...processConfigs,
  ...controlConfigs,
  ...actionConfigs,
  ...integrationConfigs,
];

/**
 * Node configuration registry by type
 * Registers each config under both its short name (e.g. "message_trigger")
 * and its full category-prefixed name (e.g. "trigger.message_trigger")
 * so lookups from PropertyPanel / useWorkflowStore always succeed.
 */
export const nodeConfigRegistry: NodeConfigRegistry = (() => {
  const registry: NodeConfigRegistry = {};
  for (const config of allNodeConfigs) {
    // Short name
    registry[config.nodeType] = config;
    // Full category.name
    registry[`${config.category}.${config.nodeType}`] = config;
  }
  // Aliases for nodes whose palette type differs from config nodeType
  // control.switch -> switch_case config
  if (registry['switch_case']) {
    registry['switch'] = registry['switch_case'];
    registry['control.switch'] = registry['switch_case'];
  }
  // action.end also points to the end config in control
  if (registry['end']) {
    registry['action.end'] = registry['end'];
  }
  return registry;
})();

/**
 * Get node configuration by type
 */
export function getNodeConfig(nodeType: string): NodeConfigMeta | undefined {
  return nodeConfigRegistry[nodeType];
}

/**
 * Get all node configurations for a category
 */
export function getNodeConfigsByCategory(
  category: NodeCategory,
): NodeConfigMeta[] {
  return allNodeConfigs.filter((config) => config.category === category);
}

/**
 * Get all entry point node configurations (trigger nodes)
 */
export function getEntryPointConfigs(): NodeConfigMeta[] {
  return allNodeConfigs.filter((config) => config.isEntryPoint);
}

/**
 * Check if a node type exists
 */
export function isValidNodeType(nodeType: string): boolean {
  return nodeType in nodeConfigRegistry;
}

/**
 * Get default configuration for a node type
 */
export function getDefaultConfig(nodeType: string): Record<string, unknown> {
  const config = getNodeConfig(nodeType);
  if (!config) return {};

  // Build default config from schema defaults
  const defaults: Record<string, unknown> = {};
  for (const field of config.configSchema) {
    defaults[field.name] = field.default;
  }

  // Override with explicit defaultConfig if provided
  if (config.defaultConfig) {
    Object.assign(defaults, config.defaultConfig);
  }

  return defaults;
}

/**
 * Validate node configuration against schema
 */
export function validateNodeConfig(
  nodeType: string,
  config: Record<string, unknown>,
): { valid: boolean; errors: string[] } {
  const nodeConfig = getNodeConfig(nodeType);
  if (!nodeConfig) {
    return { valid: false, errors: [`Unknown node type: ${nodeType}`] };
  }

  const errors: string[] = [];

  for (const field of nodeConfig.configSchema) {
    const value = config[field.name];

    // Check required fields
    if (
      field.required &&
      (value === undefined || value === null || value === '')
    ) {
      errors.push(`Field "${field.name}" is required`);
      continue;
    }

    // Skip validation for optional empty fields
    if (!field.required && (value === undefined || value === null)) {
      continue;
    }

    // Type-specific validation could be added here
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Convert node config metadata to NodeTypeMetadata format
 * (for compatibility with existing workflow store)
 */
export function toNodeTypeMetadata(config: NodeConfigMeta) {
  return {
    type: config.nodeType,
    name: config.label,
    description: config.description,
    category: config.category,
    icon: config.icon,
    color: config.color,
    inputs: config.inputs.map((input) => ({
      name: input.name,
      type: input.type,
      description: input.description,
      required: input.required,
    })),
    outputs: config.outputs.map((output) => ({
      name: output.name,
      type: output.type,
      description: output.description,
      required: output.required,
    })),
    config_schema: config.configSchema,
  };
}

/**
 * Convert all node configs to NodeTypeMetadata format
 */
export function getAllNodeTypeMetadata() {
  return allNodeConfigs.map(toNodeTypeMetadata);
}
