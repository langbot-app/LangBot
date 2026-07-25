import {
  Building2,
  Check,
  ExternalLink,
  Settings,
  Sparkles,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

import {
  switchWorkspaceAndReload,
  systemInfo,
  useCurrentWorkspace,
  useWorkspaceBootstrap,
} from '@/app/infra/http';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

export const OPEN_WORKSPACE_SETTINGS_EVENT = 'langbot:open-workspace-settings';

export function requestWorkspaceSettings(): void {
  window.dispatchEvent(new Event(OPEN_WORKSPACE_SETTINGS_EVENT));
}

export default function WorkspaceSwitcher({
  className,
}: {
  className?: string;
}) {
  const { t } = useTranslation();
  const currentWorkspace = useCurrentWorkspace();
  const workspaces = useWorkspaceBootstrap();
  const isCloud = currentWorkspace?.workspace.source === 'cloud_projection';

  if (!currentWorkspace) return null;

  const cloudPortalUrl = `${systemInfo.cloud_service_url.replace(/\/$/, '')}/cloud?workspace=${encodeURIComponent(currentWorkspace.workspace.uuid)}`;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn('min-w-44 max-w-64 justify-start', className)}
          aria-label={t('workspace.switchWorkspace')}
        >
          <Building2 className="size-4 shrink-0" />
          <span className="truncate">{currentWorkspace.workspace.name}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-64">
        <DropdownMenuLabel>{t('workspace.switchWorkspace')}</DropdownMenuLabel>
        {workspaces.map((entry) => {
          const selected =
            entry.workspace.uuid === currentWorkspace.workspace.uuid;
          return (
            <DropdownMenuItem
              key={entry.workspace.uuid}
              onClick={() => {
                if (!selected)
                  void switchWorkspaceAndReload(entry.workspace.uuid);
              }}
            >
              <Building2 className="size-4" />
              <span className="min-w-0 flex-1 truncate">
                {entry.workspace.name}
              </span>
              <span className="text-xs text-muted-foreground">
                {t(`workspace.roles.${entry.membership.role}`)}
              </span>
              {selected && <Check className="size-4" />}
            </DropdownMenuItem>
          );
        })}
        <DropdownMenuSeparator />
        {isCloud && (
          <>
            <DropdownMenuLabel className="flex items-center justify-between gap-3 font-normal">
              <span className="text-muted-foreground">
                {t('workspace.currentPlan')}
              </span>
              <span className="font-medium text-foreground">
                {currentWorkspace.plan_name || t('workspace.planUnavailable')}
              </span>
            </DropdownMenuLabel>
            <DropdownMenuItem asChild>
              <a
                href={cloudPortalUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Sparkles className="size-4" />
                {t('workspace.upgradePlan')}
                <ExternalLink className="ml-auto size-3.5" />
              </a>
            </DropdownMenuItem>
          </>
        )}
        <DropdownMenuItem onClick={requestWorkspaceSettings}>
          <Settings className="size-4" />
          {t('workspace.settings')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
