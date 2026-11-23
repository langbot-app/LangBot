import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  Loader2,
  ShieldCheck,
  ShieldOff,
  Copy,
  Check,
  Download,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';

/**
 * 'enroll' — the Account has no second factor: scan a server-rendered QR code,
 *            then confirm a code.
 * 'manage' — the Account already has one: regenerate codes or disable it.
 *
 * The mode is chosen by the caller when the dialog opens and is intentionally
 * NOT re-derived from live status, otherwise confirming an enrolment would flip
 * the dialog straight into the disable view and hide the recovery codes.
 */
export type TotpDialogMode = 'enroll' | 'manage';

type Step = 'confirm' | 'recovery' | 'manage' | 'regenerate' | 'disable';

interface TotpEnrollDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called when a change was made so the panel can refresh its status. */
  onChanged?: () => void;
  mode: TotpDialogMode;
}

export default function TotpEnrollDialog({
  open,
  onOpenChange,
  onChanged,
  mode,
}: TotpEnrollDialogProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState<Step>('confirm');
  const [loading, setLoading] = useState(false);
  // Server-rendered PNG data URL; the shared secret never reaches the browser.
  const [qrDataUrl, setQrDataUrl] = useState('');
  const [code, setCode] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  // Latched per opening so a status refresh cannot re-route an in-flight flow.
  const modeRef = useRef<TotpDialogMode>(mode);
  const changedRef = useRef(false);

  // `rotate: true` is the explicit refresh action. Leaving it false reuses the
  // server-side pending enrolment, so React StrictMode's double effect and any
  // request retry cannot invalidate the QR code already on screen.
  async function startEnroll(rotate = false) {
    try {
      const res = await httpClient.beginTotpEnroll(rotate);
      setQrDataUrl(res.qr_code_data_url);
      setCode('');
    } catch (error) {
      const apiError = error as { msg?: string };
      toast.error(apiError?.msg || t('common.error'));
    }
  }

  // Reset the wizard each time it is opened, then act on the latched mode.
  useEffect(() => {
    if (!open) {
      return;
    }
    modeRef.current = mode;
    changedRef.current = false;
    setQrDataUrl('');
    setCode('');
    setRecoveryCodes([]);
    setCopiedKey(null);

    if (mode === 'manage') {
      setStep('manage');
      return;
    }
    setStep('confirm');
    void startEnroll();
    // Intentionally keyed on `open`/`mode` only: `startEnroll` mutates local state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode]);

  function closeDialog() {
    // Flush any change once, on the way out, so the panel refreshes.
    if (changedRef.current) {
      changedRef.current = false;
      onChanged?.();
    }
    onOpenChange(false);
  }

  async function handleConfirm() {
    if (!code.trim()) {
      return;
    }
    setLoading(true);
    try {
      const res = await httpClient.confirmTotpEnroll(code.trim());
      setRecoveryCodes(res.recovery_codes || []);
      changedRef.current = true;
      // Stay on the recovery step: the codes are shown exactly once.
      setStep('recovery');
      toast.success(t('account.totpEnabledSuccess'));
    } catch {
      toast.error(t('account.totpInvalidCode'));
    } finally {
      setLoading(false);
    }
  }

  async function handleRegenerate() {
    if (!code.trim()) {
      return;
    }
    setLoading(true);
    try {
      const res = await httpClient.regenerateTotpRecoveryCodes(code.trim());
      setRecoveryCodes(res.recovery_codes || []);
      changedRef.current = true;
      setStep('recovery');
      toast.success(t('account.totpRecoveryCodesRegenerated'));
    } catch {
      toast.error(t('account.totpInvalidCode'));
    } finally {
      setLoading(false);
    }
  }

  async function handleDisable() {
    if (!code.trim()) {
      return;
    }
    setLoading(true);
    try {
      await httpClient.disableTotp(code.trim());
      changedRef.current = true;
      toast.success(t('account.totpDisabledSuccess'));
      closeDialog();
    } catch {
      toast.error(t('account.totpInvalidCode'));
    } finally {
      setLoading(false);
    }
  }

  async function copyText(value: string, key: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 1500);
    } catch {
      toast.error(t('common.error'));
    }
  }

  function downloadRecoveryCodes() {
    const blob = new Blob(
      [
        `${t('account.totpRecoveryCodesTitle')}\n\n${recoveryCodes.join('\n')}\n`,
      ],
      { type: 'text/plain' },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'langbot-recovery-codes.txt';
    link.click();
    URL.revokeObjectURL(url);
  }

  const titleByStep: Record<Step, string> = {
    confirm: t('account.totpEnrollTitle'),
    recovery: t('account.totpRecoveryCodesTitle'),
    manage: t('account.totpManageTitle'),
    regenerate: t('account.totpRegenerateCodes'),
    disable: t('account.disableTotp'),
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => (next ? onOpenChange(true) : closeDialog())}
    >
      <DialogContent className="sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5" />
            {titleByStep[step]}
          </DialogTitle>
          <DialogDescription>
            {step === 'confirm' && t('account.totpEnrollDesc')}
            {step === 'recovery' && t('account.totpRecoveryCodesDesc')}
            {step === 'manage' && t('account.totpManageDesc')}
            {step === 'regenerate' && t('account.totpRegenerateDesc')}
            {step === 'disable' && t('account.disableTotpDesc')}
          </DialogDescription>
        </DialogHeader>

        {step === 'confirm' && (
          <div className="space-y-4">
            {!qrDataUrl ? (
              <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                {t('account.totpGeneratingSecret')}
              </div>
            ) : (
              <>
                <div className="flex justify-center">
                  <img
                    src={qrDataUrl}
                    alt={t('account.totpQrAlt')}
                    className="h-[200px] w-[200px] rounded-md bg-white p-2"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="totp-code">
                    {t('account.totpEnterCode')}
                  </Label>
                  <Input
                    id="totp-code"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder={t('account.enterCode')}
                    inputMode="numeric"
                    spellCheck={false}
                    autoComplete="off"
                    className="tracking-widest"
                  />
                </div>

                <DialogFooter className="gap-2 sm:justify-between">
                  <Button
                    variant="outline"
                    onClick={() => void startEnroll(true)}
                    disabled={loading}
                    className="cursor-pointer"
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    {t('account.totpRefreshSecret')}
                  </Button>
                  <Button
                    onClick={handleConfirm}
                    disabled={loading || !code.trim()}
                    className="cursor-pointer"
                  >
                    {loading && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    {t('account.totpVerifyAndEnable')}
                  </Button>
                </DialogFooter>
              </>
            )}
          </div>
        )}

        {step === 'recovery' && (
          <div className="space-y-4">
            <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
              <p className="text-xs text-muted-foreground">
                {t('account.totpRecoveryCodesWarning')}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {recoveryCodes.map((value) => (
                <code
                  key={value}
                  className="rounded-md bg-muted px-2 py-1.5 text-center font-mono text-xs"
                >
                  {value}
                </code>
              ))}
            </div>

            <DialogFooter className="gap-2 sm:justify-between">
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="cursor-pointer"
                  onClick={() => copyText(recoveryCodes.join('\n'), 'all')}
                >
                  {copiedKey === 'all' ? (
                    <Check className="mr-2 h-3.5 w-3.5" />
                  ) : (
                    <Copy className="mr-2 h-3.5 w-3.5" />
                  )}
                  {t('common.copy')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="cursor-pointer"
                  onClick={downloadRecoveryCodes}
                >
                  <Download className="mr-2 h-3.5 w-3.5" />
                  {t('common.download')}
                </Button>
              </div>
              <Button
                size="sm"
                className="cursor-pointer"
                onClick={closeDialog}
              >
                {t('account.totpSavedCodes')}
              </Button>
            </DialogFooter>
          </div>
        )}

        {step === 'manage' && (
          <div className="space-y-3">
            <Button
              variant="outline"
              className="w-full justify-start cursor-pointer"
              onClick={() => {
                setCode('');
                setStep('regenerate');
              }}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              {t('account.totpRegenerateCodes')}
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start text-destructive hover:text-destructive cursor-pointer"
              onClick={() => {
                setCode('');
                setStep('disable');
              }}
            >
              <ShieldOff className="mr-2 h-4 w-4" />
              {t('account.disableTotp')}
            </Button>
            <DialogFooter>
              <Button
                variant="ghost"
                className="cursor-pointer"
                onClick={closeDialog}
              >
                {t('common.cancel')}
              </Button>
            </DialogFooter>
          </div>
        )}

        {(step === 'regenerate' || step === 'disable') && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="totp-manage-code">
                {t('account.totpOrRecoveryCode')}
              </Label>
              <Input
                id="totp-manage-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder={t('account.enterCode')}
                spellCheck={false}
                autoComplete="off"
              />
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                className="cursor-pointer"
                onClick={() => setStep('manage')}
              >
                {t('common.back')}
              </Button>
              <Button
                variant={step === 'disable' ? 'destructive' : 'default'}
                onClick={step === 'disable' ? handleDisable : handleRegenerate}
                disabled={loading || !code.trim()}
                className="cursor-pointer"
              >
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {step === 'disable'
                  ? t('account.disableTotp')
                  : t('account.totpRegenerateCodes')}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
