import { memo, useMemo } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import {
  PauseCircle,
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
  CONTROL_SOURCE_HANDLE,
  CONTROL_TARGET_HANDLE,
  getIconComponent,
} from './workflow-constants';
import { resolveI18nLabel } from './workflow-i18n';
import type { I18nObject } from '@/app/infra/entities/common';

const DATA_PORT_INSET = 36;
const DATA_PORT_GAP = 48;
const MIN_NODE_WIDTH = 220;
const MAX_NODE_WIDTH = 320;

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
  icon?: string; // Lucide icon name from backend
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
  const Icon = getIconComponent(nodeData.icon as string | undefined, nodeData.type);

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
  const isTerminal =
    nodeData.type === 'action.end' || nodeData.type.endsWith('.end');

  const maxDataPortCount = Math.max(
    isTrigger ? 0 : inputs.length,
    outputs.length,
  );
  const naturalNodeWidth =
    DATA_PORT_INSET * 2 +
    Math.max(0, maxDataPortCount - 1) * DATA_PORT_GAP;
  const nodeWidth = Math.min(
    MAX_NODE_WIDTH,
    Math.max(MIN_NODE_WIDTH, naturalNodeWidth),
  );
  const dataPortGap =
    maxDataPortCount > 1
      ? Math.min(
          DATA_PORT_GAP,
          (nodeWidth - DATA_PORT_INSET * 2) / (maxDataPortCount - 1),
        )
      : 0;
  const inputPortLeft = (index: number) => DATA_PORT_INSET + index * dataPortGap;
  const outputPortRight = (index: number) =>
    DATA_PORT_INSET + index * dataPortGap;

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
          'relative min-w-[220px] overflow-visible rounded-xl border-2 shadow-lg transition-all duration-200',
          colors.bg,
          colors.border,
          selected &&
            'ring-2 ring-primary ring-offset-2 ring-offset-background shadow-xl scale-[1.02]',
          status === 'running' && 'shadow-blue-200 dark:shadow-blue-900/50',
          status === 'failed' &&
            'shadow-red-200 dark:shadow-red-900/50 border-red-500',
        )}
        style={{ width: nodeWidth }}
      >
        {/* Control flow handles */}
        {!isTrigger && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Handle
                type="target"
                position={Position.Left}
                id={CONTROL_TARGET_HANDLE}
                style={{
                  top: '50%',
                  background: '#f97316',
                  width: 16,
                  height: 16,
                  borderRadius: 4,
                  border: '2px solid white',
                  boxShadow: '0 2px 6px rgba(249,115,22,0.35)',
                }}
                className="!transition-transform hover:!scale-125"
              />
            </TooltipTrigger>
            <TooltipContent side="left">
              <p className="font-medium">
                {t('workflows.controlInput', { defaultValue: 'Control input' })}
              </p>
            </TooltipContent>
          </Tooltip>
        )}

        {!isTerminal && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Handle
                type="source"
                position={Position.Right}
                id={CONTROL_SOURCE_HANDLE}
                style={{
                  top: '50%',
                  background: '#f97316',
                  width: 20,
                  height: 20,
                  borderRadius: 4,
                  border: '2px solid white',
                  boxShadow: '0 2px 6px rgba(249,115,22,0.35)',
                }}
              />
            </TooltipTrigger>
            <TooltipContent side="right">
              <p className="font-medium">
                {t('workflows.controlOutput', {
                  defaultValue: 'Control output',
                })}
              </p>
            </TooltipContent>
          </Tooltip>
        )}

        {/* Input handles - only show if not trigger */}
        {!isTrigger &&
          inputs.map((input, index) => {
            const label = getPortLabel(
              input.label,
              input.name,
              'workflows.nodeInputs',
              t,
            );

            return (
              <div key={`input-${input.name}`}>
                <span
                  className="pointer-events-none absolute -top-7 z-10 max-w-20 truncate whitespace-nowrap text-center text-[10px] font-medium text-muted-foreground"
                  style={{
                    left: inputPortLeft(index),
                    transform: 'translateX(-50%)',
                  }}
                >
                  {label}
                </span>
                <Handle
                  type="target"
                  position={Position.Top}
                  id={input.name}
                  style={{
                    left: inputPortLeft(index),
                    top: 0,
                    transform: 'translate(-50%, -50%)',
                    background: colors.handleBg,
                    width: 10,
                    height: 10,
                    border: '2px solid white',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                  }}
                  className="!transition-transform hover:!scale-125"
                />
              </div>
            );
          })}

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
        {outputs.map((output, index) => {
          const label = getPortLabel(
            output.label,
            output.name,
            'workflows.nodeOutputs',
            t,
          );

          return (
            <div key={`output-${output.name}`}>
              <span
                className="pointer-events-none absolute -bottom-7 z-10 max-w-20 truncate whitespace-nowrap text-center text-[10px] font-medium text-muted-foreground"
                style={{
                  right: outputPortRight(index),
                  transform: 'translateX(50%)',
                }}
              >
                {label}
              </span>
              <Handle
                type="source"
                position={Position.Bottom}
                id={output.name}
                style={{
                  left: 'auto',
                  right: outputPortRight(index),
                  bottom: 0,
                  transform: 'translate(50%, 50%)',
                  background: colors.handleBg,
                  width: 10,
                  height: 10,
                  border: '2px solid white',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                }}
                className="!transition-transform hover:!scale-125"
              />
            </div>
          );
        })}
      </div>
    </TooltipProvider>
  );
}

export default memo(WorkflowNodeComponent);
