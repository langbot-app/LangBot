import { useCallback, useEffect, useState } from 'react';
import type { TFunction } from 'i18next';
import { useCurrentWorkspace } from '@/app/infra/http';
import { httpClient } from '@/app/infra/http/HttpClient';
import type { MessageQuota } from '@/app/infra/entities/workspace';

const REFRESH_EVENT = 'langbot:message-quota-refresh';
const OPEN_PLANS_EVENT = 'langbot:open-cloud-plans';
const POLL_INTERVAL_MS = 60_000;

/** Ask every mounted quota view to refetch (e.g. after a Debug Chat reply). */
export function requestMessageQuotaRefresh(): void {
  window.dispatchEvent(new Event(REFRESH_EVENT));
}

/** Open the Cloud plans dialog owned by the home sidebar. */
export function openCloudPlans(): void {
  window.dispatchEvent(new Event(OPEN_PLANS_EVENT));
}

export function useOpenCloudPlansListener(open: () => void): void {
  useEffect(() => {
    window.addEventListener(OPEN_PLANS_EVENT, open);
    return () => window.removeEventListener(OPEN_PLANS_EVENT, open);
  }, [open]);
}

export interface DailyMessageQuotaState {
  /** Only Cloud Workspaces have a daily message quota. */
  cloud: boolean;
  quota: MessageQuota | null;
  error: boolean;
  refresh: () => void;
}

/**
 * Today's message usage for the current Cloud Workspace. Seeds from the
 * workspace snapshot, then polls while visible and refreshes on demand.
 */
export function useDailyMessageQuota(): DailyMessageQuotaState {
  const currentWorkspace = useCurrentWorkspace();
  const cloud = currentWorkspace?.workspace.source === 'cloud_projection';
  const workspaceUuid = currentWorkspace?.workspace.uuid;
  const [quota, setQuota] = useState<MessageQuota | null>(
    currentWorkspace?.message_quota ?? null,
  );
  const [error, setError] = useState(false);

  useEffect(() => {
    setQuota(currentWorkspace?.message_quota ?? null);
    setError(false);
  }, [workspaceUuid, currentWorkspace?.message_quota]);

  const refresh = useCallback(() => {
    if (!cloud) return;
    httpClient
      .getMessageQuota()
      .then((next) => {
        setQuota(next);
        setError(false);
      })
      .catch(() => setError(true));
  }, [cloud]);

  useEffect(() => {
    if (!cloud) return;
    refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') refresh();
    }, POLL_INTERVAL_MS);
    window.addEventListener(REFRESH_EVENT, refresh);
    window.addEventListener('focus', refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener(REFRESH_EVENT, refresh);
      window.removeEventListener('focus', refresh);
    };
  }, [cloud, refresh, workspaceUuid]);

  // The day rolls over at resets_at; refetch right after it.
  useEffect(() => {
    if (!cloud || !quota?.resets_at) return;
    const delay = new Date(quota.resets_at).getTime() - Date.now() + 2_000;
    if (!Number.isFinite(delay) || delay <= 0 || delay > 86_400_000) return;
    const timer = window.setTimeout(refresh, delay);
    return () => window.clearTimeout(timer);
  }, [cloud, quota?.resets_at, refresh]);

  return { cloud, quota, error, refresh };
}

export type QuotaLevel = 'normal' | 'warning' | 'exhausted';

export function quotaLevel(quota: MessageQuota): QuotaLevel {
  if (!quota.enforced || quota.limit <= 0) return 'normal';
  if (quota.remaining <= 0 || quota.used >= quota.limit) return 'exhausted';
  return quota.used / quota.limit >= 0.8 ? 'warning' : 'normal';
}

/** "today 08:00" / "tomorrow 08:00" in the viewer's local time zone. */
export function formatQuotaReset(t: TFunction, resetsAt: string): string {
  const reset = new Date(resetsAt);
  if (Number.isNaN(reset.getTime())) return '';
  const time = reset.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });
  const today = new Date();
  const sameDay = reset.toDateString() === today.toDateString();
  return t(sameDay ? 'dailyMessageQuota.today' : 'dailyMessageQuota.tomorrow', {
    time,
  });
}
