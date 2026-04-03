import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Download,
  FileText,
  Database,
  AlertCircle,
  Users,
  Layers,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { backendClient } from '@/app/infra/http';
import { FilterState } from '../types/monitoring';

export type ExportType =
  | 'messages'
  | 'llm-calls'
  | 'embedding-calls'
  | 'errors'
  | 'sessions';

interface ExportDropdownProps {
  filterState: FilterState;
}

export function ExportDropdown({ filterState }: ExportDropdownProps) {
  const { t } = useTranslation();
  const [exporting, setExporting] = useState<ExportType | null>(null);

  const getDateRangeParams = (): { startTime: string; endTime: string } => {
    const now = new Date();
    let startTime: Date;
    let endTime: Date = now;

    switch (filterState.timeRange) {
      case 'lastHour':
        startTime = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case 'last6Hours':
        startTime = new Date(now.getTime() - 6 * 60 * 60 * 1000);
        break;
      case 'last24Hours':
        startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        break;
      case 'last7Days':
        startTime = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case 'last30Days':
        startTime = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        break;
      case 'custom':
        if (filterState.customDateRange) {
          startTime = filterState.customDateRange.from;
          endTime = filterState.customDateRange.to;
        } else {
          startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        }
        break;
      default:
        startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    }

    return {
      startTime: startTime.toISOString(),
      endTime: endTime.toISOString(),
    };
  };

  const handleExport = async (type: ExportType) => {
    setExporting(type);
    try {
      const { startTime, endTime } = getDateRangeParams();
      const params = new URLSearchParams({
        type,
        startTime,
        endTime,
      });

      if (filterState.selectedBots.length > 0) {
        filterState.selectedBots.forEach((botId) => {
          params.append('botId', botId);
        });
      }

      if (filterState.selectedPipelines.length > 0) {
        filterState.selectedPipelines.forEach((pipelineId) => {
          params.append('pipelineId', pipelineId);
        });
      }

      // Use backendClient's downloadFile method for blob response
      const response = await backendClient.downloadFile(
        `/api/v1/monitoring/export?${params.toString()}`,
      );

      // Get filename from content-disposition header
      const contentDisposition = response.headers['content-disposition'];
      let filename = `monitoring-${type}-${Date.now()}.csv`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(
          /filename="?([^";\n]+)"?/,
        );
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }

      // Create download link
      const blob = new Blob([response.data], {
        type: 'text/csv;charset=utf-8;',
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export data:', error);
    } finally {
      setExporting(null);
    }
  };

  const exportOptions: {
    type: ExportType;
    label: string;
    icon: React.ReactNode;
  }[] = [
    {
      type: 'messages',
      label: t('monitoring.export.messages'),
      icon: <FileText className="w-4 h-4 mr-2" />,
    },
    {
      type: 'llm-calls',
      label: t('monitoring.export.llmCalls'),
      icon: <Database className="w-4 h-4 mr-2" />,
    },
    {
      type: 'embedding-calls',
      label: t('monitoring.export.embeddingCalls'),
      icon: <Layers className="w-4 h-4 mr-2" />,
    },
    {
      type: 'errors',
      label: t('monitoring.export.errors'),
      icon: <AlertCircle className="w-4 h-4 mr-2" />,
    },
    {
      type: 'sessions',
      label: t('monitoring.export.sessions'),
      icon: <Users className="w-4 h-4 mr-2" />,
    },
  ];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="shadow-sm flex-shrink-0"
          disabled={exporting !== null}
        >
          {exporting ? (
            <>
              <svg
                className="w-4 h-4 mr-2 animate-spin"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              {t('monitoring.export.exporting')}
            </>
          ) : (
            <>
              <Download className="w-4 h-4 mr-2" />
              {t('monitoring.exportData')}
            </>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel>{t('monitoring.export.title')}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {exportOptions.map((option) => (
          <DropdownMenuItem
            key={option.type}
            onClick={() => handleExport(option.type)}
            disabled={exporting !== null}
            className="cursor-pointer"
          >
            {option.icon}
            {option.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
