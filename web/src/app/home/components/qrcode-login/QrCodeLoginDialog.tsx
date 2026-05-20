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

export type QrLoginPlatform = 'feishu' | 'weixin' | 'dingtalk' | 'wecombot';

interface PlatformConfig {
  titleKey: string;
  connectingKey: string;
  scanQRCodeKey: string;
  waitingKey: string;
  successKey: string;
  failedKey: string;
  retryKey: string;
  apiBase: string;
  extractSuccess: (data: Record<string, string>) => Record<string, string>;
  successNoteKey?: string;
}

const PLATFORM_CONFIGS: Record<QrLoginPlatform, PlatformConfig> = {
  feishu: {
    titleKey: 'feishu.createApp',
    connectingKey: 'feishu.connecting',
    scanQRCodeKey: 'feishu.scanQRCode',
    waitingKey: 'feishu.waitingForScan',
    successKey: 'feishu.createSuccess',
    failedKey: 'feishu.createFailed',
    retryKey: 'feishu.retry',
    apiBase: '/api/v1/platform/adapters/lark/create-app',
    extractSuccess: (data) => ({
      app_id: data.app_id,
      app_secret: data.app_secret,
      ...(data.app_name ? { app_name: data.app_name } : {}),
    }),
  },
  weixin: {
    titleKey: 'weixin.scanLogin',
    connectingKey: 'feishu.connecting',
    scanQRCodeKey: 'weixin.scanQRCode',
    waitingKey: 'feishu.waitingForScan',
    successKey: 'weixin.loginSuccess',
    failedKey: 'weixin.loginFailed',
    retryKey: 'feishu.retry',
    apiBase: '/api/v1/platform/adapters/weixin/login',
    extractSuccess: (data) => ({
      token: data.token,
      base_url: data.base_url,
      ...(data.account_id ? { account_id: data.account_id } : {}),
    }),
  },
  dingtalk: {
    titleKey: 'dingtalk.createApp',
    connectingKey: 'dingtalk.connecting',
    scanQRCodeKey: 'dingtalk.scanQRCode',
    waitingKey: 'dingtalk.waitingForScan',
    successKey: 'dingtalk.createSuccess',
    failedKey: 'dingtalk.createFailed',
    retryKey: 'dingtalk.retry',
    apiBase: '/api/v1/platform/adapters/dingtalk/create-app',
    extractSuccess: (data) => ({
      client_id: data.client_id,
      client_secret: data.client_secret,
    }),
    successNoteKey: 'dingtalk.robotCodeNote',
  },
  wecombot: {
    titleKey: 'wecombot.createBot',
    connectingKey: 'wecombot.connecting',
    scanQRCodeKey: 'wecombot.scanQRCode',
    waitingKey: 'wecombot.waitingForScan',
    successKey: 'wecombot.createSuccess',
    failedKey: 'wecombot.createFailed',
    retryKey: 'wecombot.retry',
    apiBase: '/api/v1/platform/adapters/wecombot/create-bot',
    extractSuccess: (data) => ({
      BotId: data.botid,
      Secret: data.secret,
    }),
    successNoteKey: 'wecombot.robotNameNote',
  },
};

interface QrCodeLoginDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  platform: QrLoginPlatform;
  onSuccess: (credentials: Record<string, string>) => void;
}

type DialogState = 'connecting' | 'waiting' | 'success' | 'error';

const POLL_INTERVAL_MS = 3000;

