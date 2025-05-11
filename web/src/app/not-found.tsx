'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

export default function NotFound() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-white flex items-center justify-center">
      <div className="w-full max-w-[600px] px-4">
        <div className="flex flex-col items-center p-6">
          {/* 404 图标 */}
          <div className="mb-8">
            <div className="text-[72px] font-bold text-gray-800">404</div>
          </div>

          {/* 错误文本 */}
          <div className="text-center mb-8">
            <h1 className="text-2xl font-normal text-gray-800 mb-2">
              页面不存在
            </h1>
            <p className="text-base text-gray-600 max-w-[450px] mx-auto mb-8">
              您要查找的页面似乎不存在。请检查您输入的 URL
              是否正确，或者返回首页。
            </p>
          </div>

          {/* 按钮组 */}
          <div className="flex gap-4 mb-6">
            <Button
              variant="default"
              onClick={() => router.back()}
              className="h-9 px-4 cursor-pointer"
            >
              上一级
            </Button>
            <Button
              variant="outline"
              onClick={() => router.push('/home')}
              className="h-9 px-4 cursor-pointer"
            >
              返回主页
            </Button>
          </div>

          {/* 帮助文档链接 */}
          <div className="text-center">
            <p className="text-sm text-gray-600">
              查看
              <a
                href="https://docs.langbot.app"
                className="text-black no-underline hover:underline"
              >
                帮助文档
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
