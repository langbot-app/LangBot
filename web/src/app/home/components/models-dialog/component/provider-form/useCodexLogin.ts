import { useCallback, useEffect, useRef, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import type { CodexDeviceAuthorization } from '@/app/infra/entities/codex';
import { isCodexVerificationUri, pollDelay } from './codexPolicy';

type Phase =
  | 'disconnected'
  | 'loading'
  | 'starting'
  | 'pending'
  | 'connected'
  | 'expired'
  | 'error'
  | 'canceling';

/** One in-memory authorization, sequential polls, and stale-response fencing. */
export function useCodexLogin(enabled: boolean, providerId?: string) {
  const [phase, setPhase] = useState<Phase>('disconnected');
  const [device, setDevice] = useState<CodexDeviceAuthorization | null>(null);
  const [retrying, setRetrying] = useState(false);
  const generation = useRef(0);
  const busy = useRef(false);
  const attempt = useRef<{ uuid: string; authorizationId: string } | null>(
    null,
  );
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const deadline = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const request = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    generation.current++;
    clearTimeout(timer.current);
    clearTimeout(deadline.current);
    request.current?.abort();
    busy.current = false;
    const pending = attempt.current;
    attempt.current = null;
    return pending;
  }, []);

  const clearPending = useCallback(async () => {
    const pending = stop();
    if (pending)
      await httpClient.cancelCodexDeviceLogin(
        pending.uuid,
        pending.authorizationId,
      );
  }, [stop]);

  const loadStatus = useCallback(async (uuid: string) => {
    const version = generation.current;
    request.current = new AbortController();
    setPhase('loading');
    try {
      const status = await httpClient.getCodexAuthStatus(
        uuid,
        request.current.signal,
      );
      if (version === generation.current) setPhase(status.status);
    } catch {
      if (version === generation.current) setPhase('error');
    }
  }, []);

  useEffect(() => {
    setDevice(null);
    setPhase('disconnected');
    if (enabled && providerId) void loadStatus(providerId);
    return () => {
      // Device creation is deliberately not aborted: its late response must be
      // canceled server-side even if this form has already unmounted.
      void clearPending().catch(() => {});
    };
  }, [enabled, providerId, loadStatus, clearPending]);

  async function start(uuid: string) {
    if (busy.current) return;
    const old = stop();
    busy.current = true;
    const version = generation.current;
    setPhase('starting');
    setDevice(null);
    setRetrying(false);
    try {
      if (old)
        await httpClient.cancelCodexDeviceLogin(old.uuid, old.authorizationId);
      if (version !== generation.current) return;
      const authorization = await httpClient.startCodexDeviceLogin(uuid);
      if (version !== generation.current) {
        await httpClient.cancelCodexDeviceLogin(
          uuid,
          authorization.authorization_id,
        );
        return;
      }
      attempt.current = {
        uuid,
        authorizationId: authorization.authorization_id,
      };
      if (
        !isCodexVerificationUri(authorization.verification_uri) ||
        !Number.isFinite(authorization.expires_at)
      ) {
        await clearPending();
        setPhase('error');
        return;
      }
      setDevice(authorization);
      setPhase('pending');
      let interval = authorization.interval;
      let failures = 0;
      request.current = new AbortController();
      const signal = request.current.signal;
      const expire = () => {
        if (version !== generation.current) return;
        void clearPending().catch(() => {});
        setDevice(null);
        setPhase('expired');
      };
      deadline.current = setTimeout(
        expire,
        Math.max(0, authorization.expires_at * 1000 - Date.now()),
      );
      const poll = async () => {
        if (version !== generation.current) return;
        if (Date.now() >= authorization.expires_at * 1000) {
          expire();
          return;
        }
        try {
          const result = await httpClient.pollCodexDeviceLogin(
            uuid,
            authorization.authorization_id,
            signal,
          );
          if (version !== generation.current) return;
          if (result.status !== 'pending') {
            attempt.current = null;
            stop();
            setDevice(null);
            setPhase(result.status);
            return;
          }
          interval = result.interval ?? interval;
          failures = 0;
          setRetrying(false);
        } catch (error) {
          if (version !== generation.current) return;
          const code = (error as { code?: number }).code;
          if (
            (code === -1 || (code !== undefined && code >= 500)) &&
            failures < 3
          ) {
            failures++;
            setRetrying(true);
          } else {
            void clearPending().catch(() => {});
            setDevice(null);
            setPhase('error');
            return;
          }
        }
        timer.current = setTimeout(poll, pollDelay(interval, failures));
      };
      timer.current = setTimeout(poll, pollDelay(interval));
    } catch {
      if (version === generation.current) {
        busy.current = false;
        setPhase('error');
      }
    }
  }

  async function cancel(uuid: string) {
    setPhase('canceling');
    setDevice(null);
    const pending = clearPending();
    const version = generation.current;
    try {
      await pending;
      if (version === generation.current) await loadStatus(uuid);
    } catch {
      if (version === generation.current) setPhase('error');
    }
  }

  async function disconnect(uuid: string) {
    if (busy.current) return;
    busy.current = true;
    setPhase('loading');
    const version = generation.current;
    try {
      await httpClient.disconnectCodex(uuid);
      if (version === generation.current) await loadStatus(uuid);
    } catch {
      if (version === generation.current) setPhase('error');
    } finally {
      busy.current = false;
    }
  }

  return { phase, device, retrying, start, cancel, disconnect, loadStatus };
}
