import { memo, useMemo } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import {
  PauseCircle,
  Settings,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Play,
} from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  NODE_ICONS,
  NODE_TYPE_I18N_KEYS,
  getNodeTypeLabel,
} from './workflow-constants';
import { resolveI18nLabel, maybeTranslateKey } from './workflow-i18n';
import type { I18nObject } from '@/app/infra/entities/common';

// Use shared icon mapping
const nodeIcons = NODE_ICONS;

// Use shared i18n key mapping
const nodeTypeI18nKeys: Record<string, string> = Object.fromEntries(
  Object.entries(NODE_TYPE_I18N_KEYS).map(([k, v]) => [k, v.labelKey]),
);

// Category colors with improved design
const categoryColors: Record<
  string,
  {
    bg: string;
    border: string;
    text: string;
    icon: string;
    gradient: string;
    handleBg: string;
  }
> = {
  trigger: {
    bg: 'bg-amber-50 dark:bg-amber-950/40',
    border: 'border-amber-400 dark:border-amber-600',
    text: 'text-amber-900 dark:text-amber-100',
    icon: 'text-amber-600 dark:text-amber-400',
    gradient: 'from-amber-500/10 to-transparent',
    handleBg: '#f59e0b',
  },
  process: {
    bg: 'bg-blue-50 dark:bg-blue-950/40',
    border: 'border-blue-400 dark:border-blue-600',
    text: 'text-blue-900 dark:text-blue-100',
    icon: 'text-blue-600 dark:text-blue-400',
    gradient: 'from-blue-500/10 to-transparent',
    handleBg: '#3b82f6',
  },
  control: {
    bg: 'bg-purple-50 dark:bg-purple-950/40',
    border: 'border-purple-400 dark:border-purple-600',
    text: 'text-purple-900 dark:text-purple-100',
    icon: 'text-purple-600 dark:text-purple-400',
    gradient: 'from-purple-500/10 to-transparent',
    handleBg: '#8b5cf6',
  },
  action: {
    bg: 'bg-green-50 dark:bg-green-950/40',
    border: 'border-green-400 dark:border-green-600',
    text: 'text-green-900 dark:text-green-100',
    icon: 'text-green-600 dark:text-green-400',
    gradient: 'from-green-500/10 to-transparent',
    handleBg: '#22c55e',
  },
  integration: {
    bg: 'bg-pink-50 dark:bg-pink-950/40',
    border: 'border-pink-400 dark:border-pink-600',
    text: 'text-pink-900 dark:text-pink-100',
    icon: 'text-pink-600 dark:text-pink-400',
    gradient: 'from-pink-500/10 to-transparent',
    handleBg: '#ec4899',
  },
};

// Node execution status
export type NodeExecutionStatus =
  | 'idle'
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped';

// Status colors and icons
const statusConfig: Record<
  NodeExecutionStatus,
  {
    icon: React.ElementType;
    color: string;
    bgColor: string;
    animate?: boolean;
  }
> = {
  idle: {
    icon: Play,
    color: 'text-muted-foreground',
    bgColor: 'bg-muted',
  },
  pending: {
    icon: Clock,
    color: 'text-amber-600 dark:text-amber-400',
    bgColor: 'bg-amber-100 dark:bg-amber-900/50',
  },
  running: {
    icon: Loader2,
    color: 'text-blue-600 dark:text-blue-400',
    bgColor: 'bg-blue-100 dark:bg-blue-900/50',
    animate: true,
  },
  completed: {
    icon: CheckCircle2,
    color: 'text-green-600 dark:text-green-400',
    bgColor: 'bg-green-100 dark:bg-green-900/50',
  },
  failed: {
    icon: XCircle,
    color: 'text-red-600 dark:text-red-400',
    bgColor: 'bg-red-100 dark:bg-red-900/50',
  },
  skipped: {
    icon: PauseCircle,
    color: 'text-gray-500 dark:text-gray-400',
    bgColor: 'bg-gray-100 dark:bg-gray-800',
  },
};

