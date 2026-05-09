import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useTranslation } from 'react-i18next';
import { Loader2, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';
import QRCode from 'qrcode';

interface FeishuAppCreatorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (credentials: {
    app_id: string;
    app_secret: string;
    app_name?: string;
  }) => void;
}

type DialogState = 'connecting' | 'waiting' | 'success' | 'error';

const POLL_INTERVAL_MS = 3000;

export default function FeishuAppCreatorDialog({
  open,
  onOpenChange,
  onSuccess,
}: FeishuAppCreatorDialogProps) {
  const { t } = useTranslation();
  const [state, setState] = useState<DialogState>('connecting');
  const [qrUrl, setQrUrl] = useState('');
  const [expireIn, setExpireIn] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const [qrDataUrl, setQrDataUrl] = useState('');
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  const onOpenChangeRef = useRef(onOpenChange);
  onOpenChangeRef.current = onOpenChange;
  const tRef = useRef(t);
  tRef.current = t;

  const cleanup = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    // Cancel backend session
    if (sessionIdRef.current) {
      const token = localStorage.getItem('token');
      const baseUrl =
        import.meta.env.VITE_API_BASE_URL || window.location.origin;
      fetch(
        `${baseUrl}/api/v1/platform/adapters/lark/create-app/${sessionIdRef.current}`,
        {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        },
      ).catch(() => {});
      sessionIdRef.current = null;
    }
  }, []);

  const startRegistration = useCallback(async () => {
    cleanup();
    setState('connecting');
    setQrUrl('');
    setExpireIn(0);
    setErrorMessage('');

    const token = localStorage.getItem('token');
    const baseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin;

    try {
      const controller = new AbortController();
      abortRef.current = controller;

      const res = await fetch(
        `${baseUrl}/api/v1/platform/adapters/lark/create-app`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        },
      );

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const json = await res.json();
      if (json.code !== 0) throw new Error(json.msg || 'Request failed');

      const { session_id, qr_url, expire_at } = json.data;
      sessionIdRef.current = session_id;
      setQrUrl(qr_url);
      setState('waiting');

      // Calculate remaining seconds
      const remaining = Math.max(0, Math.floor(expire_at - Date.now() / 1000));
      setExpireIn(remaining);

      // Start countdown
      countdownRef.current = setInterval(() => {
        setExpireIn((prev) => {
          if (prev <= 1) {
            if (countdownRef.current) {
              clearInterval(countdownRef.current);
              countdownRef.current = null;
            }
            return 0;
          }
          return prev - 1;
        });
      }, 1000);

      // Start polling
      pollTimerRef.current = setInterval(async () => {
        try {
          const pollRes = await fetch(
            `${baseUrl}/api/v1/platform/adapters/lark/create-app/status/${session_id}`,
            { headers: { Authorization: `Bearer ${token}` } },
          );
          if (!pollRes.ok) return;

          const pollJson = await pollRes.json();
          if (pollJson.code !== 0) return;

          const { status, app_id, app_secret, error } = pollJson.data;

          if (status === 'success' && app_id && app_secret) {
            sessionIdRef.current = null; // backend already cleaned up
            cleanup();
            setState('success');
            setTimeout(() => {
              onSuccessRef.current({ app_id, app_secret });
              onOpenChangeRef.current(false);
            }, 1500);
          } else if (status === 'error') {
            sessionIdRef.current = null; // backend already cleaned up
            cleanup();
            setState('error');
            setErrorMessage(error || tRef.current('feishu.createFailed'));
          }
        } catch {
          // ignore poll errors, will retry next interval
        }
      }, POLL_INTERVAL_MS);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setState('error');
      setErrorMessage(
        err instanceof Error
          ? err.message
          : tRef.current('feishu.createFailed'),
      );
    }
  }, [cleanup]);

  useEffect(() => {
    if (open) {
      startRegistration();
    }
    return () => {
      cleanup();
    };
  }, [open, startRegistration, cleanup]);

  // Generate QR code locally when qrUrl changes
  useEffect(() => {
    if (!qrUrl) {
      setQrDataUrl('');
      return;
    }
    let cancelled = false;
    QRCode.toDataURL(qrUrl, { width: 224, margin: 2 }).then((url) => {
      if (!cancelled) setQrDataUrl(url);
    });
    return () => {
      cancelled = true;
    };
  }, [qrUrl]);

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      cleanup();
    }
    onOpenChange(newOpen);
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    if (m > 0) {
      return `${m}m${s.toString().padStart(2, '0')}s`;
    }
    return `${s}s`;
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('feishu.createApp')}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col items-center justify-center py-4 space-y-4">
          {/* Connecting */}
          {state === 'connecting' && (
            <div className="flex flex-col items-center space-y-3 py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {t('feishu.connecting')}
              </p>
            </div>
          )}

          {/* QR code area */}
          {state === 'waiting' && qrUrl && (
            <div className="flex flex-col items-center space-y-3">
              <p className="text-sm text-muted-foreground text-center">
                {t('feishu.scanQRCode')}
              </p>
              <div className="border rounded-lg p-2 bg-white">
                {qrDataUrl ? (
                  <img
                    src={qrDataUrl}
                    alt="Feishu QR Code"
                    className="w-56 h-56"
                  />
                ) : (
                  <div className="w-56 h-56 flex items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  </div>
                )}
              </div>
              {expireIn > 0 && (
                <p className="text-xs text-muted-foreground">
                  {t('feishu.waitingForScan')} ({formatTime(expireIn)})
                </p>
              )}
            </div>
          )}

          {/* Success */}
          {state === 'success' && (
            <div className="flex flex-col items-center space-y-3 py-8">
              <CheckCircle2 className="h-12 w-12 text-green-500" />
              <p className="text-sm text-green-600 font-medium">
                {t('feishu.createSuccess')}
              </p>
            </div>
          )}

          {/* Error */}
          {state === 'error' && (
            <div className="flex flex-col items-center space-y-3 py-8">
              <XCircle className="h-12 w-12 text-red-500" />
              <p className="text-sm text-red-600 text-center">
                {errorMessage || t('feishu.createFailed')}
              </p>
            </div>
          )}
        </div>

        {state === 'error' && (
          <DialogFooter>
            <Button variant="outline" onClick={() => handleOpenChange(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={() => startRegistration()}>
              <RefreshCw className="h-4 w-4 mr-1.5" />
              {t('feishu.retry')}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
