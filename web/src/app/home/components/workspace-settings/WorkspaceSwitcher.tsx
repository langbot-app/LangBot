import { Building2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import {
  switchWorkspaceAndReload,
  useCurrentWorkspace,
  useWorkspaceBootstrap,
} from '@/app/infra/http';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

export default function WorkspaceSwitcher({
  className,
}: {
  className?: string;
}) {
  const { t } = useTranslation();
  const currentWorkspace = useCurrentWorkspace();
  const workspaces = useWorkspaceBootstrap();

  if (!currentWorkspace || workspaces.length <= 1) return null;

  return (
    <Select
      value={currentWorkspace.workspace.uuid}
      onValueChange={switchWorkspaceAndReload}
    >
      <SelectTrigger
        size="sm"
        className={cn('min-w-44 max-w-64', className)}
        aria-label={t('workspace.switchWorkspace')}
      >
        <Building2 className="size-4 shrink-0" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent align="end">
        {workspaces.map((entry) => (
          <SelectItem key={entry.workspace.uuid} value={entry.workspace.uuid}>
            <span className="flex min-w-0 items-center gap-2">
              <span className="truncate">{entry.workspace.name}</span>
              <span className="text-xs text-muted-foreground">
                {t(`workspace.roles.${entry.membership.role}`)}
              </span>
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
