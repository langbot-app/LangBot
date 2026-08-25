import type { TFunction } from 'i18next';

export interface EventPatternGroup {
  namespace: string;
  patterns: string[];
}

function eventPatternNamespace(pattern: string) {
  if (pattern === '*') return '*';
  return pattern.split('.')[0] || pattern;
}

export function eventNamespaces(events: string[]) {
  const counts = new Map<string, number>();
  events.forEach((event) => {
    if (event === '*' || event.endsWith('.*')) return;
    const namespace = eventPatternNamespace(event);
    counts.set(namespace, (counts.get(namespace) ?? 0) + 1);
  });
  return Array.from(counts.entries())
    .filter(([, count]) => count >= 2)
    .map(([namespace]) => `${namespace}.*`)
    .sort();
}

export function groupEventPatterns(patterns: string[]): EventPatternGroup[] {
  const groups = new Map<string, string[]>();
  patterns.forEach((pattern) => {
    const namespace = eventPatternNamespace(pattern);
    const group = groups.get(namespace) ?? [];
    if (!group.includes(pattern)) group.push(pattern);
    groups.set(namespace, group);
  });

  return Array.from(groups.entries())
    .sort(([left], [right]) => {
      if (left === '*') return -1;
      if (right === '*') return 1;
      return left.localeCompare(right);
    })
    .map(([namespace, groupPatterns]) => ({
      namespace,
      patterns: groupPatterns.sort((left, right) => {
        const leftWildcard = left.endsWith('.*');
        const rightWildcard = right.endsWith('.*');
        if (leftWildcard !== rightWildcard) return leftWildcard ? -1 : 1;
        return left.localeCompare(right);
      }),
    }));
}

export function eventGroupLabel(namespace: string, t: TFunction) {
  if (namespace === '*') return t('bots.eventWildcard');
  const key = `bots.eventGroupNames.${namespace}`;
  const label = t(key);
  return label === key ? namespace : label;
}
