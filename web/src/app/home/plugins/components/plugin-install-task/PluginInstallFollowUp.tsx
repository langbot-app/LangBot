import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowRight, Blocks, Bot, LibraryBig } from 'lucide-react';
import type { ReactNode } from 'react';
import type { Plugin } from '@/app/infra/entities/plugin';
import { FollowUpKind, followUpKindsForPlugin } from './plugin-follow-up';

/**
 * One row. Exported from this file rather than living in its own module: the
 * follow-up and the pending-review line in the dialog are the only two callers,
 * so a separate file earned nothing but an import.
 *
 * Bordered with the install banner's own green so it reads as a control rather
 * than as body text next to the message.
 */
export function NextStepLink({
  to,
  icon: Icon,
  label,
  onNavigate,
  children,
}: {
  to: string;
  icon: typeof Bot;
  label?: string;
  onNavigate?: () => void;
  children: ReactNode;
}) {
  return (
    <Link
      to={to}
      onClick={onNavigate}
      aria-label={label}
      className="flex items-center gap-2 rounded-md border border-green-300 bg-white/70 px-2 py-1.5 text-xs font-medium text-green-800 hover:border-green-500 hover:bg-white dark:border-green-800 dark:bg-green-950/40 dark:text-green-200 dark:hover:border-green-600 dark:hover:bg-green-950/70"
    >
      <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
      <span className="flex-1">{children}</span>
      <ArrowRight className="w-4 h-4 shrink-0" aria-hidden="true" />
    </Link>
  );
}

const FOLLOW_UP_PRESENTATION: Record<
  FollowUpKind,
  { to: string; icon: typeof Bot; i18nKey: string }
> = {
  agents: {
    to: '/home/agents?id=new',
    icon: Bot,
    i18nKey: 'plugins.installProgress.followUp.agents',
  },
  pipelines: {
    to: '/home/pipelines?id=new',
    icon: Blocks,
    i18nKey: 'plugins.installProgress.followUp.pipelines',
  },
  knowledge: {
    to: '/home/knowledge?id=new',
    icon: LibraryBig,
    i18nKey: 'plugins.installProgress.followUp.knowledge',
  },
};

/**
 * Post-install "what now" steps derived from the components the plugin ships.
 *
 * Each row links straight into the create form (`?id=new`) rather than the
 * plain list, so the step is one click instead of landing somewhere and
 * hunting for the button.
 *
 * Renders nothing when no component needs a follow-up (Parser/Page-only
 * plugins), so the success banner stays a single line for those.
 */
export default function PluginInstallFollowUp({
  plugin,
  onNavigate,
}: {
  plugin: Plugin | null;
  onNavigate?: () => void;
}) {
  const { t } = useTranslation();
  const kinds = followUpKindsForPlugin(plugin);

  if (kinds.length === 0) return null;

  return (
    <ul
      className="mt-1.5 space-y-1"
      aria-label={t('plugins.installProgress.followUp.nextSteps')}
    >
      {kinds.map((kind) => {
        const { to, icon: Icon, i18nKey } = FOLLOW_UP_PRESENTATION[kind];
        return (
          <li key={kind}>
            <NextStepLink to={to} icon={Icon} onNavigate={onNavigate}>
              {t(i18nKey)}
            </NextStepLink>
          </li>
        );
      })}
    </ul>
  );
}
