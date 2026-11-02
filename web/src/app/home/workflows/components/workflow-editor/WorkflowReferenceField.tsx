import { useEffect, useState } from 'react';
import { backendClient } from '@/app/infra/http';

export default function WorkflowReferenceField({
  kind,
  label,
  value,
  onChange,
}: {
  kind: 'pipeline-selector' | 'workflow-selector';
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const [options, setOptions] = useState<
    Array<{ uuid?: string; name: string }>
  >([]);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    const request =
      kind === 'workflow-selector'
        ? backendClient.getWorkflows().then((result) => result.workflows)
        : backendClient.getPipelines().then((result) => result.pipelines);
    request
      .then((items) => {
        if (active) setOptions(items);
      })
      .catch((error) => {
        if (active) setError(String(error));
      });
    return () => {
      active = false;
    };
  }, [kind]);
  return (
    <label className="block space-y-2 text-sm">
      {label}
      <select
        className="block w-full rounded border bg-background p-2"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">—</option>
        {options.map((item) => (
          <option key={item.uuid} value={item.uuid}>
            {item.name}
          </option>
        ))}
      </select>
      {error && <span role="alert">{error}</span>}
    </label>
  );
}
