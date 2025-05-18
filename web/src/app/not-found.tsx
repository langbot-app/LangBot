'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useTranslation } from 'react-i18next';

export default function NotFound() {
  const router = useRouter();
  const { t } = useTranslation();

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
              {t('notFound.title')}
            </h1>
            <p className="text-base text-gray-600 max-w-[450px] mx-auto mb-8">
              {t('notFound.description')}
            </p>
          </div>

          {/* 按钮组 */}
          <div className="flex gap-4 mb-6">
            <Button
              variant="default"
              onClick={() => router.back()}
              className="h-9 px-4 cursor-pointer"
            >
              {t('notFound.back')}
            </Button>
            <Button
              variant="outline"
              onClick={() => router.push('/home')}
              className="h-9 px-4 cursor-pointer"
            >
              {t('notFound.home')}
            </Button>
          </div>

          {/* 帮助文档链接 */}
          <div className="text-center">
            <p className="text-sm text-gray-600">
              <a
                href="https://docs.langbot.app"
                className="text-black no-underline hover:underline"
              >
                {t('notFound.help')}
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