export interface WorkflowNodeData extends Record<string, unknown> {
  label: string;
  type: string;
  config: Record<string, unknown>;
  inputs?: {
    name: string;
    label?: string | Record<string, string> | I18nObject;
    type?: string;
  }[];
  outputs?: {
    name: string;
    label?: string | Record<string, string> | I18nObject;
    type?: string;
  }[];
  // Execution state
  executionStatus?: NodeExecutionStatus;
  executionError?: string;
  executionDuration?: number; // in milliseconds
  // Node type metadata from backend
  nodeTypeLabel?: Record<string, string>; // i18n label dict from backend
  nodeTypeDescription?: Record<string, string>; // i18n description from backend
}

// Helper function to get port label with i18n support
function getPortLabel(
  label: string | Record<string, string> | I18nObject | undefined,
  fallbackName: string,
  prefix: 'workflows.nodeOutputs' | 'workflows.nodeInputs',
  t: (key: string, options?: { defaultValue: string }) => string,
): string {
  if (label && typeof label === 'object') {
    const resolved = resolveI18nLabel(label);
    if (resolved) return resolved;
  }

  if (typeof label === 'string' && label) {
    if (
      label.startsWith('workflows.nodeOutputs.') ||
      label.startsWith('workflows.nodeInputs.')
    ) {
      return t(label, { defaultValue: fallbackName });
    }
    return label;
  }

  const key = `${prefix}.${fallbackName}`;
  const translated = t(key, { defaultValue: fallbackName });
  return translated === key ? fallbackName : translated;
}

// Helper function to extract i18n value from I18nObject (delegates to shared utility)
function extractI18nValue(
  i18nObj: Record<string, string> | undefined,
  _t: (key: string) => string,
): string {
  return resolveI18nLabel(i18nObj);
}

// Helper function to get node type description: show the raw type name after the dot
function getNodeTypeDescription(
  nodeType: string,
  t: (key: string, options?: { defaultValue: string }) => string,
  nodeTypeLabel?: Record<string, string>,
): string {
  return nodeType.includes('.')
    ? nodeType.split('.').slice(1).join('.')
    : nodeType;
}

