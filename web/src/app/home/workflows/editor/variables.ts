import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { WorkflowGraph, WorkflowStep } from '@/app/infra/entities/api';
import { STEP_META, rememberedKeys, stepOutputs } from '../lib/catalog';
import { ancestorsOf } from '../lib/tree';
import { eventFields } from '../lib/platform';
import { useEditor } from './EditorContext';

export interface VariableOption {
  path: string;
  label: string;
  sample?: unknown;
}

export interface VariableGroup {
  key: string;
  title: string;
  step?: WorkflowStep;
  options: VariableOption[];
}

export function useOutputLabel() {
  const { t, i18n } = useTranslation();
  return useCallback(
    (key: string) => {
      const label = (name: string) =>
        i18n.exists(`workflows.outputs.${name}`)
          ? t(`workflows.outputs.${name}`)
          : name;
      if (key.startsWith('event.')) {
        const field = key.slice(6);
        const fieldKey = `workflows.eventFields.${field.replace(/\./g, '_')}`;
        return `${label('event')} · ${i18n.exists(fieldKey) ? t(fieldKey) : field}`;
      }
      if (key.startsWith('args.')) return `${label('args')} · ${key.slice(5)}`;
      return label(key);
    },
    [t, i18n],
  );
}

/** Variables a step may reference: outputs of its ancestors plus memory. */
export function useVariableGroups(stepId: string): VariableGroup[] {
  const { t } = useTranslation();
  const { graph, lastRun, triggers } = useEditor();
  const outputLabel = useOutputLabel();
  const ancestors = ancestorsOf(graph, stepId);
  const startKeys = (): string[] => {
    const kinds = new Set(triggers.map((trigger) => trigger.type));
    const keys: string[] = [];
    if (kinds.has('message') || kinds.has('command') || kinds.has('event')) {
      keys.push(
        ...stepOutputs({ id: 'start', type: 'start', name: '', config: {} }),
      );
    }
    for (const trigger of triggers) {
      if (trigger.type === 'command') {
        for (const arg of (trigger.args as { name?: string }[]) ?? []) {
          if (arg.name) keys.push(`args.${arg.name}`);
        }
      }
    }
    const patterns = triggers.flatMap((trigger) =>
      trigger.type === 'event' ? ((trigger.events as string[]) ?? []) : [],
    );
    if (kinds.has('event')) {
      keys.push(
        'event_type',
        ...eventFields(patterns).map((field) => `event.${field}`),
        'event',
      );
    }
    if (kinds.has('webhook')) keys.push('payload');
    if (kinds.has('schedule')) keys.push('target');
    return [...new Set(keys)];
  };
  const groups: VariableGroup[] = ancestors
    .map((step) => ({
      key: step.id,
      title: step.name || t(`workflows.steps.${step.type}`),
      step,
      options: (step.type === 'start' ? startKeys() : stepOutputs(step)).map(
        (key) => ({
          path: `${step.id}.${key}`,
          label: outputLabel(key),
          sample: key
            .split('.')
            .reduce<unknown>(
              (value, part) =>
                value && typeof value === 'object'
                  ? (value as Record<string, unknown>)[part]
                  : undefined,
              lastRun[step.id]?.outputs,
            ),
        }),
      ),
    }))
    .filter((group) => group.options.length > 0);
  const memory = ancestors.flatMap(rememberedKeys);
  if (memory.length) {
    groups.push({
      key: 'memory',
      title: t('workflows.variables.memory'),
      options: [...new Set(memory)].map((path) => ({
        path: `memory.${path}`,
        label: `${t(`workflows.remember.scope.${path.split('.')[0]}`)} · ${path.split('.').slice(1).join('.')}`,
      })),
    });
  }
  return groups;
}

/** Human label of a reference path, e.g. "收到消息 · 文本". */
export function useRefLabel() {
  const { t } = useTranslation();
  const { graph } = useEditor();
  const outputLabel = useOutputLabel();
  return useCallback(
    (path: string) => refLabel(graph, path, t, outputLabel),
    [graph, t, outputLabel],
  );
}

export function refLabel(
  graph: WorkflowGraph,
  path: string,
  t: (key: string) => string,
  outputLabel: (key: string) => string,
): { text: string; known: boolean } {
  const [head, ...rest] = path.split('.');
  if (head === 'memory') {
    const [scope, ...key] = rest;
    return {
      text: `${t(`workflows.remember.scope.${scope}`)} · ${key.join('.')}`,
      known: true,
    };
  }
  const step = graph.nodes.find((node) => node.id === head);
  if (!step) return { text: path, known: false };
  const name = step.name || t(`workflows.steps.${step.type}`);
  const key = rest.join('.');
  return {
    text: [
      name,
      ...(rest[0] === 'event' || rest[0] === 'args'
        ? [outputLabel(key)]
        : [outputLabel(rest[0] ?? ''), ...rest.slice(1)]),
    ].join(' · '),
    known: Boolean(STEP_META[step.type]) && key !== '',
  };
}

export function formatSample(value: unknown): string {
  if (value === undefined || value === null || value === '') return '';
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  return text.length > 40 ? `${text.slice(0, 40)}…` : text;
}
