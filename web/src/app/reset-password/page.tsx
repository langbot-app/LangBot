import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
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
import { useNavigate } from 'react-router-dom';
import {
  Mail,
  Lock,
  ArrowLeft,
  KeyRound,
  ShieldCheck,
  LifeBuoy,
} from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ThemeToggle } from '@/components/ui/theme-toggle';

// The reset flow accepts three second-factor methods:
// * recovery_key  — the instance-wide key from data/config.yaml (default);
// * totp          — a code from the Account's authenticator app;
// * recovery_code — one of the Account's single-use recovery codes.
type ResetMethod = 'recovery_key' | 'totp' | 'recovery_code';

const formSchema = (t: (key: string) => string) =>
  z.object({
    email: z.string().email(t('common.invalidEmail')),
    recoveryKey: z.string().optional(),
    totpCode: z.string().optional(),
    newPassword: z.string().min(1, t('resetPassword.newPasswordRequired')),
  });

export default function ResetPassword() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [isResetting, setIsResetting] = useState(false);
  const [method, setMethod] = useState<ResetMethod>('recovery_key');

  const form = useForm<z.infer<ReturnType<typeof formSchema>>>({
    resolver: zodResolver(formSchema(t)),
    defaultValues: {
      email: '',
      recoveryKey: '',
      totpCode: '',
      newPassword: '',
    },
  });

  function onSubmit(values: z.infer<ReturnType<typeof formSchema>>) {
    // Validate the second factor for the selected method before calling out.
    if (method === 'recovery_key' && !values.recoveryKey?.trim()) {
      form.setError('recoveryKey', {
        message: t('resetPassword.recoveryKeyRequired'),
      });
      return;
    }
    if (method !== 'recovery_key' && !values.totpCode?.trim()) {
      form.setError('totpCode', {
        message:
          method === 'totp'
            ? t('resetPassword.totpCodeRequired')
            : t('resetPassword.recoveryCodeRequired'),
      });
      return;
    }
    handleResetPassword(
      values.email,
      values.newPassword,
      method,
      values.recoveryKey,
      values.totpCode,
    );
  }

  function handleResetPassword(
    email: string,
    newPassword: string,
    selectedMethod: ResetMethod,
    recoveryKey?: string,
    totpCode?: string,
  ) {
    setIsResetting(true);
    httpClient
      .resetPassword(email, newPassword, {
        method: selectedMethod,
        recoveryKey,
        totpCode,
      })
      .then(() => {
        toast.success(t('resetPassword.resetSuccess'));
        navigate('/login');
      })
      .catch(() => {
        toast.error(
          selectedMethod === 'recovery_key'
            ? t('resetPassword.resetFailed')
            : t('resetPassword.secondFactorFailed'),
        );
      })
      .finally(() => {
        setIsResetting(false);
      });
  }

  const methodButton = (
    value: ResetMethod,
    label: string,
    Icon: typeof KeyRound,
  ) => (
    <button
      type="button"
      onClick={() => {
        setMethod(value);
        form.clearErrors();
      }}
      className={`flex flex-1 items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 text-xs transition-colors cursor-pointer ${
        method === value
          ? 'border-primary bg-primary/10 text-primary font-medium'
          : 'border-border text-muted-foreground hover:bg-muted'
      }`}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  );

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-neutral-900">
      <Card className="w-[375px] shadow-lg dark:shadow-white/10">
        <CardHeader>
          <div className="flex justify-between items-center mb-6">
            <Link
              to="/login"
              className="flex items-center text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 transition-colors"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              {t('resetPassword.backToLogin')}
            </Link>
            <ThemeToggle />
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

              {/* Second-factor method selector */}
              <div className="space-y-2">
                <FormLabel>{t('resetPassword.verifyWith')}</FormLabel>
                <div className="flex gap-2">
                  {methodButton(
                    'recovery_key',
                    t('resetPassword.methodRecoveryKey'),
                    KeyRound,
                  )}
                  {methodButton(
                    'totp',
                    t('resetPassword.methodTotp'),
                    ShieldCheck,
                  )}
                  {methodButton(
                    'recovery_code',
                    t('resetPassword.methodRecoveryCode'),
                    LifeBuoy,
                  )}
                </div>
              </div>

              {method === 'recovery_key' ? (
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
                        {/* Recovery keys are case-sensitive base64url strings; send them verbatim */}
                        <div className="relative">
                          <KeyRound className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                          <Input
                            placeholder={t('resetPassword.enterRecoveryKey')}
                            className="pl-10 font-mono"
                            autoComplete="off"
                            spellCheck={false}
                            {...field}
                          />
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ) : (
                <FormField
                  control={form.control}
                  name="totpCode"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        {method === 'totp'
                          ? t('resetPassword.totpCode')
                          : t('resetPassword.recoveryCode')}
                      </FormLabel>
                      <FormDescription>
                        {method === 'totp'
                          ? t('resetPassword.totpCodeDescription')
                          : t('resetPassword.recoveryCodeDescription')}
                      </FormDescription>
                      <FormControl>
                        <div className="relative">
                          {method === 'totp' ? (
                            <ShieldCheck className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                          ) : (
                            <LifeBuoy className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                          )}
                          <Input
                            inputMode={method === 'totp' ? 'numeric' : 'text'}
                            placeholder={
                              method === 'totp'
                                ? t('resetPassword.enterTotpCode')
                                : t('resetPassword.enterRecoveryCodeValue')
                            }
                            className={`pl-10 ${
                              method === 'totp'
                                ? 'tracking-widest'
                                : 'font-mono'
                            }`}
                            autoComplete="off"
                            spellCheck={false}
                            {...field}
                          />
                        </div>
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
