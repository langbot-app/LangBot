/**
 * Standard platform events and APIs a workflow can use, mirroring
 * dev-docs/event-based-agents/01-event-system.md and 02-platform-api.md.
 */

/** Standard events a workflow can start from, grouped by namespace. */
export const EVENT_GROUPS: { namespace: string; events: string[] }[] = [
  {
    namespace: 'group',
    events: [
      'group.member_joined',
      'group.member_left',
      'group.member_banned',
      'group.info_updated',
    ],
  },
  {
    namespace: 'message',
    events: ['message.edited', 'message.deleted', 'message.reaction'],
  },
  {
    namespace: 'friend',
    events: ['friend.request_received', 'friend.added', 'friend.removed'],
  },
  {
    namespace: 'bot',
    events: [
      'bot.invited_to_group',
      'bot.removed_from_group',
      'bot.muted',
      'bot.unmuted',
    ],
  },
  { namespace: 'feedback', events: ['feedback.received'] },
  { namespace: 'platform', events: ['platform.specific'] },
];

export const STANDARD_EVENTS = EVENT_GROUPS.flatMap((group) => group.events);

/** Events with their own flow outside workflows. */
const HIDDEN_EVENTS = new Set(['message.received', 'interaction.callback']);

/** Adapter-specific events (e.g. wecombot.enter_chat) declared by adapters. */
export function adapterEvents(
  adapters: Record<string, AdapterCapabilities>,
): { event: string; adapters: string[] }[] {
  const found = new Map<string, string[]>();
  for (const [name, adapter] of Object.entries(adapters)) {
    for (const event of adapter.events) {
      if (HIDDEN_EVENTS.has(event) || STANDARD_EVENTS.includes(event)) continue;
      found.set(event, [...(found.get(event) ?? []), name]);
    }
  }
  return [...found.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([event, names]) => ({ event, adapters: names }));
}

const USER = (name: string) => [`${name}.id`, `${name}.nickname`];
const GROUP = ['group.id', 'group.name'];
const CHAT = ['message_id', 'chat_type', 'chat_id'];

/** Fields of each event, readable as `start.event.<field>`. */
export const EVENT_FIELDS: Record<string, string[]> = {
  'message.edited': [...CHAT, ...USER('editor'), ...GROUP],
  'message.deleted': [...CHAT, ...USER('operator'), ...GROUP],
  'message.reaction': [
    ...CHAT,
    'reaction',
    'is_add',
    ...USER('user'),
    ...GROUP,
  ],
  'group.member_joined': [
    ...GROUP,
    ...USER('member'),
    ...USER('inviter'),
    'join_type',
  ],
  'group.member_left': [
    ...GROUP,
    ...USER('member'),
    'is_kicked',
    ...USER('operator'),
  ],
  'group.member_banned': [
    ...GROUP,
    ...USER('member'),
    ...USER('operator'),
    'duration',
  ],
  'group.info_updated': [...GROUP, 'changed_fields', ...USER('operator')],
  'friend.request_received': ['request_id', ...USER('user'), 'message'],
  'friend.added': USER('user'),
  'friend.removed': USER('user'),
  'bot.invited_to_group': [...GROUP, ...USER('inviter'), 'request_id'],
  'bot.removed_from_group': [...GROUP, ...USER('operator')],
  'bot.muted': [...GROUP, ...USER('operator'), 'duration'],
  'bot.unmuted': [...GROUP, ...USER('operator')],
  'feedback.received': [
    'feedback_type',
    'feedback_content',
    'user_id',
    'message_id',
  ],
  'platform.specific': ['action', 'data'],
};

/** Fields of every event a set of trigger patterns can start from. */
export function eventFields(patterns: string[]): string[] {
  const events = new Set<string>();
  for (const pattern of patterns) {
    if (pattern === '*') STANDARD_EVENTS.forEach((event) => events.add(event));
    else if (pattern.endsWith('.*'))
      STANDARD_EVENTS.filter((event) =>
        event.startsWith(pattern.slice(0, -1)),
      ).forEach((event) => events.add(event));
    else events.add(pattern);
  }
  const fields = [...events].flatMap(
    (event) => EVENT_FIELDS[event] ?? ['data'],
  );
  return [...new Set(fields)];
}

export type ParamKind =
  'text' | 'number' | 'bool' | 'chat_type' | 'media' | 'message';

export interface ApiParam {
  key: string;
  kind?: ParamKind;
  optional?: boolean;
}

const p = (key: string, kind: ParamKind = 'text', optional = false) => ({
  key,
  kind,
  optional,
});
const CHAT_PARAMS = [
  p('chat_type', 'chat_type'),
  p('chat_id'),
  p('message_id'),
];

/** Standard platform APIs grouped for the picker (sending lives in its own steps). */
export const API_GROUPS: {
  key: string;
  apis: Record<string, ApiParam[]>;
}[] = [
  {
    key: 'group',
    apis: {
      mute_member: [p('group_id'), p('user_id'), p('duration', 'number')],
      unmute_member: [p('group_id'), p('user_id')],
      kick_member: [p('group_id'), p('user_id')],
      set_group_name: [p('group_id'), p('name')],
      get_group_info: [p('group_id')],
      get_group_member_info: [p('group_id'), p('user_id')],
      get_group_member_list: [p('group_id')],
      get_group_list: [],
      leave_group: [p('group_id')],
    },
  },
  {
    key: 'message',
    apis: {
      delete_message: CHAT_PARAMS,
      edit_message: [...CHAT_PARAMS, p('new_content', 'message')],
      forward_message: [
        p('from_chat_type', 'chat_type'),
        p('from_chat_id'),
        p('message_id'),
        p('to_chat_type', 'chat_type'),
        p('to_chat_id'),
      ],
      get_message: CHAT_PARAMS,
    },
  },
  {
    key: 'user',
    apis: {
      approve_friend_request: [
        p('request_id'),
        p('approve', 'bool'),
        p('remark', 'text', true),
      ],
      approve_group_invite: [p('request_id'), p('approve', 'bool')],
      get_user_info: [p('user_id')],
      get_friend_list: [],
    },
  },
  {
    key: 'file',
    apis: {
      upload_file: [p('file_data', 'media'), p('filename')],
      get_file_url: [p('file_id')],
    },
  },
];

export const API_PARAMS: Record<string, ApiParam[]> = Object.assign(
  {},
  ...API_GROUPS.map((group) => group.apis),
);

/** Defaults that point at the triggering message or event. */
export const PARAM_DEFAULTS: Record<string, unknown> = {
  group_id: '{{ start.group_id }}',
  user_id: '{{ start.sender_id }}',
  chat_type: '{{ start.chat_type }}',
  chat_id: '{{ start.chat_id }}',
  from_chat_type: '{{ start.chat_type }}',
  from_chat_id: '{{ start.chat_id }}',
  to_chat_type: 'group',
  message_id: '{{ start.message_id }}',
  request_id: '{{ start.event.request_id }}',
  approve: true,
  duration: '600',
};

export interface AdapterCapabilities {
  label: string;
  events: string[];
  apis: string[];
  specific: { action: string; description?: string }[];
}
