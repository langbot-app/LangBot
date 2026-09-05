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

export function debugEventDefinition(
  eventType: string,
): DebugEventDefinition | undefined {
  return Object.hasOwn(DEBUG_EVENT_DEFINITIONS, eventType)
    ? DEBUG_EVENT_DEFINITIONS[eventType]
    : undefined;
}

export function createDebugEventData(
  eventType: string,
  samples: Record<'user' | 'message' | 'feedback', string>,
) {
  const definition = debugEventDefinition(eventType);
  return {
    ...definition?.defaults,
    ...Object.fromEntries(
      (definition?.fields ?? []).map((field) => [
        field.key,
        field.sample ? samples[field.sample] : field.value,
      ]),
    ),
  };
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
) {
  return debugEventDefinition(eventType)?.fields.find((field) => {
    const value = data[field.key];
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
      !(field.key.endsWith('_id') && typeof value === 'number')
    );
  });
}

export function debugEventInputText(
  eventType: string,
  data: Record<string, unknown>,
) {
  const key = debugEventDefinition(eventType)?.messageField;
  return key && typeof data[key] === 'string' ? data[key].trim() : '';
}
