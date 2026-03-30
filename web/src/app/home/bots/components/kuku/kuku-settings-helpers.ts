export interface KukuSettingsFormValues {
  groupId: string;
  personaId: string;
  silenceMinutes: string;
  cooldownMinutes: string;
  enabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
  quietHoursTimezone: string;
}

export interface KukuGroupSettingsLike {
  group_id?: string;
  persona_id?: string;
  silence_minutes?: number;
  cooldown_minutes?: number;
  enabled?: boolean;
  quiet_hours?: {
    start?: string;
    end?: string;
    timezone?: string;
  };
}

export function createDefaultKukuSettingsFormValues(): KukuSettingsFormValues {
  return {
    groupId: '',
    personaId: 'kuku-sunny',
    silenceMinutes: '30',
    cooldownMinutes: '10',
    enabled: true,
    quietHoursStart: '',
    quietHoursEnd: '',
    quietHoursTimezone: '',
  };
}

export function mapGroupSettingsToFormValues(
  settings: KukuGroupSettingsLike,
): KukuSettingsFormValues {
  const defaults = createDefaultKukuSettingsFormValues();

  return {
    groupId: settings.group_id ?? defaults.groupId,
    personaId: settings.persona_id ?? defaults.personaId,
    silenceMinutes: String(settings.silence_minutes ?? defaults.silenceMinutes),
    cooldownMinutes: String(
      settings.cooldown_minutes ?? defaults.cooldownMinutes,
    ),
    enabled: settings.enabled ?? defaults.enabled,
    quietHoursStart: settings.quiet_hours?.start ?? defaults.quietHoursStart,
    quietHoursEnd: settings.quiet_hours?.end ?? defaults.quietHoursEnd,
    quietHoursTimezone:
      settings.quiet_hours?.timezone ?? defaults.quietHoursTimezone,
  };
}

export function buildKukuGroupSettingsPayload(values: KukuSettingsFormValues): {
  groupId: string;
  payload: {
    persona_id: string;
    silence_minutes: number;
    cooldown_minutes: number;
    enabled: boolean;
    quiet_hours: Record<string, string>;
  };
} {
  const groupId = values.groupId.trim();
  if (!groupId) {
    throw new Error('groupId is required');
  }

  const silenceMinutes = parseRequiredNonNegativeInt(
    values.silenceMinutes,
    'silenceMinutes',
  );
  const cooldownMinutes = parseRequiredNonNegativeInt(
    values.cooldownMinutes,
    'cooldownMinutes',
  );

  const quietHours: Record<string, string> = {};
  if (values.quietHoursStart.trim()) {
    quietHours.start = values.quietHoursStart.trim();
  }
  if (values.quietHoursEnd.trim()) {
    quietHours.end = values.quietHoursEnd.trim();
  }
  if (values.quietHoursTimezone.trim()) {
    quietHours.timezone = values.quietHoursTimezone.trim();
  }

  return {
    groupId,
    payload: {
      persona_id: values.personaId,
      silence_minutes: silenceMinutes,
      cooldown_minutes: cooldownMinutes,
      enabled: values.enabled,
      quiet_hours: quietHours,
    },
  };
}

function parseRequiredNonNegativeInt(value: string, fieldName: string): number {
  if (!value.trim()) {
    throw new Error(`${fieldName} is required`);
  }

  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`${fieldName} must be a non-negative integer`);
  }

  return parsed;
}
