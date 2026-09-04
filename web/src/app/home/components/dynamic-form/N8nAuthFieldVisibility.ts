const COMMON_N8N_CONFIG_FIELDS = new Set([
  'webhook-url',
  'auth-type',
  'timeout',
  'output-key',
  'response-handling',
]);

export function shouldShowN8nConfigField(
  fieldName: string,
  authType: string,
): boolean {
  if (COMMON_N8N_CONFIG_FIELDS.has(fieldName)) {
    return true;
  }

  return (
    (authType === 'basic' && fieldName.startsWith('basic-')) ||
    (authType === 'jwt' && fieldName.startsWith('jwt-')) ||
    (authType === 'header' && fieldName.startsWith('header-'))
  );
}
