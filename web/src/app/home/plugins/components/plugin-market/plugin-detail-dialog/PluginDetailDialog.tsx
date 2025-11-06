'use client';

import { useState, useEffect } from 'react';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, Download, Users } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { PluginV4 } from '@/app/infra/entities/plugin';
import { getCloudServiceClientSync } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';

interface PluginDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  author: string | null;
  pluginName: string | null;
  installPlugin: (plugin: PluginV4) => void;
}

export default function PluginDetailDialog({
  open,
  onOpenChange,
  author,
  pluginName,
  installPlugin,
}: PluginDetailDialogProps) {
  const { t } = useTranslation();
  const [plugin, setPlugin] = useState<PluginV4 | null>(null);
  const [readme, setReadme] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingReadme, setIsLoadingReadme] = useState(false);

  // 获取插件详情和README
  useEffect(() => {
    if (open && author && pluginName) {
      fetchPluginData();
    }
  }, [open, author, pluginName]);

  const fetchPluginData = async () => {
    if (!author || !pluginName) return;

    setIsLoading(true);
    try {
      // 获取插件详情
      const detailResponse = await getCloudServiceClientSync().getPluginDetail(
        author,
        pluginName,
      );
      setPlugin(detailResponse.plugin);

      // 获取README
      setIsLoadingReadme(true);
      try {
        const readmeResponse =
          await getCloudServiceClientSync().getPluginREADME(author, pluginName);
        setReadme(readmeResponse.readme);
      } catch (error) {
        console.warn('Failed to load README:', error);
        setReadme(t('market.noReadme'));
      } finally {
        setIsLoadingReadme(false);
      }
    } catch (error) {
      console.error('Failed to fetch plugin details:', error);
      toast.error(t('market.loadFailed'));
      onOpenChange(false);
    } finally {
      setIsLoading(false);
    }
  };

  if (!open) return null;

  const PluginHeader = () => (
    <div className="flex items-center gap-4 mb-6">
      <img
        src={getCloudServiceClientSync().getPluginIconURL(author!, pluginName!)}
        alt={plugin!.name}
        className="w-16 h-16 rounded-xl border bg-gray-50 object-cover flex-shrink-0"
      />
      <div className="flex-1 min-w-0">
        <h1 className="text-2xl font-bold text-gray-900 mb-2 dark:text-white">
          {extractI18nObject(plugin!.label) || plugin!.name}
        </h1>
        <div className="flex items-center gap-2 text-sm text-gray-600 mb-3 dark:text-gray-400">
          <Users className="w-4 h-4" />
          <span>
            {plugin!.author} / {plugin!.name}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="dark:bg-gray-800 dark:text-white">
            v{plugin!.latest_version}
          </Badge>
          <Badge
            variant="outline"
            className="flex items-center gap-1 dark:bg-gray-800 dark:text-white"
          >
            <Download className="w-4 h-4" />
            {plugin!.install_count.toLocaleString()} {t('market.downloads')}
          </Badge>
          {plugin!.repository && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                window.open(plugin!.repository, '_blank');
              }}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded-md transition-colors dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700 cursor-pointer"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12.001 2C6.47598 2 2.00098 6.475 2.00098 12C2.00098 16.425 4.86348 20.1625 8.83848 21.4875C9.33848 21.575 9.52598 21.275 9.52598 21.0125C9.52598 20.775 9.51348 19.9875 9.51348 19.15C7.00098 19.6125 6.35098 18.5375 6.15098 17.975C6.03848 17.6875 5.55098 16.8 5.12598 16.5625C4.77598 16.375 4.27598 15.9125 5.11348 15.9C5.90098 15.8875 6.46348 16.625 6.65098 16.925C7.55098 18.4375 8.98848 18.0125 9.56348 17.75C9.65098 17.1 9.91348 16.6625 10.201 16.4125C7.97598 16.1625 5.65098 15.3 5.65098 11.475C5.65098 10.3875 6.03848 9.4875 6.67598 8.7875C6.57598 8.5375 6.22598 7.5125 6.77598 6.1375C6.77598 6.1375 7.61348 5.875 9.52598 7.1625C10.326 6.9375 11.176 6.825 12.026 6.825C12.876 6.825 13.726 6.9375 14.526 7.1625C16.4385 5.8625 17.276 6.1375 17.276 6.1375C17.826 7.5125 17.476 8.5375 17.376 8.7875C18.0135 9.4875 18.401 10.375 18.401 11.475C18.401 15.3125 16.0635 16.1625 13.8385 16.4125C14.201 16.725 14.5135 17.325 14.5135 18.2625C14.5135 19.6 14.501 20.675 14.501 21.0125C14.501 21.275 14.6885 21.5875 15.1885 21.4875C19.259 20.1133 21.9999 16.2963 22.001 12C22.001 6.475 17.526 2 12.001 2Z" />
              </svg>
              GitHub
            </button>
          )}
        </div>
      </div>
    </div>
  );

  const PluginDescription = () => (
    <div className="mb-6">
      <p className="text-gray-700 leading-relaxed text-base dark:text-gray-400">
        {extractI18nObject(plugin!.description) || t('market.noDescription')}
      </p>
    </div>
  );

  const PluginOptions = () => (
    <div className="space-y-4">
      <Button
        onClick={() => installPlugin(plugin!)}
        className="w-full h-12 text-base font-medium"
      >
        <Download className="w-5 h-5 mr-2" />
        {t('market.install')}
      </Button>
    </div>
  );

  const ReadmeContent = () => (
    <div className="prose prose-sm max-w-none text-gray-800 dark:text-gray-400">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // 表格组件
          table: ({ ...props }) => (
            <div className="my-6 w-full overflow-x-auto rounded-lg">
              <table
                className="w-full border-collapse bg-white dark:bg-gray-800"
                {...props}
              />
            </div>
          ),
          thead: ({ ...props }) => (
            <thead
              className="bg-gray-50 dark:bg-gray-900 dark:text-gray-400"
              {...props}
            />
          ),
          tbody: ({ ...props }) => (
            <tbody
              className="divide-y divide-gray-200 dark:divide-gray-700 dark:text-gray-400"
              {...props}
            />
          ),
          th: ({ ...props }) => (
            <th
              className="px-4 py-3 text-left text-sm font-semibold text-gray-900 border-r border-gray-200 last:border-r-0 dark:border-gray-700 dark:text-gray-400"
              {...props}
            />
          ),
          td: ({ ...props }) => (
            <td
              className="px-4 py-3 text-sm text-gray-700 border-r border-gray-200 last:border-r-0 dark:border-gray-700 dark:text-gray-400"
              {...props}
            />
          ),
          tr: ({ ...props }) => (
            <tr
              className="hover:bg-gray-50 transition-colors dark:hover:bg-gray-800 dark:text-gray-400"
              {...props}
            />
          ),
          // 删除线支持
          del: ({ ...props }) => (
            <del
              className="text-gray-500 line-through dark:text-gray-400"
              {...props}
            />
          ),
          // Todo 列表支持
          input: ({ type, checked, ...props }) => {
            if (type === 'checkbox') {
              return (
                <input
                  type="checkbox"
                  checked={checked}
                  disabled
                  className="mr-2 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-default dark:border-gray-700"
                  {...props}
                />
              );
            }
            return <input type={type} {...props} />;
          },
          ul: ({ ...props }) => (
            <ul className="list-disc ml-5 dark:text-gray-400" {...props} />
          ),
          ol: ({ ...props }) => (
            <ol className="list-decimal ml-5 dark:text-gray-400" {...props} />
          ),
          li: ({ ...props }) => <li className="mb-1" {...props} />,
          h1: ({ ...props }) => (
            <h1
              className="text-3xl font-bold my-2 dark:text-gray-400"
              {...props}
            />
          ),
          h2: ({ ...props }) => (
            <h2
              className="text-2xl font-semibold mb-2 mt-4 dark:text-gray-400"
              {...props}
            />
          ),
          h3: ({ ...props }) => (
            <h3
              className="text-xl font-semibold mb-2 mt-4 dark:text-gray-400"
              {...props}
            />
          ),
          h4: ({ ...props }) => (
            <h4
              className="text-lg font-semibold mb-2 mt-4 dark:text-gray-400"
              {...props}
            />
          ),
          h5: ({ ...props }) => (
            <h5
              className="text-base font-semibold mb-2 mt-4 dark:text-gray-400"
              {...props}
            />
          ),
          h6: ({ ...props }) => (
            <h6
              className="text-sm font-semibold mb-2 mt-4 dark:text-gray-400"
              {...props}
            />
          ),
          p: ({ ...props }) => (
            <p className="leading-relaxed dark:text-gray-400" {...props} />
          ),
          code: ({ className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || '');
            const isCodeBlock = match ? true : false;

            // 如果是代码块（有语言标识），由 pre 标签处理样式，淡灰色底，黑色字
            if (isCodeBlock) {
              return (
                <code
                  className="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono dark:bg-gray-800 dark:text-gray-400"
                  {...props}
                >
                  {children}
                </code>
              );
            }

            // 内联代码样式 - 淡灰色底
            return (
              <code
                className="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono inline-block dark:bg-gray-800 dark:text-gray-400"
                {...props}
              >
                {children}
              </code>
            );
          },
          pre: ({ ...props }) => (
            <pre
              className="bg-gray-100 text-gray-800 rounded-lg my-4 shadow-sm max-h-[500px] relative dark:bg-gray-800 dark:text-gray-400"
              style={{
                // 内边距确保内容不被滚动条覆盖
                padding: '16px',
                // 保持代码不换行以启用横向滚动
                whiteSpace: 'pre',
                // 滚动设置
                overflowX: 'auto',
                overflowY: 'auto',
                // 确保滚动条在内部
                boxSizing: 'border-box',
              }}
              {...props}
            />
          ),
          // 图片组件 - 转换本地路径为API路径
          img: ({ src, alt, ...props }) => {
            // 处理图片路径
            let imageSrc = src || '';

            // 确保 src 是字符串类型
            if (typeof imageSrc !== 'string') {
              return (
                <img
                  src={src}
                  alt={alt || ''}
                  className="max-w-full h-auto rounded-lg my-4"
                  {...props}
                />
              );
            }

            // 如果是相对路径，转换为API路径
            if (
              imageSrc &&
              !imageSrc.startsWith('http://') &&
              !imageSrc.startsWith('https://') &&
              !imageSrc.startsWith('data:')
            ) {
              // 移除开头的 ./ 或 / (支持多个前缀)
              imageSrc = imageSrc.replace(/^(\.\/|\/)+/, '');

              // 如果路径以 assets/ 开头，直接使用
              // 否则假设它在 assets/ 目录下
              if (!imageSrc.startsWith('assets/')) {
                imageSrc = `assets/${imageSrc}`;
              }

              // 移除 assets/ 前缀以构建API URL
              const assetPath = imageSrc.replace(/^assets\//, '');
              imageSrc = getCloudServiceClientSync().getPluginAssetURL(
                author!,
                pluginName!,
                assetPath,
              );
            }

            return (
              <img
                src={imageSrc}
                alt={alt || ''}
                className="max-w-lg h-auto my-4"
                {...props}
              />
            );
          },
        }}
      >
        {readme}
      </ReactMarkdown>
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="!min-w-[50vw] max-w-none max-h-[90vh] h-[90vh] p-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-12 h-full">
            <Loader2 className="h-8 w-8 animate-spin" />
            <span className="ml-2">{t('market.loading')}</span>
          </div>
        ) : plugin ? (
          <div className="flex flex-col h-full overflow-hidden">
            {/* 插件信息区域 */}
            <div className="flex-shrink-0 bg-white border-b m-4 pt-2 dark:bg-black">
              <div className="flex gap-6 p-2 px-4">
                <div className="flex-1">
                  <PluginHeader />
                  <PluginDescription />
                </div>
                <div className="w-40 pr-4 flex-shrink-0">
                  <PluginOptions />
                </div>
              </div>
            </div>

            {/* README 区域 */}
            <div className="flex-1 overflow-hidden px-8">
              <div className="h-full bg-white overflow-y-auto pb-2 dark:bg-black">
                {isLoadingReadme ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin" />
                    <span className="ml-3 text-gray-600">
                      {t('market.loading')}
                    </span>
                  </div>
                ) : (
                  <ReadmeContent />
                )}
              </div>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
