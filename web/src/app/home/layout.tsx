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
  userInfo,
  systemInfo,
  initializeUserInfo,
  initializeSystemInfo,
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

// Routes that belong to the "Extensions" section
const EXTENSIONS_ROUTES = ['/home/plugins', '/home/market', '/home/mcp', '/home/plugin-pages'];

function isExtensionsRoute(pathname: string): boolean {
  return EXTENSIONS_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(route + '/'),
  );
}

export default function HomeLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const navigate = useNavigate();

  // Initialize user info if not already initialized
  useEffect(() => {
    if (!userInfo) {
      initializeUserInfo();
    }
  }, []);

  // Auto-redirect to wizard on first visit (wizard not yet completed on this instance)
  useEffect(() => {
    const checkWizard = async () => {
      try {
        // Always re-fetch to ensure we have the latest wizard_status from backend
        await initializeSystemInfo();
        if (systemInfo.wizard_status === 'none') {
          navigate('/wizard');
        }
      } catch {
        // If fetching system info fails, don't redirect
      }
    };
    checkWizard();
  }, [navigate]);

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
  const sectionLink = isExtensions ? '/home/plugins' : '/home/monitoring';

  return (
    <SidebarProvider>
      <Suspense fallback={<div />}>
        <HomeSidebar onSelectedChangeAction={onSelectedChangeAction} />
      </Suspense>

      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
          <div className="flex items-center gap-2 px-4">
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
          </div>
        </header>

        <div className="flex-1 overflow-hidden p-4 pt-0 min-w-0">
          {mainContent}
        </div>

        <SurveyWidget />
      </SidebarInset>
    </SidebarProvider>
  );
}
