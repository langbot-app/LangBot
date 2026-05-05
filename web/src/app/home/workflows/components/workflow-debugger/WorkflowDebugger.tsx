import { useState, useCallback, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useWorkflowStore, DebugLog, NodeExecutionResult } from '../../store/useWorkflowStore';
import { backendClient } from '@/app/infra/http';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Play,
  Pause,
  StepForward,
  Square,
  Bug,
  Terminal,
  Eye,
  Circle,
  RefreshCw,
  Trash2,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  XCircle,
  Plus,
  X,
} from 'lucide-react';

interface WorkflowDebuggerProps {
  workflowId: string;
  onClose?: () => void;
}

const statusIcons: Record<string, React.ElementType> = {
  pending: Clock,
  running: Loader2,
  completed: CheckCircle2,
  failed: AlertCircle,
  skipped: XCircle,
};

const statusColors: Record<string, string> = {
  pending: 'text-yellow-500',
  running: 'text-blue-500 animate-spin',
  completed: 'text-green-500',
  failed: 'text-red-500',
  skipped: 'text-gray-400',
};

const logLevelColors: Record<string, string> = {
  info: 'text-blue-400',
  warning: 'text-yellow-400',
  error: 'text-red-400',
  debug: 'text-gray-400',
};

export default function WorkflowDebugger({ workflowId, onClose }: WorkflowDebuggerProps) {
  const { t } = useTranslation();
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<string>('context');
  const [autoScroll, setAutoScroll] = useState(true);
  const [newVariable, setNewVariable] = useState({ key: '', value: '' });
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const pollCancelledRef = useRef(false);

  const {
    debugMode,
    debugState,
    debugExecutionId,
    currentNodeId,
    nodeExecutionResults,
    breakpoints,
    debugLogs,
    debugContext,
    watchedVariables,
    nodes,
    setDebugMode,
    setDebugState,
    setDebugExecutionId,
    setCurrentNodeId,
    updateNodeExecutionResult,
    clearNodeExecutionResults,
    toggleBreakpoint,
    clearBreakpoints,
    addDebugLog,
    clearDebugLogs,
    setDebugContext,
    resetDebugContext,
    addWatchedVariable,
    removeWatchedVariable,
    resetDebugState,
  } = useWorkflowStore();

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      pollCancelledRef.current = true;
    };
  }, []);

  // Auto-scroll logs
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [debugLogs, autoScroll]);

  // Start debug execution
  const handleStart = useCallback(async () => {
    try {
      setDebugState('running');
      clearNodeExecutionResults();
      clearDebugLogs();
      
      addDebugLog({ level: 'info', message: t('workflows.debug.starting') });
      
      const response = await backendClient.startWorkflowDebug(workflowId, {
        context: {
          message_content: debugContext.messageContent,
          sender_id: debugContext.senderId,
          sender_name: debugContext.senderName,
          platform: debugContext.platform,
          conversation_id: debugContext.conversationId,
          is_group: debugContext.isGroup,
        },
        variables: debugContext.customVariables,
        breakpoints: Object.keys(breakpoints).filter(k => breakpoints[k]),
      });
      
      setDebugExecutionId(response.execution_id);
      addDebugLog({ level: 'info', message: t('workflows.debug.started', { id: response.execution_id }) });
      
      // Start polling for state updates
      pollDebugState(response.execution_id);
    } catch (error) {
      setDebugState('error');
      addDebugLog({ level: 'error', message: `${t('workflows.debug.startError')}: ${error}` });
    }
  }, [workflowId, debugContext, breakpoints, t]);

  // Poll debug state
  const pollDebugState = useCallback(async (executionId: string) => {
    pollCancelledRef.current = false;
    const poll = async () => {
      if (pollCancelledRef.current) return;
      try {
        const state = await backendClient.getWorkflowDebugState(workflowId, executionId);
        if (pollCancelledRef.current) return;
        
        setDebugState(state.status as typeof debugState);
        setCurrentNodeId(state.current_node_id || null);
        
        // Update node execution results
        if (state.node_states) {
          for (const [nodeId, nodeState] of Object.entries(state.node_states)) {
            updateNodeExecutionResult(nodeId, nodeState as Partial<NodeExecutionResult>);
          }
        }
        
        // Add new logs
        if (state.new_logs) {
          for (const log of state.new_logs) {
            addDebugLog(log);
          }
        }
        
        // Continue polling if still running or paused
        if (!pollCancelledRef.current && (state.status === 'running' || state.status === 'paused')) {
          setTimeout(poll, 500);
        } else if (state.status === 'completed') {
          addDebugLog({ level: 'info', message: t('workflows.debug.completed') });
        } else if (state.status === 'error') {
          addDebugLog({ level: 'error', message: state.error || t('workflows.debug.unknownError') });
        }
      } catch (error) {
        console.error('Failed to poll debug state:', error);
      }
    };
    
    poll();
  }, [workflowId, t]);

  // Pause execution
  const handlePause = useCallback(async () => {
    if (!debugExecutionId) return;
    
    try {
      await backendClient.pauseWorkflowDebug(workflowId, debugExecutionId);
      setDebugState('paused');
      addDebugLog({ level: 'info', message: t('workflows.debug.paused') });
    } catch (error) {
      addDebugLog({ level: 'error', message: `${t('workflows.debug.pauseError')}: ${error}` });
    }
  }, [workflowId, debugExecutionId, t]);

  // Resume execution
  const handleResume = useCallback(async () => {
    if (!debugExecutionId) return;
    
    try {
      await backendClient.resumeWorkflowDebug(workflowId, debugExecutionId);
      setDebugState('running');
      addDebugLog({ level: 'info', message: t('workflows.debug.resumed') });
      pollDebugState(debugExecutionId);
    } catch (error) {
      addDebugLog({ level: 'error', message: `${t('workflows.debug.resumeError')}: ${error}` });
    }
  }, [workflowId, debugExecutionId, t, pollDebugState]);

  // Step execution
  const handleStep = useCallback(async () => {
    if (!debugExecutionId) return;
    
    try {
      const result = await backendClient.stepWorkflowDebug(workflowId, debugExecutionId);
      
      if (result.node_id) {
        setCurrentNodeId(result.node_id);
        updateNodeExecutionResult(result.node_id, result.node_state as Partial<NodeExecutionResult>);
        addDebugLog({ 
          level: 'info', 
          message: t('workflows.debug.steppedTo', { node: result.node_id }),
          nodeId: result.node_id,
        });
      }
      
      if (result.completed) {
        setDebugState('completed');
        addDebugLog({ level: 'info', message: t('workflows.debug.completed') });
      }
    } catch (error) {
      addDebugLog({ level: 'error', message: `${t('workflows.debug.stepError')}: ${error}` });
    }
  }, [workflowId, debugExecutionId, t]);

  // Stop execution
  const handleStop = useCallback(async () => {
    if (!debugExecutionId) return;
    
    try {
      await backendClient.stopWorkflowDebug(workflowId, debugExecutionId);
      resetDebugState();
      addDebugLog({ level: 'info', message: t('workflows.debug.stopped') });
    } catch (error) {
      addDebugLog({ level: 'error', message: `${t('workflows.debug.stopError')}: ${error}` });
    }
  }, [workflowId, debugExecutionId, t, resetDebugState]);

  // Toggle node expansion
  const toggleNodeExpanded = (nodeId: string) => {
    setExpandedNodes((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  };

  // Add custom variable
  const handleAddVariable = () => {
    if (newVariable.key.trim()) {
      try {
        const value = JSON.parse(newVariable.value);
        setDebugContext({
          customVariables: {
            ...debugContext.customVariables,
            [newVariable.key]: value,
          },
        });
      } catch {
        setDebugContext({
          customVariables: {
            ...debugContext.customVariables,
            [newVariable.key]: newVariable.value,
          },
        });
      }
      setNewVariable({ key: '', value: '' });
    }
  };

  // Remove custom variable
  const handleRemoveVariable = (key: string) => {
    const newVars = { ...debugContext.customVariables };
    delete newVars[key];
    setDebugContext({ customVariables: newVars });
  };

  const isRunning = debugState === 'running';
  const isPaused = debugState === 'paused';
  const canStart = debugState === 'idle' || debugState === 'completed' || debugState === 'error';

  return (
    <div className="flex flex-col h-full bg-background border-l">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <Bug className="size-5 text-primary" />
          <span className="font-semibold">{t('workflows.debug.title')}</span>
          {debugState !== 'idle' && (
            <Badge variant={isRunning ? 'default' : isPaused ? 'secondary' : 'outline'}>
              {t(`workflows.debug.state.${debugState}`)}
            </Badge>
          )}
        </div>
        {onClose && (
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="size-4" />
          </Button>
        )}
      </div>

      {/* Control Bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b bg-muted/30">
        {canStart ? (
          <Button size="sm" onClick={handleStart} className="gap-1">
            <Play className="size-4" />
            {t('workflows.debug.start')}
          </Button>
        ) : (
          <>
            {isRunning ? (
              <Button size="sm" variant="secondary" onClick={handlePause} className="gap-1">
                <Pause className="size-4" />
                {t('workflows.debug.pause')}
              </Button>
            ) : (
              <Button size="sm" onClick={handleResume} className="gap-1">
                <Play className="size-4" />
                {t('workflows.debug.resume')}
              </Button>
            )}
            <Button size="sm" variant="outline" onClick={handleStep} disabled={isRunning} className="gap-1">
              <StepForward className="size-4" />
              {t('workflows.debug.step')}
            </Button>
            <Button size="sm" variant="destructive" onClick={handleStop} className="gap-1">
              <Square className="size-4" />
              {t('workflows.debug.stop')}
            </Button>
          </>
        )}
        
        <div className="flex-1" />
        
        <Button size="sm" variant="ghost" onClick={clearBreakpoints} title={t('workflows.debug.clearBreakpoints')}>
          <Circle className="size-4" />
        </Button>
        <Button size="sm" variant="ghost" onClick={clearDebugLogs} title={t('workflows.debug.clearLogs')}>
          <Trash2 className="size-4" />
        </Button>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
        <TabsList className="mx-4 mt-2 justify-start">
          <TabsTrigger value="context" className="gap-1">
            <Terminal className="size-4" />
            {t('workflows.debug.context')}
          </TabsTrigger>
          <TabsTrigger value="variables" className="gap-1">
            <Eye className="size-4" />
            {t('workflows.debug.variables')}
          </TabsTrigger>
          <TabsTrigger value="nodes" className="gap-1">
            <CheckCircle2 className="size-4" />
            {t('workflows.debug.nodeStates')}
          </TabsTrigger>
          <TabsTrigger value="logs" className="gap-1">
            <Terminal className="size-4" />
            {t('workflows.debug.logs')}
            {debugLogs.length > 0 && (
              <Badge variant="secondary" className="ml-1 text-xs">
                {debugLogs.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* Context Tab */}
        <TabsContent value="context" className="flex-1 p-4 overflow-auto">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t('workflows.debug.messageContent')}</Label>
              <Textarea
                value={debugContext.messageContent}
                onChange={(e) => setDebugContext({ messageContent: e.target.value })}
                placeholder={t('workflows.debug.messageContentPlaceholder')}
                className="min-h-[80px]"
                disabled={!canStart}
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t('workflows.debug.senderId')}</Label>
                <Input
                  value={debugContext.senderId}
                  onChange={(e) => setDebugContext({ senderId: e.target.value })}
                  placeholder={t('workflows.debug.senderIdPlaceholder')}
                  disabled={!canStart}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('workflows.debug.senderName')}</Label>
                <Input
                  value={debugContext.senderName}
                  onChange={(e) => setDebugContext({ senderName: e.target.value })}
                  placeholder={t('workflows.debug.senderNamePlaceholder')}
                  disabled={!canStart}
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t('workflows.debug.platform')}</Label>
                <Input
                  value={debugContext.platform}
                  onChange={(e) => setDebugContext({ platform: e.target.value })}
                  placeholder={t('workflows.debug.platformPlaceholder')}
                  disabled={!canStart}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('workflows.debug.conversationId')}</Label>
                <Input
                  value={debugContext.conversationId}
                  onChange={(e) => setDebugContext({ conversationId: e.target.value })}
                  placeholder={t('workflows.debug.conversationIdPlaceholder')}
                  disabled={!canStart}
                />
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Switch
                checked={debugContext.isGroup}
                onCheckedChange={(checked) => setDebugContext({ isGroup: checked })}
                disabled={!canStart}
              />
              <Label>{t('workflows.debug.isGroup')}</Label>
            </div>

            {/* Custom Variables */}
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-sm">{t('workflows.debug.customVariables')}</CardTitle>
                <CardDescription className="text-xs">
                  {t('workflows.debug.customVariablesDesc')}
                </CardDescription>
              </CardHeader>
              <CardContent className="py-2">
                <div className="space-y-2">
                  {Object.entries(debugContext.customVariables).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-2">
                      <code className="text-xs bg-muted px-2 py-1 rounded flex-1">
                        {key}: {JSON.stringify(value)}
                      </code>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-6"
                        onClick={() => handleRemoveVariable(key)}
                        disabled={!canStart}
                      >
                        <X className="size-3" />
                      </Button>
                    </div>
                  ))}
                  
                  <div className="flex gap-2">
                    <Input
                      placeholder={t('workflows.debug.variableKey')}
                      value={newVariable.key}
                      onChange={(e) => setNewVariable({ ...newVariable, key: e.target.value })}
                      className="text-xs"
                      disabled={!canStart}
                    />
                    <Input
                      placeholder={t('workflows.debug.variableValue')}
                      value={newVariable.value}
                      onChange={(e) => setNewVariable({ ...newVariable, value: e.target.value })}
                      className="text-xs"
                      disabled={!canStart}
                    />
                    <Button
                      size="icon"
                      variant="outline"
                      onClick={handleAddVariable}
                      disabled={!canStart}
                    >
                      <Plus className="size-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Button variant="outline" size="sm" onClick={resetDebugContext} disabled={!canStart}>
              <RefreshCw className="size-4 mr-2" />
              {t('workflows.debug.resetContext')}
            </Button>
          </div>
        </TabsContent>

        {/* Variables Tab */}
        <TabsContent value="variables" className="flex-1 p-4 overflow-auto">
          <div className="space-y-4">
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-sm">{t('workflows.debug.watchedVariables')}</CardTitle>
              </CardHeader>
              <CardContent className="py-2">
                {watchedVariables.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t('workflows.debug.noWatchedVariables')}
                  </p>
                ) : (
                  <div className="space-y-1">
                    {watchedVariables.map((variable) => {
                      // Try to find value from node outputs
                      let value: unknown = undefined;
                      const parts = variable.split('.');
                      if (parts[0] === 'nodes' && parts.length >= 3) {
                        const nodeId = parts[1];
                        const outputKey = parts.slice(2).join('.');
                        const nodeResult = nodeExecutionResults[nodeId];
                        if (nodeResult?.outputs) {
                          value = nodeResult.outputs[outputKey];
                        }
                      }

                      return (
                        <div key={variable} className="flex items-center gap-2">
                          <code className="text-xs bg-muted px-2 py-1 rounded flex-1 font-mono">
                            {variable} = {value !== undefined ? JSON.stringify(value) : 'undefined'}
                          </code>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="size-6"
                            onClick={() => removeWatchedVariable(variable)}
                          >
                            <X className="size-3" />
                          </Button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Node Outputs */}
            <Card>
              <CardHeader className="py-3">
                <CardTitle className="text-sm">{t('workflows.debug.nodeOutputs')}</CardTitle>
              </CardHeader>
              <CardContent className="py-2">
                {Object.keys(nodeExecutionResults).length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t('workflows.debug.noNodeOutputs')}
                  </p>
                ) : (
                  <div className="space-y-2">
                    {Object.entries(nodeExecutionResults).map(([nodeId, result]) => {
                      const node = nodes.find((n) => n.id === nodeId);
                      return (
                        <Collapsible key={nodeId}>
                          <CollapsibleTrigger className="flex items-center gap-2 w-full text-left">
                            <ChevronRight className="size-4 transition-transform data-[state=open]:rotate-90" />
                            <span className="text-sm font-medium">
                              {node?.data.label || nodeId}
                            </span>
                            {result.outputs && Object.keys(result.outputs).length > 0 && (
                              <Badge variant="secondary" className="text-xs">
                                {Object.keys(result.outputs).length} outputs
                              </Badge>
                            )}
                          </CollapsibleTrigger>
                          <CollapsibleContent className="pl-6 pt-2">
                            {result.outputs ? (
                              <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-40">
                                {JSON.stringify(result.outputs, null, 2)}
                              </pre>
                            ) : (
                              <p className="text-xs text-muted-foreground">No outputs</p>
                            )}
                          </CollapsibleContent>
                        </Collapsible>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Node States Tab */}
        <TabsContent value="nodes" className="flex-1 p-4 overflow-auto">
          <div className="space-y-2">
            {nodes.map((node) => {
              const result = nodeExecutionResults[node.id];
              const StatusIcon = result ? statusIcons[result.status] || Clock : Clock;
              const statusColor = result ? statusColors[result.status] || '' : 'text-gray-400';
              const isCurrentNode = currentNodeId === node.id;
              const hasBreakpoint = !!breakpoints[node.id];

              return (
                <Card
                  key={node.id}
                  className={`${isCurrentNode ? 'border-primary ring-1 ring-primary' : ''}`}
                >
                  <CardHeader className="py-2 px-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleBreakpoint(node.id)}
                          className={`size-4 rounded-full border-2 ${
                            hasBreakpoint
                              ? 'bg-red-500 border-red-500'
                              : 'border-gray-400 hover:border-red-400'
                          }`}
                          title={t('workflows.debug.toggleBreakpoint')}
                        />
                        <StatusIcon className={`size-4 ${statusColor}`} />
                        <span className="text-sm font-medium">{node.data.label}</span>
                        <Badge variant="outline" className="text-xs">
                          {node.data.type}
                        </Badge>
                      </div>
                      {result?.duration !== undefined && (
                        <span className="text-xs text-muted-foreground">
                          {result.duration}ms
                        </span>
                      )}
                    </div>
                  </CardHeader>
                  {result?.error && (
                    <CardContent className="py-2 px-3">
                      <div className="text-xs text-red-500 bg-red-50 dark:bg-red-950 p-2 rounded">
                        {result.error}
                      </div>
                    </CardContent>
                  )}
                </Card>
              );
            })}
          </div>
        </TabsContent>

        {/* Logs Tab */}
        <TabsContent value="logs" className="flex-1 flex flex-col min-h-0">
          <div className="flex items-center justify-between px-4 py-2 border-b">
            <div className="flex items-center gap-2">
              <Switch
                checked={autoScroll}
                onCheckedChange={setAutoScroll}
                className="scale-75"
              />
              <Label className="text-xs">{t('workflows.debug.autoScroll')}</Label>
            </div>
            <span className="text-xs text-muted-foreground">
              {debugLogs.length} {t('workflows.debug.logEntries')}
            </span>
          </div>
          <ScrollArea className="flex-1 p-4">
            <div className="space-y-1 font-mono text-xs">
              {debugLogs.length === 0 ? (
                <p className="text-muted-foreground">{t('workflows.debug.noLogs')}</p>
              ) : (
                debugLogs.map((log) => (
                  <div key={log.id} className="flex gap-2">
                    <span className="text-muted-foreground shrink-0">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                    <span className={`shrink-0 uppercase ${logLevelColors[log.level]}`}>
                      [{log.level}]
                    </span>
                    {log.nodeId && (
                      <span className="text-purple-400 shrink-0">[{log.nodeId}]</span>
                    )}
                    <span className="text-foreground">{log.message}</span>
                    {log.data && (
                      <span className="text-muted-foreground">
                        {JSON.stringify(log.data)}
                      </span>
                    )}
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}
