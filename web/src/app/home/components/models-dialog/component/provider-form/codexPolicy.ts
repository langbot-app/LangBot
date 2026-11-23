/** Subscription credentials are server-owned, never API-key form values. */
export function providerPayload(values: {
  name: string;
  requester: string;
  base_url: string;
  api_key?: string;
}) {
  const subscription = values.requester === 'openai-codex';
  return {
    name: values.name,
    requester: values.requester,
    base_url: subscription
      ? 'https://chatgpt.com/backend-api/codex'
      : values.base_url,
    api_keys: subscription ? [] : values.api_key ? [values.api_key] : [],
  };
}

export function pollDelay(interval: number, failures = 0): number {
  const seconds = Number.isFinite(interval) && interval > 0 ? interval : 5;
  return Math.max(seconds, Math.min(60, seconds * 2 ** failures)) * 1000;
}

export function isCodexVerificationUri(uri: string): boolean {
  return uri === 'https://auth.openai.com/codex/device';
}
