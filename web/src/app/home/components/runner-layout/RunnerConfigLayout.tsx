import { useRef, useState, type ReactNode } from 'react';
import { useWatch, type Control } from 'react-hook-form';
import type { LucideIcon } from 'lucide-react';
import type { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { Button } from '@/components/ui/button';
import { preserveRunnerConfig } from '@/app/home/pipelines/components/pipeline-form/RunnerConfigPreservation';

type Values = Record<string, unknown>;

// --- Field classification -------------------------------------------------
// Runners describe their settings as one flat schema. These rules place the
// fields a bot owner touches most (model, prompt, knowledge) up front and
// fold the rest into named rows. Unknown fields fall back to the runner's
// own settings block, or "other advanced" when the runner marks them as such.

const MODEL_TYPES = new Set(['model-fallback-selector', 'llm-model-selector']);
const PROMPT_TYPES = new Set(['prompt-editor']);
const KNOWLEDGE_TYPES = new Set([
  'knowledge-base-multi-selector',
  'knowledge-base-selector',
]);
const RETRIEVAL_FIELDS = new Set([
  'retrieval-top-k',
  'rerank-model',
  'rerank-top-k',
]);
const RUNTIME_FIELDS = new Set([
  'timeout',
  'max-tool-iterations',
  'tool-execution-mode',
  'max-tool-result-chars',
  'workspace-direct-threshold',
]);
/** Display-only toggle that used to reveal advanced fields; rows replace it. */
export const ADVANCED_TOGGLE = 'advanced-settings';

export function isAdvanced(item: IDynamicFormItemSchema) {
  return item.show_if?.field === ADVANCED_TOGGLE;
}

export interface RunnerFieldGroups {
  model: IDynamicFormItemSchema[];
  prompt: IDynamicFormItemSchema[];
  knowledge: IDynamicFormItemSchema[];
  retrieval: IDynamicFormItemSchema[];
  context: IDynamicFormItemSchema[];
  runtime: IDynamicFormItemSchema[];
  sandbox: IDynamicFormItemSchema[];
  basic: IDynamicFormItemSchema[];
  advanced: IDynamicFormItemSchema[];
}

/**
 * Place a runner's flat schema into sections. `hidden` names fields another
 * part of the page owns (e.g. Chat mirrors `remove-think` in its reply row).
 */
export function groupRunnerFields(
  items: IDynamicFormItemSchema[],
  hidden: ReadonlySet<string> = new Set(),
): RunnerFieldGroups {
  const groups: RunnerFieldGroups = {
    model: [],
    prompt: [],
    knowledge: [],
    retrieval: [],
    context: [],
    runtime: [],
    sandbox: [],
    basic: [],
    advanced: [],
  };
  for (const item of items) {
    if (item.name === ADVANCED_TOGGLE || hidden.has(item.name)) continue;
    if (MODEL_TYPES.has(item.type)) groups.model.push(item);
    else if (PROMPT_TYPES.has(item.type)) groups.prompt.push(item);
    else if (KNOWLEDGE_TYPES.has(item.type)) groups.knowledge.push(item);
    else if (RETRIEVAL_FIELDS.has(item.name)) groups.retrieval.push(item);
    else if (item.name.startsWith('context-') || item.name === 'date-grounding')
      groups.context.push(item);
    else if (RUNTIME_FIELDS.has(item.name)) groups.runtime.push(item);
    else if (item.name.startsWith('box-')) groups.sandbox.push(item);
    else if (isAdvanced(item)) groups.advanced.push(item);
    else groups.basic.push(item);
  }
  return groups;
}

/** Fields whose value differs from their schema default. */
export function modifiedCount(items: IDynamicFormItemSchema[], values: Values) {
  return items.filter((item) => {
    const value = values[item.name];
    if (value === undefined) return false;
    return JSON.stringify(value) !== JSON.stringify(item.default ?? null);
  }).length;
}

/**
 * Edits a subset of one stored object. The latest stored object is read at
 * write time, so several subsets of the same object never overwrite each
 * other, and untouched keys (including ones no form shows) are preserved.
 */
export function SubsetForm({
  items,
  read,
  write,
  systemContext,
  renderItem,
}: {
  items: IDynamicFormItemSchema[];
  read: () => Values;
  write: (next: Values) => void;
  systemContext?: Values;
  renderItem?: Parameters<typeof DynamicFormComponent>[0]['renderItem'];
}) {
  const previous = useRef<Values | undefined>(undefined);
  if (items.length === 0) return null;
  return (
    <DynamicFormComponent
      itemConfigList={items}
      // Always the latest stored object: re-syncing from it never discards
      // an edit made through this or a sibling subset.
      initialValues={read()}
      systemContext={systemContext}
      // Fields in other subsets (and the retired advanced toggle) still
      // drive show_if conditions here.
      externalDependentValues={{ ...read(), [ADVANCED_TOGGLE]: true }}
      renderItem={renderItem}
      onSubmit={(emitted) => {
        const values = emitted as Values;
        const current = read();
        const next = preserveRunnerConfig(current, previous.current, values);
        previous.current = structuredClone(values);
        if (JSON.stringify(next) !== JSON.stringify(current)) write(next);
      }}
    />
  );
}

/** Re-renders only its own summary text when the watched value changes. */
export function Watch<T>({
  control,
  name,
  children,
}: {
  control: Control<any>;
  name: string;
  children: (value: T) => ReactNode;
}) {
  const value = useWatch({ control, name }) as T;
  return <>{children(value)}</>;
}

export function PrimaryBlock({
  icon: Icon,
  guide,
  title,
  hint,
  action,
  children,
}: {
  icon: LucideIcon;
  guide?: string;
  title?: string;
  hint?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      data-guide={guide}
      className="flex gap-3 rounded-lg border bg-card p-4"
    >
      <span className="flex size-8 shrink-0 items-center justify-center rounded-md border bg-background text-primary">
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1 space-y-3">
        {(title || action) && (
          <div className="flex items-start justify-between gap-3">
            <div>
              {title && <h3 className="text-sm font-semibold">{title}</h3>}
              {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
            </div>
            {action}
          </div>
        )}
        {children}
      </div>
    </section>
  );
}

/** Retrieval tuning, folded but kept mounted so its values stay validated. */
export function RetrievalSettings({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <Button
        type="button"
        variant="link"
        size="sm"
        aria-expanded={open}
        className="h-auto p-0 text-xs text-muted-foreground"
        onClick={() => setOpen(!open)}
      >
        {label}
      </Button>
      <div hidden={!open} className="pt-3">
        {children}
      </div>
    </div>
  );
}
