import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowRight, Blocks, Bot, LibraryBig } from 'lucide-react';
import type { ReactNode } from 'react';
import type { Plugin } from '@/app/infra/entities/plugin';
import { cn } from '@/lib/utils';
import { FollowUpKind, followUpKindsForPlugin } from './plugin-follow-up';

export type NextStepTone = 'success' | 'attention';

/**
 * Colours for the result banner and its rows. `attention` is the same amber
 * as the "permission confirmation required" section on the extensions page, so
 * a pending review looks identical wherever it shows up.
 */
const TONE: Record<
  NextStepTone,
  { banner: string; title: string; icon: string; list: string; row: string }
> = {
  success: {
    banner:
      'border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/30',
    title: 'text-green-700 dark:text-green-300',
    icon: 'text-green-600 dark:text-green-400',
    list: 'divide-green-200 border-green-200 dark:divide-green-900 dark:border-green-900',
    row: 'text-green-800 hover:bg-green-100/80 focus-visible:ring-green-500 dark:text-green-200 dark:hover:bg-green-900/30',
  },
  attention: {
    banner: 'border-amber-500/50 bg-amber-500/5',
    title: 'text-amber-800 dark:text-amber-300',
    icon: 'text-amber-600',
    list: 'divide-amber-500/20 border-amber-500/20',
    row: 'text-amber-800 hover:bg-amber-500/10 focus-visible:ring-amber-500 dark:text-amber-300',
  },
};

/**
 * Result banner: a status line, then its actions as rows under a divider.
 * Same shape as the pending-permissions section on the extensions page.
 */
export function NextStepBanner({
  tone,
  icon: Icon,
  title,
  children,
}: {
  tone: NextStepTone;
  icon: typeof Bot;
  title: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className={cn('overflow-hidden rounded-lg border', TONE[tone].banner)}>
      <div className="flex items-center gap-2 px-3 py-2.5">
        <Icon
          className={cn('size-5 shrink-0', TONE[tone].icon)}
          aria-hidden="true"
        />
        <span
          className={cn(
            'flex-1 break-words text-sm font-medium',
            TONE[tone].title,
          )}
        >
          {title}
        </span>
      </div>
      {children}
    </div>
  );
}

/**
 * Divided list of rows for the bottom of a {@link NextStepBanner}.
 */
export function NextStepList({
  tone,
  label,
  children,
}: {
  tone: NextStepTone;
  label?: string;
  children: ReactNode;
}) {
  return (
    <ul className={cn('divide-y border-t', TONE[tone].list)} aria-label={label}>
      {children}
    </ul>
  );
}

/**
 * One full-width row: the whole line is the hit target, the trailing arrow
 * marks it as navigation.
 */
export function NextStepLink({
  to,
  icon: Icon,
  tone = 'success',
  label,
  onNavigate,
  children,
}: {
  to: string;
  icon: typeof Bot;
  tone?: NextStepTone;
  label?: string;
  onNavigate?: () => void;
  children: ReactNode;
}) {
  return (
    <li>
      <Link
        to={to}
        onClick={onNavigate}
        aria-label={label}
        className={cn(
          'group flex min-h-9 items-center gap-2.5 px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-inset',
          TONE[tone].row,
        )}
      >
        <Icon className="size-4 shrink-0 opacity-80" aria-hidden="true" />
        <span className="flex-1 break-words">{children}</span>
        <ArrowRight
          className="size-4 shrink-0 opacity-60 transition-transform group-hover:translate-x-0.5 group-hover:opacity-100 motion-reduce:transition-none"
          aria-hidden="true"
        />
      </Link>
    </li>
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
    <NextStepList
      tone="success"
      label={t('plugins.installProgress.followUp.nextSteps')}
    >
      {kinds.map((kind) => {
        const { to, icon: Icon, i18nKey } = FOLLOW_UP_PRESENTATION[kind];
        return (
          <NextStepLink key={kind} to={to} icon={Icon} onNavigate={onNavigate}>
            {t(i18nKey)}
          </NextStepLink>
        );
      })}
    </NextStepList>
  );
}
