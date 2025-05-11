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

export default function Register() {
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
  }, []);

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

  function onSubmit(values: z.infer<typeof formSchema>) {
    handleRegister(values.email, values.password);
  }

  function handleRegister(username: string, password: string) {
    httpClient
      .initUser(username, password)
      .then((res) => {
        console.log('init user success: ', res);
        toast.success('初始化成功 请登录');
        router.push('/login');
      })
      .catch((err) => {
        console.log('init user error: ', err);
        toast.error('初始化失败：' + err.message);
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
            初始化 LangBot 👋
          </CardTitle>
          <CardDescription className="text-center">
            这是您首次启动 LangBot
            <br />
            您填写的邮箱和密码将作为初始管理员账号
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
                注册
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
