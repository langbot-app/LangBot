import { useSearchParams } from 'react-router-dom';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useEffect, useRef, useState, useCallback } from 'react';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { useTheme } from '@/components/providers/theme-provider';

/**
 * Plugin page that renders a plugin-provided HTML page in an iframe.
 * URL format: /home/plugin-pages?id=author/name/pageId
 *
 * The iframe communicates with the parent via postMessage:
 *
 * Parent → iframe:
 *   { type: 'langbot:context', theme: 'light'|'dark', language: 'zh-Hans'|'en-US' }
 *
 * iframe → Parent:
 *   { type: 'langbot:api', requestId: string, endpoint: string, method: string, body?: any }
 *
 * Parent → iframe (response):
 *   { type: 'langbot:api:response', requestId: string, data?: any, error?: string }
 */
export default function PluginPagesPage() {
  const [searchParams] = useSearchParams();
  const id = searchParams.get('id');
  const { t } = useTranslation();
  const { setDetailEntityName, pluginPages } = useSidebarData();

  // Find the matching page for breadcrumb
  const page = pluginPages.find((p) => p.id === id);

  useEffect(() => {
    setDetailEntityName(page?.name ?? id ?? '');
    return () => setDetailEntityName(null);
  }, [page, id, setDetailEntityName]);

  if (!id) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        {t('pluginPages.selectFromSidebar')}
      </div>
    );
  }

  // Parse "author/name/pageId"
  const parts = id.split('/');
  if (parts.length < 3) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        {t('pluginPages.invalidPage')}
      </div>
    );
  }

  const author = parts[0];
  const pluginName = parts[1];
  // Use the asset path from the page manifest, not the page ID
  const assetPath = page?.path ?? parts.slice(2).join('/');
  const pageId = parts.slice(2).join('/');

  return (
    <PluginPageIframe
      author={author}
      pluginName={pluginName}
      pagePath={assetPath}
      pageId={pageId}
    />
  );
}

function PluginPageIframe({
  author,
  pluginName,
  pagePath,
  pageId,
}: {
  author: string;
  pluginName: string;
  pagePath: string;
  pageId: string;
}) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [loading, setLoading] = useState(true);
  const { resolvedTheme } = useTheme();
  const { i18n } = useTranslation();

  const assetUrl = httpClient.getPluginAssetURL(author, pluginName, pagePath);

  // Send context (theme + language) to iframe
  // Use '*' as targetOrigin because sandboxed iframe has opaque (null) origin
  const sendContext = useCallback(() => {
    const iframe = iframeRef.current;
    if (iframe?.contentWindow) {
      iframe.contentWindow.postMessage(
        {
          type: 'langbot:context',
          theme: resolvedTheme,
          language: i18n.language,
        },
        '*',
      );
    }
  }, [resolvedTheme, i18n.language]);

  // Re-send context when theme or language changes
  useEffect(() => {
    if (!loading) {
      sendContext();
    }
  }, [resolvedTheme, i18n.language, loading, sendContext]);

  // Handle messages from iframe (API calls)
  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      // Validate source — only accept messages from our specific iframe window
      // This is more secure than origin checking: works with sandboxed (null-origin) iframes
      // and prevents spoofing from other windows/iframes
      if (event.source !== iframeRef.current?.contentWindow) return;

      const data = event.data;
      if (!data || typeof data !== 'object') return;

      // Validate requestId format to prevent injection
      if (data.type === 'langbot:api') {
        const { requestId, endpoint, method, body } = data;
        if (typeof requestId !== 'string' || typeof endpoint !== 'string')
          return;
        // Sanitize endpoint — must start with / and not contain ..
        if (!endpoint.startsWith('/') || endpoint.includes('..')) return;
        const normalizedMethod =
          typeof method === 'string' ? method.toUpperCase() : 'POST';
        if (
          !['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].includes(normalizedMethod)
        )
          return;
        try {
          const result = await httpClient.pluginPageApi(
            author,
            pluginName,
            pageId,
            endpoint,
            normalizedMethod,
            body,
          );
          iframeRef.current?.contentWindow?.postMessage(
            {
              type: 'langbot:api:response',
              requestId,
              data: result,
            },
            '*',
          );
        } catch (err: unknown) {
          const errorMsg = err instanceof Error ? err.message : String(err);
          iframeRef.current?.contentWindow?.postMessage(
            {
              type: 'langbot:api:response',
              requestId,
              error: errorMsg,
            },
            '*',
          );
        }
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [author, pluginName, pageId]);

  return (
    <div className="flex flex-col h-full w-full">
      {loading && (
        <div className="flex items-center justify-center h-full text-muted-foreground">
          Loading...
        </div>
      )}
      <iframe
        ref={iframeRef}
        src={assetUrl}
        className="flex-1 w-full border-0 rounded-md"
        style={{ display: loading ? 'none' : 'block' }}
        onLoad={() => {
          setLoading(false);
          sendContext();
        }}
        sandbox="allow-scripts allow-forms"
        title={`${author}/${pluginName} - ${pagePath}`}
      />
    </div>
  );
}
