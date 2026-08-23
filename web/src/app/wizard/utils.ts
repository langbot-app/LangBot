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
