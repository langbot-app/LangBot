import { useState, useEffect } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useTranslation } from 'react-i18next';
import { useTheme } from 'next-themes';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeHighlight from 'rehype-highlight';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import './github-markdown.css';

export default function PluginReadme({
  pluginAuthor,
  pluginName,
}: {
  pluginAuthor: string;
  pluginName: string;
}) {
  const { t } = useTranslation();
  const { theme, systemTheme } = useTheme();
  const [readme, setReadme] = useState<string>('');
  const [isLoadingReadme, setIsLoadingReadme] = useState(false);

  // Dynamically load highlight.js theme based on current theme
  useEffect(() => {
    const currentTheme = theme === 'system' ? systemTheme : theme;
    const isDark = currentTheme === 'dark';

    // Remove existing highlight.js theme
    const existingTheme = document.querySelector('link[data-highlight-theme]');
    if (existingTheme) {
      existingTheme.remove();
    }

    // Add new theme
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.setAttribute('data-highlight-theme', 'true');
    link.href = isDark
      ? 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css'
      : 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css';
    document.head.appendChild(link);

    return () => {
      const themeLink = document.querySelector('link[data-highlight-theme]');
      if (themeLink) {
        themeLink.remove();
      }
    };
  }, [theme, systemTheme]);

  useEffect(() => {
    // Fetch plugin README
    setIsLoadingReadme(true);
    httpClient
      .getPluginReadme(pluginAuthor, pluginName)
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
