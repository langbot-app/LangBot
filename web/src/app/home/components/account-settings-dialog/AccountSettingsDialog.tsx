'use client';

import * as React from 'react';
import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Loader2, ExternalLink } from 'lucide-react';

interface AccountSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function AccountSettingsDialog({
  open,
  onOpenChange,
}: AccountSettingsDialogProps) {
  const { t } = useTranslation();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [accountType, setAccountType] = useState<'local' | 'space'>('local');
  const [hasPassword, setHasPassword] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [spaceBindLoading, setSpaceBindLoading] = useState(false);

  // Schema with optional currentPassword
  const formSchema = z
    .object({
      currentPassword: z.string().optional(),
      newPassword: z
        .string()
        .min(1, { message: t('common.newPasswordRequired') }),
      confirmNewPassword: z
        .string()
        .min(1, { message: t('common.confirmPasswordRequired') }),
    })
    .refine((data) => data.newPassword === data.confirmNewPassword, {
      message: t('common.passwordsDoNotMatch'),
      path: ['confirmNewPassword'],
    })
    .refine(
      (data) =>
        !hasPassword ||
        (data.currentPassword && data.currentPassword.length > 0),
      {
        message: t('common.currentPasswordRequired'),
        path: ['currentPassword'],
      },
    );

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
    },
  });

  useEffect(() => {
    if (open) {
      loadUserInfo();
    }
  }, [open]);

  useEffect(() => {
    form.reset({
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
    });
  }, [hasPassword, form]);

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

  const onSubmit = async (values: z.infer<typeof formSchema>) => {
    setIsSubmitting(true);
    try {
      await httpClient.setPassword(values.newPassword, values.currentPassword);
      toast.success(t('account.passwordSetSuccess'));
      form.reset();
      setHasPassword(true);
    } catch {
      toast.error(t('common.changePasswordFailed'));
    } finally {
      setIsSubmitting(false);
    }
  };

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

  return (
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
          <div className="space-y-6">
            {/* Password Section */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium">
                {hasPassword
                  ? t('common.changePassword')
                  : t('account.setPassword')}
              </h4>
              {!hasPassword && (
                <p className="text-sm text-muted-foreground">
                  {t('account.setPasswordHint')}
                </p>
              )}
              <Form {...form}>
                <form
                  onSubmit={form.handleSubmit(onSubmit)}
                  className="space-y-4"
                >
                  {hasPassword && (
                    <FormField
                      control={form.control}
                      name="currentPassword"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('common.currentPassword')}</FormLabel>
                          <FormControl>
                            <Input
                              type="password"
                              placeholder={t('common.enterCurrentPassword')}
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}
                  <FormField
                    control={form.control}
                    name="newPassword"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('common.newPassword')}</FormLabel>
                        <FormControl>
                          <Input
                            type="password"
                            placeholder={t('common.enterNewPassword')}
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="confirmNewPassword"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('common.confirmNewPassword')}</FormLabel>
                        <FormControl>
                          <Input
                            type="password"
                            placeholder={t('common.enterConfirmPassword')}
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <Button
                    type="submit"
                    disabled={isSubmitting}
                    className="w-full"
                  >
                    {isSubmitting ? t('common.saving') : t('common.save')}
                  </Button>
                </form>
              </Form>
            </div>

            {/* Bind Space Account - only for local accounts */}
            {accountType === 'local' && (
              <>
                <Separator />
                <div className="space-y-4">
                  <h4 className="text-sm font-medium">
                    {t('account.bindSpace')}
                  </h4>
                  <p className="text-sm text-muted-foreground">
                    {t('account.bindSpaceDescription')}
                  </p>
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={handleBindSpace}
                    disabled={spaceBindLoading}
                  >
                    {spaceBindLoading ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <ExternalLink className="mr-2 h-4 w-4" />
                    )}
                    {t('account.bindSpaceButton')}
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
