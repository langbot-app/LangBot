import { useState, useEffect, useCallback, useRef, Suspense } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Separator } from '@/components/ui/separator';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Search,
  Puzzle,
  Server,
  Sparkles,
  Wrench,
  AudioWaveform,
  Hash,
  Book,
  FileText,
  AppWindow,
  SlidersHorizontal,
  X,
  Info,
} from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import PluginMarketCardComponent from './plugin-market-card/PluginMarketCardComponent';
import { PluginMarketCardVO } from './plugin-market-card/PluginMarketCardVO';
import { RecommendationLists } from './RecommendationLists';
import type { RecommendationList } from './RecommendationLists';
import {
  getCloudServiceClient,
  getCloudServiceClientSync,
} from '@/app/infra/http';
import { useTranslation } from 'react-i18next';
import { PluginV4, PluginV4Status } from '@/app/infra/entities/plugin';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { toast } from 'sonner';
import { ApiRespMarketplacePlugins } from '@/app/infra/entities/api';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { Button } from '@/components/ui/button';
import { PluginTag } from '@/app/infra/http/CloudServiceClient';

interface SortOption {
  value: string;
  label: string;
  sortBy: string;
  sortOrder: string;
}

// Persist the market filter conditions (type / component / tags / sort) across
// visits via localStorage.
const MARKET_FILTERS_KEY = 'langbot_market_filters';
interface MarketFilters {
  typeFilter?: string;
  componentFilter?: string;
  selectedTags?: string[];
  sortOption?: string;
}
function loadMarketFilters(): MarketFilters {
  try {
    return JSON.parse(localStorage.getItem(MARKET_FILTERS_KEY) || '{}');
  } catch {
    return {};
  }
}

