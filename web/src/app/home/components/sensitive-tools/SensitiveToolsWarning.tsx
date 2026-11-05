import { ShieldAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type {
  AgentPlatformTool,
  WorkspaceOperationItem,
} from '@/app/infra/entities/api';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

/** Labels of the selected tools and operations marked as dangerous. */
export function collectSensitiveTools(
  platformTools: AgentPlatformTool[],
  selectedPlatformTools: string[],
  workspaceOperations: WorkspaceOperationItem[],
  selectedWorkspaceOperations: string[],
): string[] {
  const platform = new Set(selectedPlatformTools);
  const operations = new Set(selectedWorkspaceOperations);
  return [
    ...platformTools
      .filter((tool) => tool.risk === 'dangerous' && platform.has(tool.name))
      .map((tool) => extractI18nObject(tool.label) || tool.name),
    ...workspaceOperations
      .filter((op) => op.risk === 'dangerous' && operations.has(op.id))
      .map(
        (op) =>
          extractI18nObject(
            op.label as unknown as Parameters<typeof extractI18nObject>[0],
          ) || op.id,
      ),
  ];
}

const PREVIEW_LIMIT = 6;

/**
 * Header badge warning that a processor can perform sensitive or high-risk
 * actions on behalf of anyone who can talk to its bound bots.
 */
export default function SensitiveToolsWarning({
  tools,
  settingsPage,
}: {
  tools: string[];
  /** Name of the page where these tools can be turned off. */
  settingsPage: string;
}) {
  const { t } = useTranslation();
  if (tools.length === 0) return null;
  const preview = tools
    .slice(0, PREVIEW_LIMIT)
    .join(t('sensitiveTools.listSeparator'));
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge
          variant="outline"
          role="status"
          tabIndex={0}
          className="shrink-0 gap-1 rounded-full border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
        >
          <ShieldAlert className="size-3" />
          {t('sensitiveTools.badge', { count: tools.length })}
        </Badge>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-80">
        <p className="font-medium">{t('sensitiveTools.title')}</p>
        <p className="mt-1 font-normal opacity-80">
          {t('sensitiveTools.description', { page: settingsPage })}
        </p>
        <p className="mt-1.5 font-normal opacity-80">
          {tools.length > PREVIEW_LIMIT
            ? t('sensitiveTools.listMore', {
                items: preview,
                count: tools.length,
              })
            : t('sensitiveTools.list', { items: preview })}
        </p>
      </TooltipContent>
    </Tooltip>
  );
}
