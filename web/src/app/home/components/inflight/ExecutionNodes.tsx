import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useSidebarData } from '../home-sidebar/SidebarDataContext';
import type { ExecutionRow } from '@/app/infra/entities/api/monitoring-executions';
import { executionProcessorLabel } from '../../monitoring/components/executions/ExecutionTable';
import DockIcon from './DockIcon';
import styles from './inflight.module.css';

export default function ExecutionNodes({
  row,
  processorUrl,
  running,
}: {
  row: ExecutionRow;
  processorUrl: string | null;
  running: boolean;
}) {
  const { t } = useTranslation();
  const { bots, pipelines } = useSidebarData();
  const bot = bots.find((item) => item.id === row.bot_id);
  const processor = pipelines.find((item) => item.id === row.target_id);
  const nodes = [
    {
      name: bot?.name || row.bot_name || t('inflight.debug'),
      iconURL: bot?.iconURL,
      emoji: bot?.emoji,
      kind: 'bot',
      url: row.bot_id
        ? `/home/bots?id=${encodeURIComponent(row.bot_id)}&tab=logs`
        : null,
    },
    {
      name: processor?.name || executionProcessorLabel(row),
      iconURL: processor?.iconURL,
      emoji: processor?.emoji,
      kind:
        row.target_kind === 'event_processor' ? 'processor' : row.target_kind,
      url: processorUrl,
    },
  ];
  const node = (index: number) => {
    const item = nodes[index];
    const content = (
      <>
        <Avatar className="size-5 shrink-0 rounded">
          {item.iconURL && (
            <AvatarImage src={item.iconURL} alt="" className="object-contain" />
          )}
          <AvatarFallback className="rounded bg-transparent text-base [&_svg]:size-4">
            {item.emoji || <DockIcon kind={item.kind} />}
          </AvatarFallback>
        </Avatar>
        <span className="truncate text-[11px]">{item.name}</span>
      </>
    );
    const className =
      'flex h-8 min-w-0 max-w-[125px] items-center gap-1.5 rounded-md bg-muted/40 px-1.5';
    return item.url ? (
      <Link
        to={item.url}
        title={`${index === 0 ? t('inflight.botLogs') : t('inflight.processorLogs')}: ${item.name}`}
        aria-label={`${index === 0 ? t('inflight.botLogs') : t('inflight.processorLogs')}: ${item.name}`}
        className={`${className} hover:bg-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`}
      >
        {content}
      </Link>
    ) : (
      <div className={className}>{content}</div>
    );
  };
  return (
    <div className="mt-1.5 flex items-center">
      {node(0)}
      <span
        className={`w-5 shrink-0 ${styles.connection} ${running ? styles.flowing : ''}`}
        aria-hidden="true"
      >
        <i />
      </span>
      {node(1)}
    </div>
  );
}
