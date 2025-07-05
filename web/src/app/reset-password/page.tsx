'use client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
  InputOTPSeparator,
} from '@/components/ui/input-otp';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from '@/components/ui/form';
import { useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useRouter } from 'next/navigation';
import { Mail, Lock, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import Link from 'next/link';

const REGEXP_ONLY_DIGITS_AND_CHARS = /^[0-9a-zA-Z]+$/;

const formSchema = (t: (key: string) => string) =>
  z.object({
    email: z.string().email(t('common.invalidEmail')),
    recoveryKey: z.string().min(1, t('resetPassword.recoveryKeyRequired')),
    newPassword: z.string().min(1, t('resetPassword.newPasswordRequired')),
  });

export default function ResetPassword() {
  const router = useRouter();
  const { t } = useTranslation();
  const [isResetting, setIsResetting] = useState(false);

  const form = useForm<z.infer<ReturnType<typeof formSchema>>>({
    resolver: zodResolver(formSchema(t)),
    defaultValues: {
      email: '',
      recoveryKey: '',
      newPassword: '',
    },
  });

  function onSubmit(values: z.infer<ReturnType<typeof formSchema>>) {
    handleResetPassword(values.email, values.recoveryKey, values.newPassword);
  }

  function handleResetPassword(
    email: string,
    recoveryKey: string,
    newPassword: string,
  ) {
    setIsResetting(true);
    httpClient
      .resetPassword(email, recoveryKey, newPassword)
      .then((res) => {
        console.log('reset password success: ', res);
        toast.success(t('resetPassword.resetSuccess'));
        router.push('/login');
      })
      .catch((err) => {
        console.log('reset password error: ', err);
        toast.error(t('resetPassword.resetFailed'));
      })
      .finally(() => {
        setIsResetting(false);
      });
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-[375px]">
        <CardHeader>
          <div className="flex justify-between items-center mb-6">
            <Link
              href="/login"
              className="flex items-center text-sm text-gray-600 hover:text-gray-900 transition-colors"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              {t('resetPassword.backToLogin')}
            </Link>
          </div>
          <CardTitle className="text-2xl text-center">
            {t('resetPassword.title')}
          </CardTitle>
          <CardDescription className="text-center">
            {t('resetPassword.description')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('common.email')}</FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Mail className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                        <Input
                          placeholder={t('common.enterEmail')}
                          className="pl-10"
                          {...field}
                        />
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="recoveryKey"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('resetPassword.recoveryKey')}</FormLabel>
                    <FormDescription>
                      {t('resetPassword.recoveryKeyDescription')}
                    </FormDescription>
                    <FormControl>
                      <InputOTP
                        maxLength={6}
                        value={field.value}
                        pattern={REGEXP_ONLY_DIGITS_AND_CHARS.source}
                        onChange={(value) => {
                          // 将输入的值转换为大写
                          const upperValue = value.toUpperCase();
                          field.onChange(upperValue);
                        }}
                      >
                        <InputOTPGroup>
                          <InputOTPSlot index={0} />
                          <InputOTPSlot index={1} />
                          <InputOTPSlot index={2} />
                        </InputOTPGroup>
                        <InputOTPSeparator />
                        <InputOTPGroup>
                          <InputOTPSlot index={3} />
                          <InputOTPSlot index={4} />
                          <InputOTPSlot index={5} />
                        </InputOTPGroup>
                      </InputOTP>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="newPassword"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('resetPassword.newPassword')}</FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Lock className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                        <Input
                          type="password"
                          placeholder={t('resetPassword.enterNewPassword')}
                          className="pl-10"
                          {...field}
                        />
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button
                type="submit"
                className="w-full mt-4 cursor-pointer"
                disabled={isResetting}
              >
                {isResetting
                  ? t('resetPassword.resetting')
                  : t('resetPassword.resetPassword')}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
