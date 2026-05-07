/**
 * Shared constants for the Workflow editor.
 *
 * Centralises `nodeTypeI18nKeys`, `nodeIcons`, and palette category
 * colours that were previously duplicated across WorkflowNodeComponent,
 * NodePalette, and useWorkflowStore.
 */

import {
  MessageSquare,
  Timer,
  Webhook,
  Bot,
  Brain,
  Search,
  Code,
  FileText,
  GitBranch,
  Repeat,
  GitMerge,
  PauseCircle,
  AlertCircle,
  Variable,
  Send,
  Database,
  Zap,
  Globe,
  Settings,
  Bell,
  ArrowRightLeft,
  Split,
  Layers,
  Clock,
  ListFilter,
  Workflow,
  MessageCircle,
  Cpu,
  Play,
  Plug,
  ExternalLink,
} from 'lucide-react';

import i18n from 'i18next';
import { resolveI18nLabel, maybeTranslateKey } from './workflow-i18n';

// ─── Node type → i18n key mapping ──────────────────────────────────
//
// Single source of truth.  Used by WorkflowNodeComponent,
// NodePalette, and useWorkflowStore.

export const NODE_TYPE_I18N_KEYS: Record<
  string,
  { labelKey: string; descriptionKey: string }
> = {
  // Trigger
  'trigger.message_trigger': {
    labelKey: 'workflows.nodes.messageTrigger',
    descriptionKey: 'workflows.nodes.messageTriggerDescription',
  },
  'trigger.cron_trigger': {
    labelKey: 'workflows.nodes.cronTrigger',
    descriptionKey: 'workflows.nodes.cronTriggerDescription',
  },
  'trigger.webhook_trigger': {
    labelKey: 'workflows.nodes.webhookTrigger',
    descriptionKey: 'workflows.nodes.webhookTriggerDescription',
  },
  'trigger.event_trigger': {
    labelKey: 'workflows.nodes.eventTrigger',
    descriptionKey: 'workflows.nodes.eventTriggerDescription',
  },
  // Process / AI
  'process.llm_call': {
    labelKey: 'workflows.nodes.llmCall',
    descriptionKey: 'workflows.nodes.llmCallDescription',
  },
  'process.question_classifier': {
    labelKey: 'workflows.nodes.questionClassifier',
    descriptionKey: 'workflows.nodes.questionClassifierDescription',
  },
  'process.parameter_extractor': {
    labelKey: 'workflows.nodes.parameterExtractor',
    descriptionKey: 'workflows.nodes.parameterExtractorDescription',
  },
  'process.knowledge_retrieval': {
    labelKey: 'workflows.nodes.knowledgeRetrieval',
    descriptionKey: 'workflows.nodes.knowledgeRetrievalDescription',
  },
  'process.code_executor': {
    labelKey: 'workflows.nodes.codeExecutor',
    descriptionKey: 'workflows.nodes.codeExecutorDescription',
  },
  'process.http_request': {
    labelKey: 'workflows.nodes.httpRequest',
    descriptionKey: 'workflows.nodes.httpRequestDescription',
  },
  'process.data_transform': {
    labelKey: 'workflows.nodes.dataTransform',
    descriptionKey: 'workflows.nodes.dataTransformDescription',
  },
  'process.text_template': {
    labelKey: 'workflows.nodes.textTemplate',
    descriptionKey: 'workflows.nodes.textTemplateDescription',
  },
  'process.json_transform': {
    labelKey: 'workflows.nodes.jsonTransform',
    descriptionKey: 'workflows.nodes.jsonTransformDescription',
  },
  'process.data_aggregator': {
    labelKey: 'workflows.nodes.dataAggregator',
    descriptionKey: 'workflows.nodes.dataAggregatorDescription',
  },
  'process.text_splitter': {
    labelKey: 'workflows.nodes.textSplitter',
    descriptionKey: 'workflows.nodes.textSplitterDescription',
  },
  'process.variable_assignment': {
    labelKey: 'workflows.nodes.variableAssignment',
    descriptionKey: 'workflows.nodes.variableAssignmentDescription',
  },
  // Control
  'control.condition': {
    labelKey: 'workflows.nodes.condition',
    descriptionKey: 'workflows.nodes.conditionDescription',
  },
  'control.switch': {
    labelKey: 'workflows.nodes.switch',
    descriptionKey: 'workflows.nodes.switchDescription',
  },
  'control.loop': {
    labelKey: 'workflows.nodes.loop',
    descriptionKey: 'workflows.nodes.loopDescription',
  },
  'control.iterator': {
    labelKey: 'workflows.nodes.iterator',
    descriptionKey: 'workflows.nodes.iteratorDescription',
  },
  'control.parallel': {
    labelKey: 'workflows.nodes.parallel',
    descriptionKey: 'workflows.nodes.parallelDescription',
  },
  'control.wait': {
    labelKey: 'workflows.nodes.wait',
    descriptionKey: 'workflows.nodes.waitDescription',
  },
  'control.merge': {
    labelKey: 'workflows.nodes.merge',
    descriptionKey: 'workflows.nodes.mergeDescription',
  },
  'control.variable_aggregator': {
    labelKey: 'workflows.nodes.variableAggregator',
    descriptionKey: 'workflows.nodes.variableAggregatorDescription',
  },
  // Action
  'action.send_message': {
    labelKey: 'workflows.nodes.sendMessage',
    descriptionKey: 'workflows.nodes.sendMessageDescription',
  },
  'action.reply_message': {
    labelKey: 'workflows.nodes.replyMessage',
    descriptionKey: 'workflows.nodes.replyMessageDescription',
  },
  'action.store_data': {
    labelKey: 'workflows.nodes.storeData',
    descriptionKey: 'workflows.nodes.storeDataDescription',
  },
  'action.call_pipeline': {
    labelKey: 'workflows.nodes.callPipeline',
    descriptionKey: 'workflows.nodes.callPipelineDescription',
  },
  'action.set_variable': {
    labelKey: 'workflows.nodes.setVariable',
    descriptionKey: 'workflows.nodes.setVariableDescription',
  },
  'action.opening_statement': {
    labelKey: 'workflows.nodes.openingStatement',
    descriptionKey: 'workflows.nodes.openingStatementDescription',
  },
  'action.end': {
    labelKey: 'workflows.nodes.end',
    descriptionKey: 'workflows.nodes.endDescription',
  },
  // Integration – external services
  'integration.dify_workflow': {
    labelKey: 'workflows.nodes.difyWorkflow',
    descriptionKey: 'workflows.nodes.difyWorkflowDescription',
  },
  'integration.dify_knowledge_query': {
    labelKey: 'workflows.nodes.difyKnowledgeQuery',
    descriptionKey: 'workflows.nodes.difyKnowledgeQueryDescription',
  },
  'integration.n8n_workflow': {
    labelKey: 'workflows.nodes.n8nWorkflow',
    descriptionKey: 'workflows.nodes.n8nWorkflowDescription',
  },
  'integration.langflow_flow': {
    labelKey: 'workflows.nodes.langflowFlow',
    descriptionKey: 'workflows.nodes.langflowFlowDescription',
  },
  'integration.coze_bot': {
    labelKey: 'workflows.nodes.cozeBot',
    descriptionKey: 'workflows.nodes.cozeBotDescription',
  },
  // Integration – data & tools
  'integration.database_query': {
    labelKey: 'workflows.nodes.databaseQuery',
    descriptionKey: 'workflows.nodes.databaseQueryDescription',
  },
  'integration.redis_operation': {
    labelKey: 'workflows.nodes.redisOperation',
    descriptionKey: 'workflows.nodes.redisOperationDescription',
  },
  'integration.mcp_tool': {
    labelKey: 'workflows.nodes.mcpTool',
    descriptionKey: 'workflows.nodes.mcpToolDescription',
  },
  'integration.memory_store': {
    labelKey: 'workflows.nodes.memoryStore',
    descriptionKey: 'workflows.nodes.memoryStoreDescription',
  },
};

