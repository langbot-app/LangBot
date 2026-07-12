import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { KeyRound, Sparkles, Settings, HardDrive } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from '@/components/ui/sidebar';
import { cn } from '@/lib/utils';
import AccountSettingsPanel from '@/app/home/components/account-settings-dialog/AccountSettingsPanel';
import ApiIntegrationPanel from '@/app/home/components/api-integration-dialog/ApiIntegrationPanel';
import ModelsPanel from '@/app/home/components/models-dialog/ModelsPanel';
import StorageAnalysisPanel from '@/app/home/components/storage-analysis-dialog/StorageAnalysisPanel';

// The set of settings sections shown in the unified dialog. The string values
// are also reused as the ?action= query param suffix so deep links keep working.
export type SettingsSection =
  | 'account'
  | 'apiIntegration'
  | 'models'
  | 'storageAnalysis';

// Map between a section id and its ?action= query value, so existing deep links
// (showAccountSettings, showApiIntegrationSettings, showModelSettings,
// showStorageAnalysis) continue to resolve to the right section.
export const SETTINGS_ACTION_BY_SECTION: Record<SettingsSection, string> = {
  account: 'showAccountSettings',
  apiIntegration: 'showApiIntegrationSettings',
  models: 'showModelSettings',
  storageAnalysis: 'showStorageAnalysis',
};

export const SETTINGS_SECTION_BY_ACTION: Record<string, SettingsSection> =
  Object.fromEntries(
    Object.entries(SETTINGS_ACTION_BY_SECTION).map(([section, action]) => [
      action,
      section as SettingsSection,
    ]),
  );

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  section: SettingsSection;
  onSectionChange: (section: SettingsSection) => void;
}

export default function SettingsDialog({
  open,
  onOpenChange,
  section,
  onSectionChange,
}: SettingsDialogProps) {
  const { t } = useTranslation();
  // A nested modal (e.g. the provider form) can request that we ignore
  // outer-close until it is dismissed.
  const [blocking, setBlocking] = useState(false);

  // Only the Models panel can raise a blocking nested modal. When we navigate
  // away from it (or close the dialog) the panel unmounts without resetting,
  // so clear the flag here to avoid getting stuck unable to close.
  useEffect(() => {
    if (section !== 'models' || !open) {
      setBlocking(false);
    }
  }, [section, open]);

  const navItems: {
    id: SettingsSection;
    label: string;
    title: string;
    description: string;
    icon: React.ReactNode;
  }[] = [
    {
      id: 'models',
      label: t('settingsDialog.nav.models'),
      title: t('models.title'),
      description: t('models.description'),
      icon: <Sparkles className="size-4" />,
    },
    {
      id: 'apiIntegration',
      label: t('settingsDialog.nav.api'),
      title: t('common.apiIntegration'),
      description: t('common.apiIntegrationDescription'),
      icon: <KeyRound className="size-4" />,
    },
    {
      id: 'storageAnalysis',
      label: t('settingsDialog.nav.storage'),
      title: t('storageAnalysis.title'),
      description: t('storageAnalysis.description'),
      icon: <HardDrive className="size-4" />,
    },
    {
      id: 'account',
      label: t('settingsDialog.nav.account'),
      title: t('account.settings'),
      description: t('account.settingsDescription'),
      icon: <Settings className="size-4" />,
    },
  ];

  const activeItem = navItems.find((item) => item.id === section);
  const activeLabel = activeItem?.title ?? t('settingsDialog.title');

  return (
    <Dialog
      open={open}
      onOpenChange={(newOpen) => {
        if (!newOpen && blocking) return;
        onOpenChange(newOpen);
      }}
    >
      <DialogContent
        className="h-[80vh] max-h-[800px] overflow-hidden p-0 sm:max-w-[52rem] [&>button:last-child]:z-20"
        // Fixed height so switching sections never resizes the dialog; each
        // panel scrolls its own content internally.
      >
        <DialogTitle className="sr-only">
          {t('settingsDialog.title')}
        </DialogTitle>
        <DialogDescription className="sr-only">{activeLabel}</DialogDescription>

        {/* Override the SidebarProvider wrapper's default h-svh so the two
            columns fill the dialog's fixed height instead of the viewport. */}
        <SidebarProvider className="!min-h-0 h-full">
          <Sidebar
            collapsible="none"
            className="hidden h-full w-44 shrink-0 border-r md:flex"
          >
            <SidebarContent>
              <SidebarGroup>
                <SidebarGroupContent>
                  <div className="px-2 py-3 text-sm font-semibold">
                    {t('settingsDialog.title')}
                  </div>
                  <SidebarMenu>
                    {navItems.map((item) => (
                      <SidebarMenuItem key={item.id}>
                        <SidebarMenuButton
                          isActive={section === item.id}
                          onClick={() => onSectionChange(item.id)}
                        >
                          {item.icon}
                          <span>{item.label}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            </SidebarContent>
          </Sidebar>

          <main className="flex h-full min-w-0 flex-1 flex-col overflow-hidden">
            {/* Mobile section switcher (sidebar is hidden on small screens) */}
            <div className="flex shrink-0 items-center gap-1 overflow-x-auto border-b px-3 py-2 md:hidden">
              {navItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSectionChange(item.id)}
                  className={cn(
                    'flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm',
                    section === item.id
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                      : 'text-muted-foreground',
                  )}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </button>
              ))}
            </div>

            {/* Unified section header (shared across all tabs). The extra
                right padding keeps the title clear of the dialog's close X. */}
            <div className="flex shrink-0 flex-col gap-0.5 border-b px-6 py-4 pr-12">
              <h2 className="flex items-center gap-2 text-base font-semibold">
                {activeItem?.icon}
                {activeItem?.title}
              </h2>
              {activeItem?.description && (
                <p className="text-sm text-muted-foreground">
                  {activeItem.description}
                </p>
              )}
            </div>

            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              {section === 'models' && (
                <ModelsPanel
                  active={open && section === 'models'}
                  onBlockingChange={setBlocking}
                />
              )}
              {section === 'apiIntegration' && (
                <ApiIntegrationPanel
                  active={open && section === 'apiIntegration'}
                />
              )}
              {section === 'storageAnalysis' && (
                <StorageAnalysisPanel
                  active={open && section === 'storageAnalysis'}
                />
              )}
              {section === 'account' && (
                <AccountSettingsPanel active={open && section === 'account'} />
              )}
            </div>
          </main>
        </SidebarProvider>
      </DialogContent>
    </Dialog>
  );
}
