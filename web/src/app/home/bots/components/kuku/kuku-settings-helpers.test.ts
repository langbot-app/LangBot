import { describe, expect, it } from 'vitest';

import {
  buildKukuGroupSettingsPayload,
  createDefaultKukuSettingsFormValues,
  mapGroupSettingsToFormValues,
} from './kuku-settings-helpers';

describe('buildKukuGroupSettingsPayload', () => {
  it('omits quiet hours when all quiet-hour inputs are blank', () => {
    expect(
      buildKukuGroupSettingsPayload({
        groupId: '1234567890',
        personaId: 'kuku-sunny',
        silenceMinutes: '30',
        cooldownMinutes: '10',
        enabled: true,
        quietHoursStart: '',
        quietHoursEnd: '',
        quietHoursTimezone: '',
      }),
    ).toEqual({
      groupId: '1234567890',
      payload: {
        persona_id: 'kuku-sunny',
        silence_seconds: 1800,
        cooldown_minutes: 10,
        enabled: true,
        quiet_hours: {},
      },
    });
  });

  it('includes quiet hours when any quiet-hour input is provided', () => {
    expect(
      buildKukuGroupSettingsPayload({
        groupId: '1234567890',
        personaId: 'kuku-sunny',
        silenceMinutes: '15',
        cooldownMinutes: '5',
        enabled: false,
        quietHoursStart: '00:00',
        quietHoursEnd: '08:00',
        quietHoursTimezone: 'UTC',
      }),
    ).toEqual({
      groupId: '1234567890',
      payload: {
        persona_id: 'kuku-sunny',
        silence_seconds: 900,
        cooldown_minutes: 5,
        enabled: false,
        quiet_hours: {
          start: '00:00',
          end: '08:00',
          timezone: 'UTC',
        },
      },
    });
  });

  it('throws when required inputs are invalid', () => {
    expect(() =>
      buildKukuGroupSettingsPayload({
        groupId: '   ',
        personaId: 'kuku-sunny',
        silenceMinutes: '30',
        cooldownMinutes: '10',
        enabled: true,
        quietHoursStart: '',
        quietHoursEnd: '',
        quietHoursTimezone: '',
      }),
    ).toThrow('groupId');

    expect(() =>
      buildKukuGroupSettingsPayload({
        groupId: '1234567890',
        personaId: 'kuku-sunny',
        silenceMinutes: '0',
        cooldownMinutes: '10',
        enabled: true,
        quietHoursStart: '',
        quietHoursEnd: '',
        quietHoursTimezone: '',
      }),
    ).toThrow('silenceMinutes');

    expect(() =>
      buildKukuGroupSettingsPayload({
        groupId: '1234567890',
        personaId: 'kuku-sunny',
        silenceMinutes: 'abc',
        cooldownMinutes: '10',
        enabled: true,
        quietHoursStart: '',
        quietHoursEnd: '',
        quietHoursTimezone: '',
      }),
    ).toThrow('silenceMinutes');
  });
});

describe('mapGroupSettingsToFormValues', () => {
  it('maps API settings into form values', () => {
    expect(
      mapGroupSettingsToFormValues({
        group_id: '99887766',
        persona_id: 'kuku-sunny',
        silence_seconds: 720,
        cooldown_minutes: 7,
        enabled: true,
        quiet_hours: {
          start: '23:00',
          end: '07:00',
          timezone: 'America/Los_Angeles',
        },
      }),
    ).toEqual({
      groupId: '99887766',
      personaId: 'kuku-sunny',
      silenceMinutes: '12',
      cooldownMinutes: '7',
      enabled: true,
      quietHoursStart: '23:00',
      quietHoursEnd: '07:00',
      quietHoursTimezone: 'America/Los_Angeles',
    });
  });

  it('falls back to defaults when optional fields are missing', () => {
    expect(
      mapGroupSettingsToFormValues({
        group_id: '99887766',
      }),
    ).toEqual({
      ...createDefaultKukuSettingsFormValues(),
      groupId: '99887766',
    });
  });
});
