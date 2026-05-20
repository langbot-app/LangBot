import { useCallback, useEffect, useState } from 'react';

import type { ApiRespBoxStatus } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';

/**
 * Shared hook for Box runtime status — used by every UI surface that needs
 * to gate behaviour on whether the sandbox is available. Returns:
 *
 *   - status: full payload (or null while loading / on error)
 *   - available: convenience flag (status?.available === true)
 *   - disabled: true iff Box is explicitly disabled by config
 *               (status.enabled === false), distinguishing it from
 *               "configured but currently failed"
 *   - hint: a single i18n-key choice for the banner message —
 *           'boxDisabled' / 'boxUnavailable' / null
 *   - refresh: imperative re-fetch
 *
 * Polls every ``refreshMs`` (default 30s) so a flapping runtime is picked
 * up without a page reload.
 */
export function useBoxStatus(refreshMs = 30_000) {
  const [status, setStatus] = useState<ApiRespBoxStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await httpClient.getBoxStatus();
      setStatus(data);
    } catch {
      // Keep last-known status; the dashboard polls separately so a
      // transient failure here should not blank the UI for sandbox
      // consumers.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), refreshMs);
    return () => clearInterval(id);
  }, [refresh, refreshMs]);

  const available = status?.available === true;
  const disabled = status?.available === false && status?.enabled === false;
  const hint: 'boxDisabled' | 'boxUnavailable' | null = available
    ? null
    : disabled
      ? 'boxDisabled'
      : status
        ? 'boxUnavailable'
        : null;

  return { status, loading, available, disabled, hint, refresh };
}
