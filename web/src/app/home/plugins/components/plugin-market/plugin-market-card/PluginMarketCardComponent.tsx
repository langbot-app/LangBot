import { PluginMarketCardVO } from './PluginMarketCardVO';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import {
  Wrench,
  AudioWaveform,
  Hash,
  Download,
  ExternalLink,
  Book,
} from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';

export default function PluginMarketCardComponent({
  cardVO,
  onInstall,
}: {
  cardVO: PluginMarketCardVO;
  onInstall?: (author: string, pluginName: string) => void;
}) {
  const { t } = useTranslation();
  const [isHovered, setIsHovered] = useState(false);

  function handleInstallClick(e: React.MouseEvent) {
    e.stopPropagation();
    if (onInstall) {
      onInstall(cardVO.author, cardVO.pluginName);
    }
  }

  function handleViewDetailsClick(e: React.MouseEvent) {
    e.stopPropagation();
    const detailUrl = `https://space.langbot.app/market/${cardVO.author}/${cardVO.pluginName}`;
    window.open(detailUrl, '_blank');
  }

  const kindIconMap: Record<string, React.ReactNode> = {
    Tool: <Wrench className="w-4 h-4" />,
    EventListener: <AudioWaveform className="w-4 h-4" />,
    Command: <Hash className="w-4 h-4" />,
    KnowledgeRetriever: <Book className="w-4 h-4" />,
  };

  const componentKindNameMap: Record<string, string> = {
    Tool: t('plugins.componentName.Tool'),
    EventListener: t('plugins.componentName.EventListener'),
    Command: t('plugins.componentName.Command'),
    KnowledgeRetriever: t('plugins.componentName.KnowledgeRetriever'),
  };

  return (
    <div
      className="w-[100%] h-auto min-h-[8rem] sm:min-h-[9rem] bg-white rounded-[10px] shadow-[0px_0px_4px_0_rgba(0,0,0,0.2)] p-3 sm:p-[1rem] hover:shadow-[0px_3px_6px_0_rgba(0,0,0,0.12)] transition-all duration-200 hover:scale-[1.005] dark:bg-[#1f1f22] relative"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="w-full h-full flex flex-col justify-between gap-3">
        {/* 上部分：插件信息 */}
        <div className="flex flex-row items-start justify-start gap-2 sm:gap-[1.2rem] min-h-0">
          <img
            src={cardVO.iconURL}
            alt="plugin icon"
            className="w-12 h-12 sm:w-16 sm:h-16 flex-shrink-0 rounded-[8%]"
          />

          <div className="flex-1 flex flex-col items-start justify-start gap-[0.4rem] sm:gap-[0.6rem] min-w-0 overflow-hidden">
            <div className="flex flex-col items-start justify-start w-full min-w-0">
              <div className="text-[0.65rem] sm:text-[0.7rem] text-[#666] dark:text-[#999] truncate w-full">
                {cardVO.pluginId}
              </div>
              <div className="text-base sm:text-[1.2rem] text-black dark:text-[#f0f0f0] truncate w-full">
                {cardVO.label}
              </div>
            </div>

            <div className="text-[0.7rem] sm:text-[0.8rem] text-[#666] dark:text-[#999] line-clamp-2 overflow-hidden">
              {cardVO.description}
            </div>
          </div>

          <div className="flex flex-row items-start justify-center gap-[0.4rem] flex-shrink-0">
            {cardVO.githubURL && (
              <svg
                className="w-5 h-5 sm:w-[1.4rem] sm:h-[1.4rem] text-black cursor-pointer hover:text-gray-600 dark:text-[#f0f0f0] flex-shrink-0"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(cardVO.githubURL, '_blank');
                }}
              >
                <path d="M12.001 2C6.47598 2 2.00098 6.475 2.00098 12C2.00098 16.425 4.86348 20.1625 8.83848 21.4875C9.33848 21.575 9.52598 21.275 9.52598 21.0125C9.52598 20.775 9.51348 19.9875 9.51348 19.15C7.00098 19.6125 6.35098 18.5375 6.15098 17.975C6.03848 17.6875 5.55098 16.8 5.12598 16.5625C4.77598 16.375 4.27598 15.9125 5.11348 15.9C5.90098 15.8875 6.46348 16.625 6.65098 16.925C7.55098 18.4375 8.98848 18.0125 9.56348 17.75C9.65098 17.1 9.91348 16.6625 10.201 16.4125C7.97598 16.1625 5.65098 15.3 5.65098 11.475C5.65098 10.3875 6.03848 9.4875 6.67598 8.7875C6.57598 8.5375 6.22598 7.5125 6.77598 6.1375C6.77598 6.1375 7.61348 5.875 9.52598 7.1625C10.326 6.9375 11.176 6.825 12.026 6.825C12.876 6.825 13.726 6.9375 14.526 7.1625C16.4385 5.8625 17.276 6.1375 17.276 6.1375C17.826 7.5125 17.476 8.5375 17.376 8.7875C18.0135 9.4875 18.401 10.375 18.401 11.475C18.401 15.3125 16.0635 16.1625 13.8385 16.4125C14.201 16.725 14.5135 17.325 14.5135 18.2625C14.5135 19.6 14.501 20.675 14.501 21.0125C14.501 21.275 14.6885 21.5875 15.1885 21.4875C19.259 20.1133 21.9999 16.2963 22.001 12C22.001 6.475 17.526 2 12.001 2Z"></path>
              </svg>
            )}
          </div>
        </div>

        {/* 下部分：下载量和组件列表 */}
        <div className="w-full flex flex-row items-center justify-between gap-[0.3rem] sm:gap-[0.4rem] px-0 sm:px-[0.4rem] flex-shrink-0">
          <div className="flex flex-row items-center justify-start gap-[0.3rem] sm:gap-[0.4rem]">
            <svg
              className="w-4 h-4 sm:w-[1.2rem] sm:h-[1.2rem] text-[#2563eb] flex-shrink-0"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7,10 12,15 17,10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            <div className="text-xs sm:text-sm text-[#2563eb] font-medium whitespace-nowrap">
              {cardVO.installCount.toLocaleString()}
            </div>
          </div>

          {/* 组件列表 */}
          {cardVO.components && Object.keys(cardVO.components).length > 0 && (
            <div className="flex flex-row items-center gap-1">
              {Object.entries(cardVO.components).map(([kind, count]) => (
                <Badge
                  key={kind}
                  variant="outline"
                  className="flex items-center gap-1"
                >
                  {kindIconMap[kind]}
                  {/* 响应式显示组件名称：在中等屏幕以上显示 */}
                  <span className="hidden md:inline">
                    {componentKindNameMap[kind]}
                  </span>
                  <span className="ml-1">{count}</span>
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Hover overlay with action buttons */}
      <div
        className={`absolute inset-0 bg-gray-100/55 dark:bg-black/35 rounded-[10px] flex items-center justify-center gap-3 transition-all duration-200 ${
          isHovered ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      >
        <Button
          onClick={handleInstallClick}
          className={`bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg shadow-sm flex items-center gap-2 transition-all duration-200 ${
            isHovered ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'
          }`}
          style={{ transitionDelay: isHovered ? '10ms' : '0ms' }}
        >
          <Download className="w-4 h-4" />
          {t('market.install')}
        </Button>
        <Button
          onClick={handleViewDetailsClick}
          variant="outline"
          className={`bg-white hover:bg-gray-100 text-gray-900 dark:bg-white dark:hover:bg-gray-100 dark:text-gray-900 px-4 py-2 rounded-lg shadow-sm flex items-center gap-2 transition-all duration-200 ${
            isHovered ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'
          }`}
          style={{ transitionDelay: isHovered ? '20ms' : '0ms' }}
        >
          <ExternalLink className="w-4 h-4" />
          {t('market.viewDetails')}
        </Button>
      </div>
    </div>
  );
}
