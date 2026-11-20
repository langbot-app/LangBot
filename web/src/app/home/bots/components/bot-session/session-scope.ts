/**
 * Monitoring session IDs.
 *
 * Group chats are recorded per member as
 * `groupmember_<group id length>_<group id>_<member id>`; whole-group
 * (`group_<id>`) and private (`person_<id>`) IDs keep their legacy shape.
 * Mirrors `parse_group_member_id` in
 * `src/langbot/pkg/persistence/session_summary_contract.py`.
 */
export interface GroupMemberSession {
  groupId: string;
  memberId: string;
}

const GROUP_MEMBER_PREFIX = 'groupmember_';

export function parseGroupMemberSessionId(
  sessionId: string,
): GroupMemberSession | null {
  if (!sessionId.startsWith(GROUP_MEMBER_PREFIX)) return null;
  const rest = sessionId.slice(GROUP_MEMBER_PREFIX.length);
  const separator = rest.indexOf('_');
  if (separator <= 0) return null;
  const length = rest.slice(0, separator);
  if (!/^[0-9]+$/.test(length) || String(Number(length)) !== length)
    return null;
  const payload = rest.slice(separator + 1);
  // Python measures the group ID in code points, so do the same here.
  const chars = Array.from(payload);
  const size = Number(length);
  if (chars[size] !== '_') return null;
  const memberId = chars.slice(size + 1).join('');
  if (!memberId || memberId !== memberId.trim()) return null;
  return { groupId: chars.slice(0, size).join(''), memberId };
}

export function parseSessionType(sessionId: string): 'person' | 'group' | null {
  const lower = sessionId.toLowerCase();
  if (lower.startsWith('person_')) return 'person';
  if (lower.startsWith('group_') || lower.startsWith(GROUP_MEMBER_PREFIX))
    return 'group';
  // Older records may carry a platform prefix such as `bot.PERSON_123`.
  if (lower.includes('person')) return 'person';
  if (lower.includes('group')) return 'group';
  return null;
}

/** The group ID a group session belongs to, for per-member or whole-group IDs. */
export function sessionGroupId(sessionId: string): string | null {
  const member = parseGroupMemberSessionId(sessionId);
  if (member) return member.groupId;
  const match = /^group_(.+)$/i.exec(sessionId);
  return match && !match[1].includes('#') ? match[1] : null;
}
