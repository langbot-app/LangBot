import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  Item,
  ItemMedia,
  ItemContent,
  ItemTitle,
  ItemDescription,
  ItemActions,
} from '@/components/ui/item';
import { httpClient } from '@/app/infra/http/HttpClient';
import { systemInfo } from '@/app/infra/http';
import {
  Loader2,
  ExternalLink,
  KeyRound,
  Layers,
  Fingerprint,
  Plus,
  Trash2,
  Pencil,
  ShieldCheck,
} from 'lucide-react';
import { startRegistration } from '@simplewebauthn/browser';
import PasswordChangeDialog from '../password-change-dialog/PasswordChangeDialog';
import TotpEnrollDialog from './TotpEnrollDialog';
import { PanelBody } from '../settings-dialog/panel-layout';

interface AccountSettingsPanelProps {
  // True when this panel is the active section and the dialog is open.
  active: boolean;
  onEmailResolved?: (email: string) => void;
}

interface PasskeyItem {
  uuid: string;
  name: string;
  aaguid?: string;
  transports?: string;
  backed_up?: boolean;
  created_at?: string;
  last_used_at?: string;
}

export default function AccountSettingsPanel({
  active,
  onEmailResolved,
}: AccountSettingsPanelProps) {
  const { t } = useTranslation();
  const [accountType, setAccountType] = useState<'local' | 'space'>('local');
  const [hasPassword, setHasPassword] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [spaceBindLoading, setSpaceBindLoading] = useState(false);
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [passkeys, setPasskeys] = useState<PasskeyItem[]>([]);
  const [passkeyLoading, setPasskeyLoading] = useState(false);
  const [registeringPasskey, setRegisteringPasskey] = useState(false);
  const [totpEnabled, setTotpEnabled] = useState(false);
  const [remainingRecoveryCodes, setRemainingRecoveryCodes] = useState(0);
  const [totpLoading, setTotpLoading] = useState(false);
  const [totpDialogOpen, setTotpDialogOpen] = useState(false);

  useEffect(() => {
    if (active) {
      loadUserInfo();
      loadPasskeys();
      loadTotpStatus();
    }
  }, [active]);

  async function loadUserInfo() {
    setLoading(true);
    try {
      const info = await httpClient.getUserInfo();
      setAccountType(info.account_type);
      setHasPassword(info.has_password);
      setUserEmail(info.user);
      onEmailResolved?.(info.user);
    } catch {
      toast.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  }

  async function loadPasskeys() {
    setPasskeyLoading(true);
    try {
      const list = await httpClient.getPasskeys();
      setPasskeys(list);
    } catch {
      // ignore
    } finally {
      setPasskeyLoading(false);
    }
  }

  async function loadTotpStatus() {
    setTotpLoading(true);
    try {
      const status = await httpClient.getTotpStatus();
      setTotpEnabled(status.enabled);
      setRemainingRecoveryCodes(status.remaining_recovery_codes);
    } catch {
      // ignore
    } finally {
      setTotpLoading(false);
    }
  }

  const handleAddPasskey = async () => {
    setRegisteringPasskey(true);
    try {
      const { options, challenge_token } =
        await httpClient.getPasskeyRegisterOptions(window.location.origin);
      const regResp = await startRegistration({ optionsJSON: options });
      const defaultName =
        prompt(t('account.passkeyNamePlaceholder')) || undefined;
      await httpClient.verifyPasskeyRegister(
        challenge_token,
        regResp,
        defaultName,
      );
      toast.success(t('account.passkeyAddedSuccess'));
      await loadPasskeys();
    } catch (error: any) {
      if (error?.name === 'NotAllowedError') {
        // User cancelled
      } else {
        toast.error(error?.message || t('common.error'));
      }
    } finally {
      setRegisteringPasskey(false);
    }
  };

  const handleDeletePasskey = async (uuid: string) => {
    if (!confirm(t('account.deletePasskeyConfirm'))) return;
    try {
      await httpClient.deletePasskey(uuid);
      toast.success(t('account.passkeyDeleteSuccess'));
      await loadPasskeys();
    } catch (error: any) {
      toast.error(error?.message || t('common.error'));
    }
  };

  const handleRenamePasskey = async (uuid: string, currentName: string) => {
    const newName = prompt(t('account.passkeyName'), currentName);
    if (!newName || !newName.trim() || newName === currentName) return;
    try {
      await httpClient.renamePasskey(uuid, newName.trim());
      toast.success(t('account.passkeyRenameSuccess'));
      await loadPasskeys();
    } catch (error: any) {
      toast.error(error?.message || t('common.error'));
    }
  };

  const handleBindSpace = async () => {
    setSpaceBindLoading(true);
    try {
      const currentOrigin = window.location.origin;
      const redirectUri = `${currentOrigin}/auth/space/callback?mode=bind`;
      const response = await httpClient.getSpaceBindAuthorizeUrl(redirectUri);
      window.location.href = response.authorize_url;
    } catch {
      toast.error(t('common.spaceLoginFailed'));
      setSpaceBindLoading(false);
    }
  };

  const handlePasswordDialogClose = (dialogOpen: boolean) => {
    setPasswordDialogOpen(dialogOpen);
    if (!dialogOpen) {
      // Reload user info to update password status
      loadUserInfo();
    }
  };

  return (
    <PanelBody>
      {userEmail && (
        <p className="mb-4 text-sm text-muted-foreground">{userEmail}</p>
      )}

      {loading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : (
        <div className="space-y-2">
          {/* Password Item */}
          <Item size="sm" variant="muted" className="rounded-lg">
            <ItemMedia variant="icon">
              <KeyRound className="h-4 w-4" />
            </ItemMedia>
            <ItemContent>
              <ItemTitle>{t('account.passwordStatus')}</ItemTitle>
              <ItemDescription>
                {hasPassword
                  ? t('account.passwordSetDescription')
                  : t('account.setPasswordHint')}
              </ItemDescription>
            </ItemContent>
            <ItemActions>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPasswordDialogOpen(true)}
                disabled={!systemInfo.allow_modify_login_info}
              >
                {hasPassword
                  ? t('common.changePassword')
                  : t('account.setPassword')}
              </Button>
            </ItemActions>
          </Item>

          {/* Space Account Item */}
          <Item size="sm" variant="muted" className="rounded-lg">
            <ItemMedia variant="icon">
              <Layers className="h-4 w-4" />
            </ItemMedia>
            <ItemContent>
              <ItemTitle>{t('account.spaceStatus')}</ItemTitle>
              <ItemDescription>
                {accountType === 'space'
                  ? t('account.spaceBoundDescription')
                  : t('account.bindSpaceDescription')}
              </ItemDescription>
            </ItemContent>
            {accountType === 'local' && (
              <ItemActions>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBindSpace}
                  disabled={
                    spaceBindLoading || !systemInfo.allow_modify_login_info
                  }
                >
                  {spaceBindLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <ExternalLink className="mr-2 h-4 w-4" />
                  )}
                  {t('account.bindSpaceButton')}
                </Button>
              </ItemActions>
            )}
          </Item>

          {/* Passkey Section */}
          <div className="pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-medium">
                  {t('account.passkeySectionTitle')}
                </h4>
                <p className="text-xs text-muted-foreground">
                  {t('account.passkeySectionDesc')}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleAddPasskey}
                disabled={
                  registeringPasskey || !systemInfo.allow_modify_login_info
                }
                className="cursor-pointer"
              >
                {registeringPasskey ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="mr-2 h-4 w-4" />
                )}
                {t('account.addPasskey')}
              </Button>
            </div>

            {passkeyLoading ? (
              <div className="flex justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : passkeys.length === 0 ? (
              <div className="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
                {t('account.noPasskeys')}
              </div>
            ) : (
              <div className="space-y-2">
                {passkeys.map((pk) => (
                  <Item
                    key={pk.uuid}
                    size="sm"
                    variant="muted"
                    className="rounded-lg"
                  >
                    <ItemMedia variant="icon">
                      <Fingerprint className="h-4 w-4" />
                    </ItemMedia>
                    <ItemContent>
                      <ItemTitle>{pk.name}</ItemTitle>
                      <ItemDescription>
                        {pk.created_at && (
                          <span>
                            {t('account.passkeyCreated', {
                              date: new Date(
                                pk.created_at,
                              ).toLocaleDateString(),
                            })}
                          </span>
                        )}
                        {pk.last_used_at && (
                          <span className="ml-2">
                            ·{' '}
                            {t('account.passkeyLastUsed', {
                              date: new Date(
                                pk.last_used_at,
                              ).toLocaleDateString(),
                            })}
                          </span>
                        )}
                      </ItemDescription>
                    </ItemContent>
                    <ItemActions>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 cursor-pointer"
                        onClick={() => handleRenamePasskey(pk.uuid, pk.name)}
                        disabled={!systemInfo.allow_modify_login_info}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive cursor-pointer hover:text-destructive"
                        onClick={() => handleDeletePasskey(pk.uuid)}
                        disabled={!systemInfo.allow_modify_login_info}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </ItemActions>
                  </Item>
                ))}
              </div>
            )}
          </div>

          {/* TOTP (2FA) Section */}
          <div className="pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-medium">
                  {t('account.totpSectionTitle')}
                </h4>
                <p className="text-xs text-muted-foreground">
                  {t('account.totpSectionDesc')}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setTotpDialogOpen(true)}
                disabled={totpLoading || !systemInfo.allow_modify_login_info}
                className="cursor-pointer"
              >
                {totpLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ShieldCheck className="mr-2 h-4 w-4" />
                )}
                {totpEnabled
                  ? t('account.disableTotp')
                  : t('account.enableTotp')}
              </Button>
            </div>

            <Item size="sm" variant="muted" className="rounded-lg">
              <ItemMedia variant="icon">
                <ShieldCheck className="h-4 w-4" />
              </ItemMedia>
              <ItemContent>
                <ItemTitle>
                  {totpEnabled
                    ? t('account.totpEnabled')
                    : t('account.totpDisabled')}
                </ItemTitle>
                <ItemDescription>
                  {totpEnabled
                    ? t('account.totpRecoveryCodesRemaining', {
                        count: remainingRecoveryCodes,
                      })
                    : t('account.totpSectionDesc')}
                </ItemDescription>
              </ItemContent>
            </Item>
          </div>
        </div>
      )}

      <PasswordChangeDialog
        open={passwordDialogOpen}
        onOpenChange={handlePasswordDialogClose}
        hasPassword={hasPassword}
      />

      <TotpEnrollDialog
        open={totpDialogOpen}
        onOpenChange={setTotpDialogOpen}
        enabled={totpEnabled}
        onChanged={loadTotpStatus}
      />
    </PanelBody>
  );
}
