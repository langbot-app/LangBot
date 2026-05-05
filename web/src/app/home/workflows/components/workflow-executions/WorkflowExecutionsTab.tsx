import { useState, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { backendClient } from '@/app/infra/http';
import { WorkflowExecution } from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { 
  RefreshCw, 
  Play, 
  XCircle, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Loader2,
  FileText,
  RotateCcw,
  Filter,
  TrendingUp,
  Calendar,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';

interface WorkflowExecutionsTabProps {
  workflowId: string;
}

interface ExecutionLog {
  id: string;
  timestamp: string;
  level: string;
  node_id?: string;
  message: string;
  data?: Record<string, unknown>;
}

interface WorkflowStats {
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  success_rate: number;
  average_duration_ms: number;
  last_execution_time?: string;
}

const statusIcons: Record<string, React.ElementType> = {
  pending: Clock,
  running: Loader2,
  completed: CheckCircle2,
  failed: AlertCircle,
  cancelled: XCircle,
};

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  running: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  completed: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  cancelled: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
};

const logLevelColors: Record<string, string> = {
  info: 'text-blue-600 dark:text-blue-400',
  warning: 'text-yellow-600 dark:text-yellow-400',
  error: 'text-red-600 dark:text-red-400',
  debug: 'text-gray-600 dark:text-gray-400',
};

export default function WorkflowExecutionsTab({
  workflowId,
}: WorkflowExecutionsTabProps) {
  const { t } = useTranslation();
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedExecution, setSelectedExecution] = useState<WorkflowExecution | null>(null);
  const [total, setTotal] = useState(0);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [dateFilter, setDateFilter] = useState<string>('all');
  
  // Statistics
  const [stats, setStats] = useState<WorkflowStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [showStats, setShowStats] = useState(true);
  
  // Logs
  const [executionLogs, setExecutionLogs] = useState<ExecutionLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [selectedTab, setSelectedTab] = useState('details');
  
  // Rerun
  const [rerunning, setRerunning] = useState<string | null>(null);

  // Load executions
  const loadExecutions = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await backendClient.getWorkflowExecutions(workflowId, 50, 0);
      setExecutions(resp.executions || []);
      setTotal(resp.total ?? resp.executions?.length ?? 0);
    } catch (err) {
      // Silently handle connection errors — don't spam console on backend down
      setExecutions([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  // Load statistics
  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const resp = await backendClient.getWorkflowStats(workflowId);
      setStats(resp ?? null);
    } catch {
      // Backend might not support stats endpoint yet — just show empty
      setStats(null);
    } finally {
      setStatsLoading(false);
    }
  }, [workflowId]);

  // Load execution logs
  const loadExecutionLogs = useCallback(async (executionUuid: string) => {
    setLogsLoading(true);
    try {
      const resp = await backendClient.getWorkflowExecutionLogs(workflowId, executionUuid, 200, 0);
      setExecutionLogs(resp.logs);
    } catch (err) {
      console.error('Failed to load execution logs:', err);
      setExecutionLogs([]);
    } finally {
      setLogsLoading(false);
    }
  }, [workflowId]);

  useEffect(() => {
    loadExecutions();
    loadStats();
  }, [loadExecutions, loadStats]);

  // Filter executions
  const filteredExecutions = useMemo(() => {
    let filtered = executions;
    
    // Status filter
    if (statusFilter !== 'all') {
      filtered = filtered.filter(e => e.status === statusFilter);
    }
    
    // Date filter
    if (dateFilter !== 'all') {
      const now = new Date();
      let startDate: Date;
      
      switch (dateFilter) {
        case 'today':
          startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
          break;
        case 'week':
          startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
          break;
        case 'month':
          startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
          break;
        default:
          startDate = new Date(0);
      }
      
      filtered = filtered.filter(e => {
        if (!e.started_at) return false;
        return new Date(e.started_at) >= startDate;
      });
    }
    
    return filtered;
  }, [executions, statusFilter, dateFilter]);

  // Manual trigger
  const handleManualTrigger = useCallback(async () => {
    try {
      await backendClient.executeWorkflow(workflowId, {
        trigger_type: 'manual',
      });
      toast.success(t('workflows.manualTrigger') + ' ✓');
      loadExecutions();
      loadStats();
    } catch (err: unknown) {
      const msg = (err as { msg?: string })?.msg || String(err);
      toast.error(`${t('workflows.manualTrigger')}: ${msg}`);
    }
  }, [workflowId, loadExecutions, loadStats, t]);

  // View execution details
  const handleViewDetails = useCallback(async (executionUuid: string) => {
    try {
      const resp = await backendClient.getWorkflowExecution(workflowId, executionUuid);
      setSelectedExecution(resp.execution);
      setSelectedTab('details');
      loadExecutionLogs(executionUuid);
    } catch (err: unknown) {
      const msg = (err as { msg?: string })?.msg || String(err);
      toast.error(`${t('workflows.executionDetails')}: ${msg}`);
    }
  }, [workflowId, loadExecutionLogs, t]);

  // Cancel execution
  const handleCancel = useCallback(async (executionUuid: string) => {
    try {
      await backendClient.cancelWorkflowExecution(workflowId, executionUuid);
      toast.success(t('common.cancel') + ' ✓');
      loadExecutions();
    } catch (err: unknown) {
      const msg = (err as { msg?: string })?.msg || String(err);
      toast.error(`${t('common.cancel')}: ${msg}`);
    }
  }, [workflowId, loadExecutions, t]);

  // Rerun execution
  const handleRerun = useCallback(async (executionUuid: string) => {
    setRerunning(executionUuid);
    try {
      await backendClient.rerunWorkflowExecution(workflowId, executionUuid);
      toast.success(t('workflows.rerun') + ' ✓');
      loadExecutions();
      loadStats();
    } catch (err: unknown) {
      const msg = (err as { msg?: string })?.msg || String(err);
      toast.error(`${t('workflows.rerun')}: ${msg}`);
    } finally {
      setRerunning(null);
    }
  }, [workflowId, loadExecutions, loadStats, t]);

  // Format duration
  const formatDuration = (seconds: number): string => {
    if (seconds === null || seconds === undefined || isNaN(seconds)) return '0.0s';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs.toFixed(0)}s`;
  };

  return (
    <div className="space-y-4">
      {/* Statistics Panel */}
      <Collapsible open={showStats} onOpenChange={setShowStats}>
        <CollapsibleTrigger asChild>
          <Button variant="ghost" className="w-full justify-between p-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="size-4" />
              <span className="font-medium">{t('workflows.statistics')}</span>
            </div>
            {showStats ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          {statsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          ) : stats ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {t('workflows.totalExecutions', { count: stats.total_executions ?? 0 })}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stats.total_executions ?? 0}</div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {t('workflows.successfulCount', { count: stats.successful_executions ?? 0 })}
                  </p>
                </CardContent>
              </Card>
              
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {t('workflows.successRate')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                    {((stats.success_rate ?? 0) * 100).toFixed(1)}%
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {stats.successful_executions ?? 0} / {stats.total_executions ?? 0}
                  </p>
                </CardContent>
              </Card>
              
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {t('workflows.averageDuration')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {formatDuration((stats.average_duration_ms ?? 0) / 1000)}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {t('workflows.perExecution')}
                  </p>
                </CardContent>
              </Card>
              
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {t('workflows.failedExecutions')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                    {stats.failed_executions ?? 0}
                  </div>
                  {stats.last_execution_time && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {t('workflows.lastExecution')}: {new Date(stats.last_execution_time).toLocaleDateString()}
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="text-center py-4 text-sm text-muted-foreground">
              {t('workflows.noExecutions')}
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>

      {/* Toolbar with Filters */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="size-4 text-muted-foreground" />
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder={t('workflows.filterByStatus')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('workflows.allStatuses')}</SelectItem>
                <SelectItem value="completed">{t('workflows.status.completed')}</SelectItem>
                <SelectItem value="running">{t('workflows.status.running')}</SelectItem>
                <SelectItem value="failed">{t('workflows.status.failed')}</SelectItem>
                <SelectItem value="cancelled">{t('workflows.status.cancelled')}</SelectItem>
                <SelectItem value="pending">{t('workflows.status.pending')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          <div className="flex items-center gap-2">
            <Calendar className="size-4 text-muted-foreground" />
            <Select value={dateFilter} onValueChange={setDateFilter}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder={t('workflows.filterByDate')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('workflows.allTime')}</SelectItem>
                <SelectItem value="today">{t('workflows.today')}</SelectItem>
                <SelectItem value="week">{t('workflows.lastWeek')}</SelectItem>
                <SelectItem value="month">{t('workflows.lastMonth')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          <div className="text-sm text-muted-foreground">
            {t('workflows.showingExecutions', { 
              shown: filteredExecutions.length, 
              total: total 
            })}
          </div>
        </div>
        
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => { loadExecutions(); loadStats(); }} disabled={loading}>
            <RefreshCw className={`size-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </Button>
          <Button size="sm" onClick={handleManualTrigger}>
            <Play className="size-4 mr-2" />
            {t('workflows.manualTrigger')}
          </Button>
        </div>
      </div>

      {/* Executions Table */}
      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('workflows.executionId')}</TableHead>
              <TableHead>{t('workflows.status')}</TableHead>
              <TableHead>{t('workflows.triggerType')}</TableHead>
              <TableHead>{t('workflows.startedAt')}</TableHead>
              <TableHead>{t('workflows.duration')}</TableHead>
              <TableHead>{t('common.actions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredExecutions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  {loading ? t('common.loading') : t('workflows.noExecutions')}
                </TableCell>
              </TableRow>
            ) : (
              filteredExecutions.map((execution) => {
                const StatusIcon = statusIcons[execution.status] || Clock;
                const duration = execution.completed_at && execution.started_at
                  ? Math.round((new Date(execution.completed_at).getTime() - new Date(execution.started_at).getTime()) / 1000)
                  : null;

                return (
                  <TableRow key={execution.uuid}>
                    <TableCell className="font-mono text-xs">
                      {execution.uuid.slice(0, 8)}...
                    </TableCell>
                    <TableCell>
                      <Badge className={statusColors[execution.status]}>
                        <StatusIcon className={`size-3 mr-1 ${execution.status === 'running' ? 'animate-spin' : ''}`} />
                        {t(`workflows.status.${execution.status}`)}
                      </Badge>
                    </TableCell>
                    <TableCell>{execution.trigger_type || '-'}</TableCell>
                    <TableCell>
                      {execution.started_at
                        ? new Date(execution.started_at).toLocaleString()
                        : '-'}
                    </TableCell>
                    <TableCell>
                      {duration !== null ? `${duration}s` : '-'}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewDetails(execution.uuid)}
                        >
                          {t('common.details')}
                        </Button>
                        {execution.status === 'running' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleCancel(execution.uuid)}
                          >
                            {t('common.cancel')}
                          </Button>
                        )}
                        {(execution.status === 'completed' || execution.status === 'failed') && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRerun(execution.uuid)}
                            disabled={rerunning === execution.uuid}
                          >
                            {rerunning === execution.uuid ? (
                              <Loader2 className="size-3 animate-spin mr-1" />
                            ) : (
                              <RotateCcw className="size-3 mr-1" />
                            )}
                            {t('workflows.rerun')}
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Execution Details Dialog */}
      <Dialog open={!!selectedExecution} onOpenChange={() => setSelectedExecution(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>{t('workflows.executionDetails')}</DialogTitle>
            <DialogDescription>
              {selectedExecution?.uuid}
            </DialogDescription>
          </DialogHeader>

          {selectedExecution && (
            <Tabs value={selectedTab} onValueChange={setSelectedTab} className="flex-1 flex flex-col overflow-hidden">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="details">{t('workflows.details')}</TabsTrigger>
                <TabsTrigger value="nodes">{t('workflows.nodeExecutions')}</TabsTrigger>
                <TabsTrigger value="logs">
                  <FileText className="size-3 mr-1" />
                  {t('workflows.logs')}
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="details" className="flex-1 overflow-auto space-y-4 mt-4">
                {/* Summary */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">{t('workflows.status')}:</span>
                    <Badge className={`ml-2 ${statusColors[selectedExecution.status]}`}>
                      {t(`workflows.status.${selectedExecution.status}`)}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t('workflows.triggerType')}:</span>
                    <span className="ml-2">{selectedExecution.trigger_type || '-'}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t('workflows.startedAt')}:</span>
                    <span className="ml-2">
                      {selectedExecution.started_at 
                        ? new Date(selectedExecution.started_at).toLocaleString() 
                        : '-'}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t('workflows.completedAt')}:</span>
                    <span className="ml-2">
                      {selectedExecution.completed_at 
                        ? new Date(selectedExecution.completed_at).toLocaleString() 
                        : '-'}
                    </span>
                  </div>
                </div>

                {/* Error message */}
                {selectedExecution.error && (
                  <div className="bg-destructive/10 border border-destructive/20 rounded p-3">
                    <div className="text-sm font-medium text-destructive mb-1">
                      {t('workflows.error')}
                    </div>
                    <div className="text-sm text-destructive/80 font-mono whitespace-pre-wrap">
                      {selectedExecution.error}
                    </div>
                  </div>
                )}

                {/* Result */}
                {selectedExecution.result && (
                  <div>
                    <h4 className="font-medium mb-2">{t('workflows.result')}</h4>
                    <pre className="bg-muted p-3 rounded text-xs overflow-x-auto max-h-[200px]">
                      {JSON.stringify(selectedExecution.result, null, 2)}
                    </pre>
                  </div>
                )}
                
                {/* Rerun button */}
                <div className="flex justify-end pt-4">
                  <Button 
                    onClick={() => {
                      handleRerun(selectedExecution.uuid);
                      setSelectedExecution(null);
                    }}
                    disabled={selectedExecution.status === 'running'}
                  >
                    <RotateCcw className="size-4 mr-2" />
                    {t('workflows.rerunExecution')}
                  </Button>
                </div>
              </TabsContent>
              
              <TabsContent value="nodes" className="flex-1 overflow-auto mt-4">
                {selectedExecution.node_executions && selectedExecution.node_executions.length > 0 ? (
                  <ScrollArea className="h-[400px]">
                    <div className="space-y-2 pr-4">
                      {selectedExecution.node_executions.map((nodeExec) => {
                        const NodeStatusIcon = statusIcons[nodeExec.status] || Clock;
                        const isFailedNode = nodeExec.status === 'failed';
                        return (
                          <div
                            key={nodeExec.node_id}
                            className={`border rounded p-3 text-sm ${
                              isFailedNode
                                ? 'border-red-300 bg-red-50/70 dark:border-red-800 dark:bg-red-950/20'
                                : 'border-border'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 min-w-0 flex-wrap">
                                  <span className={isFailedNode ? 'font-medium text-red-700 dark:text-red-300 break-all' : 'font-medium break-all'}>
                                    {nodeExec.node_id}
                                  </span>
                                  {typeof nodeExec.retry_count === 'number' && nodeExec.retry_count > 0 && (
                                    <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5">
                                      retry {nodeExec.retry_count}
                                    </Badge>
                                  )}
                                </div>
                                <div
                                  className={`text-xs mt-1 break-all ${
                                    isFailedNode
                                      ? 'text-red-600/80 dark:text-red-400/80'
                                      : 'text-muted-foreground'
                                  }`}
                                >
                                  {nodeExec.node_type}
                                </div>
                              </div>
                              <Badge className={`${statusColors[nodeExec.status]} shrink-0`}>
                                <NodeStatusIcon className="size-3 mr-1" />
                                {nodeExec.status}
                              </Badge>
                            </div>
                            {nodeExec.inputs && Object.keys(nodeExec.inputs).length > 0 && (
                              <div className="mt-2">
                                <div className="text-xs text-muted-foreground mb-1">{t('workflows.inputs')}:</div>
                                <pre className="bg-muted p-2 rounded text-xs overflow-x-auto max-h-[100px] whitespace-pre-wrap break-all">
                                  {JSON.stringify(nodeExec.inputs, null, 2)}
                                </pre>
                              </div>
                            )}
                            {nodeExec.outputs && Object.keys(nodeExec.outputs).length > 0 && (
                              <div className="mt-2">
                                <div className="text-xs text-muted-foreground mb-1">{t('workflows.outputs')}:</div>
                                <pre className="bg-muted p-2 rounded text-xs overflow-x-auto max-h-[100px] whitespace-pre-wrap break-all">
                                  {JSON.stringify(nodeExec.outputs, null, 2)}
                                </pre>
                              </div>
                            )}
                            {nodeExec.error && (
                              <div className="mt-2 rounded border border-destructive/20 bg-destructive/10 p-2">
                                <div className="text-[11px] font-medium text-destructive mb-1">
                                  {t('workflows.error')}
                                </div>
                                <div className="text-destructive text-xs whitespace-pre-wrap break-all font-mono">
                                  {nodeExec.error}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </ScrollArea>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {t('workflows.noNodeExecutions')}
                  </div>
                )}
              </TabsContent>
              
              <TabsContent value="logs" className="flex-1 overflow-hidden mt-4">
                {logsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="size-6 animate-spin text-muted-foreground" />
                  </div>
                ) : executionLogs.length > 0 ? (
                  <ScrollArea className="h-[400px] border rounded">
                    <div className="p-2 space-y-1 font-mono text-xs">
                      {executionLogs.map((log) => (
                        <div 
                          key={log.id} 
                          className={`flex gap-2 p-1 hover:bg-muted/50 rounded ${logLevelColors[log.level]}`}
                        >
                          <span className="text-muted-foreground shrink-0">
                            {new Date(log.timestamp).toLocaleTimeString()}
                          </span>
                          <span className="uppercase w-12 shrink-0 font-semibold">
                            [{log.level}]
                          </span>
                          {log.node_id && (
                            <span className="text-muted-foreground shrink-0">
                              [{log.node_id}]
                            </span>
                          )}
                          <span className="flex-1 break-all">{log.message}</span>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {t('workflows.noLogs')}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
