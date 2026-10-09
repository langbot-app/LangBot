type ToolDisplay = {
  fields: readonly string[];
  kind?: 'reply';
  recipient?: string;
};

// Explicit display declarations for built-in tools. Unknown tools have no
// summary: their parameters remain available in the payload disclosure.
const TOOL_DISPLAYS: Readonly<Record<string, ToolDisplay>> = {
  exec: { fields: ['command'] },
  read: { fields: ['path'] },
  write: { fields: ['path'] },
  edit: { fields: ['path'] },
  glob: { fields: ['pattern', 'path'] },
  grep: { fields: ['pattern', 'path'] },
  event_reply: { fields: ['text'], kind: 'reply' },
  platform_send_message: { fields: ['text'], kind: 'reply', recipient: 'target_id' },
  event_delete_message: { fields: [] },
  event_get_actor: { fields: [] },
  event_get_group: { fields: [] },
  event_get_group_member: { fields: [] },
  event_mute_member: { fields: ['duration'] },
  event_unmute_member: { fields: [] },
  event_kick_member: { fields: [] },
  event_respond_friend_request: { fields: ['approve', 'remark'] },
  event_respond_group_invite: { fields: ['approve'] },
  platform_get_message: { fields: ['chat_id', 'message_id'] },
  platform_delete_message: { fields: ['chat_id', 'message_id'] },
  platform_get_group_info: { fields: ['group_id'] },
  platform_get_group_list: { fields: [] },
  platform_get_group_member_list: { fields: ['group_id'] },
  platform_get_group_member_info: { fields: ['group_id', 'user_id'] },
  platform_set_group_name: { fields: ['group_id', 'name'] },
  platform_mute_member: { fields: ['group_id', 'user_id', 'duration'] },
  platform_unmute_member: { fields: ['group_id', 'user_id'] },
  platform_kick_member: { fields: ['group_id', 'user_id'] },
  platform_leave_group: { fields: ['group_id'] },
  platform_get_user_info: { fields: ['user_id'] },
  platform_get_friend_list: { fields: [] },
};

export function toolDisplay(name: string): ToolDisplay | undefined {
  return Object.prototype.hasOwnProperty.call(TOOL_DISPLAYS, name)
    ? TOOL_DISPLAYS[name] : undefined;
}

export function toolSummary(name: string, parameters: Record<string, unknown>) {
  const display = toolDisplay(name);
  const fields = (display?.fields ?? []).flatMap((field) => {
    const value = parameters[field];
    if (!['string', 'number', 'boolean'].includes(typeof value) || value === '') return [];
    return [{ field, text: String(value) }];
  });
  return {
    text: fields.map(({ field, text }) =>
      display?.kind === 'reply' || display?.fields.length === 1 ? text : `${field}: ${text}`,
    ).join('\n'),
    recipient: display?.recipient && typeof parameters[display.recipient] === 'string'
      ? String(parameters[display.recipient]) : '',
  };
}
