import { ExtensionCardVO, ExtensionType } from './ExtensionCardVO';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { useTranslation } from 'react-i18next';
import { BugIcon, ExternalLink, Ellipsis, Trash, ArrowUp } from 'lucide-react';
import { getCloudServiceClientSync, systemInfo } from '@/app/infra/http';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  MCPSessionStatus,
} from '@/app/infra/entities/api';

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

  const getTypeBadgeColor = (type: ExtensionType) => {
    switch (type) {
      case 'mcp':
        return 'border-sky-500 text-sky-600 dark:border-sky-400 dark:text-sky-300';
      case 'skill':
        return 'border-emerald-500 text-emerald-600 dark:border-emerald-400 dark:text-emerald-300';
      default:
        return 'border-violet-500 text-violet-600 dark:border-violet-400 dark:text-violet-300';
    }
  };

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

  const getStatusColor = (status?: string) => {
    switch (status) {
      case MCPSessionStatus.CONNECTED:
        return 'text-green-600';
      case MCPSessionStatus.CONNECTING:
        return 'text-yellow-600';
      case MCPSessionStatus.ERROR:
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const renderPluginContent = () => (
    <>
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
        <Badge
          variant="outline"
          className={`text-[0.7rem] flex-shrink-0 ${getTypeBadgeColor(cardVO.type)}`}
        >
          {getTypeLabel(cardVO.type)}
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
      <div className="text-[0.8rem] text-[#666] line-clamp-2 dark:text-[#999] w-full">
        {cardVO.description}
      </div>
    </>
  );

  const renderMCPContent = () => (
    <>
      <div className="text-[0.7rem] text-[#666] dark:text-[#999] truncate w-full">
        MCP Server
      </div>
      <div className="flex flex-row items-center justify-start gap-[0.4rem] flex-wrap max-w-full">
        <div className="text-[1.2rem] text-black dark:text-[#f0f0f0] truncate max-w-[10rem]">
          {cardVO.label}
        </div>
        <Badge
          variant="outline"
          className={`text-[0.7rem] flex-shrink-0 ${getTypeBadgeColor('mcp')}`}
        >
          MCP
        </Badge>
        {cardVO.mode && (
          <Badge
            variant="outline"
            className="text-[0.7rem] border-gray-400 text-gray-600 dark:text-gray-300 flex-shrink-0"
          >
            {cardVO.mode.toUpperCase()}
          </Badge>
        )}
        <Badge
          variant="outline"
          className={`text-[0.7rem] flex-shrink-0 ${
            cardVO.enabled
              ? 'border-green-400 text-green-600 dark:text-green-400'
              : 'border-gray-400 text-gray-600 dark:text-gray-300'
          }`}
        >
          {cardVO.enabled ? t('mcp.statusConnected') : t('mcp.statusDisabled')}
        </Badge>
      </div>
      <div className="text-[0.8rem] text-[#666] line-clamp-2 dark:text-[#999] w-full">
        {cardVO.description || t('mcp.noToolsFound')}
        {cardVO.tools !== undefined && cardVO.tools > 0 && (
          <span className="ml-1">{t('mcp.toolCount', { count: cardVO.tools })}</span>
        )}
      </div>
    </>
  );

  const renderSkillContent = () => (
    <>
      <div className="text-[0.7rem] text-[#666] dark:text-[#999] truncate w-full">
        Skill
      </div>
      <div className="flex flex-row items-center justify-start gap-[0.4rem] flex-wrap max-w-full">
        <div className="text-[1.2rem] text-black dark:text-[#f0f0f0] truncate max-w-[10rem]">
          {cardVO.label}
        </div>
        <Badge
          variant="outline"
          className={`text-[0.7rem] flex-shrink-0 ${getTypeBadgeColor('skill')}`}
        >
          {t('common.skill')}
        </Badge>
      </div>
      <div className="text-[0.8rem] text-[#666] line-clamp-2 dark:text-[#999] w-full">
        {cardVO.description}
      </div>
    </>
  );

  return (
    <>
      <div
        className="w-[100%] h-[10rem] bg-white rounded-[10px] border border-[#e4e4e7] dark:border-[#27272a] p-[1.2rem] cursor-pointer dark:bg-[#1f1f22] relative transition-all duration-200 hover:border-[#a1a1aa] dark:hover:border-[#3f3f46]"
        onClick={() => onCardClick()}
      >
        <div className="w-full h-full flex flex-row items-start justify-start gap-[1.2rem]">
          <img
            src={cardVO.iconURL || httpClient.getPluginIconURL(cardVO.author, cardVO.name)}
            alt="extension icon"
            className="w-16 h-16 rounded-[8%] flex-shrink-0"
          />

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
                    <Button
                      variant="ghost"
                      className="bg-white dark:bg-[#1f1f22] hover:bg-gray-100 dark:hover:bg-[#2a2a2d]"
                    >
                      <Ellipsis className="w-4 h-4" />
                    </Button>
                    {cardVO.hasUpdate && (
                      <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-white dark:border-[#1f1f22]"></div>
                    )}
                  </div>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  {cardVO.type === 'plugin' && cardVO.install_source === 'marketplace' && (
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
                  {cardVO.type === 'plugin' && (cardVO.install_source === 'github' || cardVO.install_source === 'marketplace') && (
                    <DropdownMenuItem
                      className="flex flex-row items-center justify-start gap-[0.4rem] cursor-pointer"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (cardVO.install_source === 'github') {
                          window.open(cardVO.install_info?.github_url as string, '_blank');
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
      </div>
    </>
  );
}