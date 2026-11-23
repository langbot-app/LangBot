import { Building2, Settings } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import {
  switchWorkspaceAndReload,
  useCurrentWorkspace,
  useWorkspaceBootstrap,
} from '@/app/infra/http';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import WorkspacePlanBadge from './WorkspacePlanBadge';

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

  if (!currentWorkspace) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn('h-9 min-w-0 gap-1.5 px-2.5 text-sm', className)}
          aria-label={t('workspace.switchWorkspace')}
        >
          <Building2 className="size-4 shrink-0" />
          <span className="max-w-[6rem] truncate">
            {currentWorkspace.workspace.name}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64 p-1.5">
        <DropdownMenuLabel className="px-3 py-2 text-sm">
          {t('workspace.switchWorkspace')}
        </DropdownMenuLabel>
        {workspaces.map((entry) => {
          const selected =
            entry.workspace.uuid === currentWorkspace.workspace.uuid;
          return (
            <DropdownMenuItem
              key={entry.workspace.uuid}
              className={cn(
                'min-h-11 gap-2 px-2 py-1.5',
                selected && 'bg-muted',
              )}
              onClick={() => {
                if (!selected)
                  void switchWorkspaceAndReload(entry.workspace.uuid);
              }}
            >
              <Building2 className="size-4 shrink-0" />
              <span className="max-w-[7rem] min-w-0 flex-1 truncate font-medium">
                {entry.workspace.name}
              </span>
              {entry.workspace.source === 'cloud_projection' && (
                <WorkspacePlanBadge planName={entry.plan_name} />
              )}
              {selected && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8"
                  aria-label={t('workspace.settings')}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    requestWorkspaceSettings();
                  }}
                >
                  <Settings className="size-4" />
                </Button>
              )}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
