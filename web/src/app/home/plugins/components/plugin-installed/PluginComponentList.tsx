import { TFunction } from 'i18next';
import { Wrench, AudioWaveform, Hash, Book } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export default function PluginComponentList({
  components,
  showComponentName,
  showTitle,
  useBadge,
  t,
  responsive = false,
}: {
  components: Record<string, number>;
  showComponentName: boolean;
  showTitle: boolean;
  useBadge: boolean;
  t: TFunction;
  responsive?: boolean;
}) {
  const kindIconMap: Record<string, React.ReactNode> = {
    Tool: <Wrench className="w-5 h-5" />,
    EventListener: <AudioWaveform className="w-5 h-5" />,
    Command: <Hash className="w-5 h-5" />,
    RAGEngine: <Book className="w-5 h-5" />,
  };

  const componentKindList = Object.keys(components || {});

  return (
    <>
      {showTitle && <div>{t('plugins.componentsList')}</div>}
      {componentKindList.length > 0 && (
        <>
          {componentKindList.map((kind) => {
            return useBadge ? (
              <Badge
                key={kind}
                variant="outline"
                className="flex items-center gap-1"
              >
                {kindIconMap[kind]}
                {/* 响应式显示组件名称：在中等屏幕以上显示 */}
                {responsive ? (
                  <span className="hidden md:inline">
                    {t('plugins.componentName.' + kind)}
                  </span>
                ) : (
                  showComponentName && t('plugins.componentName.' + kind)
                )}
                <span className="ml-1">{components[kind]}</span>
              </Badge>
            ) : (
              <div
                key={kind}
                className="flex flex-row items-center justify-start gap-[0.2rem]"
              >
                {kindIconMap[kind]}
                {/* 响应式显示组件名称：在中等屏幕以上显示 */}
                {responsive ? (
                  <span className="hidden md:inline">
                    {t('plugins.componentName.' + kind)}
                  </span>
                ) : (
                  showComponentName && t('plugins.componentName.' + kind)
                )}
                <span className="ml-1">{components[kind]}</span>
              </div>
            );
          })}
        </>
      )}

      {componentKindList.length === 0 && <div>{t('plugins.noComponents')}</div>}
    </>
  );
}
