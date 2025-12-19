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
import { ThemeToggle } from '@/components/ui/theme-toggle';

const formSchema = (t: (key: string) => string) =>
  z.object({
    email: z.string().email(t('common.invalidEmail')),
    password: z.string().min(1, t('common.emptyPassword')),
  });

export default function Register() {
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

              <Button type="submit" className="w-full mt-4 cursor-pointer">
                {t('register.register')}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
