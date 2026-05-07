import { useCallback, useMemo, useState } from 'react';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Trash2,
  Settings,
  ArrowRight,
  ArrowLeft,
  Variable,
  Code,
  ChevronDown,
  ChevronRight,
  Copy,
  Info,
  Sparkles,
} from 'lucide-react';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { getNodeConfig } from './node-configs';
import i18n from 'i18next';
import { I18nObject } from '@/app/infra/entities/common';
import { normalizeWorkflowNodeTypeMeta } from './workflow-node-metadata';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';

import { resolveI18nLabel, maybeTranslateKey } from './workflow-i18n';

// Delegate to shared utility
const translateIfKey = (value: string | undefined): string | undefined => {
  if (!value) return value;
  return maybeTranslateKey(value);
};

// Delegate to shared utility
const extractI18nLabel = (
  obj: Record<string, string> | I18nObject | undefined,
): string | undefined => {
  if (!obj) return undefined;
  const result = resolveI18nLabel(obj as Record<string, string>);
  return result || undefined;
};

// Get translated type label using i18n
const getTypeLabel = (type: string | undefined): string => {
  if (!type) return '';
  const i18nKey = `workflows.type.${type.toLowerCase()}`;
  const translated = i18n.t(i18nKey);
  // If translation key doesn't exist, return the original type
  return translated === i18nKey ? type : translated;
};

interface PropertyPanelProps {
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
}

// Variable reference component
// Format variable reference to show only the short name
const formatVariableName = (fullPath: string): string => {
  // nodes.node_xxx.body -> body
  // message.content -> content
  const parts = fullPath.split('.');
  return parts.length > 2 ? parts.slice(2).join('.') : parts[parts.length - 1];
};

const resolvePortDisplayLabel = (
  port: { name: string; label?: string | Record<string, string> | I18nObject },
  prefix: 'workflows.nodeInputs' | 'workflows.nodeOutputs',
): string => {
  if (port.label) {
    if (typeof port.label === 'object') {
      const resolved = extractI18nLabel(port.label as Record<string, string>);
      if (resolved) return resolved;
    } else {
      const resolved = translateIfKey(port.label);
      if (resolved && resolved !== port.label) return resolved;
      if (resolved && !resolved.startsWith('workflows.')) return resolved;
    }
  }

  const translated = translateIfKey(`${prefix}.${port.name}`);
  return translated && translated !== `${prefix}.${port.name}`
    ? translated
    : port.name;
};

