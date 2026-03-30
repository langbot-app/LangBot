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
  silence_seconds?: number;
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

  const silenceSec = settings.silence_seconds ?? 1800;
  return {
    groupId: settings.group_id ?? defaults.groupId,
    personaId: settings.persona_id ?? defaults.personaId,
    silenceMinutes: String(Math.max(1, Math.round(silenceSec / 60))),
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
    silence_seconds: number;
    cooldown_minutes: number;
    enabled: boolean;
    quiet_hours: Record<string, string>;
  };
} {
  const groupId = values.groupId.trim();
  if (!groupId) {
    throw new Error('groupId is required');
  }

  const silenceMinutes = parseRequiredPositiveInt(
    values.silenceMinutes,
    'silenceMinutes',
  );
  const silenceSeconds = Math.min(86400, Math.max(60, silenceMinutes * 60));
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
      silence_seconds: silenceSeconds,
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

function parseRequiredPositiveInt(value: string, fieldName: string): number {
  const parsed = parseRequiredNonNegativeInt(value, fieldName);
  if (parsed < 1) {
    throw new Error(`${fieldName} must be at least 1`);
  }
  return parsed;
}