// Flat version: type → label key only (convenience for store / node component)
export const NODE_TYPE_LABEL_KEYS: Record<string, string> = Object.fromEntries(
  Object.entries(NODE_TYPE_I18N_KEYS).map(([k, v]) => [k, v.labelKey]),
);

// Category i18n
export const CATEGORY_I18N_KEYS: Record<string, { labelKey: string }> = {
  trigger: { labelKey: 'workflows.nodes.trigger' },
  process: { labelKey: 'workflows.nodes.process' },
  control: { labelKey: 'workflows.nodes.control' },
  action: { labelKey: 'workflows.nodes.action' },
  integration: { labelKey: 'workflows.nodes.integration' },
};

// ─── Icon mapping ───────────────────────────────────────────────────

export const NODE_ICONS: Record<string, React.ElementType> = {
  // Trigger
  'trigger.message': MessageSquare,
  'trigger.message_trigger': MessageSquare,
  'trigger.schedule': Timer,
  'trigger.cron': Timer,
  'trigger.cron_trigger': Timer,
  'trigger.webhook': Webhook,
  'trigger.webhook_trigger': Webhook,
  'trigger.manual': Zap,
  'trigger.event': Bell,
  'trigger.event_trigger': Bell,
  // Process / AI
  'process.llm': Brain,
  'process.llm_call': Brain,
  'process.knowledge': Search,
  'process.knowledge_retrieval': Search,
  'process.code': Code,
  'process.code_executor': Code,
  'process.template': FileText,
  'process.text_template': FileText,
  'process.data_transform': ArrowRightLeft,
  'process.http': Globe,
  'process.http_request': Globe,
  'process.question_classifier': ListFilter,
  'process.parameter_extractor': Variable,
  'process.json_transform': ArrowRightLeft,
  'process.data_aggregator': Layers,
  'process.text_splitter': Code,
  'process.variable_assignment': Variable,
  // Control
  'control.condition': GitBranch,
  'control.switch': Split,
  'control.loop': Repeat,
  'control.iterator': Repeat,
  'control.parallel': Layers,
  'control.merge': GitMerge,
  'control.variable_aggregator': GitMerge,
  'control.delay': Timer,
  'control.wait': Clock,
  'control.error_handler': AlertCircle,
  // Action
  'action.reply': Send,
  'action.reply_message': Send,
  'action.send_message': MessageCircle,
  'action.variable': Variable,
  'action.set_variable': Variable,
  'action.store_data': Database,
  'action.database': Database,
  'action.notify': Bell,
  'action.external': Globe,
  'action.call_pipeline': Workflow,
  'action.opening_statement': MessageSquare,
  'action.end': PauseCircle,
  // Integration – external services
  'integration.dify': Bot,
  'integration.dify_workflow': Bot,
  'integration.dify_knowledge_query': Search,
  'integration.n8n': Settings,
  'integration.n8n_workflow': Settings,
  'integration.langflow': Workflow,
  'integration.langflow_flow': Workflow,
  'integration.coze': Bot,
  'integration.coze_bot': Bot,
  // Integration – data & tools
  'integration.database_query': Database,
  'integration.redis_operation': Cpu,
  'integration.mcp_tool': Settings,
  'integration.memory_store': Layers,
};

