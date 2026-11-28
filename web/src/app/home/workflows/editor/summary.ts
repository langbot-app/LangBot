import type { TFunction } from 'i18next';
import type { WorkflowStep, WorkflowTrigger } from '@/app/infra/entities/api';
import { triggerSummary } from './TriggersEditor';
import { parseTemplate } from '../lib/template';
import type { EditorResources } from './EditorContext';
import { extractI18nObject } from '@/i18n/I18nProvider';

type Label = (path: string) => { text: string };

function plainTemplate(value: unknown, label: Label) {
  if (typeof value !== 'string') return '';
  return parseTemplate(value)
    .map((segment) =>
      segment.kind === 'text'
        ? segment.text
        : `「${label(segment.path).text}」`,
    )
    .join('')
    .replace(/\s+/g, ' ')
    .trim();
}

/** One-line description shown under a step's name on the canvas. */
export function stepSummary(
  step: WorkflowStep,
  t: TFunction,
  resources: EditorResources,
  label: Label,
  triggers: WorkflowTrigger[] = [],
): string {
  const config = step.config;
  const model = () =>
    resources.models.find((item) => item.uuid === config.model_uuid)?.name ??
    t('workflows.summary.noModel');
  const count = (key: string) =>
    Array.isArray(config[key]) ? (config[key] as unknown[]).length : 0;
  switch (step.type) {
    case 'start':
      return triggers.length
        ? triggers.map((trigger) => triggerSummary(trigger, t)).join(' · ')
        : t('workflows.summary.start');
    case 'llm':
      return model();
    case 'classify':
      return t('workflows.summary.classify', {
        count: count('categories'),
        model: model(),
      });
    case 'extract':
      return (
        ((config.fields as { key?: string }[]) ?? [])
          .map((field) => field.key)
          .filter(Boolean)
          .join('、') || model()
      );
    case 'condition':
      return t('workflows.summary.condition', { count: count('cases') });
    case 'remember':
      return `${t(`workflows.remember.scope.${String(config.scope ?? 'run')}`)} · ${(
        (config.items as { key?: string }[]) ?? []
      )
        .map((item) => item.key)
        .filter(Boolean)
        .join('、')}`;
    case 'reply':
      return plainTemplate(config.text, label) || t('workflows.summary.empty');
    case 'send':
      return `${t(`workflows.send.${config.target_type === 'person' ? 'person' : 'group'}`)} ${plainTemplate(config.target_id, label)}`;
    case 'http':
      return `${String(config.method ?? 'GET')} ${plainTemplate(config.url, label) || '—'}`;
    case 'handoff': {
      const target =
        config.target_type === 'workflow'
          ? resources.workflows.find((item) => item.uuid === config.target_uuid)
              ?.name
          : resources.processors.find(
              (item) => item.uuid === config.target_uuid,
            )?.name;
      return target ?? t('workflows.summary.noTarget');
    }
    case 'platform': {
      const action = String(config.action ?? '');
      const tool = resources.platformTools.find((item) => item.name === action);
      if (tool) return extractI18nObject(tool.label);
      if (action === 'call_platform_api') {
        const name = (config.params as { action?: string } | undefined)?.action;
        return name || t('workflows.platform.actions.custom');
      }
      return action
        ? t(`workflows.platform.actions.${action}`)
        : t('workflows.stepDesc.platform');
    }
    default:
      return t(`workflows.stepDesc.${step.type}`);
  }
}
