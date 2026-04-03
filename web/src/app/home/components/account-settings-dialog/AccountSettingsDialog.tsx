

import * as React from 'react';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
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
import { Loader2, ExternalLink, KeyRound } from 'lucide-react';
import PasswordChangeDialog from '../password-change-dialog/PasswordChangeDialog';

interface AccountSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function AccountSettingsDialog({
  open,
  onOpenChange,
}: AccountSettingsDialogProps) {
  const { t } = useTranslation();
  const [accountType, setAccountType] = useState<'local' | 'space'>('local');
  const [hasPassword, setHasPassword] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [spaceBindLoading, setSpaceBindLoading] = useState(false);
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);

  useEffect(() => {
    if (open) {
      loadUserInfo();
    }
  }, [open]);

  async function loadUserInfo() {
    setLoading(true);
    try {
      const info = await httpClient.getUserInfo();
      setAccountType(info.account_type);
      setHasPassword(info.has_password);
      setUserEmail(info.user);
    } catch {
      toast.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  }

  const handleBindSpace = async () => {
    setSpaceBindLoading(true);
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        toast.error(t('common.error'));
        setSpaceBindLoading(false);
        return;
      }
      const currentOrigin = window.location.origin;
      const redirectUri = `${currentOrigin}/auth/space/callback?mode=bind`;
      // Pass token as state for security verification
      const response = await httpClient.getSpaceAuthorizeUrl(
        redirectUri,
        token,
      );
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
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('account.settings')}</DialogTitle>
            <DialogDescription>{userEmail}</DialogDescription>
          </DialogHeader>

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
                  <svg
                    className="h-4 w-4"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M12 2L2 7L12 12L22 7L12 2Z"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M2 17L12 22L22 17"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M2 12L12 17L22 12"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
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
        </DialogContent>
      </Dialog>

      <PasswordChangeDialog
        open={passwordDialogOpen}
        onOpenChange={handlePasswordDialogClose}
        hasPassword={hasPassword}
      />
    </>
  );
}
