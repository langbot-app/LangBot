import { ExtensionCardVO, ExtensionType } from './ExtensionCardVO';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { useTranslation } from 'react-i18next';
import {
  BugIcon,
  ExternalLink,
  Ellipsis,
  Trash,
  ArrowUp,
  Server,
  Sparkles,
  Puzzle,
} from 'lucide-react';
import { getCloudServiceClientSync, systemInfo } from '@/app/infra/http';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

type ExtensionCardComponentProps = {
  cardVO: ExtensionCardVO;
  onCardClick: () => void;
  onDeleteClick: (cardVO: ExtensionCardVO) => void;
  onUpgradeClick?: (cardVO: ExtensionCardVO) => void;
};

export default function ExtensionCardComponent({
  cardVO,
  onCardClick,
  onDeleteClick,
  onUpgradeClick,
}: ExtensionCardComponentProps) {
  const { t } = useTranslation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [iconFailed, setIconFailed] = useState(false);

  const FallbackIcon =
    cardVO.type === 'mcp'
      ? Server
      : cardVO.type === 'skill'
        ? Sparkles
        : Puzzle;
  const iconSrc =
    cardVO.iconURL || httpClient.getPluginIconURL(cardVO.author, cardVO.name);
  const showFallback = iconFailed || !iconSrc;

  const getTypeLabel = (type: ExtensionType) => {
    switch (type) {
      case 'mcp':
        return 'MCP';
      case 'skill':
        return t('common.skill');
      default:
        return t('market.typePlugin');
    }
  };

  const getTypeIcon = (type: ExtensionType) => {
    switch (type) {
      case 'mcp':
        return Server;
      case 'skill':
        return Sparkles;
      default:
        return Puzzle;
    }
  };

  const renderTypeBadge = (type: ExtensionType) => {
    const TypeIcon = getTypeIcon(type);
    return (
      <Badge
        variant="outline"
        className="flex-shrink-0 gap-1.5 border-blue-200 bg-blue-50/60 text-[0.7rem] text-blue-700 dark:border-blue-500/40 dark:bg-blue-500/10 dark:text-blue-300"
      >
        <TypeIcon className="size-3.5" />
        {getTypeLabel(type)}
      </Badge>
    );
  };

  const renderPluginContent = () => (
    <>
      <div className="text-[0.7rem] text-muted-foreground truncate w-full">
        {cardVO.author} / {cardVO.name}
      </div>
      <div className="flex flex-row items-center justify-start gap-[0.4rem] flex-wrap max-w-full">
        <div className="text-[1.2rem] text-foreground truncate max-w-[10rem]">
          {cardVO.label}
        </div>
        <Badge variant="outline" className="text-[0.7rem] flex-shrink-0">
          v{cardVO.version}
        </Badge>
        {renderTypeBadge(cardVO.type)}
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
      <div className="text-[0.8rem] text-muted-foreground line-clamp-2 w-full">
        {cardVO.description}
      </div>
    </>
  );

  const renderMCPContent = () => (
    <>
      <div className="text-[0.7rem] text-muted-foreground truncate w-full">
        MCP Server
      </div>
      <div className="flex flex-row items-center justify-start gap-[0.4rem] flex-wrap max-w-full">
        <div className="text-[1.2rem] text-foreground truncate max-w-[10rem]">
          {cardVO.label}
        </div>
        {renderTypeBadge('mcp')}
        {cardVO.mode && (
          <Badge
            variant="outline"
            className="text-[0.7rem] border-gray-400 text-gray-600 dark:text-gray-300 flex-shrink-0"
          >
            {cardVO.mode.toUpperCase()}
          </Badge>
        )}
        {(() => {
          // Reflect the real runtime status, not just the enabled flag.
          // A server can be enabled but still CONNECTING or in ERROR — showing
          // "Connected" in those cases is misleading.
          const runtime = cardVO.enabled
            ? cardVO.runtimeStatus ?? 'connecting'
            : 'disabled';
          const badgeClass: Record<string, string> = {
            connected: 'border-green-400 text-green-600 dark:text-green-400',
            connecting: 'border-amber-400 text-amber-600 dark:text-amber-400',
            error: 'border-red-400 text-red-600 dark:text-red-400',
            disabled: 'border-gray-400 text-gray-600 dark:text-gray-300',
          };
          const badgeLabel: Record<string, string> = {
            connected: t('mcp.statusConnected'),
            connecting: t('mcp.connecting'),
            error: t('mcp.statusError'),
            disabled: t('mcp.statusDisabled'),
          };
          return (
            <Badge
              variant="outline"
              className={`text-[0.7rem] flex-shrink-0 ${badgeClass[runtime] ?? badgeClass.disabled}`}
            >
              {badgeLabel[runtime] ?? badgeLabel.disabled}
            </Badge>
          );
        })()}
      </div>
      <div className="text-[0.8rem] text-muted-foreground line-clamp-2 w-full">
        {cardVO.description ||
          (cardVO.tools !== undefined && cardVO.tools > 0
            ? t('mcp.toolCount', { count: cardVO.tools })
            : t('mcp.noToolsFound'))}
      </div>
    </>
  );

  const renderSkillContent = () => (
    <>
      <div className="text-[0.7rem] text-muted-foreground truncate w-full">
        Skill
      </div>
      <div className="flex flex-row items-center justify-start gap-[0.4rem] flex-wrap max-w-full">
        <div className="text-[1.2rem] text-foreground truncate max-w-[10rem]">
          {cardVO.label}
        </div>
        {renderTypeBadge('skill')}
      </div>
      <div className="text-[0.8rem] text-muted-foreground line-clamp-2 w-full">
        {cardVO.description}
      </div>
    </>
  );

  return (
    <>
      <Card
        className="w-full h-[10rem] py-5 px-5 cursor-pointer relative gap-0 shadow-xs transition-shadow duration-200 hover:shadow-md"
        onClick={() => onCardClick()}
      >
        <div className="w-full h-full flex flex-row items-start justify-start gap-[1.2rem]">
          {showFallback ? (
            <div className="w-16 h-16 flex-shrink-0 flex items-center justify-center">
              <FallbackIcon className="w-12 h-12 text-blue-500" />
            </div>
          ) : (
            <img
              src={iconSrc}
              alt="extension icon"
              className="w-16 h-16 rounded-[8%] flex-shrink-0"
              onError={() => setIconFailed(true)}
            />
          )}

          <div className="flex-1 min-w-0 h-full flex flex-col items-start justify-between gap-[0.6rem]">
            <div className="flex flex-col items-start justify-start w-full min-w-0 flex-1 overflow-hidden">
              {cardVO.type === 'plugin' && renderPluginContent()}
              {cardVO.type === 'mcp' && renderMCPContent()}
              {cardVO.type === 'skill' && renderSkillContent()}
            </div>
          </div>

          <div
            className="flex flex-col items-center justify-between h-full relative z-20 flex-shrink-0"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-center"></div>

            <div className="flex items-center justify-center">
              <DropdownMenu
                open={dropdownOpen}
                onOpenChange={(open) => {
                  setDropdownOpen(open);
                }}
              >
                <DropdownMenuTrigger asChild>
                  <div className="relative">
                    <Button variant="ghost" size="icon">
                      <Ellipsis className="w-4 h-4" />
                    </Button>
                    {cardVO.hasUpdate && (
                      <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-destructive rounded-full border-2 border-card"></div>
                    )}
                  </div>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  {cardVO.type === 'plugin' &&
                    cardVO.install_source === 'marketplace' && (
                      <DropdownMenuItem
                        className="flex flex-row items-center justify-start gap-[0.4rem] cursor-pointer"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onUpgradeClick) {
                            onUpgradeClick(cardVO);
                          }
                          setDropdownOpen(false);
                        }}
                      >
                        <ArrowUp className="w-4 h-4" />
                        <span>{t('plugins.update')}</span>
                        {cardVO.hasUpdate && (
                          <Badge className="ml-auto bg-red-500 hover:bg-red-500 text-white text-[0.6rem] px-1.5 py-0 h-4">
                            {t('plugins.new')}
                          </Badge>
                        )}
                      </DropdownMenuItem>
                    )}
                  {cardVO.type === 'plugin' &&
                    (cardVO.install_source === 'github' ||
                      cardVO.install_source === 'marketplace') && (
                      <DropdownMenuItem
                        className="flex flex-row items-center justify-start gap-[0.4rem] cursor-pointer"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (cardVO.install_source === 'github') {
                            window.open(
                              cardVO.install_info?.github_url as string,
                              '_blank',
                            );
                          } else if (cardVO.install_source === 'marketplace') {
                            window.open(
                              getCloudServiceClientSync().getPluginMarketplaceURL(
                                systemInfo.cloud_service_url,
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
                    <span>
                      {cardVO.type === 'mcp'
                        ? t('mcp.deleteServer')
                        : cardVO.type === 'skill'
                          ? t('skills.delete')
                          : t('plugins.delete')}
                    </span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}
