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
import { useEffect } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useRouter } from 'next/navigation';
import { Mail, Lock } from 'lucide-react';
import langbotIcon from '@/app/assets/langbot-logo.webp';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import Link from 'next/link';
import { ThemeToggle } from '@/components/ui/theme-toggle';

const formSchema = (t: (key: string) => string) =>
  z.object({
    email: z.string().email(t('common.invalidEmail')),
    password: z.string().min(1, t('common.emptyPassword')),
  });

export default function Login() {
  const router = useRouter();
  const { t } = useTranslation();

  const form = useForm<z.infer<ReturnType<typeof formSchema>>>({
    resolver: zodResolver(formSchema(t)),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  useEffect(() => {
    getIsInitialized();
    checkIfAlreadyLoggedIn();
  }, []);

  function getIsInitialized() {
    httpClient
      .checkIfInited()
      .then((res) => {
        if (!res.initialized) {
          router.push('/register');
        }
      })
      .catch(() => {});
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
      .then((res) => {
        localStorage.setItem('token', res.token);
        localStorage.setItem('userEmail', username);
        router.push('/home');
        toast.success(t('common.loginSuccess'));
      })
      .catch(() => {
        toast.error(t('common.loginFailed'));
      });
  }

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

              <Button type="submit" className="w-full mt-4 cursor-pointer">
                {t('common.login')}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
