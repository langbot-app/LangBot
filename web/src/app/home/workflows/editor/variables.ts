import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { WorkflowGraph, WorkflowStep } from '@/app/infra/entities/api';
import { STEP_META, rememberedKeys, stepOutputs } from '../lib/catalog';
import { ancestorsOf } from '../lib/tree';
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
    (key: string) =>
      i18n.exists(`workflows.outputs.${key}`)
        ? t(`workflows.outputs.${key}`)
        : key,
    [t, i18n],
  );
}

/** Variables a step may reference: outputs of its ancestors plus memory. */
export function useVariableGroups(stepId: string): VariableGroup[] {
  const { t } = useTranslation();
  const { graph, lastRun } = useEditor();
  const outputLabel = useOutputLabel();
  const ancestors = ancestorsOf(graph, stepId);
  const groups: VariableGroup[] = ancestors
    .map((step) => ({
      key: step.id,
      title: step.name || t(`workflows.steps.${step.type}`),
      step,
      options: stepOutputs(step).map((key) => ({
        path: `${step.id}.${key}`,
        label: outputLabel(key),
        sample: lastRun[step.id]?.outputs?.[key],
      })),
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
    text: `${name} · ${outputLabel(rest[0] ?? '')}${rest.length > 1 ? `.${rest.slice(1).join('.')}` : ''}`,
    known: Boolean(STEP_META[step.type]) && key !== '',
  };
}

export function formatSample(value: unknown): string {
  if (value === undefined || value === null || value === '') return '';
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  return text.length > 40 ? `${text.slice(0, 40)}…` : text;
}
