import type { WorkflowGraph } from '@/app/infra/entities/api';

export type WorkflowPreset = 'blank' | 'intent' | 'keyword' | 'api';

export const WORKFLOW_PRESETS: WorkflowPreset[] = [
  'blank',
  'intent',
  'keyword',
  'api',
];

type T = (key: string) => string;

/** Starter graphs offered when a workflow is created. */
export function presetGraph(preset: WorkflowPreset, t: T): WorkflowGraph {
  const start = {
    id: 'start',
    type: 'start' as const,
    name: t('workflows.steps.start'),
    config: {},
  };
  switch (preset) {
    case 'intent':
      return {
        nodes: [
          start,
          {
            id: 'classify_1',
            type: 'classify',
            name: t('workflows.presets.intent.classify'),
            config: {
              model_uuid: '',
              categories: [
                {
                  id: 'c1',
                  label: t('workflows.presets.intent.categoryA'),
                  description: '',
                },
              ],
            },
          },
          {
            id: 'llm_1',
            type: 'llm',
            name: t('workflows.steps.llm'),
            config: {
              model_uuid: '',
              prompt: '{{ start.text }}',
              use_history: true,
              on_error: 'stop',
            },
          },
          {
            id: 'reply_1',
            type: 'reply',
            name: t('workflows.steps.reply'),
            config: { text: '{{ llm_1.text }}' },
          },
          {
            id: 'reply_2',
            type: 'reply',
            name: t('workflows.steps.reply'),
            config: { text: t('workflows.presets.intent.otherReply') },
          },
        ],
        edges: [
          { from: 'start', to: 'classify_1' },
          { from: 'classify_1', branch: 'c1', to: 'llm_1' },
          { from: 'llm_1', to: 'reply_1' },
          { from: 'classify_1', branch: 'else', to: 'reply_2' },
        ],
      };
    case 'keyword':
      return {
        nodes: [
          start,
          {
            id: 'condition_1',
            type: 'condition',
            name: t('workflows.presets.keyword.condition'),
            config: {
              cases: [
                {
                  id: 'case1',
                  label: t('workflows.presets.keyword.caseLabel'),
                  match: 'any',
                  rules: [
                    {
                      left: '{{ start.text }}',
                      op: 'contains',
                      right: t('workflows.presets.keyword.keyword'),
                    },
                  ],
                },
              ],
            },
          },
          {
            id: 'reply_1',
            type: 'reply',
            name: t('workflows.steps.reply'),
            config: { text: t('workflows.presets.keyword.answer') },
          },
        ],
        edges: [
          { from: 'start', to: 'condition_1' },
          { from: 'condition_1', branch: 'case1', to: 'reply_1' },
        ],
      };
    case 'api':
      return {
        nodes: [
          start,
          {
            id: 'http_1',
            type: 'http',
            name: t('workflows.presets.api.http'),
            config: {
              method: 'GET',
              url: 'https://example.com/api?q={{ start.text }}',
              headers: [],
              body: '',
              timeout: 15,
              on_error: 'stop',
            },
          },
          {
            id: 'llm_1',
            type: 'llm',
            name: t('workflows.presets.api.llm'),
            config: {
              model_uuid: '',
              prompt: t('workflows.presets.api.prompt'),
              use_history: false,
              on_error: 'stop',
            },
          },
          {
            id: 'reply_1',
            type: 'reply',
            name: t('workflows.steps.reply'),
            config: { text: '{{ llm_1.text }}' },
          },
        ],
        edges: [
          { from: 'start', to: 'http_1' },
          { from: 'http_1', to: 'llm_1' },
          { from: 'llm_1', to: 'reply_1' },
        ],
      };
    default:
      return {
        nodes: [
          start,
          {
            id: 'reply_1',
            type: 'reply',
            name: t('workflows.steps.reply'),
            config: { text: '{{ start.text }}' },
          },
        ],
        edges: [{ from: 'start', to: 'reply_1' }],
      };
  }
}
