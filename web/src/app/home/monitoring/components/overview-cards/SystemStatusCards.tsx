import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Plug,
  Box,
  CircleCheck,
  CircleX,
  Loader2,
  ChevronDown,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  ApiRespPluginSystemStatus,
  ApiRespBoxStatus,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';

function StatusDot({ ok }: { ok: boolean | null }) {
  if (ok === null)
    return <span className="w-2 h-2 rounded-full bg-muted-foreground/40" />;
  return ok ? (
    <span className="w-2 h-2 rounded-full bg-green-500" />
  ) : (
    <span className="w-2 h-2 rounded-full bg-red-500" />
  );
}

export default function SystemStatusCard() {
  const { t } = useTranslation();
  const [pluginStatus, setPluginStatus] =
    useState<ApiRespPluginSystemStatus | null>(null);
  const [boxStatus, setBoxStatus] = useState<ApiRespBoxStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const [plugin, box] = await Promise.all([
        httpClient.getPluginSystemStatus().catch(() => null),
        httpClient.getBoxStatus().catch(() => null),
      ]);
      setPluginStatus(plugin);
      setBoxStatus(box);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const pluginOk = pluginStatus
    ? pluginStatus.is_enable && pluginStatus.is_connected
    : null;
  const boxOk = boxStatus ? boxStatus.available : null;

  if (loading) {
    return (
      <Card className="transition-all duration-300">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {t('monitoring.systemStatus')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Card className="transition-all duration-300 group cursor-pointer hover:border-primary/30">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {t('monitoring.systemStatus')}
            </CardTitle>
            <ChevronDown className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" />
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center gap-2">
              <StatusDot ok={pluginOk} />
              <Plug className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-sm">{t('monitoring.pluginRuntime')}</span>
            </div>
            <div className="flex items-center gap-2">
              <StatusDot ok={boxOk} />
              <Box className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-sm">{t('monitoring.boxRuntime')}</span>
            </div>
          </CardContent>
        </Card>
      </PopoverTrigger>
      <PopoverContent className="w-72" align="start">
        <div className="space-y-3">
          {/* Plugin Runtime */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Plug className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">
                {t('monitoring.pluginRuntime')}
              </span>
            </div>
            <div className="ml-6 text-xs space-y-0.5">
              <div className="flex items-center gap-1.5">
                {pluginOk ? (
                  <CircleCheck className="w-3.5 h-3.5 text-green-600" />
                ) : (
                  <CircleX className="w-3.5 h-3.5 text-red-500" />
                )}
                <span className={pluginOk ? 'text-green-600' : 'text-red-500'}>
                  {pluginOk
                    ? t('monitoring.connected')
                    : pluginStatus && !pluginStatus.is_enable
                      ? t('monitoring.disabled')
                      : t('monitoring.disconnected')}
                </span>
              </div>
              {pluginStatus && !pluginStatus.is_enable && (
                <p className="text-muted-foreground">
                  {t('monitoring.pluginDisabled')}
                </p>
              )}
              {pluginStatus &&
                !pluginOk &&
                pluginStatus.is_enable &&
                pluginStatus.plugin_connector_error &&
                pluginStatus.plugin_connector_error !== 'ok' && (
                  <p className="text-red-400 break-all">
                    {pluginStatus.plugin_connector_error}
                  </p>
                )}
            </div>
          </div>

          <div className="border-t" />

          {/* Box Runtime */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Box className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">
                {t('monitoring.boxRuntime')}
              </span>
            </div>
            <div className="ml-6 text-xs space-y-0.5">
              <div className="flex items-center gap-1.5">
                {boxOk ? (
                  <CircleCheck className="w-3.5 h-3.5 text-green-600" />
                ) : (
                  <CircleX className="w-3.5 h-3.5 text-red-500" />
                )}
                <span className={boxOk ? 'text-green-600' : 'text-red-500'}>
                  {boxOk
                    ? t('monitoring.connected')
                    : t('monitoring.disconnected')}
                </span>
              </div>
              {boxStatus && !boxOk && boxStatus.connector_error && (
                <p className="text-red-400 break-all">
                  {boxStatus.connector_error}
                </p>
              )}
              {boxStatus && (
                <div className="text-muted-foreground space-y-0.5">
                  {boxStatus.backend && (
                    <p>
                      {t('monitoring.boxBackend')}:{' '}
                      <span className="text-foreground font-mono">
                        {boxStatus.backend.name}
                      </span>
                    </p>
                  )}
                  <p>
                    {t('monitoring.boxProfile')}:{' '}
                    <span className="text-foreground font-mono">
                      {boxStatus.profile}
                    </span>
                  </p>
                  {boxOk && boxStatus.active_sessions !== undefined && (
                    <p>
                      {t('monitoring.boxSandboxes')}:{' '}
                      <span className="text-foreground font-mono">
                        {boxStatus.active_sessions}
                      </span>
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