function VariableReference({
  variable,
  onCopy,
}: {
  variable: { name: string; label?: string; type?: string };
  onCopy: (ref: string) => void;
}) {
  const ref = `{{${variable.name}}}`;
  const displayName = variable.label || formatVariableName(variable.name);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center justify-between py-1 px-2 rounded bg-muted/50 text-sm group overflow-hidden w-full cursor-default">
          <div className="flex items-center gap-2 min-w-0 flex-1 overflow-hidden">
            <Variable className="size-3.5 text-muted-foreground flex-shrink-0" />
            <span className="truncate font-mono text-xs min-w-0">
              {displayName}
            </span>
            {variable.type && (
              <Badge
                variant="outline"
                className="text-[10px] px-1 py-0 flex-shrink-0"
              >
                {getTypeLabel(variable.type)}
              </Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="size-6 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
            onClick={() => onCopy(ref)}
          >
            <Copy className="size-3" />
          </Button>
        </div>
      </TooltipTrigger>
      <TooltipContent side="left" className="max-w-xs">
        <code className="text-xs break-all">{ref}</code>
      </TooltipContent>
    </Tooltip>
  );
}

// Collapsible section component
function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
  badge,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className="w-full overflow-hidden"
    >
      <CollapsibleTrigger asChild>
        <button className="w-full flex items-center gap-2 py-2 px-1 hover:bg-muted/50 rounded transition-colors min-w-0 overflow-hidden">
          {isOpen ? (
            <ChevronDown className="size-4 text-muted-foreground flex-shrink-0" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground flex-shrink-0" />
          )}
          <Icon className="size-4 text-muted-foreground flex-shrink-0" />
          <span className="font-medium text-sm flex-1 text-left truncate min-w-0">
            {title}
          </span>
          {badge}
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="pl-6 pr-1 pb-2 w-full overflow-hidden">
        <div className="w-full overflow-hidden">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export default function PropertyPanel({
  selectedNodeId,
  selectedEdgeId,
}: PropertyPanelProps) {
  const { t } = useTranslation();
  const {
    nodes,
    edges,
    nodeTypes,
    updateNodeConfig,
    updateNodeLabel,
    deleteNode,
    deleteEdge,
    updateEdgeCondition,
    pushHistory,
  } = useWorkflowStore();

  // Use extractI18nObject for i18n handling (it automatically handles language detection)

  // Get selected node
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return nodes.find((n) => n.id === selectedNodeId) || null;
  }, [nodes, selectedNodeId]);

  // Get selected edge
  const selectedEdge = useMemo(() => {
    if (!selectedEdgeId) return null;
    return edges.find((e) => e.id === selectedEdgeId) || null;
  }, [edges, selectedEdgeId]);

  // Get node type metadata for selected node
  // Priority: API metadata first, local registry as normalized fallback
  const nodeTypeMeta = useMemo(() => {
    if (!selectedNode) return null;

    const nodeType = selectedNode.data.type;
    return normalizeWorkflowNodeTypeMeta(
      nodeType,
      nodeTypes.find((t) => t.type === nodeType),
    );
  }, [selectedNode, nodeTypes]);

  // Get local node config for additional metadata not carried by backend schema
  const localNodeConfig = useMemo(() => {
    if (!selectedNode) return null;
    const nodeType = selectedNode.data.type;
    return getNodeConfig(nodeType) || null;
  }, [selectedNode]);

  // Prefer local registry config schema so workflow editor can reuse the existing
  // form item definitions, i18n labels/descriptions and option labels consistently.
  // Fall back to backend metadata for nodes that do not exist in the local registry.
  const configSchema = useMemo(() => {
    const localConfigSchema =
      (localNodeConfig?.configSchema as IDynamicFormItemSchema[]) || [];
    const backendConfigSchema =
      (nodeTypeMeta?.config_schema as IDynamicFormItemSchema[]) || [];
    const rawConfigSchema =
      localConfigSchema.length > 0 ? localConfigSchema : backendConfigSchema;

    return rawConfigSchema.map((item) => {
      const backendItem = backendConfigSchema.find(
        (candidate) => candidate.name === item.name || candidate.id === item.id,
      );

      return {
        ...(backendItem || {}),
        ...item,
        label: item.label ||
          backendItem?.label || {
            en_US: item.name,
            zh_Hans: item.name,
          },
        description: item.description ||
          backendItem?.description || {
            en_US: '',
            zh_Hans: '',
          },
        options: item.options || backendItem?.options,
        show_if: item.show_if || backendItem?.show_if,
      };
    });
  }, [localNodeConfig?.configSchema, nodeTypeMeta?.config_schema]);

  // Get available input variables from connected upstream nodes
  const availableInputVariables = useMemo(() => {
    if (!selectedNode) return [];

    const variables: {
      nodeId: string;
      nodeLabel: string;
      outputs: { name: string; label?: string; type?: string }[];
    }[] = [];

    // Find all upstream nodes
    const incomingEdges = edges.filter((e) => e.target === selectedNode.id);
    const upstreamNodeIds = incomingEdges.map((e) => e.source);

    for (const nodeId of upstreamNodeIds) {
      const node = nodes.find((n) => n.id === nodeId);
      if (node) {
        const outputs = node.data.outputs || [{ name: 'output', type: 'any' }];
        variables.push({
          nodeId: node.id,
          nodeLabel: node.data.label,
          outputs: outputs.map((o) => ({
            name: `nodes.${node.id}.${o.name}`,
            label: resolvePortDisplayLabel(o, 'workflows.nodeOutputs'),
            type: o.type,
          })),
        });
      }
    }

    // Add global variables
    variables.push({
      nodeId: '__global__',
      nodeLabel: t('workflows.globalVariables'),
      outputs: [
        {
          name: 'message.content',
          label: t('workflows.messageContent'),
          type: 'string',
        },
        {
          name: 'message.sender',
          label: t('workflows.messageSender'),
          type: 'string',
        },
        {
          name: 'context.platform',
          label: t('workflows.platform'),
          type: 'string',
        },
        {
          name: 'context.session_id',
          label: t('workflows.sessionId'),
          type: 'string',
        },
        {
          name: 'context.timestamp',
          label: t('workflows.timestamp'),
          type: 'datetime',
        },
      ],
    });

    return variables;
  }, [selectedNode, edges, nodes, t]);

  // Handle label change
  const handleLabelChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (selectedNodeId) {
        updateNodeLabel(selectedNodeId, e.target.value);
      }
    },
    [selectedNodeId, updateNodeLabel],
  );

  // Handle config change from dynamic form
  const handleConfigChange = useCallback(
    (values: object): unknown => {
      if (selectedNodeId) {
        updateNodeConfig(selectedNodeId, values as Record<string, unknown>);
        pushHistory();
      }
      return undefined;
    },
    [selectedNodeId, updateNodeConfig, pushHistory],
  );

  // Handle node delete
  const handleDeleteNode = useCallback(() => {
    if (selectedNodeId) {
      deleteNode(selectedNodeId);
    }
  }, [selectedNodeId, deleteNode]);

  // Handle edge delete
  const handleDeleteEdge = useCallback(() => {
    if (selectedEdgeId) {
      deleteEdge(selectedEdgeId);
    }
  }, [selectedEdgeId, deleteEdge]);

  // Handle edge condition change
  const handleConditionChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      if (selectedEdgeId) {
        updateEdgeCondition(selectedEdgeId, e.target.value);
      }
    },
    [selectedEdgeId, updateEdgeCondition],
  );

  // Copy variable reference
  const handleCopyVariable = useCallback(
    (ref: string) => {
      navigator.clipboard.writeText(ref);
      toast.success(t('common.copySuccess'));
    },
    [t],
  );

  // No selection
  if (!selectedNodeId && !selectedEdgeId) {
    return (
      <div className="h-full w-full flex flex-col overflow-hidden">
        <div className="p-4 border-b w-full overflow-hidden">
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <Settings className="size-4" />
            {t('workflows.properties')}
          </h3>
        </div>
        <div className="flex-1 flex items-center justify-center w-full overflow-hidden">
          <div className="text-center p-8 w-full max-w-full overflow-hidden">
            <Settings className="size-12 mx-auto mb-3 opacity-20" />
            <p className="text-sm text-muted-foreground">
              {t('workflows.selectNodeOrEdge')}
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              {t('workflows.selectNodeOrEdgeHint')}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Edge selected
  if (selectedEdge) {
    const sourceNode = nodes.find((n) => n.id === selectedEdge.source);
    const targetNode = nodes.find((n) => n.id === selectedEdge.target);

    return (
      <TooltipProvider>
        <div className="h-full w-full flex flex-col overflow-hidden">
          <div className="p-4 border-b w-full overflow-hidden">
            <h3 className="font-semibold text-sm flex items-center gap-2">
              <ArrowRight className="size-4" />
              {t('workflows.edgeProperties')}
            </h3>
          </div>

          <ScrollArea className="flex-1 w-full min-h-0">
            <div className="p-4 space-y-4 w-full overflow-hidden box-border">
              {/* Connection info */}
              <div className="bg-muted/50 p-3 rounded-lg w-full overflow-hidden">
                <div className="flex items-center gap-2 text-sm min-w-0 w-full overflow-hidden">
                  <Badge
                    variant="outline"
                    className="font-mono text-xs truncate max-w-[35%] flex-shrink min-w-0"
                  >
                    {sourceNode?.data.label || selectedEdge.source}
                  </Badge>
                  <ArrowRight className="size-4 text-muted-foreground flex-shrink-0" />
                  <Badge
                    variant="outline"
                    className="font-mono text-xs truncate max-w-[35%] flex-shrink min-w-0"
                  >
                    {targetNode?.data.label || selectedEdge.target}
                  </Badge>
                </div>
              </div>

              {/* Condition */}
              <CollapsibleSection
                title={t('workflows.condition')}
                icon={Code}
                badge={
                  selectedEdge.data?.condition ? (
                    <Badge
                      variant="secondary"
                      className="text-xs flex-shrink-0"
                    >
                      {t('workflows.hasCondition')}
                    </Badge>
                  ) : null
                }
              >
                <div className="space-y-2 w-full overflow-hidden">
                  <Textarea
                    value={selectedEdge.data?.condition || ''}
                    onChange={handleConditionChange}
                    placeholder={t('workflows.conditionPlaceholder')}
                    rows={4}
                    className="font-mono text-sm w-full"
                  />
                  <div className="flex items-start gap-2 text-xs text-muted-foreground">
                    <Info className="size-3.5 mt-0.5 flex-shrink-0" />
                    <p>{t('workflows.conditionHelp')}</p>
                  </div>
                </div>
              </CollapsibleSection>

              <Separator />

              {/* Delete edge */}
              <div className="w-full overflow-hidden">
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive" size="sm" className="w-full">
                      <Trash2 className="size-4 mr-2 flex-shrink-0" />
                      <span className="truncate">
                        {t('workflows.deleteEdge')}
                      </span>
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>
                        {t('workflows.deleteEdgeConfirm')}
                      </AlertDialogTitle>
                      <AlertDialogDescription>
                        {t('workflows.deleteEdgeConfirmDesc')}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter className="flex-wrap gap-2">
                      <AlertDialogCancel className="flex-1 min-w-[80px]">
                        {t('common.cancel')}
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleDeleteEdge}
                        className="flex-1 min-w-[80px]"
                      >
                        {t('common.delete')}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          </ScrollArea>
        </div>
      </TooltipProvider>
    );
  }

  // Node selected
  if (selectedNode) {
    const nodeInputs = selectedNode.data.inputs ||
      nodeTypeMeta?.inputs || [{ name: 'input', type: 'any' }];
    const nodeOutputs = selectedNode.data.outputs ||
      nodeTypeMeta?.outputs || [{ name: 'output', type: 'any' }];

    // Extract i18n labels using extractI18nLabel
    const nodeLabel = nodeTypeMeta?.label
      ? extractI18nLabel(nodeTypeMeta.label)
      : selectedNode.data.type;
    const nodeDescription = nodeTypeMeta?.description
      ? extractI18nLabel(nodeTypeMeta.description)
      : undefined;

    // Get node category color from local config
    const nodeColor = localNodeConfig?.color || nodeTypeMeta?.color;

    return (
      <TooltipProvider>
        <div className="h-full w-full flex flex-col overflow-hidden">
          {/* Header */}
          <div className="p-4 border-b w-full overflow-hidden">
            <h3 className="font-semibold text-sm flex items-center gap-2">
              <Sparkles className="size-4" />
              {t('workflows.nodeProperties')}
            </h3>
          </div>

          <ScrollArea className="flex-1 w-full min-h-0">
            <div className="p-4 space-y-4 w-full box-border">
              {/* Node type info */}
              <div className="bg-muted/50 p-3 rounded-lg space-y-2 w-full overflow-hidden">
                <div className="flex items-center gap-2 min-w-0 overflow-hidden">
                  <Badge className="font-mono text-xs truncate max-w-full">
                    {selectedNode.data.type}
                  </Badge>
                </div>
                {nodeDescription && (
                  <p className="text-xs text-muted-foreground">
                    {nodeDescription}
                  </p>
                )}
              </div>

              {/* Basic Info */}
              <CollapsibleSection
                title={t('workflows.basicInfo')}
                icon={Settings}
              >
                <div className="space-y-3 w-full overflow-hidden">
                  <div className="space-y-1.5 w-full overflow-hidden">
                    <Label htmlFor="node-label" className="text-xs">
                      {t('workflows.nodeLabel')}
                    </Label>
                    <Input
                      id="node-label"
                      value={selectedNode.data.label}
                      onChange={handleLabelChange}
                      placeholder={t('workflows.nodeLabelPlaceholder')}
                      className="h-8 w-full"
                    />
                  </div>

                  <div className="space-y-1.5 w-full overflow-hidden">
                    <Label className="text-xs text-muted-foreground">
                      {t('workflows.nodeId')}
                    </Label>
                    <div className="flex items-center gap-2 min-w-0 w-full overflow-hidden">
                      <code className="text-xs bg-muted px-2 py-1 rounded flex-1 truncate min-w-0 overflow-hidden">
                        {selectedNode.id}
                      </code>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-6 flex-shrink-0"
                        onClick={() => handleCopyVariable(selectedNode.id)}
                      >
                        <Copy className="size-3" />
                      </Button>
                    </div>
                  </div>
                </div>
              </CollapsibleSection>

              {/* Input/Output Variables */}
              <CollapsibleSection
                title={t('workflows.inputOutputVariables')}
                icon={Variable}
                badge={
                  <Badge variant="secondary" className="text-xs flex-shrink-0">
                    {nodeInputs.length} / {nodeOutputs.length}
                  </Badge>
                }
              >
                <div className="space-y-3 w-full overflow-hidden">
                  {/* Inputs */}
                  <div className="space-y-1.5 w-full overflow-hidden">
                    <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                      <ArrowLeft className="size-3" />
                      {t('workflows.inputs')}
                    </div>
                    <div className="space-y-1 w-full overflow-hidden">
                      {nodeInputs.map((input) => (
                        <div
                          key={input.name}
                          className="flex items-center gap-2 py-1 px-2 rounded bg-blue-50 dark:bg-blue-950/30 text-sm overflow-hidden w-full min-w-0"
                        >
                          <Variable className="size-3.5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                          <span className="font-mono text-xs truncate min-w-0 flex-1">
                            {resolvePortDisplayLabel(
                              input,
                              'workflows.nodeInputs',
                            )}
                          </span>
                          {input.type && (
                            <Badge
                              variant="outline"
                              className="text-[10px] px-1 py-0 flex-shrink-0"
                            >
                              {getTypeLabel(input.type)}
                            </Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Outputs */}
                  <div className="space-y-1.5 w-full overflow-hidden">
                    <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                      <ArrowRight className="size-3" />
                      {t('workflows.outputs')}
                    </div>
                    <div className="space-y-1 w-full overflow-hidden">
                      {nodeOutputs.map((output) => (
                        <VariableReference
                          key={output.name}
                          variable={{
                            name: `nodes.${selectedNode.id}.${output.name}`,
                            label: resolvePortDisplayLabel(
                              output,
                              'workflows.nodeOutputs',
                            ),
                            type: output.type,
                          }}
                          onCopy={handleCopyVariable}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </CollapsibleSection>

              {/* Available Variables from upstream nodes */}
              {availableInputVariables.length > 0 && (
                <CollapsibleSection
                  title={t('workflows.availableVariables')}
                  icon={Code}
                  defaultOpen={false}
                >
                  <div className="space-y-3 w-full overflow-hidden">
                    {availableInputVariables.map((group) => (
                      <div
                        key={group.nodeId}
                        className="space-y-1.5 w-full overflow-hidden"
                      >
                        <div className="text-xs font-medium text-muted-foreground">
                          {group.nodeLabel}
                        </div>
                        <div className="space-y-1 w-full overflow-hidden">
                          {group.outputs.map((variable) => (
                            <VariableReference
                              key={variable.name}
                              variable={variable}
                              onCopy={handleCopyVariable}
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </CollapsibleSection>
              )}

              {/* Node configuration */}
              {configSchema.length > 0 && (
                <CollapsibleSection
                  title={t('workflows.nodeConfig')}
                  icon={Settings}
                  badge={
                    <Badge
                      variant="secondary"
                      className="text-xs flex-shrink-0"
                    >
                      {configSchema.length}
                    </Badge>
                  }
                >
                  <div className="space-y-2 w-full overflow-hidden box-border">
                    <DynamicFormComponent
                      itemConfigList={configSchema}
                      initialValues={
                        selectedNode.data.config as Record<string, object>
                      }
                      onSubmit={handleConfigChange}
                    />
                  </div>
                </CollapsibleSection>
              )}

              {/* Show message if no config schema */}
              {configSchema.length === 0 && (
                <div className="text-sm text-muted-foreground text-center py-4 bg-muted/30 rounded-lg">
                  <Settings className="size-6 mx-auto mb-2 opacity-50" />
                  <p>{t('workflows.noConfigOptions')}</p>
                </div>
              )}

              <Separator />

              {/* Delete node */}
              <div className="w-full overflow-hidden">
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive" size="sm" className="w-full">
                      <Trash2 className="size-4 mr-2 flex-shrink-0" />
                      <span className="truncate">
                        {t('workflows.deleteNode')}
                      </span>
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>
                        {t('workflows.deleteNodeConfirm')}
                      </AlertDialogTitle>
                      <AlertDialogDescription>
                        {t('workflows.deleteNodeConfirmDesc')}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter className="flex-wrap gap-2">
                      <AlertDialogCancel className="flex-1 min-w-[80px]">
                        {t('common.cancel')}
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleDeleteNode}
                        className="flex-1 min-w-[80px]"
                      >
                        {t('common.delete')}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          </ScrollArea>
        </div>
      </TooltipProvider>
    );
  }

  return null;
}
