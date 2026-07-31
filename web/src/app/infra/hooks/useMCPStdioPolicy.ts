import { useCallback, useEffect, useState } from 'react';

import { httpClient } from '@/app/infra/http/HttpClient';

/**
 * Load the instance-level stdio MCP gate independently of Box health.
 *
 * The hook fails closed while loading or when System Info is unavailable.
 * This is only a WebUI guard; the backend loader enforces the same gate at
 * the final transport boundary.
 */
export function useMCPStdioPolicy() {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const info = await httpClient.getSystemInfo();
      setEnabled(info.mcp_stdio_enabled === true);
    } catch {
      setEnabled(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { enabled, loading, refresh };
}
