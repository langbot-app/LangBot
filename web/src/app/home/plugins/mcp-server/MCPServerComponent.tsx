'use client';

import { useEffect, useState } from 'react';
import styles from '@/app/home/plugins/plugins.module.css';
// import { MCPMarketCardVO } from '@/app/home/plugins/mcp-market/mcp-market-card/MCPMarketCardVO';
// import MCPMarketCardComponent from '@/app/home/plugins/mcp-market/mcp-market-card/MCPMarketCardComponent';
import MCPCardComponent from '@/app/home/plugins/mcp/mcp-card/MCPCardComponent';
import { MCPCardVO } from '@/app/home/plugins/mcp/MCPCardVO';
// import { spaceClient } from '@/app/infra/http/HttpClient';
import { useTranslation } from 'react-i18next';
// import { Input } from '@/components/ui/input';
// import {
//   Pagination,
//   PaginationContent,
//   PaginationItem,
//   PaginationLink,
//   PaginationNext,
//   PaginationPrevious,
// } from '@/components/ui/pagination';
// import {
//   Select,
//   SelectContent,
//   SelectItem,
//   SelectTrigger,
//   SelectValue,
// } from '@/components/ui/select';

import { httpClient } from '@/app/infra/http/HttpClient';

export default function MCPMarketComponent({
  onEditServer,
  toolsCountCache = {},
}: {
  askInstallServer?: (githubURL: string) => void;
  onEditServer?: (serverName: string) => void;
  toolsCountCache?: Record<string, number>;
}) {
  const { t } = useTranslation();
  // const [marketServerList, setMarketServerList] = useState<MCPMarketCardVO[]>(
  //   [],
  // );
  const [installedServers, setInstalledServers] = useState<MCPCardVO[]>([]);
  // const [totalCount, setTotalCount] = useState(0);
  // const [nowPage, setNowPage] = useState(1);
  // const [searchKeyword, setSearchKeyword] = useState('');
  const [loading, setLoading] = useState(false);
  // const [sortByValue, setSortByValue] = useState<string>('pushed_at');
  // const [sortOrderValue, setSortOrderValue] = useState<string>('DESC');
  // const searchTimeout = useRef<NodeJS.Timeout | null>(null);
  // const pageSize = 12;

  useEffect(() => {
    initData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 当工具数量缓存变化时，重新获取服务器列表
  useEffect(() => {
    fetchInstalledServers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toolsCountCache]);

  function initData() {
    fetchInstalledServers();
    // getServerList(); // GitHub 市场功能暂时注释
  }

  function fetchInstalledServers() {
    setLoading(true);
    httpClient
      .getMCPServers()
      .then((resp) => {
        const servers = resp.servers.map((server) => {
          const vo = new MCPCardVO(server);
          // 如果缓存中有工具数量，使用缓存值覆盖
          if (toolsCountCache[server.name] !== undefined) {
            vo.tools = toolsCountCache[server.name];
          }
          return vo;
        });
        setInstalledServers(servers);
        setLoading(false);
      })
      .catch((error) => {
        console.error('Failed to fetch MCP servers:', error);
        setLoading(false);
      });
  }

  // GitHub 市场功能暂时注释
  // function onInputSearchKeyword(keyword: string) {
  //   setSearchKeyword(keyword);
  //   if (searchTimeout.current) {
  //     clearTimeout(searchTimeout.current);
  //   }
  //   searchTimeout.current = setTimeout(() => {
  //     setNowPage(1);
  //     getServerList(1, keyword);
  //   }, 500);
  // }

  // function getServerList(
  //   page: number = nowPage,
  //   keyword: string = searchKeyword,
  //   sortBy: string = sortByValue,
  //   sortOrder: string = sortOrderValue,
  // ) {
  //   // GitHub 安装功能暂时注释
  //   // spaceClient
  //   //   .getMCPMarketServers(page, pageSize, keyword, sortBy, sortOrder)
  //   //   .then((res) => {
  //   //     setMarketServerList(
  //   //       res.servers.map((marketServer) => {
  //   //         let repository = marketServer.repository;
  //   //         if (repository.startsWith('https://github.com/')) {
  //   //           repository = repository.replace('https://github.com/', '');
  //   //         }
  //   //         if (repository.startsWith('github.com/')) {
  //   //           repository = repository.replace('github.com/', '');
  //   //         }
  //   //         const author = repository.split('/')[0];
  //   //         const name = repository.split('/')[1];
  //   //         return new MCPMarketCardVO({
  //   //           author: author,
  //   //           description: marketServer.description,
  //   //           githubURL: `https://github.com/${repository}`,
  //   //           name: name,
  //   //           serverId: String(marketServer.ID),
  //   //           starCount: marketServer.stars,
  //   //           version:
  //   //             'version' in marketServer
  //   //               ? String(marketServer.version)
  //   //               : '1.0.0',
  //   //         });
  //   //       }),
  //   //     );
  //   //     setTotalCount(res.total);
  //   //     setLoading(false);
  //   //     console.log('market servers:', res);
  //   //   })
  //   //   .catch((error) => {
  //   //     console.error(t('mcp.getServerListError'), error);
  //   //     setLoading(false);
  //   //   });
  // }

  // function handlePageChange(page: number) {
  //   setNowPage(page);
  //   getServerList(page);
  // }

  // function handleSortChange(value: string) {
  //   const [newSortBy, newSortOrder] = value.split(',').map((s) => s.trim());
  //   setSortByValue(newSortBy);
  //   setSortOrderValue(newSortOrder);
  //   setNowPage(1);
  //   getServerList(1, searchKeyword, newSortBy, newSortOrder);
  // }

  return (
    <div className={`${styles.marketComponentBody}`}>
      {/* 已安装的服务器列表 */}
      <div className="mb-6">
        <div className={`${styles.pluginListContainer}`}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              {t('mcp.loading')}
            </div>
          ) : installedServers.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              {t('mcp.noServerInstalled')}
            </div>
          ) : (
            installedServers.map((server, index) => (
              <div key={`${server.name}-${index}`}>
                <MCPCardComponent
                  cardVO={server}
                  onCardClick={() => {
                    if (onEditServer) {
                      onEditServer(server.name);
                    }
                  }}
                  onRefresh={fetchInstalledServers}
                />
              </div>
            ))
          )}
        </div>
      </div>

      {/* GitHub 市场功能暂时注释 */}
      {/* <div className="flex items-center justify-start mb-2 mt-2 pl-[0.8rem] pr-[0.8rem]">
        <Input
          style={{
            width: '300px',
          }}
          value={searchKeyword}
          placeholder={t('mcp.searchServer')}
          onChange={(e) => onInputSearchKeyword(e.target.value)}
        />

        <Select
          value={`${sortByValue},${sortOrderValue}`}
          onValueChange={handleSortChange}
        >
          <SelectTrigger className="w-[180px] ml-2 cursor-pointer">
            <SelectValue placeholder={t('mcp.sortBy')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="stars,DESC">{t('mcp.mostStars')}</SelectItem>
            <SelectItem value="created_at,DESC">
              {t('mcp.recentlyAdded')}
            </SelectItem>
            <SelectItem value="pushed_at,DESC">
              {t('mcp.recentlyUpdated')}
            </SelectItem>
          </SelectContent>
        </Select>

        <div className="flex items-center justify-end ml-2">
          {totalCount > 0 && (
            <Pagination>
              <PaginationContent>
                <PaginationItem className="cursor-pointer">
                  <PaginationPrevious
                    onClick={() => handlePageChange(nowPage - 1)}
                    className={
                      nowPage <= 1 ? 'pointer-events-none opacity-50' : ''
                    }
                  />
                </PaginationItem>

                {(() => {
                  const totalPages = Math.ceil(totalCount / pageSize);
                  const maxVisiblePages = 5;
                  let startPage = Math.max(
                    1,
                    nowPage - Math.floor(maxVisiblePages / 2),
                  );
                  const endPage = Math.min(
                    totalPages,
                    startPage + maxVisiblePages - 1,
                  );

                  if (endPage - startPage + 1 < maxVisiblePages) {
                    startPage = Math.max(1, endPage - maxVisiblePages + 1);
                  }

                  return Array.from(
                    { length: endPage - startPage + 1 },
                    (_, i) => {
                      const pageNum = startPage + i;
                      return (
                        <PaginationItem
                          key={pageNum}
                          className="cursor-pointer"
                        >
                          <PaginationLink
                            isActive={pageNum === nowPage}
                            onClick={() => handlePageChange(pageNum)}
                          >
                            <span className="text-black select-none">
                              {pageNum}
                            </span>
                          </PaginationLink>
                        </PaginationItem>
                      );
                    },
                  );
                })()}

                <PaginationItem className="cursor-pointer">
                  <PaginationNext
                    onClick={() => handlePageChange(nowPage + 1)}
                    className={
                      nowPage >= Math.ceil(totalCount / pageSize)
                        ? 'pointer-events-none opacity-50'
                        : ''
                    }
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          )}
        </div>
      </div>

      <div className={`${styles.pluginListContainer}`}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            {t('mcp.loading')}
          </div>
        ) : marketServerList.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            {t('mcp.noMatchingServers')}
          </div>
        ) : (
          marketServerList.map((vo, index) => (
            <div key={`${vo.serverId}-${index}`}>
              <MCPMarketCardComponent
                cardVO={vo}
                installServer={(githubURL) => {
                  askInstallServer(githubURL);
                }}
              />
            </div>
          ))
        )}
      </div> */}
    </div>
  );
}
