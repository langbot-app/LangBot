import { PluginCardVO } from '@/app/home/plugins/components/plugin-installed/PluginCardVO';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { useTranslation } from 'react-i18next';
import {
  BugIcon,
  ExternalLink,
  Ellipsis,
  Trash,
  ArrowUp,
  Settings,
  FileText,
} from 'lucide-react';
import { getCloudServiceClientSync } from '@/app/infra/http';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import PluginComponentList from '@/app/home/plugins/components/plugin-installed/PluginComponentList';

export default function PluginCardComponent({
  cardVO,
  onCardClick,
  onDeleteClick,
  onUpgradeClick,
  onViewReadme,
}: {
  cardVO: PluginCardVO;
  onCardClick: () => void;
  onDeleteClick: (cardVO: PluginCardVO) => void;
  onUpgradeClick: (cardVO: PluginCardVO) => void;
  onViewReadme: (cardVO: PluginCardVO) => void;
}) {
  const { t } = useTranslation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  return (
    <>
      <div
        className="w-[100%] h-[10rem] bg-white rounded-[10px] shadow-[0px_2px_2px_0_rgba(0,0,0,0.2)] p-[1.2rem] cursor-pointer dark:bg-[#1f1f22] relative transition-all duration-200 hover:shadow-[0px_3px_6px_0_rgba(0,0,0,0.12)] hover:scale-[1.005]"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => {
          if (!dropdownOpen) {
            setIsHovered(false);
          }
        }}
      >
        <div className="w-full h-full flex flex-row items-start justify-start gap-[1.2rem]">
          {/* Icon - fixed width */}
          <img
            src={httpClient.getPluginIconURL(cardVO.author, cardVO.name)}
            alt="plugin icon"
            className="w-16 h-16 rounded-[8%] flex-shrink-0"
          />

          {/* Content area - flexible width with min-width to prevent overflow */}
          <div className="flex-1 min-w-0 h-full flex flex-col items-start justify-between gap-[0.6rem]">
            {/* Top content area - allows overflow with max height */}
            <div className="flex flex-col items-start justify-start w-full min-w-0 flex-1 overflow-hidden">
              <div className="flex flex-col items-start justify-start w-full min-w-0">
                <div className="text-[0.7rem] text-[#666] dark:text-[#999] truncate w-full">
                  {cardVO.author} / {cardVO.name}
                </div>
                <div className="flex flex-row items-center justify-start gap-[0.4rem] flex-wrap max-w-full">
                  <div className="text-[1.2rem] text-black dark:text-[#f0f0f0] truncate max-w-[10rem]">
                    {cardVO.label}
                  </div>
                  <Badge
                    variant="outline"
                    className="text-[0.7rem] flex-shrink-0"
                  >
                    v{cardVO.version}
                  </Badge>
                  {cardVO.debug && (
                    <Badge
                      variant="outline"
                      className="text-[0.7rem] border-orange-400 text-orange-400 flex-shrink-0"
                    >
                      <BugIcon className="w-4 h-4" />
                      {t('plugins.debugging')}
                    </Badge>
                  )}
                  {!cardVO.debug && (
                    <>
                      {cardVO.install_source === 'github' && (
                        <Badge
                          variant="outline"
                          className="text-[0.7rem] border-blue-400 text-blue-400 flex-shrink-0"
                        >
                          {t('plugins.fromGithub')}
                        </Badge>
                      )}
                      {cardVO.install_source === 'local' && (
                        <Badge
                          variant="outline"
                          className="text-[0.7rem] border-green-400 text-green-400 flex-shrink-0"
                        >
                          {t('plugins.fromLocal')}
                        </Badge>
                      )}
                      {cardVO.install_source === 'marketplace' && (
                        <Badge
                          variant="outline"
                          className="text-[0.7rem] border-purple-400 text-purple-400 flex-shrink-0"
                        >
                          {t('plugins.fromMarketplace')}
                        </Badge>
                      )}
                    </>
                  )}
                </div>
              </div>

              <div className="text-[0.8rem] text-[#666] line-clamp-2 dark:text-[#999] w-full">
                {cardVO.description}
              </div>
            </div>

            {/* Components list - fixed at bottom */}
            <div className="w-full flex flex-row items-start justify-start gap-[0.6rem] flex-shrink-0 min-h-[1.5rem]">
              <PluginComponentList
                components={(() => {
                  const componentKindCount: Record<string, number> = {};
                  for (const component of cardVO.components) {
                    const kind = component.manifest.manifest.kind;
                    if (componentKindCount[kind]) {
                      componentKindCount[kind]++;
                    } else {
                      componentKindCount[kind] = 1;
                    }
                  }
                  return componentKindCount;
                })()}
                showComponentName={false}
                showTitle={true}
                useBadge={false}
                t={t}
              />
            </div>
          </div>

          {/* Menu button - fixed width and position */}
          <div className="flex flex-col items-center justify-between h-full relative z-20 flex-shrink-0">
            <div className="flex items-center justify-center"></div>

            <div className="flex items-center justify-center">
              <DropdownMenu
                open={dropdownOpen}
                onOpenChange={(open) => {
                  setDropdownOpen(open);
                  if (!open) {
                    setIsHovered(false);
                  }
                }}
              >
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    className="bg-white dark:bg-[#1f1f22] hover:bg-gray-100 dark:hover:bg-[#2a2a2d]"
                  >
                    <Ellipsis className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  {/**upgrade */}
                  {cardVO.install_source === 'marketplace' && (
                    <DropdownMenuItem
                      className="flex flex-row items-center justify-start gap-[0.4rem] cursor-pointer"
                      onClick={(e) => {
                        e.stopPropagation();
                        onUpgradeClick(cardVO);
                        setDropdownOpen(false);
                      }}
                    >
                      <ArrowUp className="w-4 h-4" />
                      <span>{t('plugins.update')}</span>
                    </DropdownMenuItem>
                  )}
                  {/**view source */}
                  {(cardVO.install_source === 'github' ||
                    cardVO.install_source === 'marketplace') && (
                    <DropdownMenuItem
                      className="flex flex-row items-center justify-start gap-[0.4rem] cursor-pointer"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (cardVO.install_source === 'github') {
                          window.open(
                            cardVO.install_info.github_url,
                            '_blank',
                          );
                        } else if (cardVO.install_source === 'marketplace') {
                          window.open(
                            getCloudServiceClientSync().getPluginMarketplaceURL(
                              cardVO.author,
                              cardVO.name,
                            ),
                            '_blank',
                          );
                        }
                        setDropdownOpen(false);
                      }}
                    >
                      <ExternalLink className="w-4 h-4" />
                      <span>{t('plugins.viewSource')}</span>
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem
                    className="flex flex-row items-center justify-start gap-[0.4rem] cursor-pointer text-red-600 focus:text-red-600"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteClick(cardVO);
                      setDropdownOpen(false);
                    }}
                  >
                    <Trash className="w-4 h-4" />
                    <span>{t('plugins.delete')}</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>

        {/* Hover overlay with action buttons */}
        <div
          className={`absolute inset-0 bg-gray-100/55 dark:bg-black/35 rounded-[10px] flex items-center justify-center gap-3 transition-all duration-200 z-10 ${
            isHovered ? 'opacity-100' : 'opacity-0 pointer-events-none'
          }`}
        >
          <Button
            onClick={(e) => {
              e.stopPropagation();
              onViewReadme(cardVO);
            }}
            className={`bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg shadow-sm flex items-center gap-2 transition-all duration-200 ${
              isHovered
                ? 'translate-y-0 opacity-100'
                : 'translate-y-1 opacity-0'
            }`}
            style={{ transitionDelay: isHovered ? '10ms' : '0ms' }}
          >
            <FileText className="w-4 h-4" />
            {t('plugins.readme')}
          </Button>
          <Button
            onClick={(e) => {
              e.stopPropagation();
              onCardClick();
            }}
            variant="outline"
            className={`bg-white hover:bg-gray-100 text-gray-900 dark:bg-white dark:hover:bg-gray-100 dark:text-gray-900 px-4 py-2 rounded-lg shadow-sm flex items-center gap-2 transition-all duration-200 ${
              isHovered
                ? 'translate-y-0 opacity-100'
                : 'translate-y-1 opacity-0'
            }`}
            style={{ transitionDelay: isHovered ? '20ms' : '0ms' }}
          >
            <Settings className="w-4 h-4" />
            {t('plugins.config')}
          </Button>
        </div>
      </div>
    </>
  );
}
