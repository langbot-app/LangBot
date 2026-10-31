import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { backendClient } from '@/app/infra/http';
import type { WorkflowExecution } from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useCurrentWorkspace } from '@/app/infra/http';
import { useWorkflowStore } from '../../store/useWorkflowStore';

export function ExecutionDetail({
  execution,
}: {
  execution: WorkflowExecution;
}) {
  return (
    <div className="space-y-3">
      <p>
        {execution.uuid}: {execution.status}
      </p>
      {execution.error && <p role="alert">{execution.error}</p>}
      {execution.node_executions?.map((node) => (
        <details key={node.node_id} className="rounded border p-3">
          <summary>
            {node.node_id} ({node.node_type}): {node.status}
          </summary>
          <pre className="overflow-auto whitespace-pre-wrap text-xs">
            {JSON.stringify(
              { inputs: node.inputs, outputs: node.outputs, error: node.error },
              null,
              2,
            )}
          </pre>
        </details>
      ))}
    </div>
  );
}

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
  const [replies, setReplies] = useState<string[]>([]);
  const [execution, setExecution] = useState<WorkflowExecution>();
  const [error, setError] = useState('');
  async function run() {
    useWorkflowStore.getState().clearNodeExecutionResults();
    setRunning(true);
    setError('');
    setReplies([]);
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
    <div className="space-y-4 overflow-auto p-2">
      <h2>{t('workflows.testRun')}</h2>
      <Textarea
        aria-label={t('workflows.testInput')}
        value={message}
        onChange={(event) => setMessage(event.target.value)}
      />
      <select
        aria-label={t('workflows.sessionType')}
        value={sessionType}
        onChange={(event) =>
          setSessionType(event.target.value as 'person' | 'group')
        }
      >
        <option value="person">{t('workflows.person')}</option>
        <option value="group">{t('workflows.group')}</option>
      </select>
      <Button
        onClick={() => void run()}
        disabled={!canRun || running || !message.trim()}
      >
        {running ? t('common.loading') : t('workflows.testRun')}
      </Button>
      {error && <p role="alert">{error}</p>}
      <h3>{t('workflows.replies')}</h3>
      {replies.map((reply, index) => (
        <pre key={index} className="whitespace-pre-wrap">
          {reply}
        </pre>
      ))}
      {execution && <ExecutionDetail execution={execution} />}
    </div>
  );
}
