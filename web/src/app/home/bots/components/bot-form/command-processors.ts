import type {
  Agent,
  BotCommandSettings,
  CommandProcessorDescriptor,
} from '@/app/infra/entities/api';

const PLUGIN_REF_PREFIX = 'plugin:';

export const DEFAULT_COMMAND_SETTINGS: BotCommandSettings = {
  enabled: true,
  prefixes: ['/'],
  processors: [],
};

/** Plugin id (`author/name`) a command processor instance belongs to. */
export function commandProcessorPluginId(agent?: Agent): string {
  const ref = agent?.component_ref ?? '';
  return ref.startsWith(PLUGIN_REF_PREFIX)
    ? ref.slice(PLUGIN_REF_PREFIX.length)
    : '';
}

/** Whether any command of a plugin declares per-bot settings. */
export function hasCommandSettings(
  descriptor?: CommandProcessorDescriptor,
): boolean {
  return (descriptor?.commands ?? []).some(
    (command) => command.config_schema.length > 0,
  );
}

/** Command parameters filled with each field's schema default. */
export function commandSchemaDefaults(
  descriptor?: CommandProcessorDescriptor,
): Record<string, Record<string, unknown>> {
  return Object.fromEntries(
    (descriptor?.commands ?? []).map((command) => [
      command.name,
      Object.fromEntries(
        command.config_schema
          .filter((field) => field.default !== undefined)
          .map((field) => [field.name, field.default]),
      ),
    ]),
  );
}
