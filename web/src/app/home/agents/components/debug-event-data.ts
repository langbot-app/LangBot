export interface DebugEventField {
  key: string;
  label: string;
  value: string | number;
  sample?: 'user' | 'message' | 'feedback';
  multiline?: boolean;
  required?: boolean;
  min?: number;
  max?: number;
  placeholder?: string;
}

interface DebugEventDefinition {
  fields: DebugEventField[];
  defaults?: Record<string, unknown>;
  messageField?: string;
}

const group: DebugEventField = {
  key: 'group_id',
  label: 'groupId',
  value: 'debug-group',
};
const member: DebugEventField = {
  key: 'member_id',
  label: 'memberId',
  value: 'debug-user',
};
const memberName: DebugEventField = {
  key: 'member_name',
  label: 'memberName',
  value: '',
  sample: 'user',
};
const user: DebugEventField = {
  key: 'user_id',
  label: 'userId',
  value: 'debug-user',
};
const userName: DebugEventField = {
  key: 'user_name',
  label: 'userName',
  value: '',
  sample: 'user',
};
const requester: DebugEventField = {
  key: 'requester_id',
  label: 'requesterId',
  value: 'debug-user',
};
const messageId: DebugEventField = {
  key: 'message_id',
  label: 'messageId',
  value: 'debug-message',
};
const duration: DebugEventField = {
  key: 'duration',
  label: 'duration',
  value: 60,
  min: 0,
};
const message: DebugEventField = {
  key: 'text',
  label: 'message',
  value: '',
  sample: 'message',
  multiline: true,
  required: true,
};
const membership: DebugEventDefinition = {
  fields: [memberName, member, group],
};
const friendship: DebugEventDefinition = { fields: [userName, user] };
const deletion: DebugEventDefinition = { fields: [messageId, group] };

// The compact form projects the existing debug API data fields. Fields omitted
// from the form, including custom fields, remain editable in the same JSON data.
const DEBUG_EVENT_DEFINITIONS: Record<string, DebugEventDefinition> = {
  'message.received': {
    fields: [
      message,
      userName,
      { ...group, value: '', placeholder: 'privateChat' },
    ],
    defaults: { user_id: 'debug-user' },
    messageField: 'text',
  },
  'message.edited': {
    fields: [{ ...message, label: 'newMessage' }, messageId, group],
    messageField: 'text',
  },
  'message.deleted': deletion,
  'message.recalled': deletion,
  'message.reaction': {
    fields: [
      { key: 'reaction', label: 'reaction', value: '👍' },
      messageId,
      group,
    ],
    defaults: { is_add: true },
  },
  'group.member_joined': membership,
  'group.member_left': membership,
  'group.member_banned': { fields: [member, group, duration] },
  'group.info_updated': {
    fields: [
      { key: 'group_name', label: 'groupName', value: 'debug-group' },
      group,
    ],
  },
  'friend.request_received': {
    fields: [
      {
        key: 'message',
        label: 'verificationMessage',
        value: '',
        sample: 'message',
        multiline: true,
      },
      {
        key: 'requester_name',
        label: 'requesterName',
        value: '',
        sample: 'user',
      },
      requester,
    ],
    defaults: { request_id: 'debug-friend-request' },
  },
  'friend.added': friendship,
  'friend.removed': friendship,
  'bot.invited_to_group': {
    fields: [group, requester],
    defaults: { request_id: 'debug-group-request' },
  },
  'bot.muted': { fields: [group, duration] },
  'bot.unmuted': { fields: [group] },
  'bot.removed_from_group': { fields: [group] },
  'feedback.received': {
    fields: [
      {
        key: 'content',
        label: 'feedback',
        value: '',
        sample: 'feedback',
        multiline: true,
      },
      { key: 'rating', label: 'rating', value: 5, min: 1, max: 5 },
    ],
  },
  'platform.specific': {
    fields: [
      { key: 'event_name', label: 'eventName', value: 'debug-platform-event' },
    ],
  },
};

// Event processors receive the SDK's typed EBA payload, rather than Agent debug aliases.
const PROCESSOR_EVENT_DEFINITIONS: Record<string, DebugEventDefinition> =
  Object.fromEntries(
    Object.entries(DEBUG_EVENT_DEFINITIONS)
      .filter(([type]) => type !== 'message.recalled')
      .map(([type, definition]) => {
        const paths: Record<string, string> = {
          group_id: 'group.id',
          group_name: 'group.name',
          member_id: 'member.id',
          member_name: 'member.nickname',
          user_id: 'user.id',
          user_name: 'user.nickname',
          requester_id:
            type === 'bot.invited_to_group' ? 'inviter.id' : 'user.id',
          requester_name: 'user.nickname',
          event_name: 'action',
        };
        return [
          type,
          {
            ...definition,
            fields: definition.fields.map((field) => ({
              ...field,
              key: paths[field.key] ?? field.key,
            })),
          },
        ];
      }),
  );
