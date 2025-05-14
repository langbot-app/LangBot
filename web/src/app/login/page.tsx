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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
import { Mail, Lock, Globe } from 'lucide-react';
import langbotIcon from '@/app/assets/langbot-logo.webp';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import i18n from '@/i18n';

const formSchema = (t: (key: string) => string) =>
  z.object({
    email: z.string().email(t('common.invalidEmail')),
    password: z.string().min(1, t('common.emptyPassword')),
  });

export default function Login() {
  const router = useRouter();
  const { t } = useTranslation();
  const [currentLanguage, setCurrentLanguage] = useState<string>(i18n.language);

  const form = useForm<z.infer<ReturnType<typeof formSchema>>>({
    resolver: zodResolver(formSchema(t)),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  useEffect(() => {
    judgeLanguage();
    getIsInitialized();
    checkIfAlreadyLoggedIn();
  }, []);

  const judgeLanguage = () => {
    // here's for user have never set the language
    // judge the language by the browser
    const language = navigator.language;
    if (language) {
      let lang = 'zh-Hans';
      if (language === 'zh-CN') {
        lang = 'zh-Hans';
      } else {
        lang = 'en-US';
      }
      i18n.changeLanguage(lang);
      setCurrentLanguage(lang);
      localStorage.setItem('langbot_language', lang);
    }
  };

  const handleLanguageChange = (value: string) => {
    i18n.changeLanguage(value);
    setCurrentLanguage(value);
    localStorage.setItem('langbot_language', value);
  };

  function getIsInitialized() {
    httpClient
      .checkIfInited()
      .then((res) => {
        if (!res.initialized) {
          router.push('/register');
        }
      })
      .catch((err) => {
        console.log('error at getIsInitialized: ', err);
      });
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
      .catch((err) => {
        console.log('error at checkIfAlreadyLoggedIn: ', err);
      });
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
        console.log('login success: ', res);
        router.push('/home');
        toast.success(t('common.loginSuccess'));
      })
      .catch((err) => {
        console.log('login error: ', err);

        toast.error(t('common.loginFailed'));
      });
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-[375px]">
        <CardHeader>
          <div className="flex justify-end mb-6">
            <Select
              value={currentLanguage}
              onValueChange={handleLanguageChange}
            >
              <SelectTrigger className="w-[140px]">
                <Globe className="h-4 w-4 mr-2" />
                <SelectValue placeholder={t('common.language')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="zh-Hans">简体中文</SelectItem>
                <SelectItem value="en-US">English</SelectItem>
              </SelectContent>
            </Select>
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
                {t('common.login')}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
