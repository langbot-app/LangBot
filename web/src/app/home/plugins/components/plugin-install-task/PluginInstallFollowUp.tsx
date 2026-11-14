import { useTranslation } from 'react-i18next';
import { Blocks, Bot, LibraryBig } from 'lucide-react';
import type { Plugin } from '@/app/infra/entities/plugin';
import { FollowUpKind, followUpKindsForPlugin } from './plugin-follow-up';
import PluginNextStepRow from './PluginNextStepRow';

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
    <div
      className="mt-1.5 space-y-1"
      role="group"
      aria-label={t('plugins.installProgress.followUp.nextSteps')}
    >
      <p className="text-xs font-medium text-green-700 dark:text-green-300">
        {t('plugins.installProgress.followUp.nextSteps')}
      </p>
      {kinds.map((kind) => {
        const { to, icon: Icon, i18nKey } = FOLLOW_UP_PRESENTATION[kind];
        return (
          <PluginNextStepRow
            key={kind}
            to={to}
            icon={Icon}
            text={t(i18nKey)}
            onNavigate={onNavigate}
          />
        );
      })}
    </div>
  );
}
