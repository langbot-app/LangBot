import type { Plugin } from '@/app/infra/entities/plugin';

/**
 * Which follow-up each component kind needs after a successful install.
 *
 * EventListener, Tool and Command are all reached through a pipeline, so they
 * collapse into one entry: a plugin that ships two of them (or all three)
 * still shows the pipeline step once.
 */
export type FollowUpKind = 'agents' | 'pipelines' | 'knowledge';

const FOLLOW_UP_BY_COMPONENT_KIND: Record<string, FollowUpKind> = {
  Runner: 'agents',
  EventListener: 'pipelines',
  Tool: 'pipelines',
  Command: 'pipelines',
  KnowledgeEngine: 'knowledge',
};

/** Stable order, so the same component set always renders the same steps. */
const FOLLOW_UP_ORDER: FollowUpKind[] = ['agents', 'pipelines', 'knowledge'];

/**
 * Map an installed plugin's components to the follow-up steps it needs.
 *
 * Deduplicated and ordered: a plugin with Runner + Tool asks for both an Agent
 * and a pipeline, and a plugin with Tool + Command + EventListener asks for the
 * pipeline step exactly once.
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
