'use client';

import { useEffect, useState, useRef } from 'react';
import MCPCardComponent from '@/app/home/plugins/mcp-server/mcp-card/MCPCardComponent';
import { MCPCardVO } from '@/app/home/plugins/mcp-server/MCPCardVO';
import { useTranslation } from 'react-i18next';
import { MCPSessionStatus } from '@/app/infra/entities/api';

import { httpClient } from '@/app/infra/http/HttpClient';

export default function MCPComponent({
  onEditServer,
}: {
  askInstallServer?: (githubURL: string) => void;
  onEditServer?: (serverName: string) => void;
}) {
  const { t } = useTranslation();
  const [installedServers, setInstalledServers] = useState<MCPCardVO[]>([]);
  const [loading, setLoading] = useState(false);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    fetchInstalledServers();

    return () => {
      // Cleanup: clear polling interval when component unmounts
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  // Check if any enabled server is connecting and start/stop polling accordingly
  useEffect(() => {
    const hasConnecting = installedServers.some(
      (server) =>
        server.enable && server.status === MCPSessionStatus.CONNECTING,
    );

    if (hasConnecting && !pollingIntervalRef.current) {
      // Start polling every 3 seconds
      pollingIntervalRef.current = setInterval(() => {
        fetchInstalledServers();
      }, 3000);
    } else if (!hasConnecting && pollingIntervalRef.current) {
      // Stop polling when no enabled server is connecting
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [installedServers]);

  function fetchInstalledServers() {
    setLoading(true);
    httpClient
      .getMCPServers()
      .then((resp) => {
        const servers = resp.servers.map((server) => new MCPCardVO(server));
        setInstalledServers(servers);
        setLoading(false);
      })
      .catch((error) => {
        console.error('Failed to fetch MCP servers:', error);
        setLoading(false);
      });
  }

  return (
    <div className="w-full h-full">
      {/* 已安装的服务器列表 */}
      <div className="w-full px-[0.8rem] pt-[0rem]  gap-4">
        {loading ? (
          <div className="flex flex-col items-center justify-center text-gray-500 h-[calc(100vh-16rem)] w-full gap-2">
            {t('mcp.loading')}
          </div>
        ) : installedServers.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-gray-500 h-[calc(100vh-16rem)] w-full gap-2">
            <svg
              className="h-[3rem] w-[3rem]"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M4.5 7.65311V16.3469L12 20.689L19.5 16.3469V7.65311L12 3.311L4.5 7.65311ZM12 1L21.5 6.5V17.5L12 23L2.5 17.5V6.5L12 1ZM6.49896 9.97065L11 12.5765V17.625H13V12.5765L17.501 9.97066L16.499 8.2398L12 10.8445L7.50104 8.2398L6.49896 9.97065Z"></path>
            </svg>
            <div className="text-lg mb-2">{t('mcp.noServerInstalled')}</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pt-[2rem]">
            {installedServers.map((server, index) => (
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
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