// 内部组件，用于处理搜索参数
function MarketPageContent({
  installPlugin,
  headerActions,
}: {
  installPlugin: (plugin: PluginV4) => void;
  headerActions?: React.ReactNode;
}) {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();

  const validTypes = ['plugin', 'mcp', 'skill'];

  const extensionTypeOptions = [
    { value: 'all', label: t('market.filters.allFormats'), icon: null },
    { value: 'plugin', label: t('market.typePlugin'), icon: Puzzle },
    { value: 'mcp', label: t('market.typeMCP'), icon: Server },
    { value: 'skill', label: t('market.typeSkill'), icon: Sparkles },
  ];

  const [searchQuery, setSearchQuery] = useState('');
  const [componentFilter, setComponentFilter] = useState<string>(
    () => loadMarketFilters().componentFilter ?? 'all',
  );
  const [typeFilter, setTypeFilter] = useState<string>(() => {
    const type = searchParams.get('type');
    if (type && validTypes.includes(type)) {
      return type;
    }
    const saved = loadMarketFilters().typeFilter;
    return saved && validTypes.includes(saved) ? saved : 'all';
  });
  const activeAdvancedFilters =
    (typeFilter === 'all' ? 0 : 1) + (componentFilter === 'all' ? 0 : 1);
  const [selectedTags, setSelectedTags] = useState<string[]>(
    () => loadMarketFilters().selectedTags ?? [],
  );
  const [availableTags, setAvailableTags] = useState<PluginTag[]>([]);
  const [tagNames, setTagNames] = useState<Record<string, string>>({});
  const [recommendationLists, setRecommendationLists] = useState<
    RecommendationList[]
  >([]);
  const [plugins, setPlugins] = useState<PluginMarketCardVO[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [total, setTotal] = useState(0);
  // Per-format extension counts shown next to the type filter options.
  const [typeCounts, setTypeCounts] = useState<Record<string, number>>({});
  const [sortOption, setSortOption] = useState<string>(
    () => loadMarketFilters().sortOption ?? 'install_count_desc',
  );

  // Persist filter conditions so they survive navigation / reload.
  useEffect(() => {
    try {
      localStorage.setItem(
        MARKET_FILTERS_KEY,
        JSON.stringify({
          typeFilter,
          componentFilter,
          selectedTags,
          sortOption,
        }),
      );
    } catch {
      // ignore storage errors
    }
  }, [typeFilter, componentFilter, selectedTags, sortOption]);

  const pageSize = 24; // 每页24个
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const isComposingRef = useRef(false);

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

  const componentOptions = [
    { value: 'all', label: t('market.allComponents'), icon: null },
    { value: 'Tool', label: t('market.componentName.Tool'), icon: Wrench },
    { value: 'Command', label: t('market.componentName.Command'), icon: Hash },
    {
      value: 'EventListener',
      label: t('market.componentName.EventListener'),
      icon: AudioWaveform,
    },
    {
      value: 'KnowledgeEngine',
      label: t('market.componentName.KnowledgeEngine'),
      icon: Book,
    },
    {
      value: 'Parser',
      label: t('market.componentName.Parser'),
      icon: FileText,
    },
    {
      value: 'Page',
      label: t('market.componentName.Page'),
      icon: AppWindow,
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
  const transformToVO = useCallback(
    (plugin: PluginV4): PluginMarketCardVO => {
      const cloudClient = getCloudServiceClientSync();
      const iconURL = cloudClient.resolveMarketplaceIconURL(
        plugin.type,
        plugin.author,
        plugin.name,
        plugin.icon,
      );

      return new PluginMarketCardVO({
        pluginId: plugin.author + ' / ' + plugin.name,
        author: plugin.author,
        pluginName: plugin.name,
        label: extractI18nObject(plugin.label),
        description:
          extractI18nObject(plugin.description) || t('market.noDescription'),
        installCount: plugin.install_count || 0,
        iconURL,
        githubURL: plugin.repository,
        version: plugin.latest_version,
        components: plugin.components || {},
        tags: plugin.tags || [],
        type: plugin.type,
      });
    },
    [t],
  );

  // 获取插件列表
  const fetchPlugins = useCallback(
    async (
      page: number,
      isSearch: boolean = false,
      reset: boolean = false,
      queryOverride?: string,
    ) => {
      if (page === 1) {
        setIsLoading(true);
      } else {
        setIsLoadingMore(true);
      }

      try {
        const { sortBy, sortOrder } = getCurrentSort();
        const query = (queryOverride ?? searchQuery).trim();

        const response =
          await getCloudServiceClientSync().searchMarketplaceExtensions({
            query: isSearch ? query : '',
            page,
            page_size: pageSize,
            sort_by: sortBy,
            sort_order: sortOrder,
            type_filter: typeFilter === 'all' ? undefined : typeFilter,
            component_filter:
              componentFilter === 'all' ? undefined : componentFilter,
            tags_filter: selectedTags.length > 0 ? selectedTags : undefined,
          });

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
          newPlugins.length > 0 &&
            (reset || page === 1
              ? newPlugins.length
              : plugins.length + newPlugins.length) < total,
        );
      } catch (error) {
        console.error('Failed to fetch plugins:', error);
        toast.error(t('market.loadFailed'));
      } finally {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    },
    [
      searchQuery,
      componentFilter,
      selectedTags,
      pageSize,
      transformToVO,
      plugins.length,
      getCurrentSort,
      typeFilter,
    ],
  );

  // 初始加载
  useEffect(() => {
    // Resolve the cloud service base URL (from system info) before any
    // marketplace fetch — otherwise the sync client may still hold the default
    // URL and hit space.langbot.app instead of the configured instance.
    (async () => {
      await getCloudServiceClient();
      fetchPlugins(1, false, true);
      fetchAvailableTags();
      fetchRecommendationLists();
      fetchTypeCounts();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 获取推荐列表（精选，混合插件/MCP/Skill）
  const fetchRecommendationLists = async () => {
    try {
      const client = await getCloudServiceClient();
      const { lists } = await client.getRecommendationLists();
      setRecommendationLists(lists || []);
    } catch (error) {
      console.error('Failed to fetch recommendation lists:', error);
    }
  };

  // 获取可用标签
  const fetchAvailableTags = async () => {
    try {
      const response = await getCloudServiceClientSync().getAllTags();
      const tags = response.tags || [];
      setAvailableTags(tags);

      // Build tag names map for all components to use
      const nameMap: Record<string, string> = {};
      tags.forEach((tag: PluginTag) => {
        const displayName = {
          en_US: tag.display_name.en_US || tag.tag,
          zh_Hans: tag.display_name.zh_Hans || tag.tag,
          zh_Hant: tag.display_name.zh_Hant,
          ja_JP: tag.display_name.ja_JP,
        };
        nameMap[tag.tag] = extractI18nObject(displayName);
      });
      setTagNames(nameMap);
    } catch (error) {
      console.error('Failed to fetch tags:', error);
    }
  };

  // 获取各扩展格式的数量（用于筛选器标签上的计数）
  const fetchTypeCounts = async () => {
    const types = ['plugin', 'mcp', 'skill'];
    try {
      const results = await Promise.all(
        types.map((type) =>
          getCloudServiceClientSync()
            .searchMarketplaceExtensions({
              page: 1,
              page_size: 1,
              type_filter: type,
            })
            .then((res) => res.total)
            .catch(() => 0),
        ),
      );
      const counts: Record<string, number> = {};
      types.forEach((type, i) => {
        counts[type] = results[i];
      });
      setTypeCounts(counts);
    } catch (error) {
      console.error('Failed to fetch extension type counts:', error);
    }
  };

  // 搜索功能
  const handleSearch = useCallback(
    (query: string) => {
      setSearchQuery(query);
      setCurrentPage(1);
      setPlugins([]);
      fetchPlugins(1, !!query.trim(), true, query);
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

      if (isComposingRef.current) {
        return;
      }

      // 设置新的定时器
      searchTimeoutRef.current = setTimeout(() => {
        handleSearch(value);
      }, 500);
    },
    [handleSearch],
  );

  // 排序选项变化处理
  const handleSortChange = useCallback((value: string) => {
    setSortOption(value);
    setCurrentPage(1);
    setPlugins([]);
  }, []);

  // Handle type filter change
  const handleTypeFilterChange = useCallback((value: string) => {
    setTypeFilter(value);
    if (value !== 'plugin') {
      setComponentFilter('all');
    }
    setCurrentPage(1);
    setSelectedTags([]);
    setPlugins([]);

    // Update URL query param to keep it in sync
    const params = new URLSearchParams(window.location.search);
    if (value === 'all') {
      params.delete('type');
    } else {
      params.set('type', value);
    }
    const newUrl = params.toString()
      ? `${window.location.pathname}?${params.toString()}`
      : window.location.pathname;
    window.history.replaceState({}, '', newUrl);
  }, []);

  const handleComponentFilterChange = useCallback((value: string) => {
    setComponentFilter(value);
    setCurrentPage(1);
    setPlugins([]);

    if (value !== 'all') {
      setTypeFilter('plugin');

      const params = new URLSearchParams(window.location.search);
      params.set('type', 'plugin');
      const newUrl = params.toString()
        ? `${window.location.pathname}?${params.toString()}`
        : window.location.pathname;
      window.history.replaceState({}, '', newUrl);
    }
  }, []);

  // 当排序选项或组件筛选或类型筛选变化时重新加载数据
  useEffect(() => {
    fetchPlugins(1, !!searchQuery.trim(), true);
  }, [sortOption, componentFilter, typeFilter]);

  // Tags 筛选变化时重新搜索
  useEffect(() => {
    if (!isLoading) {
      setCurrentPage(1);
      fetchPlugins(1, searchQuery.trim() !== '', true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTags]);

  // 处理 tags 变化
  const handleTagsChange = useCallback((tags: string[]) => {
    setSelectedTags(tags);
  }, []);

  // 处理安装插件
  const handleInstallPlugin = useCallback(
    async (cardVO: PluginMarketCardVO) => {
      try {
        if (cardVO.type === 'mcp' || cardVO.type === 'skill') {
          // For MCP and Skill, directly pass the data - backend will fetch from Space
          const pluginV4: PluginV4 = {
            id: 0,
            plugin_id: `${cardVO.author}/${cardVO.pluginName}`,
            mcp_id:
              cardVO.type === 'mcp'
                ? `${cardVO.author}/${cardVO.pluginName}`
                : undefined,
            skill_id:
              cardVO.type === 'skill'
                ? `${cardVO.author}/${cardVO.pluginName}`
                : undefined,
            author: cardVO.author,
            name: cardVO.pluginName,
            label: { en_US: cardVO.label, zh_Hans: cardVO.label },
            description: {
              en_US: cardVO.description,
              zh_Hans: cardVO.description,
            },
            icon: cardVO.iconURL,
            repository: cardVO.githubURL,
            tags: cardVO.tags || [],
            install_count: cardVO.installCount,
            latest_version: cardVO.version,
            components: cardVO.components || {},
            status: PluginV4Status.Live,
            type: cardVO.type,
            created_at: '',
            updated_at: '',
          };
          installPlugin(pluginV4);
          return;
        }

        // For plugin type, fetch full details via API
        const response = await getCloudServiceClientSync().getPluginDetail(
          cardVO.author,
          cardVO.pluginName,
        );
        if (!response?.plugin) {
          console.error('Failed to install plugin: plugin not found', {
            author: cardVO.author,
            pluginName: cardVO.pluginName,
          });
          toast.error(t('market.installFailed'));
          return;
        }
        const pluginV4: PluginV4 = response.plugin;

        // Call the install function passed from parent
        installPlugin(pluginV4);
      } catch (error) {
        console.error('Failed to install plugin:', error);
        toast.error(t('market.installFailed'));
      }
    },
    [installPlugin, t],
  );

  // 清理定时器
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, []);

  const visiblePlugins = plugins;

  // 加载更多
  const loadMore = useCallback(() => {
    if (!isLoadingMore && hasMore) {
      const nextPage = currentPage + 1;
      setCurrentPage(nextPage);
      fetchPlugins(nextPage, !!searchQuery.trim());
    }
  }, [currentPage, isLoadingMore, hasMore, fetchPlugins, searchQuery]);

  // Check if content fills the viewport and load more if needed
  const checkAndLoadMore = useCallback(() => {
    const scrollContainer = scrollContainerRef.current;
    if (!scrollContainer || isLoading || isLoadingMore || !hasMore) return;

    const { scrollHeight, clientHeight } = scrollContainer;
    // If content doesn't fill the viewport (no scrollbar), load more
    if (scrollHeight <= clientHeight) {
      loadMore();
    }
  }, [loadMore, isLoading, isLoadingMore, hasMore]);

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

  // Check if we need to load more after content changes or initial load
  useEffect(() => {
    // Small delay to ensure DOM has updated
    const timer = setTimeout(() => {
      checkAndLoadMore();
    }, 100);
    return () => clearTimeout(timer);
  }, [plugins, checkAndLoadMore]);

  // Also check on window resize
  useEffect(() => {
    const handleResize = () => {
      checkAndLoadMore();
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [checkAndLoadMore]);

  // 安装插件
  // const handleInstallPlugin = (plugin: PluginV4) => {
  // };

  return (
    <div className="h-full flex flex-col">
      {/* Fixed header section with search, sort, and status */}
      <div className="flex-none px-3 sm:px-4 py-2 sm:py-4 space-y-4 sm:space-y-6 container mx-auto">
        {/* 搜索、排序和筛选入口 */}
        <div className="flex w-full items-center justify-center gap-2 sm:gap-3">
          <div className="relative min-w-0 flex-1 lg:max-w-xl">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
            <Input
              placeholder={
                total > 0
                  ? t('market.searchPlaceholderCount', { count: total })
                  : t('market.searchPlaceholder')
              }
              value={searchQuery}
              onChange={(e) => handleSearchInputChange(e.target.value)}
              onCompositionStart={() => {
                isComposingRef.current = true;
              }}
              onCompositionEnd={(e) => {
                isComposingRef.current = false;
                handleSearchInputChange((e.target as HTMLInputElement).value);
              }}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  if (searchTimeoutRef.current) {
                    clearTimeout(searchTimeoutRef.current);
                  }
                  handleSearch(searchQuery);
                }
              }}
              className="min-w-0 pl-10 pr-4 text-sm sm:text-base"
            />
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <Select value={sortOption} onValueChange={handleSortChange}>
              <SelectTrigger className="w-28 shrink-0 text-xs sm:w-40 sm:text-sm">
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

            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className="relative shrink-0 px-3 sm:px-4"
                >
                  <SlidersHorizontal className="h-4 w-4" />
                  <span className="hidden sm:inline">
                    {t('market.filters.more')}
                  </span>
                  {activeAdvancedFilters > 0 && (
                    <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] leading-none text-primary-foreground">
                      {activeAdvancedFilters}
                    </span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-[320px] space-y-4">
                <div>
                  <div className="text-sm font-medium">
                    {t('market.filters.advancedTitle')}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {t('market.filters.advancedDescription')}
                  </div>
                </div>
                <Separator />
                <div className="space-y-2">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t('market.filters.technicalType')}
                  </div>
                  <ToggleGroup
                    type="single"
                    spacing={2}
                    size="sm"
                    value={typeFilter}
                    onValueChange={(value) => {
                      if (value) handleTypeFilterChange(value);
                    }}
                    className="flex flex-wrap justify-start gap-2"
                  >
                    {extensionTypeOptions.map((option) => {
                      const Icon = option.icon;
                      const count = typeCounts[option.value];
                      return (
                        <ToggleGroupItem
                          key={option.value}
                          value={option.value}
                          aria-label={option.label}
                          className="cursor-pointer text-xs"
                        >
                          {Icon && <Icon className="mr-1 h-3.5 w-3.5" />}
                          {option.label}
                          {typeof count === 'number' && (
                            <span className="ml-1 text-muted-foreground">
                              ({count})
                            </span>
                          )}
                        </ToggleGroupItem>
                      );
                    })}
                  </ToggleGroup>
                </div>
                <Separator />
                <div className="space-y-2">
                  <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                    {t('market.filterByComponent')}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          className="inline-flex text-muted-foreground/70 hover:text-foreground"
                          aria-label={t('market.filterByComponentHint')}
                        >
                          <Info className="size-3.5" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-64">
                        {t('market.filterByComponentHint')}
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <ToggleGroup
                    type="single"
                    spacing={2}
                    size="sm"
                    value={componentFilter}
                    onValueChange={(value) => {
                      if (value) handleComponentFilterChange(value);
                    }}
                    className="flex flex-wrap justify-start gap-2"
                  >
                    {componentOptions.map((option) => {
                      const Icon = option.icon;
                      return (
                        <ToggleGroupItem
                          key={option.value}
                          value={option.value}
                          aria-label={option.label}
                          className="cursor-pointer text-xs"
                        >
                          {Icon && <Icon className="mr-1 h-3.5 w-3.5" />}
                          {option.label}
                        </ToggleGroupItem>
                      );
                    })}
                  </ToggleGroup>
                </div>
              </PopoverContent>
            </Popover>

            {headerActions}
          </div>
        </div>

        {/* 用真实标签做快速筛选 —— 始终单行横向滚动，避免标签变多时换行错位 */}
        <div className="relative mx-auto w-full max-w-4xl">
          <div className="scrollbar-hide flex items-center gap-1.5 overflow-x-auto pb-1 pr-6">
            <Button
              type="button"
              variant={selectedTags.length === 0 ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 shrink-0 px-2.5 text-xs"
              onClick={() => handleTagsChange([])}
            >
              {t('market.allExtensions')}
            </Button>
            {availableTags.map((tag) => {
              const selected = selectedTags.includes(tag.tag);
              return (
                <Button
                  key={tag.tag}
                  type="button"
                  variant={selected ? 'secondary' : 'ghost'}
                  size="sm"
                  className="h-7 shrink-0 px-2.5 text-xs"
                  onClick={() => {
                    const newTags = selected
                      ? selectedTags.filter((t) => t !== tag.tag)
                      : [...selectedTags, tag.tag];
                    handleTagsChange(newTags);
                  }}
                >
                  {tagNames[tag.tag] || tag.tag}
                  {selected && <X className="h-3 w-3" />}
                </Button>
              );
            })}
          </div>
          {/* 右侧渐隐，提示还有更多标签可横向滚动查看 */}
          <div className="pointer-events-none absolute right-0 top-0 bottom-1 w-8 bg-gradient-to-l from-background to-transparent" />
        </div>
      </div>

      {/* Scrollable extension list section */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-3 sm:px-4 pb-6 container mx-auto"
      >
        {/* 推荐列表（仅在无搜索/筛选时展示，混合插件/MCP/Skill） */}
        {!searchQuery &&
          typeFilter === 'all' &&
          componentFilter === 'all' &&
          selectedTags.length === 0 && (
            <RecommendationLists
              lists={recommendationLists}
              tagNames={tagNames}
              onInstall={handleInstallPlugin}
            />
          )}

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner text={t('market.loading')} />
          </div>
        ) : plugins.length === 0 ? (
          <div className="text-center text-muted-foreground py-12">
            {searchQuery ? t('market.noResults') : t('market.noPlugins')}
            {' · '}
            <a
              href="https://github.com/langbot-app/langbot-plugin-demo/issues/new?template=plugin-request.yml"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              {t('market.requestPlugin')}
            </a>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-6 mt-6">
              {visiblePlugins.map((plugin) => (
                <PluginMarketCardComponent
                  key={plugin.pluginId}
                  cardVO={plugin}
                  onInstall={handleInstallPlugin}
                  tagNames={tagNames}
                />
              ))}
            </div>

            {/* Loading more indicator */}
            {isLoadingMore && (
              <div className="flex items-center justify-center py-6">
                <LoadingSpinner size="sm" text={t('market.loadingMore')} />
              </div>
            )}

            {/* No more data hint */}
            {!hasMore && plugins.length > 0 && (
              <div className="text-center text-muted-foreground py-6">
                {searchQuery
                  ? t('market.allLoadedCount', { count: total })
                  : t('market.allLoaded')}
                {' · '}
                <a
                  href="https://github.com/langbot-app/langbot-plugin-demo/issues/new?template=plugin-request.yml"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  {t('market.requestPlugin')}
                </a>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// 主组件，包装在 Suspense 中
export default function MarketPage({
  installPlugin,
  headerActions,
}: {
  installPlugin: (plugin: PluginV4) => void;
  headerActions?: React.ReactNode;
}) {
  return (
    <Suspense
      fallback={
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner text="加载中..." />
          </div>
        </div>
      }
    >
      <MarketPageContent
        installPlugin={installPlugin}
        headerActions={headerActions}
      />
    </Suspense>
  );
}
