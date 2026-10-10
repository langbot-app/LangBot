export const MODEL_CONFIGURATION_CHANGED =
  'langbot:model-configuration-changed';

export async function notifyAfterModelConfigurationChange<T>(
  request: Promise<T>,
): Promise<T> {
  const result = await request;
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(MODEL_CONFIGURATION_CHANGED));
  }
  return result;
}
