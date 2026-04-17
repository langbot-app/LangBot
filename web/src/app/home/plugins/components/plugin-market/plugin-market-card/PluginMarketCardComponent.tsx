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
  FileText,
  Github,
  Tag,
} from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';

export default function PluginMarketCardComponent({
  cardVO,
  onInstall,
  tagNames = {},
}: {
  cardVO: PluginMarketCardVO;
  onInstall?: (author: string, pluginName: string) => void;
  tagNames?: Record<string, string>;
}) {
  const { t } = useTranslation();
  const [isHovered, setIsHovered] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [visibleTags, setVisibleTags] = useState(2);

  // Measure how many tags fit in the bottom row
  useEffect(() => {
    const tags = cardVO.tags;
    if (!bottomRef.current || !tags || tags.length === 0) return;

    const measure = () => {
      const container = bottomRef.current;
      if (!container) return;
      const width = container.offsetWidth;
      const availableForTags = width - 140 - 80;
      if (availableForTags <= 0) {
        setVisibleTags(0);
        return;
      }
      const tagWidth = 80;
      const plusBadgeWidth = 40;
      const maxTags = Math.max(
        0,
        Math.floor((availableForTags - plusBadgeWidth) / tagWidth),
      );
      if (maxTags >= tags.length) {
        setVisibleTags(tags.length);
      } else {
        setVisibleTags(Math.max(1, maxTags));
      }
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(bottomRef.current);
    return () => observer.disconnect();
  }, [cardVO.tags]);

  const remainingTags = cardVO.tags ? cardVO.tags.length - visibleTags : 0;

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
    KnowledgeEngine: <Book className="w-4 h-4" />,
    Parser: <FileText className="w-4 h-4" />,
  };

  return (
    <div
      className="w-[100%] h-auto min-h-[8rem] sm:min-h-[9rem] bg-white rounded-[10px] border border-[#e4e4e7] dark:border-[#27272a] p-3 sm:p-[1rem] hover:border-[#a1a1aa] dark:hover:border-[#3f3f46] transition-all duration-200 dark:bg-[#1f1f22] relative"
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
              <div className="flex items-center gap-1.5 w-full min-w-0">
                <div className="text-base sm:text-[1.2rem] text-black dark:text-[#f0f0f0] truncate">
                  {cardVO.label}
                </div>
              </div>
            </div>

            <div className="text-[0.7rem] sm:text-[0.8rem] text-[#666] dark:text-[#999] line-clamp-2 overflow-hidden">
              {cardVO.description}
            </div>
          </div>

          <div className="flex flex-row items-start justify-center gap-[0.4rem] flex-shrink-0">
            {cardVO.githubURL && (
              <Github
                className="w-5 h-5 sm:w-[1.4rem] sm:h-[1.4rem] text-black cursor-pointer hover:text-gray-600 dark:text-[#f0f0f0] flex-shrink-0"
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(cardVO.githubURL, '_blank');
                }}
              />
            )}
          </div>
        </div>

        {/* 下部分：下载量、标签和组件列表 */}
        <div
          ref={bottomRef}
          className="w-full flex flex-row items-center justify-between gap-2 px-0 sm:px-[0.4rem] flex-shrink-0 overflow-hidden"
        >
          <div className="flex flex-row items-center justify-start gap-2 min-w-0 overflow-hidden">
            {/* 下载数量 */}
            <div className="flex flex-row items-center gap-[0.3rem] sm:gap-[0.4rem] flex-shrink-0">
              <Download className="w-4 h-4 sm:w-[1.2rem] sm:h-[1.2rem] text-[#2563eb] dark:text-[#5b8def] flex-shrink-0" />
              <div className="text-xs sm:text-sm text-[#2563eb] dark:text-[#5b8def] font-medium whitespace-nowrap">
                {cardVO.installCount?.toLocaleString() ?? '0'}
              </div>
            </div>

            {/* Tags - adaptive */}
            {cardVO.tags && cardVO.tags.length > 0 && visibleTags > 0 && (
              <div className="flex flex-row items-center gap-1.5 overflow-hidden flex-shrink min-w-0">
                {cardVO.tags.slice(0, visibleTags).map((tag) => (
                  <Badge
                    key={tag}
                    variant="secondary"
                    className="text-[0.65rem] sm:text-[0.7rem] px-2 py-0.5 h-5 flex items-center gap-1 flex-shrink-0 whitespace-nowrap"
                  >
                    <Tag className="w-2.5 h-2.5 flex-shrink-0" />
                    <span className="truncate max-w-[5rem]">
                      {tagNames[tag] || tag}
                    </span>
                  </Badge>
                ))}
                {remainingTags > 0 && (
                  <Badge
                    variant="outline"
                    className="text-[0.65rem] sm:text-[0.7rem] px-1.5 py-0.5 h-5 flex items-center flex-shrink-0 whitespace-nowrap"
                  >
                    +{remainingTags}
                  </Badge>
                )}
              </div>
            )}
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
