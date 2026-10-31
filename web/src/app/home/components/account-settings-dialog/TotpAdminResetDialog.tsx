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
  Copy,
  Check,
  Download,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';

/**
 * Owner/admin driven re-binding of another Account's second factor.
 *
 * The manager walks the Account through a fresh enrolment: the QR code is
 * rendered server-side (the shared secret never reaches the browser), the
 * Account scans it and reads back the 6-digit code, and the manager enters that
 * code to activate the credential. Recovery codes are then handed over.
 *
 * The previous authenticator stops working as soon as a new enrolment starts.
 */
type Step = 'confirm' | 'recovery';

interface TotpAdminResetDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The Account whose second factor is being re-bound. */
  accountUuid: string;
  /** Display name of that Account, used in the copy. */
  accountUser: string;
  /** Called when a change was made so the panel can refresh its status. */
  onChanged?: () => void;
}

export default function TotpAdminResetDialog({
  open,
  onOpenChange,
  accountUuid,
  accountUser,
  onChanged,
}: TotpAdminResetDialogProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState<Step>('confirm');
  const [loading, setLoading] = useState(false);
  const [qrDataUrl, setQrDataUrl] = useState('');
  const [code, setCode] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const changedRef = useRef(false);

  async function startReset() {
    try {
      const res = await httpClient.adminBeginTotpEnroll(accountUuid);
      setQrDataUrl(res.qr_code_data_url);
      setCode('');
    } catch (error) {
      const apiError = error as { msg?: string };
      toast.error(apiError?.msg || t('common.error'));
    }
  }

  // Reset the wizard each time it is opened for a (possibly new) Account.
  useEffect(() => {
    if (!open) {
      return;
    }
    changedRef.current = false;
    setStep('confirm');
    setQrDataUrl('');
    setCode('');
    setRecoveryCodes([]);
    setCopiedKey(null);
    void startReset();
    // Intentionally keyed on `open`/`accountUuid` only: `startReset` mutates state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, accountUuid]);

  function closeDialog() {
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
      const res = await httpClient.adminConfirmTotpEnroll(
        accountUuid,
        code.trim(),
      );
      setRecoveryCodes(res.recovery_codes || []);
      changedRef.current = true;
      setStep('recovery');
      toast.success(t('account.totpEnabledSuccess'));
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
        `${t('account.totpRecoveryCodesTitle')} - ${accountUser}\n\n${recoveryCodes.join('\n')}\n`,
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

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => (next ? onOpenChange(true) : closeDialog())}
    >
      <DialogContent className="sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5" />
            {step === 'confirm'
              ? t('account.totpAdminResetTitle', { user: accountUser })
              : t('account.totpRecoveryCodesTitle')}
          </DialogTitle>
          <DialogDescription>
            {step === 'confirm'
              ? t('account.totpAdminResetDesc')
              : t('account.totpRecoveryCodesDesc')}
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
                <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                  <p className="text-xs text-muted-foreground">
                    {t('account.totpAdminResetWarning', { user: accountUser })}
                  </p>
                </div>

                <div className="flex justify-center">
                  <img
                    src={qrDataUrl}
                    alt={t('account.totpQrAlt')}
                    className="h-[200px] w-[200px] rounded-md bg-white p-2"
                  />
                </div>

                <p className="text-xs text-muted-foreground">
                  {t('account.totpAdminResetHint')}
                </p>

                <div className="space-y-2">
                  <Label htmlFor="totp-admin-code">
                    {t('account.totpEnterCode')}
                  </Label>
                  <Input
                    id="totp-admin-code"
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
                    onClick={() => void startReset()}
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
                {t('account.totpAdminHandOverCodes', { user: accountUser })}
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
      </DialogContent>
    </Dialog>
  );
}
