import { useState, useEffect } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import rehypeHighlight from 'rehype-highlight';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import { getAPILanguageCode } from '@/i18n/I18nProvider';
import '@/styles/github-markdown.css';
import { useAuthenticatedPluginAsset } from '@/hooks/useAuthenticatedPluginResource';

function AuthenticatedReadmeImage({
  author,
  name,
  filepath,
  alt,
  ...props
}: {
  author: string;
  name: string;
  filepath: string;
  alt?: string;
} & React.ImgHTMLAttributes<HTMLImageElement>) {
  const { url, error } = useAuthenticatedPluginAsset(author, name, filepath);
  if (error)
    return (
      <span className="text-sm text-muted-foreground">{alt || filepath}</span>
    );
  if (!url)
    return (
      <span className="inline-block h-6 w-24 animate-pulse rounded bg-muted" />
    );
  return (
    <img
      src={url}
      alt={alt || ''}
      className="max-w-lg h-auto my-4"
      {...props}
    />
  );
}

function PluginReadmeImage({
  author,
  name,
  src,
  alt,
  ...props
}: {
  author: string;
  name: string;
  src?: string;
  alt?: string;
} & React.ImgHTMLAttributes<HTMLImageElement>) {
  const imageSrc = typeof src === 'string' ? src : '';
  if (!imageSrc || /^(https?:\/\/|data:)/i.test(imageSrc)) {
    return (
      <img
        src={imageSrc}
        alt={alt || ''}
        className="max-w-lg h-auto my-4"
        {...props}
      />
    );
  }
  let filepath = imageSrc.replace(/^(\.\/|\/)+/, '');
  filepath = filepath.replace(/^assets\//, '');
  return (
    <AuthenticatedReadmeImage
      author={author}
      name={name}
      filepath={filepath}
      alt={alt}
      {...props}
    />
  );
}

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
              rehypeSanitize,
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
              img: ({ src, alt, ...props }) => (
                <PluginReadmeImage
                  author={pluginAuthor}
                  name={pluginName}
                  src={typeof src === 'string' ? src : undefined}
                  alt={alt}
                  {...props}
                />
              ),
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
