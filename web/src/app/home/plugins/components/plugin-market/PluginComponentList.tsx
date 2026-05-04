import { Fragment } from 'react';
import { TFunction } from 'i18next';
import { Wrench, AudioWaveform, Hash, Book, FileText } from 'lucide-react';
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
    KnowledgeEngine: <Book className="w-5 h-5" />,
    Parser: <FileText className="w-5 h-5" />,
  };

  const componentKindList = Object.keys(components || {});

  return (
    <>
      {showTitle && <div>{t('market.componentsList')}</div>}
      {componentKindList.length > 0 && (
        <>
          {componentKindList.map((kind) => {
            return (
              <Fragment key={kind}>
                {useBadge && (
                  <Badge variant="outline" className="flex items-center gap-1">
                    {kindIconMap[kind]}
                    {responsive ? (
                      <span className="hidden md:inline">
                        {t('market.componentName.' + kind)}
                      </span>
                    ) : (
                      showComponentName && t('market.componentName.' + kind)
                    )}
                    <span className="ml-1">{components[kind]}</span>
                  </Badge>
                )}

                {!useBadge && (
                  <div
                    className="flex flex-row items-center justify-start gap-[0.2rem]"
                  >
                    {kindIconMap[kind]}
                    {responsive ? (
                      <span className="hidden md:inline">
                        {t('market.componentName.' + kind)}
                      </span>
                    ) : (
                      showComponentName && t('market.componentName.' + kind)
                    )}
                    <span className="ml-1">{components[kind]}</span>
                  </div>
                )}
              </Fragment>
            );
          })}
        </>
      )}

      {componentKindList.length === 0 && <div>{t('market.noComponents')}</div>}
    </>
  );
}