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
  ShieldOff,
} from 'lucide-react';
import { startRegistration } from '@simplewebauthn/browser';
import PasswordChangeDialog from '../password-change-dialog/PasswordChangeDialog';
import TotpEnrollDialog, { type TotpDialogMode } from './TotpEnrollDialog';
import TotpAdminResetDialog from './TotpAdminResetDialog';
import { PanelBody } from '../settings-dialog/panel-layout';

interface AccountSettingsPanelProps {
  // True when this panel is the active section and the dialog is open.
  active: boolean;
  onEmailResolved?: (email: string) => void;
}

interface TotpAccountRow {
  account_uuid: string;
  user: string;
  status?: string;
  enabled: boolean;
  last_used_at?: string | null;
  recovery_codes_remaining: number;
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
  const [totpDialogOpen, setTotpDialogOpen] = useState(false);
  // Latched when the dialog opens so a status refresh cannot swap the flow.
  const [totpDialogMode, setTotpDialogMode] =
    useState<TotpDialogMode>('enroll');
  // Owner/admin re-binding flow: the target Account is latched on open.
  const [adminResetOpen, setAdminResetOpen] = useState(false);
  const [adminResetTarget, setAdminResetTarget] =
    useState<TotpAccountRow | null>(null);
  const [totpRows, setTotpRows] = useState<TotpAccountRow[]>([]);
  const [isManager, setIsManager] = useState(false);
  const [accountUuid, setAccountUuid] = useState('');
  const [totpStatus, setTotpStatus] = useState<{
    enabled: boolean;
    pending: boolean;
    recovery_codes_remaining: number;
    last_used_at?: string | null;
  } | null>(null);

  useEffect(() => {
    if (active) {
      loadUserInfo();
      loadPasskeys();
    }
  }, [active]);

