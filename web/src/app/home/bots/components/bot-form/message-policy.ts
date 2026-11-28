import type { TFunction } from 'i18next';
import type {
  Agent,
  EventBinding,
  HookProcessor,
  MessagePolicy,
  MessagePolicyOverride,
  MessagePolicySectionName,
  PluginSelection,
} from '@/app/infra/entities/api';

export const POLICY_SECTIONS: MessagePolicySectionName[] = [
  'trigger',
  'safety',
  'output',
];

export const DEFAULT_PLUGIN_SELECTION: PluginSelection = {
  enable_all: true,
  plugins: [],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

/** Mirror of the backend ``merge_policy``: dicts merge key by key, lists are replaced. */
export function mergePolicy<T>(base: T, override: unknown): T {
  const result: Record<string, unknown> = isRecord(base)
    ? structuredClone(base as Record<string, unknown>)
    : {};
  if (!isRecord(override)) return result as T;
  for (const [key, value] of Object.entries(override)) {
    if (isRecord(value) && isRecord(result[key])) {
      result[key] = mergePolicy(result[key], value);
    } else if (value !== undefined) {
      result[key] = structuredClone(value);
    }
  }
  return result as T;
}

/** Messages reach a route through ``message.received``; only those routes carry a policy. */
export function isMessageRoute(binding: EventBinding): boolean {
  return (
    (binding.target_type === 'pipeline' || binding.target_type === 'agent') &&
    ['message.received', 'message.*', '*'].includes(binding.event_pattern)
  );
}

export function routeKey(binding: EventBinding, index: number): string {
  return binding.id || `new-${index}`;
}

export function routeLabel(
  binding: EventBinding,
  index: number,
  agents: Agent[],
): string {
  const target = agents.find((agent) => agent.uuid === binding.target_uuid);
  const name = target
    ? `${target.emoji ? `${target.emoji} ` : ''}${target.name}`
    : '';
  const description = binding.description?.trim();
  return description || name || `#${index + 1}`;
}

const ELEMENT_KEYS = new Set([
  'Image',
  'Voice',
  'File',
  'Forward',
  'Face',
  'At',
  'AtAll',
  'Quote',
]);

/** One condition in readable form, e.g. 'Message text contains "agent:"'. */
function conditionText(filter: Record<string, unknown>, t: TFunction): string {
  const field = String(filter.field ?? '');
  const operator = t(`bots.operator_${String(filter.operator ?? 'eq')}`);
  const raw = filter.value;
  let fieldLabel = field;
  let value = `"${String(raw ?? '')}"`;
  if (field === 'is_at_bot') {
    fieldLabel = t('bots.filterIsAtBot');
    value =
      raw === true || raw === 'true'
        ? t('bots.mentionYes')
        : t('bots.mentionNo');
  } else if (field === 'chat_type') {
    fieldLabel = t('bots.filterChatType');
    value =
      raw === 'group'
        ? t('bots.sessionTypeGroup')
        : t('bots.sessionTypePerson');
  } else if (field === 'message_element_types') {
    fieldLabel = t('bots.filterMessageElement');
    if (ELEMENT_KEYS.has(String(raw))) value = t(`bots.element${String(raw)}`);
  } else if (field === 'chat_id') {
    fieldLabel = t('bots.filterChatId');
  } else if (field === 'message_text') {
    fieldLabel = t('bots.filterMessageText');
  }
  return `${fieldLabel} ${operator} ${value}`;
}

/** When a route applies, derived from its conditions; never needs user input. */
export function routeConditionSummary(
  binding: EventBinding,
  t: TFunction,
): string {
  const filters = Array.isArray(binding.filters) ? binding.filters : [];
  if (filters.length === 0) return t('bots.routeSummary.always');
  return filters
    .map((filter) => conditionText(filter as Record<string, unknown>, t))
    .join(' · ');
}

/**
 * Second line under a route's name: where it goes (when the name is a note)
 * and when it applies.
 */
export function routeDetail(
  binding: EventBinding,
  agents: Agent[],
  t: TFunction,
): string {
  const conditions = routeConditionSummary(binding, t);
  if (!binding.description?.trim()) return conditions;
  const target = agents.find((agent) => agent.uuid === binding.target_uuid);
  return target ? `${target.name} · ${conditions}` : conditions;
}

export function routeProcessor(binding: EventBinding): HookProcessor {
  return binding.target_type === 'pipeline' ? 'messaging' : 'agent';
}

export function hasSectionOverride(policy?: MessagePolicyOverride | null) {
  return POLICY_SECTIONS.some(
    (section) =>
      isRecord(policy?.[section]) && Object.keys(policy![section]!).length > 0,
  );
}

export function hasPluginOverride(policy?: MessagePolicyOverride | null) {
  return isRecord(policy?.plugins);
}

/** The settings a route runs with: bot policy with the route override applied. */
export function resolveRoutePolicy(
  botPolicy: MessagePolicy | undefined,
  override: MessagePolicyOverride | null | undefined,
): MessagePolicy {
  const { plugins, ...sections } = override ?? {};
  const resolved = mergePolicy(botPolicy ?? {}, sections);
  if (isRecord(plugins)) resolved.plugins = structuredClone(plugins);
  return resolved;
}

/**
 * Normalize a route override for writing. ``plugins: null`` is explicit so the
 * backend drops a stored route selection instead of keeping it; an override
 * with nothing left becomes ``null``.
 */
export function normalizeRouteOverride(
  policy: MessagePolicyOverride | null | undefined,
): MessagePolicyOverride | null {
  if (!policy) return null;
  const next: MessagePolicyOverride = {};
  for (const section of POLICY_SECTIONS) {
    if (isRecord(policy[section]) && Object.keys(policy[section]!).length > 0) {
      next[section] = policy[section];
    }
  }
  if (isRecord(policy.plugins)) next.plugins = policy.plugins;
  if (Object.keys(next).length === 0) return null;
  if (!next.plugins) next.plugins = null;
  return next;
}

export function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  if (isRecord(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value ?? null);
}

/** Whether the bot default lets every message through (the migrated-bot default). */
export function admitsEverything(
  policy: MessagePolicy | undefined,
  neutral: MessagePolicy | undefined,
): boolean {
  if (!policy || !neutral) return false;
  const resolved = mergePolicy(neutral, policy);
  return (
    stableJson(resolved.trigger) === stableJson(neutral.trigger) &&
    stableJson(resolved.safety) === stableJson(neutral.safety)
  );
}

export function selectionIncludes(
  selection: PluginSelection | undefined,
  pluginId: string,
): boolean {
  const effective = selection ?? DEFAULT_PLUGIN_SELECTION;
  if (effective.enable_all) return true;
  return effective.plugins.some(
    (item) => `${item.author}/${item.name}` === pluginId,
  );
}

export function toggleSelection(
  selection: PluginSelection | undefined,
  pluginId: string,
  enabled: boolean,
): PluginSelection {
  const current = selection ?? DEFAULT_PLUGIN_SELECTION;
  const [author = '', name = ''] = pluginId.split('/');
  const rest = current.plugins.filter(
    (item) => `${item.author}/${item.name}` !== pluginId,
  );
  return {
    enable_all: current.enable_all,
    plugins: enabled ? [...rest, { author, name }] : rest,
  };
}

/** Lifecycle steps of a bot message, in the order the host runs them. */
export const LIFECYCLE_STEPS = [
  'received',
  'command',
  'admission',
  'before',
  'process',
  'after',
  'send',
] as const;
export type LifecycleStep = (typeof LIFECYCLE_STEPS)[number];

const EVENT_STEP: Record<string, LifecycleStep> = {
  GroupMessageReceived: 'received',
  PersonMessageReceived: 'received',
  GroupCommandSent: 'command',
  PersonCommandSent: 'command',
  GroupNormalMessageReceived: 'before',
  PersonNormalMessageReceived: 'before',
  PromptPreProcessing: 'before',
  NormalMessageResponded: 'after',
};

/** Lifecycle step of a hook; ``null`` for observe-only platform events. */
export function eventStep(event: string): LifecycleStep | null {
  return EVENT_STEP[event] ?? null;
}

export const LIFECYCLE_EVENTS = Object.keys(EVENT_STEP);

/**
 * Whether a stored bot policy admits every message: no group rules, lists,
 * ignore rules, rate limit or content filter. A missing policy admits all.
 */
export function policyAdmitsAll(policy: MessagePolicy | undefined): boolean {
  if (!policy) return true;
  const trigger = policy.trigger ?? {};
  const safety = policy.safety ?? {};
  const list = (value: unknown) => (Array.isArray(value) ? value.length : 0);
  const access = trigger['access-control'] ?? {};
  const ignore = trigger['ignore-rules'] ?? {};
  return (
    trigger['group-respond-rules']?.enabled === false &&
    list(access[access.mode === 'whitelist' ? 'whitelist' : 'blacklist']) ===
      0 &&
    access.mode !== 'whitelist' &&
    list(ignore.prefix) + list(ignore.regexp) === 0 &&
    safety['rate-limit']?.enabled !== true &&
    safety['content-filter']?.['check-sensitive-words'] !== true
  );
}
