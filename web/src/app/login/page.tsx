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

const formSchema = z.object({
  email: z.string().email('请输入有效的邮箱地址'),
  password: z.string().min(1, '请输入密码'),
});

export default function Login() {
  const router = useRouter();

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
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
  function onSubmit(values: z.infer<typeof formSchema>) {
    handleLogin(values.email, values.password);
  }

  function handleLogin(username: string, password: string) {
    httpClient
      .authUser(username, password)
      .then((res) => {
        localStorage.setItem('token', res.token);
        console.log('login success: ', res);
        router.push('/home');
        toast.success('登录成功');
      })
      .catch((err) => {
        console.log('login error: ', err);

        toast.error('登录失败，请检查邮箱和密码是否正确');
      });
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-[360px]">
        <CardHeader>
          <img
            src={langbotIcon.src}
            alt="LangBot"
            className="w-16 h-16 mb-4 mx-auto"
          />
          <CardTitle className="text-2xl text-center">
            欢迎回到 LangBot 👋
          </CardTitle>
          <CardDescription className="text-center">登录以继续</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>邮箱</FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Mail className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                        <Input
                          placeholder="输入邮箱地址"
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
                    <FormLabel>密码</FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Lock className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                        <Input
                          type="password"
                          placeholder="输入密码"
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
                登录
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