function WorkflowNodeComponent({ data, selected }: NodeProps) {
  const { t } = useTranslation();
  const nodeData = data as WorkflowNodeData;
  const category = nodeData.type.split('.')[0];
  const colors = categoryColors[category] || categoryColors.process;
  const Icon = nodeIcons[nodeData.type] || Settings;

  // Get execution status
  const status = nodeData.executionStatus || 'idle';
  const statusInfo = statusConfig[status];
  const StatusIcon = statusInfo.icon;

  // Get inputs and outputs with defaults (use i18n keys for default labels)
  const inputs = useMemo(() => {
    return (
      nodeData.inputs || [
        { name: 'input', label: 'workflows.nodeInputs.input', type: 'any' },
      ]
    );
  }, [nodeData.inputs]);

  const outputs = useMemo(() => {
    return (
      nodeData.outputs || [
        { name: 'output', label: 'workflows.nodeOutputs.output', type: 'any' },
      ]
    );
  }, [nodeData.outputs]);

  // Determine if this is a trigger node (no inputs)
  const isTrigger = category === 'trigger';

  // Format execution duration
  const formattedDuration = useMemo(() => {
    if (!nodeData.executionDuration) return null;
    if (nodeData.executionDuration < 1000) {
      return `${nodeData.executionDuration}ms`;
    }
    return `${(nodeData.executionDuration / 1000).toFixed(2)}s`;
  }, [nodeData.executionDuration]);

  return (
    <TooltipProvider>
      <div
        className={cn(
          'min-w-[200px] max-w-[280px] rounded-xl border-2 shadow-lg transition-all duration-200',
          colors.bg,
          colors.border,
          selected &&
            'ring-2 ring-primary ring-offset-2 ring-offset-background shadow-xl scale-[1.02]',
          status === 'running' && 'shadow-blue-200 dark:shadow-blue-900/50',
          status === 'failed' &&
            'shadow-red-200 dark:shadow-red-900/50 border-red-500',
        )}
      >
        {/* Input handles - only show if not trigger */}
        {!isTrigger &&
          inputs.map((input, index) => (
            <Tooltip key={`input-${input.name}`}>
              <TooltipTrigger asChild>
                <Handle
                  type="target"
                  position={Position.Left}
                  id={input.name}
                  style={{
                    top:
                      inputs.length === 1
                        ? '50%'
                        : `${((index + 1) / (inputs.length + 1)) * 100}%`,
                    background: colors.handleBg,
                    width: 12,
                    height: 12,
                    border: '2px solid white',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                  }}
                  className="!transition-transform hover:!scale-125"
                />
              </TooltipTrigger>
              <TooltipContent side="left">
                <p className="font-medium">
                  {getPortLabel(
                    input.label,
                    input.name,
                    'workflows.nodeInputs',
                    t,
                  )}
                </p>
                {input.type && (
                  <p className="text-xs text-muted-foreground">{input.type}</p>
                )}
              </TooltipContent>
            </Tooltip>
          ))}

        {/* Node content */}
        <div className={cn('p-3 bg-gradient-to-b', colors.gradient)}>
          {/* Header row with icon and status */}
          <div className="flex items-start gap-2.5">
            {/* Node icon */}
            <div
              className={cn(
                'p-2 rounded-lg shrink-0',
                colors.icon,
                'bg-white/60 dark:bg-black/20',
                'shadow-sm',
              )}
            >
              <Icon className="size-5" />
            </div>

            {/* Title and type */}
            <div className="flex-1 min-w-0 pt-0.5">
              <div
                className={cn('font-semibold text-sm truncate', colors.text)}
              >
                {nodeData.label}
              </div>
              <div className="text-xs text-muted-foreground truncate mt-0.5">
                {getNodeTypeDescription(
                  nodeData.type,
                  t,
                  nodeData.nodeTypeLabel,
                )}
              </div>
            </div>

            {/* Status indicator */}
            {status !== 'idle' && (
              <div
                className={cn('p-1 rounded-full shrink-0', statusInfo.bgColor)}
              >
                <StatusIcon
                  className={cn(
                    'size-4',
                    statusInfo.color,
                    statusInfo.animate && 'animate-spin',
                  )}
                />
              </div>
            )}
          </div>

          {/* Execution info */}
          {(status === 'completed' || status === 'failed') && (
            <div
              className={cn(
                'mt-2 pt-2 border-t flex items-center justify-between text-xs',
                'border-black/5 dark:border-white/5',
              )}
            >
              <div className={cn('flex items-center gap-1', statusInfo.color)}>
                <StatusIcon className="size-3" />
                <span className="capitalize">{status}</span>
              </div>
              {formattedDuration && (
                <span className="text-muted-foreground">
                  {formattedDuration}
                </span>
              )}
            </div>
          )}

          {/* Error message */}
          {status === 'failed' && nodeData.executionError && (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="mt-2 p-2 rounded-md bg-red-100 dark:bg-red-950/50 text-xs text-red-700 dark:text-red-300 truncate cursor-help">
                  {nodeData.executionError}
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[300px]">
                <p className="text-sm">{nodeData.executionError}</p>
              </TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Output handles */}
        {outputs.map((output, index) => (
          <Tooltip key={`output-${output.name}`}>
            <TooltipTrigger asChild>
              <Handle
                type="source"
                position={Position.Right}
                id={output.name}
                style={{
                  top:
                    outputs.length === 1
                      ? '50%'
                      : `${((index + 1) / (outputs.length + 1)) * 100}%`,
                  background: colors.handleBg,
                  width: 12,
                  height: 12,
                  border: '2px solid white',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                }}
                className="!transition-transform hover:!scale-125"
              />
            </TooltipTrigger>
            <TooltipContent side="right">
              <p className="font-medium">
                {getPortLabel(
                  output.label,
                  output.name,
                  'workflows.nodeOutputs',
                  t,
                )}
              </p>
              {output.type && (
                <p className="text-xs text-muted-foreground">{output.type}</p>
              )}
            </TooltipContent>
          </Tooltip>
        ))}
      </div>
    </TooltipProvider>
  );
}

export default memo(WorkflowNodeComponent);
