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
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useEffect, useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useNavigate } from 'react-router-dom';
import { Mail, Lock, ArrowLeft, KeyRound, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ThemeToggle } from '@/components/ui/theme-toggle';

type RecoveryMethod = 'recoveryKey' | 'totp' | 'recoveryCode';

const formSchema = (t: (key: string) => string) =>
  z.object({
    email: z.string().email(t('common.invalidEmail')),
    recoveryKey: z.string().optional(),
    totpCode: z.string().optional(),
    recoveryCode: z.string().optional(),
    newPassword: z.string().min(1, t('resetPassword.newPasswordRequired')),
  });

export default function ResetPassword() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [isResetting, setIsResetting] = useState(false);
  const [method, setMethod] = useState<RecoveryMethod>('recoveryKey');
  // Whether TOTP is enabled for the email currently entered. `null` means we have
  // not yet resolved it (empty/invalid email), so the TOTP methods stay disabled
  // until we can confirm the account actually enrolled one.
  const [totpEnabledForEmail, setTotpEnabledForEmail] = useState<
    boolean | null
  >(null);

  const form = useForm<z.infer<ReturnType<typeof formSchema>>>({
    resolver: zodResolver(formSchema(t)),
    defaultValues: {
      email: '',
      recoveryKey: '',
      totpCode: '',
      recoveryCode: '',
      newPassword: '',
    },
  });

  // Watch the email so we can resolve, per account, whether TOTP is enabled.
  const email = form.watch('email');

  // Resolve whether the entered email has TOTP enabled; only then may the user
  // pick the TOTP / recovery-code verification methods. While unresolved (empty
  // or invalid email) both TOTP methods stay disabled, so an account without
  // TOTP can never select them.
  useEffect(() => {
    if (!email || !z.string().email().safeParse(email).success) {
      setTotpEnabledForEmail(null);
      setMethod('recoveryKey');
      return;
    }
    let cancelled = false;
    // Debounce so we only query once the user pauses typing.
    const timer = setTimeout(() => {
      httpClient
        .checkTotpForEmail(email)
        .then((res) => {
          if (cancelled) {
            return;
          }
          setTotpEnabledForEmail(res.totp_enabled);
          if (!res.totp_enabled) {
            setMethod('recoveryKey');
          }
        })
        .catch(() => {
          if (!cancelled) {
            // Fail closed: if we cannot confirm TOTP, only the recovery key is
            // offered rather than letting an unverified TOTP path through.
            setTotpEnabledForEmail(null);
            setMethod('recoveryKey');
          }
        });
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [email]);

  const totpMethodsDisabled = totpEnabledForEmail !== true;

  function onSubmit(values: z.infer<ReturnType<typeof formSchema>>) {
    if (method === 'recoveryKey') {
      if (!values.recoveryKey || !values.recoveryKey.trim()) {
        toast.error(t('resetPassword.recoveryKeyRequired'));
        return;
      }
      handleResetPassword(
        values.email,
        { recoveryKey: values.recoveryKey.trim() },
        values.newPassword,
      );
      return;
    }
    if (method === 'totp') {
      if (!values.totpCode || !values.totpCode.trim()) {
        toast.error(t('resetPassword.totpCodeRequired'));
        return;
      }
      handleResetPassword(
        values.email,
        { totpCode: values.totpCode.trim() },
        values.newPassword,
      );
      return;
    }
    if (!values.recoveryCode || !values.recoveryCode.trim()) {
      toast.error(t('resetPassword.recoveryCodeRequired'));
      return;
    }
    handleResetPassword(
      values.email,
      { recoveryCode: values.recoveryCode.trim() },
      values.newPassword,
    );
  }

  function handleResetPassword(
    email: string,
    factor:
      | { recoveryKey: string }
      | { totpCode: string }
      | { recoveryCode: string },
    newPassword: string,
  ) {
    setIsResetting(true);
    httpClient
      .resetPassword(email, newPassword, factor)
      .then(() => {
        toast.success(t('resetPassword.resetSuccess'));
        navigate('/login');
      })
      .catch((error: unknown) => {
        const apiError = error as { code?: string };
        if (apiError?.code === 'totp_not_enabled') {
          toast.error(t('resetPassword.totpNotEnabled'));
        } else if (apiError?.code === 'totp_invalid_code') {
          toast.error(t('resetPassword.invalidTotpCode'));
        } else {
          toast.error(t('resetPassword.resetFailed'));
        }
      })
      .finally(() => {
        setIsResetting(false);
      });
  }

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

              {/* Recovery method selector: recovery key, TOTP, or recovery code.
                  The TOTP-based methods are only selectable once we have
                  confirmed the entered account actually enrolled TOTP. */}
              <div className="space-y-3">
                <FormLabel>{t('resetPassword.verifyMethod')}</FormLabel>
                <Tabs
                  value={method}
                  onValueChange={(v) => setMethod(v as RecoveryMethod)}
                >
                  <TabsList className="w-full">
                    <TabsTrigger value="recoveryKey" className="flex-1">
                      {t('resetPassword.recoveryKey')}
                    </TabsTrigger>
                    <TabsTrigger
                      value="totp"
                      className="flex-1"
                      disabled={totpMethodsDisabled}
                    >
                      {t('resetPassword.totpMethod')}
                    </TabsTrigger>
                    <TabsTrigger
                      value="recoveryCode"
                      className="flex-1"
                      disabled={totpMethodsDisabled}
                    >
                      {t('resetPassword.recoveryCodeMethod')}
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
                {totpMethodsDisabled && (
                  <p className="text-xs text-muted-foreground">
                    {t('resetPassword.totpMethodsUnavailable')}
                  </p>
                )}
              </div>

              {method === 'recoveryKey' && (
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
              )}

              {method === 'totp' && (
                <FormField
                  control={form.control}
                  name="totpCode"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('resetPassword.totpCode')}</FormLabel>
                      <FormDescription>
                        {t('resetPassword.totpMethodDescription')}
                      </FormDescription>
                      <FormControl>
                        <div className="relative">
                          <ShieldCheck className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                          <Input
                            placeholder={t('resetPassword.enterTotpCode')}
                            className="pl-10 font-mono tracking-widest"
                            inputMode="numeric"
                            autoComplete="one-time-code"
                            maxLength={6}
                            {...field}
                          />
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {method === 'recoveryCode' && (
                <FormField
                  control={form.control}
                  name="recoveryCode"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('resetPassword.recoveryCode')}</FormLabel>
                      <FormControl>
                        <div className="relative">
                          <ShieldCheck className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                          <Input
                            placeholder={t('resetPassword.enterRecoveryCode')}
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
