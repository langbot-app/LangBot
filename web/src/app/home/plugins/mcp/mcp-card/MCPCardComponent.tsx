import { MCPCardVO } from '@/app/home/plugins/mcp/MCPCardVO';
import { useState, useEffect } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

export default function MCPCardComponent({
  cardVO,
  onCardClick,
  onRefresh,
}: {
  cardVO: MCPCardVO;
  onCardClick: () => void;
  onRefresh: () => void;
}) {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(cardVO.enable);
  const [switchEnable, setSwitchEnable] = useState(true);
  const [testing, setTesting] = useState(false);
  const [toolsCount, setToolsCount] = useState(cardVO.tools);
  const [status, setStatus] = useState(cardVO.status);
  const [error, setError] = useState(cardVO.error);

  // 响应cardVO的变化，更新本地状态
  useEffect(() => {
    console.log(`[MCPCard ${cardVO.name}] Status updated:`, {
      status: cardVO.status,
      tools: cardVO.tools,
      error: cardVO.error,
    });
    setStatus(cardVO.status);
    setError(cardVO.error);
    setToolsCount(cardVO.tools);
    setEnabled(cardVO.enable);
  }, [cardVO.name, cardVO.status, cardVO.error, cardVO.tools, cardVO.enable]);

  function getStatusColor(): string {
    switch (status) {
      case 'connected':
        return 'text-green-600';
      case 'disconnected':
        return 'text-gray-500';
      case 'error':
        return 'text-red-600';
      case 'disabled':
        return 'text-gray-400';
      default:
        return 'text-gray-500';
    }
  }

  function getStatusIcon(): string {
    switch (status) {
      case 'connected':
        return 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z';
      case 'disconnected':
        return 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z';
      case 'error':
        return 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z';
      case 'disabled':
        return 'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636';
      default:
        return 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z';
    }
  }

  function handleEnable(checked: boolean) {
    setSwitchEnable(false);
    httpClient
      .toggleMCPServer(cardVO.name, checked)
      .then(() => {
        setEnabled(checked);
        toast.success(t('mcp.saveSuccess'));
        onRefresh();
        setSwitchEnable(true);
      })
      .catch((err) => {
        toast.error(t('mcp.modifyFailed') + err.message);
        setSwitchEnable(true);
      });
  }

  function handleTest(e: React.MouseEvent) {
    e.stopPropagation(); // 阻止事件冒泡
    setTesting(true);
    httpClient
      .testMCPServer(cardVO.name)
      .then((resp) => {
        const taskId = resp.task_id;
        // 监控任务状态
        const interval = setInterval(() => {
          httpClient.getAsyncTask(taskId).then((taskResp) => {
            if (taskResp.runtime.done) {
              clearInterval(interval);
              if (taskResp.runtime.exception) {
                toast.error(t('mcp.testFailed') + taskResp.runtime.exception);
              } else {
                // 解析测试结果获取工具数量
                try {
                  const rawResult = taskResp.runtime.result as
                    | string
                    | {
                        status?: string;
                        tools_count?: number;
                        tools_names_lists?: string[];
                        error?: string;
                      }
                    | undefined;

                  if (rawResult) {
                    let result: {
                      status?: string;
                      tools_count?: number;
                      tools_names_lists?: string[];
                      error?: string;
                    };

                    if (typeof rawResult === 'string') {
                      result = JSON.parse(rawResult.replace(/'/g, '"'));
                    } else {
                      result = rawResult;
                    }

                    if (result.tools_count !== undefined) {
                      setToolsCount(result.tools_count);
                      toast.success(
                        t('mcp.testSuccess') +
                          ` - ${result.tools_count} ${t('mcp.toolsFound')}`,
                      );
                    } else {
                      toast.success(t('mcp.testSuccess'));
                    }
                  } else {
                    toast.success(t('mcp.testSuccess'));
                  }
                } catch (parseError) {
                  console.error('Failed to parse test result:', parseError);
                  toast.success(t('mcp.testSuccess'));
                }
                onRefresh();
              }
              setTesting(false);
            }
          });
        }, 1000);
      })
      .catch((err) => {
        toast.error(t('mcp.testFailed') + err.message);
        setTesting(false);
      });
  }

  return (
    <div
      className="w-[100%] h-[10rem] bg-white rounded-[10px] shadow-[0px_2px_2px_0_rgba(0,0,0,0.2)] p-[1.2rem] cursor-pointer"
      onClick={onCardClick}
    >
      <div className="w-full h-full flex flex-row items-start justify-start gap-[1.2rem]">
        <svg
          className="w-16 h-16 text-[#2288ee]"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M13.5 2C13.5 2.82843 14.1716 3.5 15 3.5C15.8284 3.5 16.5 2.82843 16.5 2C16.5 1.17157 15.8284 0.5 15 0.5C14.1716 0.5 13.5 1.17157 13.5 2ZM8.5 8C8.5 8.82843 9.17157 9.5 10 9.5C10.8284 9.5 11.5 8.82843 11.5 8C11.5 7.17157 10.8284 6.5 10 6.5C9.17157 6.5 8.5 7.17157 8.5 8ZM1.5 14C1.5 14.8284 2.17157 15.5 3 15.5C3.82843 15.5 4.5 14.8284 4.5 14C4.5 13.1716 3.82843 12.5 3 12.5C2.17157 12.5 1.5 13.1716 1.5 14ZM19.5 14C19.5 14.8284 20.1716 15.5 21 15.5C21.8284 15.5 22.5 14.8284 22.5 14C22.5 13.1716 21.8284 12.5 21 12.5C20.1716 12.5 19.5 13.1716 19.5 14ZM8.5 20C8.5 20.8284 9.17157 21.5 10 21.5C10.8284 21.5 11.5 20.8284 11.5 20C11.5 19.1716 10.8284 19 10 19C9.17157 19 8.5 19.1716 8.5 20ZM2.5 8L6.5 8L6.5 10L2.5 10L2.5 8ZM13.5 8L17.5 8L17.5 10L13.5 10L13.5 8ZM8.5 2L8.5 6L10.5 6L10.5 2L8.5 2ZM8.5 14L8.5 18L10.5 18L10.5 14L8.5 14ZM2.5 14L6.5 14L6.5 16L2.5 16L2.5 14ZM13.5 14L17.5 14L17.5 16L13.5 16L13.5 14Z"></path>
        </svg>

        <div className="w-full h-full flex flex-col items-start justify-between gap-[0.6rem]">
          <div className="flex flex-col items-start justify-start">
            <div className="flex flex-col items-start justify-start">
              <div className="flex flex-row items-center justify-start gap-[0.4rem]">
                <div className="text-[1.2rem] text-black">{cardVO.name}</div>
                <Badge variant="outline" className="text-[0.7rem]">
                  {cardVO.mode.toUpperCase()}
                </Badge>
              </div>
            </div>

            <div className="flex flex-row items-center justify-start gap-[0.4rem] mt-1">
              <svg
                className={`w-4 h-4 ${getStatusColor()}`}
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d={getStatusIcon()}
                />
              </svg>
              <div className={`text-[0.8rem] ${getStatusColor()}`}>
                {status === 'connected' && t('mcp.statusConnected')}
                {status === 'disconnected' && t('mcp.statusDisconnected')}
                {status === 'error' && t('mcp.statusError')}
                {status === 'disabled' && t('mcp.statusDisabled')}
              </div>
            </div>

            {error && (
              <div className="text-[0.7rem] text-red-500 line-clamp-2 mt-1">
                {error}
              </div>
            )}
          </div>

          <div className="w-full flex flex-row items-start justify-start gap-[0.6rem]">
            <div className="flex h-full flex-row items-center justify-center gap-[0.4rem]">
              <svg
                className="w-[1.2rem] h-[1.2rem] text-black"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M5.32943 3.27158C6.56252 2.8332 7.9923 3.10749 8.97927 4.09446C10.1002 5.21537 10.3019 6.90741 9.5843 8.23385L20.293 18.9437L18.8788 20.3579L8.16982 9.64875C6.84325 10.3669 5.15069 10.1654 4.02952 9.04421C3.04227 8.05696 2.7681 6.62665 3.20701 5.39332L5.44373 7.63C6.02952 8.21578 6.97927 8.21578 7.56505 7.63C8.15084 7.04421 8.15084 6.09446 7.56505 5.50868L5.32943 3.27158ZM15.6968 5.15512L18.8788 3.38736L20.293 4.80157L18.5252 7.98355L16.7574 8.3371L14.6361 10.4584L13.2219 9.04421L15.3432 6.92289L15.6968 5.15512ZM8.97927 13.2868L10.3935 14.7011L5.09018 20.0044C4.69966 20.3949 4.06649 20.3949 3.67597 20.0044C3.31334 19.6417 3.28744 19.0699 3.59826 18.6774L3.67597 18.5902L8.97927 13.2868Z" />
              </svg>
              <div className="text-base text-black font-medium">
                {t('mcp.toolCount', { count: toolsCount })}
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-center justify-between h-full">
          <div
            className="flex items-center justify-center"
            onClick={(e) => e.stopPropagation()}
          >
            <Switch
              className="cursor-pointer"
              checked={enabled}
              onCheckedChange={handleEnable}
              disabled={!switchEnable}
            />
          </div>

          <div className="flex items-center justify-center gap-[0.4rem]">
            <Button
              variant="ghost"
              size="sm"
              className="p-1 h-8 w-8"
              onClick={(e) => handleTest(e)}
              disabled={testing}
            >
              <svg
                className={`w-4 h-4 text-gray-600 ${
                  testing ? 'animate-spin' : ''
                }`}
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
