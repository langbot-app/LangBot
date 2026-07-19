import HomeSidebar from '@/app/home/components/home-sidebar/HomeSidebar';
import SurveyWidget from '@/app/home/components/survey/SurveyWidget';
import React, {
  useState,
  useCallback,
  useMemo,
  useEffect,
  Suspense,
} from 'react';
import { SidebarChildVO } from '@/app/home/components/home-sidebar/HomeSidebarChild';
import {
  SidebarDataProvider,
  useSidebarData,
} from '@/app/home/components/home-sidebar/SidebarDataContext';
import { I18nObject } from '@/app/infra/entities/common';
import {
  bootstrapWorkspaceSession,
  systemInfo,
  initializeSystemInfo,
  useCurrentWorkspace,
} from '@/app/infra/http';
import { useNavigate, useLocation } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { CircleHelp } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar';
import { Separator } from '@/components/ui/separator';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import {
  PluginInstallTaskProvider,
  PluginInstallProgressDialog,
} from '@/app/home/plugins/components/plugin-install-task';
import { setDocumentTitle } from '@/hooks/useDocumentTitle';
import WorkspaceSwitcher from '@/app/home/components/workspace-settings/WorkspaceSwitcher';

// Routes that belong to the "Extensions" section
const EXTENSIONS_ROUTES = [
  '/home/extensions',
  '/home/add-extension',
  '/home/mcp',
  '/home/skills',
  '/home/plugin-pages',
];

// Map a /home route to the i18n key for its type-level title. Used as a robust
// fallback for the document title on direct page loads, before the sidebar's
// onSelectedChange has populated the local `title` state. Detail routes reuse
// the section key (prefix match), e.g. /home/mcp?id=... -> mcp.title.
const HOME_TITLE_KEYS: { match: (path: string) => boolean; key: string }[] = [
  { match: (p) => p.startsWith('/home/monitoring'), key: 'monitoring.title' },
  { match: (p) => p.startsWith('/home/bots'), key: 'bots.title' },
  { match: (p) => p.startsWith('/home/pipelines'), key: 'pipelines.title' },
  {
    match: (p) => p.startsWith('/home/add-extension'),
    key: 'sidebar.addExtension',
  },
  { match: (p) => p.startsWith('/home/extensions'), key: 'plugins.title' },
  { match: (p) => p.startsWith('/home/mcp'), key: 'mcp.title' },
  { match: (p) => p.startsWith('/home/knowledge'), key: 'knowledge.title' },
  { match: (p) => p.startsWith('/home/skills'), key: 'skills.title' },
  {
    match: (p) => p.startsWith('/home/plugin-pages'),
    key: 'sidebar.pluginPages',
  },
];

function isExtensionsRoute(pathname: string): boolean {
  return EXTENSIONS_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(route + '/'),
  );
}

const HOME_CONTENT_MAX_WIDTH = 'max-w-[1360px]';

