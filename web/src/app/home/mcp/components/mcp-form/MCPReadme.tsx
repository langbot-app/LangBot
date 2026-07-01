import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import rehypeHighlight from 'rehype-highlight';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import { useTranslation } from 'react-i18next';
import '@/styles/github-markdown.css';

/**
 * Renders the README markdown captured from LangBot Space at install time.
 * The README is stored on the MCP server record (``server.readme``) so this
 * works offline and regardless of the server's runtime/connection state.
 *
 * MCP marketplace READMEs reference images by absolute URL (the upstream repo),
 * so — unlike plugin READMEs — no asset-path rewriting is needed here.
 */
export default function MCPReadme({ readme }: { readme?: string }) {
  const { t } = useTranslation();

  if (!readme || !readme.trim()) {
    return (
      <div className="flex min-h-[220px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
        {t('mcp.noReadme')}
      </div>
    );
  }

  return (
    <div className="w-full overflow-auto">
      <div className="markdown-body max-w-none p-1 pt-0">
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
            ol: ({ children }) => <ol className="list-decimal">{children}</ol>,
            li: ({ children }) => <li className="ml-4">{children}</li>,
            a: ({ children, href, ...props }) => (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                {...props}
              >
                {children}
              </a>
            ),
            img: ({ src, alt, ...props }) => (
              <img
                src={src}
                alt={alt || ''}
                className="my-4 h-auto max-w-full rounded-lg"
                {...props}
              />
            ),
          }}
        >
          {readme}
        </ReactMarkdown>
      </div>
    </div>
  );
}
