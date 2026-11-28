import type { EventBinding } from '@/app/infra/entities/api';

/** Add explicit private/group routes, preserving all existing user routes. */
/** Notes that tell the two template routes apart in route lists. */
export interface MessageRoutingTemplateNotes {
  person: string;
  group: string;
}

export function appendMessageRoutingTemplate(
  bindings: EventBinding[],
  target: Pick<EventBinding, 'target_type' | 'target_uuid'>,
  notes?: MessageRoutingTemplateNotes,
): EventBinding[] {
  const routes: EventBinding[] = [
    {
      event_pattern: 'message.received',
      ...target,
      priority: 0,
      enabled: true,
      filters: [{ field: 'chat_type', operator: 'eq', value: 'person' }],
      ...(notes ? { description: notes.person } : {}),
    },
    {
      event_pattern: 'message.received',
      ...target,
      priority: 0,
      enabled: true,
      filters: [
        { field: 'chat_type', operator: 'eq', value: 'group' },
        { field: 'is_at_bot', operator: 'eq', value: true },
      ],
      ...(notes ? { description: notes.group } : {}),
    },
  ];
  const sameFilters = (a: EventBinding, b: EventBinding) => {
    const left = a.filters ?? [];
    const right = b.filters ?? [];
    return (
      left.length === right.length &&
      left.every((filter) =>
        right.some(
          (other) =>
            filter.field === other.field &&
            filter.operator === other.operator &&
            filter.value === other.value,
        ),
      )
    );
  };
  return [
    ...bindings,
    ...routes.filter(
      (route) =>
        !bindings.some(
          (binding) =>
            binding.event_pattern === route.event_pattern &&
            sameFilters(binding, route),
        ),
    ),
  ];
}
