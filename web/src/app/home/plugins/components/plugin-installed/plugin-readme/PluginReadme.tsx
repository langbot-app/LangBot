import { useState, useEffect } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeHighlight from 'rehype-highlight';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import { getAPILanguageCode } from '@/i18n/I18nProvider';
import './github-markdown.css';

export default function PluginReadme({
  pluginAuthor,
  pluginName,
}: {
  pluginAuthor: string;
  pluginName: string;
}) {
  const { t } = useTranslation();
  const [readme, setReadme] = useState<string>('');
  const [isLoadingReadme, setIsLoadingReadme] = useState(false);

  const language = getAPILanguageCode();

  useEffect(() => {
    // Fetch plugin README
    setIsLoadingReadme(true);
    httpClient
      .getPluginReadme(pluginAuthor, pluginName, language)
      .then((res) => {
        setReadme(res.readme);
      })
      .catch(() => {
        setReadme('');
      })
      .finally(() => {
        setIsLoadingReadme(false);
      });
  }, [pluginAuthor, pluginName]);

  return (
    <div className="w-full h-full overflow-auto">
      {isLoadingReadme ? (
        <div className="p-6 text-sm text-gray-500 dark:text-gray-400">
          {t('plugins.loadingReadme')}
        </div>
      ) : readme ? (
        <div className="markdown-body p-6 max-w-none pt-0">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[
              rehypeRaw,
              rehypeHighlight,
              rehypeSlug,
              [
                rehypeAutolinkHeadings,
                {
                  behavior: 'wrap',
                  properties: {
                    className: ['anchor'],
                  },
                },
              ],
            ]}
            components={{
              ul: ({ children }) => <ul className="list-disc">{children}</ul>,
              ol: ({ children }) => (
                <ol className="list-decimal">{children}</ol>
              ),
              li: ({ children }) => <li className="ml-4">{children}</li>,
              img: ({ src, alt, ...props }) => {
                let imageSrc = src || '';

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

                if (
                  imageSrc &&
                  !imageSrc.startsWith('http://') &&
                  !imageSrc.startsWith('https://') &&
                  !imageSrc.startsWith('data:')
                ) {
                  imageSrc = imageSrc.replace(/^(\.\/|\/)+/, '');

                  if (!imageSrc.startsWith('assets/')) {
                    imageSrc = `assets/${imageSrc}`;
                  }

                  const assetPath = imageSrc.replace(/^assets\//, '');
                  imageSrc = httpClient.getPluginAssetURL(
                    pluginAuthor,
                    pluginName,
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
      ) : (
        <div className="p-6 text-sm text-gray-500 dark:text-gray-400">
          {t('plugins.noReadme')}
        </div>
      )}
    </div>
  );
}
