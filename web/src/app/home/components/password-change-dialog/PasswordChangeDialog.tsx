

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
  DialogFooter,
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
import { httpClient } from '@/app/infra/http/HttpClient';

interface PasswordChangeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  hasPassword?: boolean;
}

export default function PasswordChangeDialog({
  open,
  onOpenChange,
  hasPassword = true,
}: PasswordChangeDialogProps) {
  const { t } = useTranslation();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const getFormSchema = () =>
    z
      .object({
        currentPassword: hasPassword
          ? z.string().min(1, { message: t('common.currentPasswordRequired') })
          : z.string().optional(),
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
      });

  const formSchema = getFormSchema();

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
    },
  });

  // Reset form when dialog opens/closes or hasPassword changes
  useEffect(() => {
    if (open) {
      form.reset({
        currentPassword: '',
        newPassword: '',
        confirmNewPassword: '',
      });
    }
  }, [open, hasPassword, form]);

  const onSubmit = async (values: z.infer<typeof formSchema>) => {
    setIsSubmitting(true);
    try {
      if (hasPassword) {
        await httpClient.changePassword(
          values.currentPassword!,
          values.newPassword,
        );
        toast.success(t('common.changePasswordSuccess'));
      } else {
        await httpClient.setPassword(values.newPassword, undefined);
        toast.success(t('account.passwordSetSuccess'));
      }
      form.reset();
      onOpenChange(false);
    } catch {
      toast.error(t('common.changePasswordFailed'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {hasPassword
              ? t('common.changePassword')
              : t('account.setPassword')}
          </DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
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
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                {t('common.cancel')}
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? t('common.saving') : t('common.save')}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
