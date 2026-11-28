import type { Plugin } from '@/app/infra/entities/plugin';

/**
 * Which follow-up each component kind needs after a successful install.
 *
 * Commands and event listeners are enabled on a bot (its Plugins tab), so they
 * collapse into one "bots" step; tools are granted to a Chat (pipeline).
 */
export type FollowUpKind = 'agents' | 'bots' | 'pipelines' | 'knowledge';

const FOLLOW_UP_BY_COMPONENT_KIND: Record<string, FollowUpKind> = {
  Runner: 'agents',
  EventListener: 'bots',
  Tool: 'pipelines',
  Command: 'bots',
  KnowledgeEngine: 'knowledge',
};

/** Stable order, so the same component set always renders the same steps. */
const FOLLOW_UP_ORDER: FollowUpKind[] = [
  'agents',
  'bots',
  'pipelines',
  'knowledge',
];

/**
 * Map an installed plugin's components to the follow-up steps it needs.
 *
 * Deduplicated and ordered: a plugin with Runner + Tool asks for both an Agent
 * and a pipeline, and a plugin with Command + EventListener asks for the bot
 * step exactly once.
 */
export function followUpKindsForPlugin(
  plugin: Pick<Plugin, 'components'> | null | undefined,
): FollowUpKind[] {
  const needed = new Set<FollowUpKind>();
  for (const component of plugin?.components ?? []) {
    const kind = component?.manifest?.manifest?.kind;
    const followUp = kind ? FOLLOW_UP_BY_COMPONENT_KIND[kind] : undefined;
    if (followUp) needed.add(followUp);
  }
  return FOLLOW_UP_ORDER.filter((kind) => needed.has(kind));
}
