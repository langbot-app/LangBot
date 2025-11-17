'use client';

import { useState, useEffect, useCallback, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Search, Loader2 } from 'lucide-react';
import PluginMarketCardComponent from './plugin-market-card/PluginMarketCardComponent';
import { PluginMarketCardVO } from './plugin-market-card/PluginMarketCardVO';
import PluginDetailDialog from './plugin-detail-dialog/PluginDetailDialog';
import { getCloudServiceClientSync } from '@/app/infra/http';
import { useTranslation } from 'react-i18next';
import { PluginV4 } from '@/app/infra/entities/plugin';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { toast } from 'sonner';
import { ApiRespMarketplacePlugins } from '@/app/infra/entities/api';

interface SortOption {
  value: string;
  label: string;
  sortBy: string;
  sortOrder: string;
}

// 内部组件，用于处理搜索参数
function MarketPageContent({
  installPlugin,
}: {
  installPlugin: (plugin: PluginV4) => void;
}) {
  const { t } = useTranslation();
  const searchParams = useSearchParams();

  const [searchQuery, setSearchQuery] = useState('');
  const [plugins, setPlugins] = useState<PluginMarketCardVO[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [sortOption, setSortOption] = useState('install_count_desc');

  // Plugin detail dialog state
  const [selectedPluginAuthor, setSelectedPluginAuthor] = useState<
    string | null
  >(null);
  const [selectedPluginName, setSelectedPluginName] = useState<string | null>(
    null,
  );
  const [dialogOpen, setDialogOpen] = useState(false);

  const pageSize = 16; // 每页16个，4行x4列
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  // 排序选项
  const sortOptions: SortOption[] = [
    {
      value: 'created_at_desc',
      label: t('market.sort.recentlyAdded'),
      sortBy: 'created_at',
      sortOrder: 'DESC',
    },
    {
      value: 'updated_at_desc',
      label: t('market.sort.recentlyUpdated'),
      sortBy: 'updated_at',
      sortOrder: 'DESC',
    },
    {
      value: 'install_count_desc',
      label: t('market.sort.mostDownloads'),
      sortBy: 'install_count',
      sortOrder: 'DESC',
    },
    {
      value: 'install_count_asc',
      label: t('market.sort.leastDownloads'),
      sortBy: 'install_count',
      sortOrder: 'ASC',
    },
  ];

  // 获取当前排序参数
  const getCurrentSort = useCallback(() => {
    const option = sortOptions.find((opt) => opt.value === sortOption);
    return option
      ? { sortBy: option.sortBy, sortOrder: option.sortOrder }
      : { sortBy: 'install_count', sortOrder: 'DESC' };
  }, [sortOption]);

  // 将API响应转换为VO对象
  const transformToVO = useCallback((plugin: PluginV4): PluginMarketCardVO => {
    return new PluginMarketCardVO({
      pluginId: plugin.author + ' / ' + plugin.name,
      author: plugin.author,
      pluginName: plugin.name,
      label: extractI18nObject(plugin.label),
      description:
        extractI18nObject(plugin.description) || t('market.noDescription'),
      installCount: plugin.install_count,
      iconURL: getCloudServiceClientSync().getPluginIconURL(
        plugin.author,
        plugin.name,
      ),
      githubURL: plugin.repository,
      version: plugin.latest_version,
    });
  }, []);

  // 获取插件列表
  const fetchPlugins = useCallback(
    async (page: number, isSearch: boolean = false, reset: boolean = false) => {
      if (page === 1) {
        setIsLoading(true);
      } else {
        setIsLoadingMore(true);
      }

      try {
        let response;
        const { sortBy, sortOrder } = getCurrentSort();

        if (isSearch && searchQuery.trim()) {
          response = await getCloudServiceClientSync().searchMarketplacePlugins(
            searchQuery.trim(),
            page,
            pageSize,
            sortBy,
            sortOrder,
          );
        } else {
          response = await getCloudServiceClientSync().getMarketplacePlugins(
            page,
            pageSize,
            sortBy,
            sortOrder,
          );
        }

        const data: ApiRespMarketplacePlugins = response;
        const newPlugins = data.plugins.map(transformToVO);
        const total = data.total;

        if (reset || page === 1) {
          setPlugins(newPlugins);
        } else {
          setPlugins((prev) => [...prev, ...newPlugins]);
        }

        setTotal(total);
        setHasMore(
          data.plugins.length === pageSize &&
            plugins.length + newPlugins.length < total,
        );
      } catch (error) {
        console.error('Failed to fetch plugins:', error);
        toast.error(t('market.loadFailed'));
      } finally {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    },
    [searchQuery, pageSize, transformToVO, plugins.length, getCurrentSort],
  );

  // 初始加载
  useEffect(() => {
    fetchPlugins(1, false, true);
  }, []);

  // 搜索功能
  const handleSearch = useCallback(
    (query: string) => {
      setSearchQuery(query);
      setCurrentPage(1);
      setPlugins([]);
      fetchPlugins(1, !!query.trim(), true);
    },
    [fetchPlugins],
  );

  // 防抖搜索
  const handleSearchInputChange = useCallback(
    (value: string) => {
      setSearchQuery(value);

      // 清除之前的定时器
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }

      // 设置新的定时器
      searchTimeoutRef.current = setTimeout(() => {
        handleSearch(value);
      }, 300);
    },
    [handleSearch],
  );

  // 排序选项变化处理
  const handleSortChange = useCallback((value: string) => {
    setSortOption(value);
    setCurrentPage(1);
    setPlugins([]);
    // fetchPlugins will be called by useEffect when sortOption changes
  }, []);

  // 当排序选项变化时重新加载数据
  useEffect(() => {
    fetchPlugins(1, !!searchQuery.trim(), true);
  }, [sortOption]);

  // 处理URL参数，检查是否需要打开插件详情对话框
  useEffect(() => {
    const author = searchParams.get('author');
    const pluginName = searchParams.get('plugin');

    if (author && pluginName) {
      setSelectedPluginAuthor(author);
      setSelectedPluginName(pluginName);
      setDialogOpen(true);
    }
  }, [searchParams]);

  // 插件详情对话框处理函数
  const handlePluginClick = useCallback(
    (author: string, pluginName: string) => {
      setSelectedPluginAuthor(author);
      setSelectedPluginName(pluginName);
      setDialogOpen(true);
    },
    [],
  );

  const handleDialogClose = useCallback(() => {
    setDialogOpen(false);
    setSelectedPluginAuthor(null);
    setSelectedPluginName(null);
  }, []);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, []);

  // 加载更多
  const loadMore = useCallback(() => {
    if (!isLoadingMore && hasMore) {
      const nextPage = currentPage + 1;
      setCurrentPage(nextPage);
      fetchPlugins(nextPage, !!searchQuery.trim());
    }
  }, [currentPage, isLoadingMore, hasMore, fetchPlugins, searchQuery]);

  // Listen to scroll events on the scroll container
  useEffect(() => {
    const scrollContainer = scrollContainerRef.current;
    if (!scrollContainer) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
      // Load more when scrolled to within 100px of the bottom
      if (scrollTop + clientHeight >= scrollHeight - 100) {
        loadMore();
      }
    };

    scrollContainer.addEventListener('scroll', handleScroll);
    return () => scrollContainer.removeEventListener('scroll', handleScroll);
  }, [loadMore]);

  // 安装插件
  // const handleInstallPlugin = (plugin: PluginV4) => {
  //   console.log('install plugin', plugin);
  // };

  return (
    <div className="h-full flex flex-col">
      {/* Fixed header with search and sort controls */}
      <div className="flex-shrink-0 space-y-4 px-3 sm:px-4 py-4 sm:py-6">
        {/* Search box */}
        <div className="flex items-center justify-center">
          <div className="relative w-full max-w-2xl">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
            <Input
              placeholder={t('market.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => handleSearchInputChange(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  // Immediately search, clear debounce timer
                  if (searchTimeoutRef.current) {
                    clearTimeout(searchTimeoutRef.current);
                  }
                  handleSearch(searchQuery);
                }
              }}
              className="pl-10 pr-4 text-sm sm:text-base"
            />
          </div>
        </div>

        {/* Sort dropdown */}
        <div className="flex items-center justify-center">
          <div className="w-full max-w-2xl flex items-center gap-2 sm:gap-3">
            <span className="text-xs sm:text-sm text-muted-foreground whitespace-nowrap">
              {t('market.sortBy')}:
            </span>
            <Select value={sortOption} onValueChange={handleSortChange}>
              <SelectTrigger className="w-40 sm:w-48 text-xs sm:text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {sortOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Search results stats */}
        {total > 0 && (
          <div className="text-center text-muted-foreground text-sm">
            {searchQuery
              ? t('market.searchResults', { count: total })
              : t('market.totalPlugins', { count: total })}
          </div>
        )}
      </div>

      {/* Scrollable content area */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-3 sm:px-4"
      >
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin" />
            <span className="ml-2">{t('market.loading')}</span>
          </div>
        ) : plugins.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-muted-foreground">
              {searchQuery ? t('market.noResults') : t('market.noPlugins')}
            </div>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-6 pb-6">
              {plugins.map((plugin) => (
                <PluginMarketCardComponent
                  key={plugin.pluginId}
                  cardVO={plugin}
                  onPluginClick={handlePluginClick}
                />
              ))}
            </div>

            {/* Loading more indicator */}
            {isLoadingMore && (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="h-6 w-6 animate-spin" />
                <span className="ml-2">{t('market.loadingMore')}</span>
              </div>
            )}

            {/* No more data hint */}
            {!hasMore && plugins.length > 0 && (
              <div className="text-center text-muted-foreground py-6">
                {t('market.allLoaded')}
              </div>
            )}
          </>
        )}
      </div>

      {/* Plugin detail dialog */}
      <PluginDetailDialog
        open={dialogOpen}
        onOpenChange={handleDialogClose}
        author={selectedPluginAuthor}
        pluginName={selectedPluginName}
        installPlugin={installPlugin}
      />
    </div>
  );
}

// 主组件，包装在 Suspense 中
export default function MarketPage({
  installPlugin,
}: {
  installPlugin: (plugin: PluginV4) => void;
}) {
  return (
    <Suspense
      fallback={
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin" />
            <span className="ml-2">加载中...</span>
          </div>
        </div>
      }
    >
      <MarketPageContent installPlugin={installPlugin} />
    </Suspense>
  );
}
