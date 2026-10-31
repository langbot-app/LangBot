import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { backendClient } from '@/app/infra/http';
import type { WorkflowExecution } from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import { ExecutionDetail } from '../workflow-debug-dialog/WorkflowDebugDialog';

export default function WorkflowExecutionsTab({
  workflowId,
}: {
  workflowId: string;
}) {
  const { t } = useTranslation();
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [selected, setSelected] = useState<WorkflowExecution>();
  const [error, setError] = useState('');
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const load = useCallback(async () => {
    try {
      const result = await backendClient.getWorkflowExecutions(
        workflowId,
        20,
        offset,
      );
      setExecutions(result.executions);
      setTotal(result.total);
      setError('');
    } catch (error) {
      setError(String(error));
    }
  }, [workflowId, offset]);
  useEffect(() => {
    void load();
  }, [load]);
  async function select(uuid: string) {
    try {
      setSelected(
        (await backendClient.getWorkflowExecution(workflowId, uuid)).execution,
      );
    } catch (error) {
      setError(String(error));
    }
  }
  return (
    <div className="space-y-4 overflow-auto p-2">
      <Button onClick={() => void load()}>{t('common.refresh')}</Button>
      {error && <p role="alert">{error}</p>}
      {executions.map((execution) => (
        <button
          key={execution.uuid}
          className="block w-full rounded border p-3 text-left"
          onClick={() => void select(execution.uuid)}
        >
          {execution.started_at} — {execution.uuid} — {execution.status}
        </button>
      ))}
      <Button
        disabled={offset === 0}
        onClick={() => setOffset(Math.max(0, offset - 20))}
      >
        {t('common.previous')}
      </Button>
      <Button
        disabled={offset + 20 >= total}
        onClick={() => setOffset(offset + 20)}
      >
        {t('common.next')}
      </Button>
      {selected && <ExecutionDetail execution={selected} />}
    </div>
  );
}
