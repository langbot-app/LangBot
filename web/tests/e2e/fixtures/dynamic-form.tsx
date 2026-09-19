import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { getBoxScopeContext } from '@/app/home/pipelines/components/pipeline-form/BoxScopeContext';
import type { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import scope from '../../fixtures/sandbox-scope-schema.json';
import '@/app/global.css';

// Browser component fixture only. These legacy context keys are NOT supplied by
// PipelineForm in 4.11: actual execution scope remains owned by the Runner Host.
const params = new URLSearchParams(window.location.search);
const initialValues = {
  [scope.name]: scope.default,
  mode: 'live',
  secret: '',
  count: 3,
};
const fields = [
  { ...scope, id: 'scope' },
  {
    id: 'mode',
    name: 'mode',
    type: 'select',
    label: { en_US: 'Mode' },
    default: 'live',
    options: [
      { name: 'live', label: { en_US: 'Live' } },
      { name: 'hidden', label: { en_US: 'Hidden' } },
    ],
  },
  {
    id: 'secret',
    name: 'secret',
    type: 'secret',
    label: { en_US: 'Plugin secret' },
    default: '',
    show_if: { field: 'mode', operator: 'eq', value: 'live' },
    disable_if: { field: '__system.locked', operator: 'eq', value: true },
    disabled_tooltip: { en_US: 'Locked by context' },
    disabled_tooltip_overrides: [
      {
        when: { field: 'mode', operator: 'in', value: ['live'] },
        tooltip: { en_US: 'Live reason wins' },
      },
    ],
  },
  {
    id: 'count',
    name: 'count',
    type: 'number',
    label: { en_US: 'Plugin count' },
    default: 3,
    show_if: { field: 'mode', operator: 'neq', value: 'hidden' },
  },
] as IDynamicFormItemSchema[];

function Fixture() {
  const [context, setContext] = useState<Record<string, unknown>>({
    ...getBoxScopeContext(
      params.get('available') === 'true',
      params.get('forced') || '',
    ),
    locked: false,
  });
  const [saved, setSaved] = useState({});
  useEffect(() => {
    const update = (event: Event) =>
      setContext((current) => ({
        ...current,
        ...(event as CustomEvent<Record<string, unknown>>).detail,
      }));
    window.addEventListener('test-form-context', update);
    return () => window.removeEventListener('test-form-context', update);
  }, []);
  return (
    <main className="p-8 max-w-2xl">
      <DynamicFormComponent
        itemConfigList={fields}
        initialValues={initialValues}
        externalDependentValues={{ mode: 'hidden', '__system.locked': true }}
        systemContext={context}
        onSubmit={setSaved}
      />
      <output data-testid="saved-values">{JSON.stringify(saved)}</output>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<Fixture />);
