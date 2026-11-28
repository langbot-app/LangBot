import type { LucideIcon } from 'lucide-react';
import {
  AudioLines,
  BookOpen,
  Code,
  Database,
  Dices,
  Forward,
  GitBranch,
  Globe,
  History,
  MessageCircle,
  Mic,
  Reply,
  ScanText,
  Send,
  Shield,
  Sparkles,
  Split,
} from 'lucide-react';
import type { WorkflowStep, WorkflowStepType } from '@/app/infra/entities/api';

export type StepCategory = 'ai' | 'logic' | 'action';

export interface StepMeta {
  type: WorkflowStepType;
  category: StepCategory;
  icon: LucideIcon;
  /** Tailwind classes for the icon tile. */
  tone: string;
  /** Static output keys; dynamic keys come from `outputs()`. */
  outputs: string[];
  branching?: 'categories' | 'cases';
  terminal?: boolean;
  defaults: () => Record<string, unknown>;
}

const AI = 'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-300';
const LOGIC =
  'bg-violet-50 text-violet-600 dark:bg-violet-950/40 dark:text-violet-300';
const DATA = 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300';
const ACTION =
  'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300';
const NET = 'bg-sky-50 text-sky-600 dark:bg-sky-950/40 dark:text-sky-300';
const HANDOFF =
  'bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-300';

export const STEP_META: Record<WorkflowStepType, StepMeta> = {
  start: {
    type: 'start',
    category: 'logic',
    icon: MessageCircle,
    tone: DATA,
    outputs: [
      'text',
      'sender_name',
      'sender_id',
      'is_group',
      'group_id',
      'platform',
      'images',
    ],
    defaults: () => ({}),
  },
  llm: {
    type: 'llm',
    category: 'ai',
    icon: Sparkles,
    tone: AI,
    outputs: ['text'],
    defaults: () => ({
      model_uuid: '',
      prompt: '{{ start.text }}',
      use_history: true,
      on_error: 'stop',
    }),
  },
  classify: {
    type: 'classify',
    category: 'ai',
    icon: Split,
    tone: LOGIC,
    outputs: ['category'],
    branching: 'categories',
    defaults: () => ({
      model_uuid: '',
      categories: [{ id: 'c1', label: '', description: '' }],
    }),
  },
  extract: {
    type: 'extract',
    category: 'ai',
    icon: ScanText,
    tone: AI,
    outputs: ['ok'],
    defaults: () => ({
      model_uuid: '',
      fields: [{ key: '', description: '', type: 'text' }],
    }),
  },
  knowledge: {
    type: 'knowledge',
    category: 'ai',
    icon: BookOpen,
    tone: AI,
    outputs: ['text', 'chunks'],
    defaults: () => ({ kb_uuid: '', query: '{{ start.text }}', top_k: 5 }),
  },
  tts: {
    type: 'tts',
    category: 'ai',
    icon: AudioLines,
    tone: AI,
    outputs: ['voice'],
    defaults: () => ({ model_uuid: '', text: '' }),
  },
  asr: {
    type: 'asr',
    category: 'ai',
    icon: Mic,
    tone: AI,
    outputs: ['text'],
    defaults: () => ({ model_uuid: '', voice: '{{ start.voice }}' }),
  },
  condition: {
    type: 'condition',
    category: 'logic',
    icon: GitBranch,
    tone: LOGIC,
    outputs: ['matched'],
    branching: 'cases',
    defaults: () => ({
      cases: [
        {
          id: 'case1',
          label: '',
          match: 'all',
          rules: [{ left: '{{ start.text }}', op: 'contains', right: '' }],
        },
      ],
    }),
  },
  random: {
    type: 'random',
    category: 'logic',
    icon: Dices,
    tone: LOGIC,
    outputs: ['value'],
    defaults: () => ({ mode: 'pick', items: [''] }),
  },
  remember: {
    type: 'remember',
    category: 'logic',
    icon: Database,
    tone: DATA,
    outputs: [],
    defaults: () => ({
      scope: 'user',
      items: [{ key: '', op: 'set', value: '' }],
    }),
  },
  history: {
    type: 'history',
    category: 'logic',
    icon: History,
    tone: DATA,
    outputs: ['text', 'messages'],
    defaults: () => ({ scope: 'conversation', limit: 50 }),
  },
  code: {
    type: 'code',
    category: 'logic',
    icon: Code,
    tone: DATA,
    outputs: [],
    defaults: () => ({ language: 'python', code: '', inputs: {}, outputs: [] }),
  },
  reply: {
    type: 'reply',
    category: 'action',
    icon: Reply,
    tone: ACTION,
    outputs: ['sent'],
    defaults: () => ({ text: '' }),
  },
  send: {
    type: 'send',
    category: 'action',
    icon: Send,
    tone: ACTION,
    outputs: ['sent'],
    defaults: () => ({ target_type: 'group', target_id: '', text: '' }),
  },
  http: {
    type: 'http',
    category: 'action',
    icon: Globe,
    tone: NET,
    outputs: ['status', 'body', 'json'],
    defaults: () => ({
      method: 'GET',
      url: '',
      headers: [],
      body: '',
      timeout: 15,
      on_error: 'stop',
    }),
  },
  platform: {
    type: 'platform',
    category: 'action',
    icon: Shield,
    tone: NET,
    outputs: ['result'],
    defaults: () => ({ action: '', params: {} }),
  },
  handoff: {
    type: 'handoff',
    category: 'action',
    icon: Forward,
    tone: HANDOFF,
    outputs: [],
    terminal: true,
    defaults: () => ({ target_type: 'chat', target_uuid: '', text: '' }),
  },
};

