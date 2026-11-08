import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowRight, Blocks, Bot, LibraryBig } from 'lucide-react';
import type { Plugin } from '@/app/infra/entities/plugin';
import { FollowUpKind, followUpKindsForPlugin } from './plugin-follow-up';

const FOLLOW_UP_PRESENTATION: Record<
  FollowUpKind,
  { to: string; icon: typeof Bot; i18nKey: string }
> = {
  agents: {
    to: '/home/agents',
    icon: Bot,
    i18nKey: 'plugins.installProgress.followUp.agents',
  },
  pipelines: {
    to: '/home/pipelines',
    icon: Blocks,
    i18nKey: 'plugins.installProgress.followUp.pipelines',
  },
  knowledge: {
    to: '/home/knowledge',
    icon: LibraryBig,
    i18nKey: 'plugins.installProgress.followUp.knowledge',
  },
};

/**
 * Post-install "what now" steps derived from the components the plugin ships.
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
    <div className="mt-1.5 space-y-1">
      {kinds.map((kind) => {
        const { to, icon: Icon, i18nKey } = FOLLOW_UP_PRESENTATION[kind];
        return (
          <Link
            key={kind}
            to={to}
            onClick={onNavigate}
            className="flex items-center gap-1.5 text-xs text-green-700 hover:underline dark:text-green-300"
          >
            <Icon className="w-3.5 h-3.5 shrink-0" />
            <span className="flex-1">{t(i18nKey)}</span>
            <ArrowRight className="w-3.5 h-3.5 shrink-0" />
          </Link>
        );
      })}
    </div>
  );
}
