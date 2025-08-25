'use client';

import { useState, useEffect } from 'react';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, Download, Users } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { PluginV4 } from '@/app/infra/entities/plugin';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { getCloudServiceClientSync } from '@/app/infra/http';

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
      console.log('detailResponse', detailResponse);
      setPlugin(detailResponse.plugin);

      // 获取README
      setIsLoadingReadme(true);
      try {
        const readmeResponse =
          await getCloudServiceClientSync().getPluginREADME(author, pluginName);
        console.log('readmeResponse', readmeResponse);
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="!min-w-[65vw] !min-h-[65vh] max-h-[85vh] overflow-hidden p-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin" />
            <span className="ml-2">{t('cloud.loading')}</span>
          </div>
        ) : plugin ? (
          <div className="flex h-full">
            {/* 左侧：插件基本信息 */}
            <div className="w-2/5 p-6 border-r border-gray-200 overflow-y-auto">
              {/* 插件图标和标题 */}
              <div className="flex items-start gap-4 mb-6">
                <img
                  src={getCloudServiceClientSync().getPluginIconURL(
                    author!,
                    pluginName!,
                  )}
                  alt={plugin.name}
                  className="w-16 h-16 rounded-xl border bg-gray-50 object-cover flex-shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">
                    {extractI18nObject(plugin.label) || plugin.name}
                  </h2>
                  <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                    <Users className="w-4 h-4" />
                    <span>
                      {plugin.author} / {plugin.name}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-sm text-gray-600 mb-2">
                    <Badge variant="outline" className="text-sm">
                      v{plugin.latest_version}
                    </Badge>

                    <Badge
                      variant="outline"
                      className="text-sm flex items-center gap-1"
                    >
                      <Download className="w-5 h-5" />
                      <span className="font-medium">
                        {plugin.install_count.toLocaleString()}{' '}
                        {t('market.downloads')}
                      </span>
                    </Badge>

                    {plugin.repository && (
                      <svg
                        className="w-[1.2rem] h-[1.2rem] text-black cursor-pointer hover:text-gray-600"
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                        onClick={(e) => {
                          e.stopPropagation();
                          window.open(plugin.repository, '_blank');
                        }}
                      >
                        <path d="M12.001 2C6.47598 2 2.00098 6.475 2.00098 12C2.00098 16.425 4.86348 20.1625 8.83848 21.4875C9.33848 21.575 9.52598 21.275 9.52598 21.0125C9.52598 20.775 9.51348 19.9875 9.51348 19.15C7.00098 19.6125 6.35098 18.5375 6.15098 17.975C6.03848 17.6875 5.55098 16.8 5.12598 16.5625C4.77598 16.375 4.27598 15.9125 5.11348 15.9C5.90098 15.8875 6.46348 16.625 6.65098 16.925C7.55098 18.4375 8.98848 18.0125 9.56348 17.75C9.65098 17.1 9.91348 16.6625 10.201 16.4125C7.97598 16.1625 5.65098 15.3 5.65098 11.475C5.65098 10.3875 6.03848 9.4875 6.67598 8.7875C6.57598 8.5375 6.22598 7.5125 6.77598 6.1375C6.77598 6.1375 7.61348 5.875 9.52598 7.1625C10.326 6.9375 11.176 6.825 12.026 6.825C12.876 6.825 13.726 6.9375 14.526 7.1625C16.4385 5.8625 17.276 6.1375 17.276 6.1375C17.826 7.5125 17.476 8.5375 17.376 8.7875C18.0135 9.4875 18.401 10.375 18.401 11.475C18.401 15.3125 16.0635 16.1625 13.8385 16.4125C14.201 16.725 14.5135 17.325 14.5135 18.2625C14.5135 19.6 14.501 20.675 14.501 21.0125C14.501 21.275 14.6885 21.5875 15.1885 21.4875C19.259 20.1133 21.9999 16.2963 22.001 12C22.001 6.475 17.526 2 12.001 2Z"></path>
                      </svg>
                    )}
                  </div>
                </div>
              </div>

              {/* 插件描述 */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">
                  {t('market.description')}
                </h3>
                <p className="text-gray-700 leading-relaxed">
                  {extractI18nObject(plugin.description) ||
                    t('market.noDescription')}
                </p>
              </div>

              {/* 标签 */}
              {plugin.tags && plugin.tags.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">
                    {t('market.tags')}
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {plugin.tags.map((tag) => (
                      <Badge key={tag} variant="secondary" className="text-sm">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* 操作按钮 */}
              <div className="space-y-3">
                <Button
                  onClick={() => installPlugin(plugin)}
                  className="w-full h-12 text-base font-medium"
                >
                  <Download className="w-5 h-5 mr-2" />
                  {t('market.install')}
                </Button>
                {/* {plugin.repository && (
                  <Button 
                    variant="outline" 
                    onClick={handleOpenRepository}
                    className="w-full h-12 text-base"
                  >
                    <ExternalLink className="w-5 h-5 mr-2" />
                    {t('market.repository')}
                  </Button>
                )} */}
              </div>
            </div>

            {/* 右侧：README内容 */}
            <div className="w-3/5 p-2 overflow-y-auto">
              <div className=" rounded-lg p-6 min-h-[500px]">
                {isLoadingReadme ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin" />
                    <span className="ml-3 text-gray-600">
                      {t('cloud.loading')}
                    </span>
                  </div>
                ) : (
                  <div className="prose prose-sm max-w-none text-gray-800">
                    <ReactMarkdown
                      components={{
                        // 自定义样式
                        h1: ({ children }) => (
                          <h1 className="text-xl font-bold mb-4 text-gray-900 border-b border-gray-200 pb-2">
                            {children}
                          </h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-lg font-semibold mb-3 text-gray-900 mt-6">
                            {children}
                          </h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-base font-medium mb-2 text-gray-900 mt-4">
                            {children}
                          </h3>
                        ),
                        p: ({ children }) => (
                          <p className="mb-4 leading-relaxed text-gray-700">
                            {children}
                          </p>
                        ),
                        ul: ({ children }) => (
                          <ul className="mb-4 pl-6 list-disc space-y-1">
                            {children}
                          </ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="mb-4 pl-6 list-decimal space-y-1">
                            {children}
                          </ol>
                        ),
                        li: ({ children }) => (
                          <li className="text-gray-700">{children}</li>
                        ),
                        code: ({ children, node }) => {
                          const isInline =
                            node?.children?.length === 1 &&
                            node?.children[0]?.type === 'text';
                          return isInline ? (
                            <code className="bg-gray-200 p-1 rounded-md text-sm font-mono whitespace-pre-wrap border">
                              {children}
                            </code>
                          ) : (
                            <code className="block bg-gray-200 p-3 rounded-md text-sm font-mono whitespace-pre-wrap border">
                              {children}
                            </code>
                          );
                        },
                        blockquote: ({ children }) => (
                          <blockquote className="border-l-4 border-blue-300 pl-4 py-2 mb-4 italic bg-blue-50 text-gray-700 rounded-r-md">
                            {children}
                          </blockquote>
                        ),
                        a: ({ href, children }) => (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 underline"
                          >
                            {children}
                          </a>
                        ),
                      }}
                    >
                      {readme}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
