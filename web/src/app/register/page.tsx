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
import { httpClient } from '@/app/infra/http/HttpClient';
import { useRouter } from 'next/navigation';
import { Mail, Lock, Loader2 } from 'lucide-react';
import langbotIcon from '@/app/assets/langbot-logo.webp';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { ThemeToggle } from '@/components/ui/theme-toggle';

const formSchema = (t: (key: string) => string) =>
  z.object({
    email: z.string().email(t('common.invalidEmail')),
    password: z.string().min(1, t('common.emptyPassword')),
  });

export default function Register() {
  const router = useRouter();
  const { t } = useTranslation();
  const [spaceLoading, setSpaceLoading] = useState(false);

  const form = useForm<z.infer<ReturnType<typeof formSchema>>>({
    resolver: zodResolver(formSchema(t)),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  useEffect(() => {
    getIsInitialized();
  }, []);

  function getIsInitialized() {
    httpClient
      .checkIfInited()
      .then((res) => {
        if (res.initialized) {
          router.push('/login');
        }
      })
      .catch(() => {});
  }

  function onSubmit(values: z.infer<ReturnType<typeof formSchema>>) {
    handleRegister(values.email, values.password);
  }

  function handleRegister(username: string, password: string) {
    httpClient
      .initUser(username, password)
      .then(() => {
        toast.success(t('register.initSuccess'));
        router.push('/login');
      })
      .catch((err: Error) => {
        toast.error(t('register.initFailed') + err.message);
      });
  }

  // Space OAuth redirect handler
  const handleSpaceLoginClick = async () => {
    setSpaceLoading(true);

    try {
      // Build the redirect URI to the OAuth callback page
      const currentOrigin = window.location.origin;
      const redirectUri = `${currentOrigin}/auth/space/callback`;

      // Get the authorization URL from backend
      const response = await httpClient.getSpaceAuthorizeUrl(redirectUri);

      // Redirect to Space authorization page
      window.location.href = response.authorize_url;
    } catch {
      toast.error(t('common.spaceLoginFailed'));
      setSpaceLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-neutral-900">
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
            {t('register.title')}
          </CardTitle>
          <CardDescription className="text-center">
            {t('register.description')}
            <br />
            {t('register.adminAccountNote')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Space Login - Recommended */}
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
              {t('register.initWithSpace')}
            </Button>
            <p className="text-xs text-center text-muted-foreground">
              {t('register.spaceRecommended')}
            </p>
          </div>

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

          {/* Local Account Registration */}
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
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('common.password')}</FormLabel>
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
                variant="outline"
                className="w-full cursor-pointer"
              >
                {t('register.registerWithPassword')}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
