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

export default function Register() {
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
  }, []);

  const judgeLanguage = () => {
    if (i18n.language === 'zh-CN' || i18n.language === 'zh-Hans') {
      setCurrentLanguage('zh-Hans');
      localStorage.setItem('langbot_language', 'zh-Hans');
    } else if (i18n.language === 'ja' || i18n.language === 'ja-JP') {
      setCurrentLanguage('ja-JP');
      localStorage.setItem('langbot_language', 'ja-JP');
    } else {
      setCurrentLanguage('en-US');
      localStorage.setItem('langbot_language', 'en-US');
    }
    // check if the language is already set
    const lang = localStorage.getItem('langbot_language');
    console.log('lang: ', lang);
    if (lang) {
      i18n.changeLanguage(lang);
      setCurrentLanguage(lang);
    } else {
      const language = navigator.language;
      if (language) {
        let lang = 'zh-Hans';
        if (language === 'zh-CN') {
          lang = 'zh-Hans';
        } else if (language === 'ja' || language === 'ja-JP') {
          lang = 'ja-JP';
        } else {
          lang = 'en-US';
        }
        console.log('language: ', lang);
        i18n.changeLanguage(lang);
        setCurrentLanguage(lang);
        localStorage.setItem('langbot_language', lang);
      }
    }
  };

  const handleLanguageChange = (value: string) => {
    console.log('handleLanguageChange: ', value);
    i18n.changeLanguage(value);
    setCurrentLanguage(value);
    localStorage.setItem('langbot_language', value);
  };

  function getIsInitialized() {
    httpClient
      .checkIfInited()
      .then((res) => {
        if (res.initialized) {
          router.push('/login');
        }
      })
      .catch((err) => {
        console.log('error at getIsInitialized: ', err);
      });
  }

  function onSubmit(values: z.infer<ReturnType<typeof formSchema>>) {
    handleRegister(values.email, values.password);
  }

  function handleRegister(username: string, password: string) {
    httpClient
      .initUser(username, password)
      .then((res) => {
        console.log('init user success: ', res);
        toast.success(t('register.initSuccess'));
        router.push('/login');
      })
      .catch((err) => {
        console.log('init user error: ', err);
        toast.error(t('register.initFailed') + err.message);
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
                <SelectItem value="ja-JP">日本語</SelectItem>
              </SelectContent>
            </Select>
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