for (const [type, chain, sender] of [
  ['message.received', 'message_chain', 'sender'],
  ['message.edited', 'new_content', 'editor'],
]) {
  PROCESSOR_EVENT_DEFINITIONS[type] = {
    fields: [
      { ...message, key: `${chain}.0.text` },
      { ...userName, key: `${sender}.nickname` },
      { ...user, key: `${sender}.id` },
      { key: 'chat_id', label: 'chatId', value: 'debug-user' },
    ],
    defaults: {
      [chain]: [{ type: 'Plain', text: '' }],
      chat_type: 'private',
      message_id: 'debug-message',
    },
    messageField: `${chain}.0.text`,
  };
}
for (const type of ['message.deleted', 'message.reaction']) {
  const definition = PROCESSOR_EVENT_DEFINITIONS[type];
  definition.fields = definition.fields.filter(
    (field) => field.key !== 'group.id',
  );
  definition.fields.push({
    key: 'chat_id',
    label: 'chatId',
    value: 'debug-user',
  });
  definition.defaults = { ...definition.defaults, chat_type: 'private' };
}
PROCESSOR_EVENT_DEFINITIONS['feedback.received'] = {
  fields: [
    {
      key: 'feedback_content',
      label: 'feedback',
      value: '',
      sample: 'feedback',
      multiline: true,
    },
    {
      key: 'feedback_type',
      label: 'feedbackType',
      value: 1,
      min: 1,
      max: 3,
      required: true,
    },
    user,
    messageId,
  ],
  defaults: { feedback_id: 'debug-feedback' },
};

export const processorDebugEventTypes = Object.keys(
  PROCESSOR_EVENT_DEFINITIONS,
);

export function getDebugEventField(data: unknown, path: string): unknown {
  return path
    .split('.')
    .reduce<unknown>(
      (value, key) =>
        value && typeof value === 'object' && Object.hasOwn(value, key)
          ? (value as Record<string, unknown>)[key]
          : undefined,
      data,
    );
}

export function setDebugEventField(
  data: Record<string, unknown>,
  path: string,
  value: unknown,
): Record<string, unknown> {
  const [key, ...rest] = path.split('.');
  if (['__proto__', 'constructor', 'prototype'].includes(key)) return data;
  const current = data[key];
  const next = rest.length
    ? setDebugEventField(
        current && typeof current === 'object'
          ? (current as Record<string, unknown>)
          : {},
        rest.join('.'),
        value,
      )
    : value;
  return Array.isArray(data)
    ? Object.assign([...data], { [key]: next })
    : { ...data, [key]: next };
}

export function debugEventDefinition(
  eventType: string,
  processor = false,
): DebugEventDefinition | undefined {
  const definitions = processor
    ? PROCESSOR_EVENT_DEFINITIONS
    : DEBUG_EVENT_DEFINITIONS;
  return Object.hasOwn(definitions, eventType)
    ? definitions[eventType]
    : undefined;
}

export function createDebugEventData(
  eventType: string,
  samples: Record<'user' | 'message' | 'feedback', string>,
  processor = false,
) {
  const definition = debugEventDefinition(eventType, processor);
  return (definition?.fields ?? []).reduce<Record<string, unknown>>(
    (data, field) =>
      setDebugEventField(
        data,
        field.key,
        field.sample ? samples[field.sample] : field.value,
      ),
    { ...definition?.defaults },
  );
}

export function parseDebugEventData(
  text: string,
): Record<string, unknown> | null {
  try {
    const value = JSON.parse(text);
    return value && !Array.isArray(value) && typeof value === 'object'
      ? value
      : null;
  } catch {
    return null;
  }
}

export function invalidDebugEventField(
  eventType: string,
  data: Record<string, unknown>,
  processor = false,
) {
  return debugEventDefinition(eventType, processor)?.fields.find((field) => {
    const value = getDebugEventField(data, field.key);
    // Rich messages are edited as full JSON; a first Plain component is not required.
    if (processor && field.key.endsWith('.0.text')) {
      const chain = data[field.key.split('.')[0]];
      if (
        Array.isArray(chain) &&
        chain.length > 0 &&
        (chain.length > 1 || chain[0]?.type !== 'Plain')
      )
        return false;
    }
    if (
      value === undefined ||
      value === null ||
      (typeof value === 'string' && !value.trim())
    )
      return field.required;
    if (typeof field.value === 'number') {
      return (
        typeof value !== 'number' ||
        !Number.isFinite(value) ||
        !Number.isInteger(value) ||
        (field.min !== undefined && value < field.min) ||
        (field.max !== undefined && value > field.max)
      );
    }
    return (
      typeof value !== 'string' &&
      !(
        (field.key.endsWith('_id') || field.key.endsWith('.id')) &&
        typeof value === 'number'
      )
    );
  });
}

export function debugEventInputText(
  eventType: string,
  data: Record<string, unknown>,
  processor = false,
) {
  const key = debugEventDefinition(eventType, processor)?.messageField;
  const value = key ? getDebugEventField(data, key) : undefined;
  return typeof value === 'string' ? value.trim() : '';
}