/** Steps the editor has a form for; others stay out of the picker. */
export const EDITABLE_TYPES = new Set<WorkflowStepType>([
  'llm',
  'classify',
  'extract',
  'condition',
  'remember',
  'reply',
  'send',
  'http',
  'handoff',
]);

/** Order of steps in the picker; types the server does not offer are hidden. */
export const PICKER_ORDER: WorkflowStepType[] = [
  'llm',
  'classify',
  'extract',
  'knowledge',
  'tts',
  'asr',
  'condition',
  'random',
  'remember',
  'history',
  'code',
  'reply',
  'send',
  'http',
  'platform',
  'handoff',
];

type Row = Record<string, unknown>;

function rows(value: unknown): Row[] {
  return Array.isArray(value)
    ? value.filter((row): row is Row => !!row && typeof row === 'object')
    : [];
}

/** Output keys a later step can reference. */
export function stepOutputs(step: WorkflowStep): string[] {
  const meta = STEP_META[step.type];
  if (!meta) return [];
  if (step.type === 'extract') {
    return [
      ...rows(step.config.fields)
        .map((row) => String(row.key ?? ''))
        .filter(Boolean),
      'ok',
    ];
  }
  if (step.type === 'code') {
    return rows(step.config.outputs)
      .map((row) => String(row.key ?? ''))
      .filter(Boolean);
  }
  return meta.outputs;
}

/** Memory keys written by a remember step, as `scope.key` paths. */
export function rememberedKeys(step: WorkflowStep): string[] {
  if (step.type !== 'remember') return [];
  const scope = String(step.config.scope ?? 'run');
  return rows(step.config.items)
    .map((row) => String(row.key ?? '').split('.')[0])
    .filter(Boolean)
    .map((key) => `${scope}.${key}`);
}

export interface BranchInfo {
  id: string;
  label: string;
  isElse?: boolean;
}

/** Branches of a branching step, always ending with the implicit `else`. */
export function stepBranches(
  step: WorkflowStep,
  elseLabel: string,
  fallback: (index: number) => string,
): BranchInfo[] | null {
  const meta = STEP_META[step.type];
  if (!meta?.branching) return null;
  const list = rows(step.config[meta.branching]).map((row, index) => ({
    id: String(row.id ?? ''),
    label: String(row.label ?? '').trim() || fallback(index),
  }));
  return [...list, { id: 'else', label: elseLabel, isElse: true }];
}
