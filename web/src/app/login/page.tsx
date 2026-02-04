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
import { LanguageSelector } from '@/components/ui/language-selector';
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
} from '@/components/ui/form';
import { useEffect, useState } from 'react';
import { httpClient, initializeUserInfo } from '@/app/infra/http';
import { useRouter } from 'next/navigation';
import { Mail, Lock, Loader2 } from 'lucide-react';
import langbotIcon from '@/app/assets/langbot-logo.webp';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import Link from 'next/link';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { LoadingSpinner } from '@/components/ui/loading-spinner';

const formSchema = (t: (key: string) => string) =>
  z.object({
    email: z.string().email(t('common.invalidEmail')),
    password: z.string().min(1, t('common.emptyPassword')),
  });

type AccountType = 'local' | 'space';

export default function Login() {
  const router = useRouter();
  const { t } = useTranslation();
  const [spaceLoading, setSpaceLoading] = useState(false);
  const [accountType, setAccountType] = useState<AccountType | null>(null);
  const [hasPassword, setHasPassword] = useState(false);
  const [loading, setLoading] = useState(true);

  const form = useForm<z.infer<ReturnType<typeof formSchema>>>({
    resolver: zodResolver(formSchema(t)),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  useEffect(() => {
    checkAccountInfo();
  }, []);

  async function checkAccountInfo() {
    try {
      const res = await httpClient.getAccountInfo();
      if (!res.initialized) {
        router.push('/register');
        return;
      }
      setAccountType(res.account_type || 'local');
      setHasPassword(res.has_password || false);
      setLoading(false);

      // Also check if already logged in
      checkIfAlreadyLoggedIn();
    } catch {
      setLoading(false);
    }
  }

  function checkIfAlreadyLoggedIn() {
    httpClient
      .checkUserToken()
      .then((res) => {
        if (res.token) {
          localStorage.setItem('token', res.token);
          router.push('/home');
        }
      })
      .catch(() => {});
  }

  function onSubmit(values: z.infer<ReturnType<typeof formSchema>>) {
    handleLogin(values.email, values.password);
  }

  function handleLogin(username: string, password: string) {
    httpClient
      .authUser(username, password)
      .then(async (res) => {
        localStorage.setItem('token', res.token);
        localStorage.setItem('userEmail', username);
        await initializeUserInfo();
        router.push('/home');
        toast.success(t('common.loginSuccess'));
      })
      .catch(() => {
        toast.error(t('common.loginFailed'));
      });
  }

  const handleSpaceLoginClick = async () => {
    setSpaceLoading(true);
    try {
      const currentOrigin = window.location.origin;
      const redirectUri = `${currentOrigin}/auth/space/callback`;
      const response = await httpClient.getSpaceAuthorizeUrl(redirectUri);
      window.location.href = response.authorize_url;
    } catch {
      toast.error(t('common.spaceLoginFailed'));
      setSpaceLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-neutral-900">
        <LoadingSpinner />
      </div>
    );
  }

  // Determine what to show based on account type
  const showLocalLogin =
    accountType === 'local' || (accountType === 'space' && hasPassword);
  const showSpaceLogin = accountType === 'space';

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:dark:bg-neutral-900">
      <Card className="w-[375px] shadow-lg dark:shadow-white/10">
        <CardHeader>
          <div className="flex justify-between items-center mb-6">
            <ThemeToggle />
            <LanguageSelector />
          </div>
          <img
            src={langbotIcon.src}
            alt="LangBot"
            className="w-16 h-16 mb-4 mx-auto"
          />
          <CardTitle className="text-2xl text-center">
            {t('common.welcome')}
          </CardTitle>
          <CardDescription className="text-center">
            {t('common.continueToLogin')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Space Login - only show for space accounts */}
          {showSpaceLogin && (
            <div className="space-y-3">
              <Button
                type="button"
                className="w-full cursor-pointer"
                onClick={handleSpaceLoginClick}
                disabled={spaceLoading}
              >
                {spaceLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <svg
                    className="mr-2 h-4 w-4"
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
                )}
                {t('common.loginWithSpace')}
              </Button>
            </div>
          )}

          {/* Divider - only show if both login methods are available */}
          {showSpaceLogin && showLocalLogin && (
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-white dark:bg-card px-2 text-muted-foreground">
                  {t('common.or')}
                </span>
              </div>
            </div>
          )}

          {/* Local Account Login - show for local accounts or space accounts with password */}
          {showLocalLogin && (
            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                className="space-y-6"
              >
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
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <div className="flex justify-between">
                        <FormLabel>{t('common.password')}</FormLabel>
                        <Link
                          href="/reset-password"
                          className="text-sm text-blue-500"
                        >
                          {t('common.forgotPassword')}
                        </Link>
                      </div>

                      <FormControl>
                        <div className="relative">
                          <Lock className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                          <Input
                            type="password"
                            placeholder={t('common.enterPassword')}
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
                  variant={showSpaceLogin ? 'outline' : 'default'}
                  className="w-full cursor-pointer"
                >
                  {t('common.loginWithPassword')}
                </Button>
              </form>
            </Form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
