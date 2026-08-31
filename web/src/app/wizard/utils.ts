export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;

  if (typeof error === 'object' && error !== null && 'msg' in error) {
    const message = (error as { msg?: unknown }).msg;
    if (typeof message === 'string') return message;
  }

  return String(error);
}

function createSigningSecret(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join(
    '',
  );
}

export function ensureHttpBotSigningSecret(
  adapterName: string,
  config: Record<string, unknown>,
): Record<string, unknown> {
  if (
    adapterName !== 'http_bot' ||
    config.signature_required === false ||
    (typeof config.inbound_secret === 'string' && config.inbound_secret)
  ) {
    return config;
  }

  return {
    ...config,
    inbound_secret: createSigningSecret(),
  };
}

export function findDefaultPipeline<
  T extends { uuid?: string; is_default?: boolean },
>(pipelines: T[]): T | undefined {
  return pipelines.find(
    (pipeline) =>
      pipeline.is_default === true &&
      typeof pipeline.uuid === 'string' &&
      pipeline.uuid.length > 0,
  );
}

interface WebhookConfigItem {
  name: string;
  show_if?: {
    field: string;
    operator: 'eq' | 'neq' | 'in';
    value: unknown;
  };
}

export function isWebhookModeEnabled(
  configItems: WebhookConfigItem[],
  configValues: Record<string, unknown>,
): boolean {
  const webhookField = configItems.find((item) => item.name === 'webhook_url');
  if (!webhookField) return false;
  if (!webhookField.show_if) return true;

  const condition = webhookField.show_if;
  const actualValue = configValues[condition.field];
  if (condition.operator === 'eq') return actualValue === condition.value;
  if (condition.operator === 'neq') return actualValue !== condition.value;
  return (
    Array.isArray(condition.value) && condition.value.includes(actualValue)
  );
}

interface RequiredConfigItem {
  name: string;
  required: boolean;
  default: unknown;
}

function isPlaceholderDefault(value: string, defaultValue: unknown): boolean {
  if (typeof defaultValue !== 'string' || value !== defaultValue.trim()) {
    return false;
  }
  return /(^|:\/\/)your-/i.test(value);
}

export function isRequiredRunnerConfigComplete(
  configItems: RequiredConfigItem[],
  configValues: Record<string, unknown>,
): boolean {
  return configItems
    .filter((item) => item.required)
    .every((item) => {
      const value = configValues[item.name];
      if (typeof value === 'string') {
        const normalizedValue = value.trim();
        return (
          normalizedValue.length > 0 &&
          !isPlaceholderDefault(normalizedValue, item.default)
        );
      }
      if (Array.isArray(value)) return value.length > 0;
      return value !== undefined && value !== null;
    });
}

export function configureLocalAgentPrimaryModel(
  config: Record<string, unknown>,
  modelUuid: string,
): Record<string, unknown> {
  const aiConfig = (config.ai ?? {}) as Record<string, unknown>;
  const runnerConfig = (aiConfig.runner ?? {}) as Record<string, unknown>;
  const localAgentConfig = (aiConfig['local-agent'] ?? {}) as Record<
    string,
    unknown
  >;
  const modelConfig = (localAgentConfig.model ?? {}) as Record<string, unknown>;

  return {
    ...config,
    ai: {
      ...aiConfig,
      runner: { ...runnerConfig, runner: 'local-agent' },
      'local-agent': {
        ...localAgentConfig,
        model: {
          ...modelConfig,
          primary: modelUuid,
          fallbacks: Array.isArray(modelConfig.fallbacks)
            ? modelConfig.fallbacks
            : [],
        },
      },
    },
  };
}
