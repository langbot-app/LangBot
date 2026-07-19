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
import { Loader2, ExternalLink, KeyRound, Layers } from 'lucide-react';
import PasswordChangeDialog from '../password-change-dialog/PasswordChangeDialog';
import { PanelBody } from '../settings-dialog/panel-layout';

interface AccountSettingsPanelProps {
  // True when this panel is the active section and the dialog is open.
  active: boolean;
  onEmailResolved?: (email: string) => void;
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

  useEffect(() => {
    if (active) {
      loadUserInfo();
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
        </div>
      )}

      <PasswordChangeDialog
        open={passwordDialogOpen}
        onOpenChange={handlePasswordDialogClose}
        hasPassword={hasPassword}
      />
    </PanelBody>
  );
}