  // Depends on `accountUuid`: the self row is keyed by it, so it must load after
  // the Account is resolved rather than in the same pass.
  useEffect(() => {
    if (active && accountUuid) {
      void loadTotpStatus();
      void loadTotpAccounts();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, accountUuid]);

  async function loadTotpStatus() {
    try {
      const own = await httpClient.getTotpStatus();
      setTotpStatus(own);
      setTotpRows((prev) => {
        const rest = prev.filter((row) => row.account_uuid !== accountUuid);
        return [
          {
            account_uuid: accountUuid,
            user: userEmail,
            enabled: own.enabled,
            last_used_at: own.last_used_at ?? null,
            recovery_codes_remaining: own.recovery_codes_remaining,
          },
          ...rest,
        ];
      });
    } catch {
      // A disabled or unavailable second factor must not break the panel.
      setTotpStatus(null);
    }
  }

  // Owners and admins may see and manage every Account's second factor.
  async function loadTotpAccounts() {
    try {
      const res = await httpClient.getTotpAccounts();
      // The role rule lives in the API: owners and admins receive the Workspace
      // list, everyone else receives 403. Deriving manager state from the list
      // length would hide oversight in a single-member Workspace.
      setIsManager(true);
      setTotpRows(res.accounts || []);
    } catch {
      // A non-manager receives 403 here; the panel keeps working on own state.
      setIsManager(false);
    }
  }

  // Owners/admins re-bind the Account by walking them through a fresh QR scan
  // rather than silently revoking, so the Account is never left locked out.
  function handleRevokeTotp(row: TotpAccountRow) {
    setAdminResetTarget(row);
    setAdminResetOpen(true);
  }

  async function loadUserInfo() {
    setLoading(true);
    try {
      const info = await httpClient.getUserInfo();
      setAccountType(info.account_type);
      setHasPassword(info.has_password);
      setUserEmail(info.user);
      setAccountUuid(info.account_uuid);
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

          {/* TOTP second factor. The card is informational: changing the factor
              happens from the action on the Account's own row. */}
          <div className="pt-4 space-y-3">
            <div>
              <h4 className="text-sm font-medium flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4" />
                {t('account.totpSectionTitle')}
              </h4>
              <p className="text-xs text-muted-foreground">
                {isManager
                  ? t('account.totpManagerSectionDesc')
                  : totpStatus?.enabled
                    ? t('account.totpEnabledDesc', {
                        count: totpStatus.recovery_codes_remaining,
                      })
                    : t('account.totpSectionDesc')}
              </p>
            </div>

            {totpRows.length === 0 ? (
              <div className="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
                {t('account.noAccounts')}
              </div>
            ) : (
              <div className="space-y-2">
                {totpRows.map((row) => {
                  // Managers re-bind someone else's factor through a dialog that
                  // shows a server-rendered QR code: the Account scans it and
                  // reads the code back, so the secret still only reaches their
                  // authenticator.
                  const isSelf = row.account_uuid === accountUuid;
                  return (
                    <Item
                      key={row.account_uuid}
                      size="sm"
                      variant="muted"
                      className="rounded-lg"
                    >
                      <ItemMedia variant="icon">
                        {row.enabled ? (
                          <ShieldCheck className="h-4 w-4" />
                        ) : (
                          <ShieldOff className="h-4 w-4" />
                        )}
                      </ItemMedia>
                      <ItemContent>
                        <ItemTitle>
                          {row.user}
                          {isSelf && (
                            <span className="ml-1 text-xs font-normal text-muted-foreground">
                              ({t('account.you')})
                            </span>
                          )}
                        </ItemTitle>
                        <ItemDescription>
                          {row.enabled
                            ? `${t('account.totpStatusEnabled')} · ${t(
                                'account.totpCodesRemaining',
                                { count: row.recovery_codes_remaining },
                              )}`
                            : t('account.totpStatusDisabled')}
                          {row.last_used_at && (
                            <span className="ml-2">
                              ·{' '}
                              {t('account.totpLastUsed', {
                                date: new Date(
                                  row.last_used_at,
                                ).toLocaleDateString(),
                              })}
                            </span>
                          )}
                        </ItemDescription>
                      </ItemContent>
                      <ItemActions>
                        {isSelf ? (
                          <Button
                            variant={row.enabled ? 'outline' : 'default'}
                            size="sm"
                            className="h-8 cursor-pointer"
                            onClick={() => {
                              setTotpDialogMode(
                                row.enabled ? 'manage' : 'enroll',
                              );
                              setTotpDialogOpen(true);
                            }}
                            disabled={!systemInfo.allow_modify_login_info}
                          >
                            {row.enabled
                              ? t('account.manageTotp')
                              : t('account.enableTotp')}
                          </Button>
                        ) : (
                          isManager && (
                            // Managers can both re-bind an enabled Account and
                            // force-enable one that never had a second factor.
                            <Button
                              variant={row.enabled ? 'ghost' : 'default'}
                              size="sm"
                              className={
                                row.enabled
                                  ? 'h-8 cursor-pointer text-destructive hover:text-destructive'
                                  : 'h-8 cursor-pointer'
                              }
                              onClick={() => handleRevokeTotp(row)}
                              disabled={!systemInfo.allow_modify_login_info}
                            >
                              {row.enabled ? (
                                <>
                                  <Trash2 className="mr-1 h-3.5 w-3.5" />
                                  {t('account.revokeTotp')}
                                </>
                              ) : (
                                t('account.enableTotp')
                              )}
                            </Button>
                          )
                        )}
                      </ItemActions>
                    </Item>
                  );
                })}
              </div>
            )}
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
        onChanged={() => {
          void loadTotpStatus();
          void loadTotpAccounts();
        }}
        mode={totpDialogMode}
      />

      <TotpAdminResetDialog
        open={adminResetOpen}
        onOpenChange={setAdminResetOpen}
        accountUuid={adminResetTarget?.account_uuid ?? ''}
        accountUser={adminResetTarget?.user ?? ''}
        onChanged={() => {
          void loadTotpStatus();
          void loadTotpAccounts();
        }}
      />
    </PanelBody>
  );
}