export default function HomeLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const navigate = useNavigate();
  const location = useLocation();
  const currentWorkspace = useCurrentWorkspace();
  const [identityReady, setIdentityReady] = useState(false);

  // Resolve the instance, Account, and Workspace before mounting any
  // Workspace-owned page. The second system-info read uses the now-stable
  // selector and therefore returns the selected Workspace's wizard metadata.
  useEffect(() => {
    let cancelled = false;
    bootstrapWorkspaceSession()
      .then(async (result) => {
        if (result.status === 'selection-required') {
          const returnTo = `${location.pathname}${location.search}`;
          navigate(
            `/workspaces/select?returnTo=${encodeURIComponent(returnTo)}`,
            { replace: true },
          );
          return false;
        }
        if (result.status === 'unavailable') {
          throw new Error('No Workspace is available for this Account');
        }
        await initializeSystemInfo({ throwOnError: true });
        return true;
      })
      .then((ready) => {
        if (!cancelled && ready) setIdentityReady(true);
      })
      .catch(() => {
        if (!cancelled) navigate('/login', { replace: true });
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname, location.search, navigate]);

  // A read-only member may view resources but must not enter mutation-only
  // routes. The backend remains the authoritative authorization boundary.
  useEffect(() => {
    if (!identityReady || !currentWorkspace) return;
    if (currentWorkspace.permissions.includes('resource.manage')) return;

    const params = new URLSearchParams(location.search);
    const createOnlyRoute =
      location.pathname === '/home/add-extension' ||
      params.get('id') === 'new' ||
      (location.pathname === '/home/skills' &&
        params.get('action') === 'create');
    if (createOnlyRoute) {
      const fallback =
        location.pathname === '/home/add-extension'
          ? '/home/extensions'
          : location.pathname;
      navigate(fallback, { replace: true });
    }
  }, [
    currentWorkspace,
    identityReady,
    location.pathname,
    location.search,
    navigate,
  ]);

  // Auto-redirect only after the Workspace bootstrap above has loaded the
  // selected Workspace's wizard state.
  useEffect(() => {
    if (!identityReady) return;
    if (systemInfo.wizard_status === 'none') {
      navigate('/wizard', { replace: true });
    }
  }, [identityReady, navigate]);

  if (!identityReady) return <div />;

  return (
    <SidebarDataProvider>
      <PluginInstallTaskProvider>
        <HomeLayoutInner>{children}</HomeLayoutInner>
        <PluginInstallProgressDialog />
      </PluginInstallTaskProvider>
    </SidebarDataProvider>
  );
}

function HomeLayoutInner({ children }: { children: React.ReactNode }) {
  const [title, setTitle] = useState<string>('');
  const [helpLink, setHelpLink] = useState<I18nObject>({
    en_US: '',
    zh_Hans: '',
  });
  const { detailEntityName } = useSidebarData();
  const location = useLocation();
  const pathname = location.pathname;
  const { t } = useTranslation();

  const onSelectedChangeAction = useCallback((child: SidebarChildVO) => {
    setTitle(child.name);
    setHelpLink(child.helpLink);
  }, []);

  // Memoize the main content area to prevent re-renders when sidebar state changes
  const mainContent = useMemo(() => children, [children]);

  const resolvedHelpLink = extractI18nObject(helpLink);

  // Determine breadcrumb section label and default link based on current route
  const isExtensions = isExtensionsRoute(pathname);
  const sectionLabel = isExtensions
    ? t('sidebar.extensions')
    : t('sidebar.home');
  const sectionLink = isExtensions ? '/home/extensions' : '/home/monitoring';

  // Drive the browser tab title for the /home section. The type-level label
  // prefers the sidebar-provided `title`, falling back to a route-derived key on
  // direct page loads. When a sub-entity (plugin / MCP / pipeline / KB / skill)
  // is open, its name is prepended: "<entity> · <type> · LangBot".
  useEffect(() => {
    const routeEntry = HOME_TITLE_KEYS.find((e) => e.match(pathname));
    const fallbackType =
      routeEntry && t(routeEntry.key) !== routeEntry.key
        ? t(routeEntry.key)
        : null;
    const typeLabel = title || fallbackType;
    setDocumentTitle(detailEntityName, typeLabel);
  }, [pathname, title, detailEntityName, t]);

  return (
    <SidebarProvider>
      <Suspense fallback={<div />}>
        <HomeSidebar onSelectedChangeAction={onSelectedChangeAction} />
      </Suspense>

      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
          <div className="flex w-full items-center gap-2 px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator
              orientation="vertical"
              className="mr-2 data-[orientation=vertical]:h-4"
            />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden md:block">
                  <BreadcrumbLink asChild>
                    <Link to={sectionLink}>{sectionLabel}</Link>
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>{title}</BreadcrumbPage>
                </BreadcrumbItem>
                {detailEntityName && (
                  <>
                    <BreadcrumbSeparator />
                    <BreadcrumbItem>
                      <BreadcrumbPage>{detailEntityName}</BreadcrumbPage>
                    </BreadcrumbItem>
                  </>
                )}
                {resolvedHelpLink && (
                  <>
                    <BreadcrumbItem>
                      <a
                        href={resolvedHelpLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <CircleHelp className="size-3.5" />
                      </a>
                    </BreadcrumbItem>
                  </>
                )}
              </BreadcrumbList>
            </Breadcrumb>
            <WorkspaceSwitcher className="ml-auto w-44" />
          </div>
        </header>

        <main className="flex-1 overflow-hidden min-w-0 px-4 pb-4 pt-0">
          <div
            className={`mx-auto h-full w-full min-w-0 ${HOME_CONTENT_MAX_WIDTH}`}
          >
            {mainContent}
          </div>
        </main>

        <SurveyWidget />
      </SidebarInset>
    </SidebarProvider>
  );
}
