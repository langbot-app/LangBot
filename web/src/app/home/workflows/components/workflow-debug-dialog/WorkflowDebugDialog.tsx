import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CircleAlert, FlaskConical, Loader2, Play } from 'lucide-react';
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import type { WorkflowExecution } from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { ExecutionDetail } from '../workflow-executions/ExecutionDetail';

export default function WorkflowDebugDialog({
  workflowId,
}: {
  workflowId: string;
}) {
  const { t } = useTranslation();
  const canRun = useCurrentWorkspace()?.permissions.includes('runtime.operate');
  const [message, setMessage] = useState('');
  const [sessionType, setSessionType] = useState<'person' | 'group'>('person');
  const [running, setRunning] = useState(false);
  const [replies, setReplies] = useState<string[] | null>(null);
  const [execution, setExecution] = useState<WorkflowExecution>();
  const [error, setError] = useState('');

  async function run() {
    useWorkflowStore.getState().clearNodeExecutionResults();
    setRunning(true);
    setError('');
    setReplies(null);
    setExecution(undefined);
    try {
      const result = await backendClient.runWorkflow(workflowId, {
        message,
        session_type: sessionType,
      });
      setReplies(result.replies);
      const detail = await backendClient.getWorkflowExecution(
        workflowId,
        result.execution_uuid,
      );
      setExecution(detail.execution);
      for (const node of detail.execution.node_executions || []) {
        useWorkflowStore.getState().updateNodeExecutionResult(node.node_id, {
          status: node.status,
          inputs: node.inputs,
          outputs: node.outputs,
          error: node.error,
        });
      }
    } catch (error) {
      setError(String(error));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="grid h-full min-h-0 gap-4 lg:grid-cols-[minmax(280px,380px)_1fr]">
      <div className="flex h-fit flex-col gap-4 rounded-xl border bg-card p-4">
        <div className="space-y-1">
          <p className="text-sm font-medium">{t('workflows.testRun')}</p>
          <p className="text-xs text-muted-foreground">
            {t('workflows.run.runHint')}
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="workflow-test-message">
            {t('workflows.testInput')}
          </Label>
          <Textarea
            id="workflow-test-message"
            rows={5}
            value={message}
            placeholder={t('workflows.run.messagePlaceholder')}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === 'Enter' &&
                (event.metaKey || event.ctrlKey) &&
                canRun &&
                !running &&
                message.trim()
              ) {
                event.preventDefault();
                void run();
              }
            }}
          />
        </div>
        <div className="space-y-2">
          <Label>{t('workflows.sessionType')}</Label>
          <Select
            value={sessionType}
            onValueChange={(value) =>
              setSessionType(value as 'person' | 'group')
            }
          >
            <SelectTrigger
              className="w-full"
              aria-label={t('workflows.sessionType')}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="person">{t('workflows.person')}</SelectItem>
              <SelectItem value="group">{t('workflows.group')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button
          onClick={() => void run()}
          disabled={!canRun || running || !message.trim()}
        >
          {running ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Play className="size-4" />
          )}
          {t('workflows.run.start')}
        </Button>
        {!canRun && (
          <p className="text-xs text-muted-foreground">
            {t('workflows.run.noPermission')}
          </p>
        )}
      </div>

      <div className="min-h-0 space-y-4 overflow-y-auto">
        {error && (
          <p
            role="alert"
            className="flex items-start gap-2 rounded-xl border border-red-200/70 bg-red-50/70 p-3 text-sm text-red-700 dark:border-red-800/50 dark:bg-red-950/30 dark:text-red-300"
          >
            <CircleAlert className="mt-0.5 size-4 shrink-0" />
            <span className="break-all">{error}</span>
          </p>
        )}
        {replies === null && !error ? (
          <div className="flex h-full min-h-80 flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-8 text-center">
            <FlaskConical className="size-8 text-muted-foreground" />
            <p className="max-w-sm text-sm text-muted-foreground">
              {running ? t('workflows.run.running') : t('workflows.run.empty')}
            </p>
          </div>
        ) : (
          replies !== null && (
            <div className="space-y-2 rounded-xl border bg-card p-4">
              <p className="text-sm font-medium">{t('workflows.replies')}</p>
              {replies.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {t('workflows.run.noReplies')}
                </p>
              ) : (
                replies.map((reply, index) => (
                  <div
                    key={index}
                    data-testid="workflow-test-reply"
                    className="w-fit max-w-full rounded-2xl rounded-tl-sm bg-muted px-3.5 py-2 text-sm whitespace-pre-wrap break-words"
                  >
                    {reply}
                  </div>
                ))
              )}
            </div>
          )
        )}
        {execution && <ExecutionDetail execution={execution} />}
      </div>
    </div>
  );
}