export default function QrCodeLoginDialog({
  open,
  onOpenChange,
  platform,
  onSuccess,
}: QrCodeLoginDialogProps) {
  const { t } = useTranslation();
  const platformConfig = PLATFORM_CONFIGS[platform];

  const [state, setState] = useState<DialogState>('connecting');
  const [qrDataUrl, setQrDataUrl] = useState('');
  const [expireIn, setExpireIn] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const cleanedRef = useRef(false);

  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  const onOpenChangeRef = useRef(onOpenChange);
  onOpenChangeRef.current = onOpenChange;
  const tRef = useRef(t);
  tRef.current = t;
  const platformConfigRef = useRef(platformConfig);
  platformConfigRef.current = platformConfig;

  const cleanup = useCallback(() => {
    if (cleanedRef.current) return;
    cleanedRef.current = true;

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
        `${baseUrl}${platformConfigRef.current.apiBase}/${sessionIdRef.current}`,
        {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
          keepalive: true,
        },
      ).catch(() => {});
      sessionIdRef.current = null;
    }
  }, []);

  const startLogin = useCallback(async () => {
    cleanup();
    cleanedRef.current = false;
    setState('connecting');
    setQrDataUrl('');
    setExpireIn(0);
    setErrorMessage('');

    const token = localStorage.getItem('token');
    const baseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin;
    const cfg = platformConfigRef.current;

    try {
      const controller = new AbortController();
      abortRef.current = controller;

      const res = await fetch(`${baseUrl}${cfg.apiBase}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const json = await res.json();
      if (json.code !== 0) throw new Error(json.msg || 'Request failed');

      const { session_id, qr_data_url, qr_url, expire_at } = json.data;
      sessionIdRef.current = session_id;

      // qr_data_url is a pre-rendered data URL (WeChat);
      // qr_url is a plain URL string (Feishu) that needs local QR generation.
      if (qr_data_url) {
        setQrDataUrl(qr_data_url);
      } else if (qr_url) {
        const dataUrl = await QRCode.toDataURL(qr_url, {
          width: 224,
          margin: 2,
        });
        setQrDataUrl(dataUrl);
      }
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
            `${baseUrl}${cfg.apiBase}/status/${session_id}`,
            { headers: { Authorization: `Bearer ${token}` } },
          );
          if (!pollRes.ok) return;

          const pollJson = await pollRes.json();
          if (pollJson.code !== 0) return;

          const { status, error, ...rest } = pollJson.data;

          if (status === 'success') {
            sessionIdRef.current = null; // backend already cleaned up
            cleanup();
            setState('success');
            setTimeout(() => {
              onSuccessRef.current(cfg.extractSuccess(rest));
              onOpenChangeRef.current(false);
            }, 1500);
          } else if (status === 'error') {
            sessionIdRef.current = null;
            cleanup();
            setState('error');
            setErrorMessage(error || tRef.current(cfg.failedKey));
          }
        } catch {
          // ignore poll errors, will retry next interval
        }
      }, POLL_INTERVAL_MS);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setState('error');
      setErrorMessage(
        err instanceof Error ? err.message : tRef.current(cfg.failedKey),
      );
    }
  }, [cleanup]);

  useEffect(() => {
    if (open) {
      startLogin();
    }
    return () => {
      cleanup();
    };
  }, [open, startLogin, cleanup]);

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
          <DialogTitle>{t(platformConfig.titleKey)}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col items-center justify-center py-4 space-y-4">
          {/* Connecting */}
          {state === 'connecting' && (
            <div className="flex flex-col items-center space-y-3 py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {t(platformConfig.connectingKey)}
              </p>
            </div>
          )}

          {/* QR code area */}
          {state === 'waiting' && qrDataUrl && (
            <div className="flex flex-col items-center space-y-3">
              <p className="text-sm text-muted-foreground text-center">
                {t(platformConfig.scanQRCodeKey)}
              </p>
              <div className="border rounded-lg p-2 bg-white">
                <img src={qrDataUrl} alt="QR Code" className="w-56 h-56" />
              </div>
              {expireIn > 0 && (
                <p className="text-xs text-muted-foreground">
                  {t(platformConfig.waitingKey)} ({formatTime(expireIn)})
                </p>
              )}
            </div>
          )}

          {/* Success */}
          {state === 'success' && (
            <div className="flex flex-col items-center space-y-3 py-8">
              <CheckCircle2 className="h-12 w-12 text-green-500" />
              <p className="text-sm text-green-600 font-medium">
                {t(platformConfig.successKey)}
              </p>
              {platformConfig.successNoteKey && (
                <p className="text-xs text-muted-foreground text-center max-w-xs">
                  {t(platformConfig.successNoteKey)}
                </p>
              )}
            </div>
          )}

          {/* Error */}
          {state === 'error' && (
            <div className="flex flex-col items-center space-y-3 py-8">
              <XCircle className="h-12 w-12 text-red-500" />
              <p className="text-sm text-red-600 text-center">
                {errorMessage || t(platformConfig.failedKey)}
              </p>
            </div>
          )}
        </div>

        {state === 'error' && (
          <DialogFooter>
            <Button variant="outline" onClick={() => handleOpenChange(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={() => startLogin()}>
              <RefreshCw className="h-4 w-4 mr-1.5" />
              {t(platformConfig.retryKey)}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