// ─── Category palette colours ───────────────────────────────────────

export const PALETTE_CATEGORY_COLORS: Record<string, string> = {
  trigger: 'text-amber-600 dark:text-amber-400',
  process: 'text-blue-600 dark:text-blue-400',
  control: 'text-purple-600 dark:text-purple-400',
  action: 'text-green-600 dark:text-green-400',
  integration: 'text-pink-600 dark:text-pink-400',
};

export const PALETTE_CATEGORY_BG: Record<string, string> = {
  trigger:
    'bg-amber-100 dark:bg-amber-900/30 hover:bg-amber-200 dark:hover:bg-amber-900/50',
  process:
    'bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-900/50',
  control:
    'bg-purple-100 dark:bg-purple-900/30 hover:bg-purple-200 dark:hover:bg-purple-900/50',
  action:
    'bg-green-100 dark:bg-green-900/30 hover:bg-green-200 dark:hover:bg-green-900/50',
  integration:
    'bg-pink-100 dark:bg-pink-900/30 hover:bg-pink-200 dark:hover:bg-pink-900/50',
};

export const PALETTE_CATEGORY_BORDER: Record<string, string> = {
  trigger: 'border-amber-300 dark:border-amber-700',
  process: 'border-blue-300 dark:border-blue-700',
  control: 'border-purple-300 dark:border-purple-700',
  action: 'border-green-300 dark:border-green-700',
  integration: 'border-pink-300 dark:border-pink-700',
};

export const CATEGORY_ICONS: Record<string, React.ElementType> = {
  trigger: Zap,
  process: Cpu,
  control: GitBranch,
  action: Play,
  integration: Plug,
};

// ─── Helpers ────────────────────────────────────────────────────────

/**
 * Find the i18n keys for a node type, with fuzzy matching so both
 * "trigger.message_trigger" and "message_trigger" work.
 */
export function findNodeI18nKeys(
  type: string,
): { labelKey: string; descriptionKey: string } | undefined {
  let keys = NODE_TYPE_I18N_KEYS[type];
  if (keys) return keys;

  // Try stripping or adding category prefix
  const parts = type.split('.');
  const typeName = parts[parts.length - 1];
  if (parts.length > 1) {
    keys = NODE_TYPE_I18N_KEYS[type]; // already tried
  } else {
    for (const cat of [
      'trigger',
      'process',
      'control',
      'action',
      'integration',
    ]) {
      keys = NODE_TYPE_I18N_KEYS[`${cat}.${typeName}`];
      if (keys) return keys;
    }
  }

  // Scan all entries for a tail match
  for (const [k, v] of Object.entries(NODE_TYPE_I18N_KEYS)) {
    if (k.endsWith(`.${typeName}`) || k === typeName) return v;
  }
  return undefined;
}

/**
 * Resolve a human-readable label for a node type.
 * Priority: i18n key → backend label dict → prettified type string.
 */
export function getNodeTypeLabel(
  type: string,
  labelDict?: Record<string, string>,
): string {
  // 1. i18n key
  const keys = findNodeI18nKeys(type);
  if (keys) {
    const translated = i18n.t(keys.labelKey, { defaultValue: '' });
    if (translated) return translated;
  }

  // 2. Backend label dict
  if (labelDict) {
    const label = resolveI18nLabel(labelDict);
    if (label) return label;
  }

  // 3. Prettify type string
  const base = type.includes('.') ? type.split('.').slice(1).join('.') : type;
  return base
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}
