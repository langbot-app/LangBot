import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Plug,
  Box,
  CircleCheck,
  CircleX,
  Loader2,
  Info,
  Container,
  Clock,
  Timer,
  Cpu,
  HardDrive,
  Network,
  Image,
  FolderOpen,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  ApiRespPluginSystemStatus,
  ApiRespBoxStatus,
  BoxSessionInfo,
} from '@/app/infra/entities/api';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
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

interface SystemStatusCardProps {
  refreshKey?: number;
}

export default function SystemStatusCard({
  refreshKey,
}: SystemStatusCardProps) {
  const { t } = useTranslation();
  const [pluginStatus, setPluginStatus] =
    useState<ApiRespPluginSystemStatus | null>(null);
  const [boxStatus, setBoxStatus] = useState<ApiRespBoxStatus | null>(null);
  const [boxSessions, setBoxSessions] = useState<BoxSessionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const [plugin, box, sessions] = await Promise.all([
        httpClient.getPluginSystemStatus().catch(() => null),
        httpClient.getBoxStatus().catch(() => null),
        httpClient.getBoxSessions().catch(() => [] as BoxSessionInfo[]),
      ]);
      setPluginStatus(plugin);
      setBoxStatus(box);
      setBoxSessions(sessions);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30_000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchStatus, refreshKey]);

  const pluginOk = pluginStatus
    ? pluginStatus.is_enable && pluginStatus.is_connected
    : null;
  const boxOk = boxStatus ? boxStatus.available : null;

  const handleOpenDialog = (e: React.MouseEvent) => {
    e.stopPropagation();
    fetchStatus();
    setDialogOpen(true);
  };

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
    <>
      <Card className="transition-all duration-300 group">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {t('monitoring.systemStatus')}
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={handleOpenDialog}
          >
            <Info className="w-4 h-4" />
          </Button>
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

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>{t('monitoring.systemStatus')}</DialogTitle>
          </DialogHeader>

          <TooltipProvider>
            <div className="space-y-5 overflow-y-auto flex-1 pr-1">
              {/* Plugin Runtime */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Plug className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm font-semibold">
                    {t('monitoring.pluginRuntime')}
                  </span>
                </div>
                <div className="ml-6 text-sm space-y-1">
                  <div className="flex items-center gap-1.5">
                    {pluginOk ? (
                      <CircleCheck className="w-4 h-4 text-green-600" />
                    ) : (
                      <CircleX className="w-4 h-4 text-red-500" />
                    )}
                    <span
                      className={
                        pluginOk
                          ? 'text-green-600 font-medium'
                          : 'text-red-500 font-medium'
                      }
                    >
                      {pluginOk
                        ? t('monitoring.connected')
                        : pluginStatus && !pluginStatus.is_enable
                          ? t('monitoring.disabled')
                          : t('monitoring.disconnected')}
                    </span>
                  </div>
                  {pluginStatus && !pluginStatus.is_enable && (
                    <p className="text-muted-foreground text-xs">
                      {t('monitoring.pluginDisabled')}
                    </p>
                  )}
                  {pluginStatus &&
                    !pluginOk &&
                    pluginStatus.is_enable &&
                    pluginStatus.plugin_connector_error &&
                    pluginStatus.plugin_connector_error !== 'ok' && (
                      <p className="text-red-400 text-xs break-all">
                        {pluginStatus.plugin_connector_error}
                      </p>
                    )}
                </div>
              </div>

              <div className="border-t" />

              {/* Box Runtime */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Box className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm font-semibold">
                    {t('monitoring.boxRuntime')}
                  </span>
                </div>
                <div className="ml-6 text-sm space-y-1">
                  <div className="flex items-center gap-1.5">
                    {boxOk ? (
                      <CircleCheck className="w-4 h-4 text-green-600" />
                    ) : (
                      <CircleX className="w-4 h-4 text-red-500" />
                    )}
                    <span
                      className={
                        boxOk
                          ? 'text-green-600 font-medium'
                          : 'text-red-500 font-medium'
                      }
                    >
                      {boxOk
                        ? t('monitoring.connected')
                        : t('monitoring.disconnected')}
                    </span>
                  </div>
                  {boxStatus && !boxOk && boxStatus.connector_error && (
                    <p className="text-red-400 text-xs break-all">
                      {boxStatus.connector_error}
                    </p>
                  )}
                  {boxStatus && (
                    <div className="text-muted-foreground text-xs space-y-0.5">
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

                  {/* Active Sandboxes */}
                  {boxSessions.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {boxSessions.map((session) => (
                        <div
                          key={session.session_id}
                          className="rounded-lg border p-3 space-y-2"
                        >
                          <div className="flex items-center gap-1.5 min-w-0">
                            <Container className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="font-mono font-semibold text-foreground truncate text-sm">
                                  {session.session_id}
                                </span>
                              </TooltipTrigger>
                              <TooltipContent>
                                {session.session_id}
                              </TooltipContent>
                            </Tooltip>
                          </div>
                          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                            <div className="flex items-center gap-1.5 text-muted-foreground min-w-0">
                              <Image className="w-3 h-3 flex-shrink-0" />
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span className="text-foreground font-mono truncate">
                                    {session.image}
                                  </span>
                                </TooltipTrigger>
                                <TooltipContent>{session.image}</TooltipContent>
                              </Tooltip>
                            </div>
                            <div className="flex items-center gap-1.5 text-muted-foreground">
                              <HardDrive className="w-3 h-3 flex-shrink-0" />
                              <span className="text-foreground">
                                {session.backend_name}
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5 text-muted-foreground">
                              <Cpu className="w-3 h-3 flex-shrink-0" />
                              <span className="text-foreground">
                                {session.cpus} CPU / {session.memory_mb} MB
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5 text-muted-foreground">
                              <Network className="w-3 h-3 flex-shrink-0" />
                              <span className="text-foreground">
                                {session.network}
                              </span>
                            </div>
                            {session.host_path && (
                              <div className="flex items-center gap-1.5 text-muted-foreground col-span-2 min-w-0">
                                <FolderOpen className="w-3 h-3 flex-shrink-0" />
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <span className="text-foreground font-mono truncate">
                                      {session.host_path} : {session.mount_path}{' '}
                                      <span className="text-muted-foreground">
                                        ({session.host_path_mode})
                                      </span>
                                    </span>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    {session.host_path} : {session.mount_path} (
                                    {session.host_path_mode})
                                  </TooltipContent>
                                </Tooltip>
                              </div>
                            )}
                            <div className="flex items-center gap-1.5 text-muted-foreground">
                              <Clock className="w-3 h-3 flex-shrink-0" />
                              <span>
                                {t('monitoring.boxSessionCreated')}:{' '}
                                <span className="text-foreground">
                                  {new Date(
                                    session.created_at,
                                  ).toLocaleString()}
                                </span>
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5 text-muted-foreground">
                              <Clock className="w-3 h-3 flex-shrink-0" />
                              <span>
                                {t('monitoring.boxSessionLastUsed')}:{' '}
                                <span className="text-foreground">
                                  {new Date(
                                    session.last_used_at,
                                  ).toLocaleString()}
                                </span>
                              </span>
                            </div>
                            {boxStatus?.session_ttl_sec != null &&
                              boxStatus.session_ttl_sec > 0 &&
                              (() => {
                                const elapsed =
                                  (Date.now() -
                                    new Date(session.last_used_at).getTime()) /
                                  1000;
                                const remaining = Math.max(
                                  0,
                                  boxStatus.session_ttl_sec! - elapsed,
                                );
                                const mins = Math.floor(remaining / 60);
                                const secs = Math.floor(remaining % 60);
                                return (
                                  <div className="flex items-center gap-1.5 text-muted-foreground col-span-2">
                                    <Timer className="w-3 h-3 flex-shrink-0" />
                                    <span>
                                      {t('monitoring.boxSessionTTL')}:{' '}
                                      <span
                                        className={
                                          remaining <= 60
                                            ? 'text-amber-600 font-medium'
                                            : 'text-foreground'
                                        }
                                      >
                                        {remaining <= 0
                                          ? t('monitoring.boxSessionExpiring')
                                          : `${mins}m ${secs.toString().padStart(2, '0')}s`}
                                      </span>
                                    </span>
                                  </div>
                                );
                              })()}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </TooltipProvider>
        </DialogContent>
      </Dialog>
    </>
  );
}
