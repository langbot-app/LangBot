export function resolveBackendBaseUrl(
  configuredBaseUrl: string | undefined,
  origin: string,
): string {
  const normalizedOrigin = origin.replace(/\/+$/, '');
  const configured = configuredBaseUrl?.trim() ?? '';

  if (!configured || configured === '/') {
    return normalizedOrigin;
  }

  if (/^https?:\/\//i.test(configured)) {
    return configured.replace(/\/+$/, '');
  }

  return `${normalizedOrigin}/${configured.replace(/^\/+|\/+$/g, '')}`;
}

export function getBackendBaseUrl(): string {
  return resolveBackendBaseUrl(
    import.meta.env.VITE_API_BASE_URL,
    window.location.origin,
  );
}
