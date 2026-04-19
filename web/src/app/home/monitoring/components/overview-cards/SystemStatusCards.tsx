import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Plug, Box, CircleCheck, CircleX, Loader2 } from 'lucide-react';
import {
  ApiRespPluginSystemStatus,
  ApiRespBoxStatus,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';

interface StatusCardProps {
  icon: React.ReactNode;
  title: string;
  connected: boolean | null;
  connectedLabel: string;
  disconnectedLabel: string;
  details?: { label: string; value: string }[];
  loading: boolean;
}

function StatusCard({
  icon,
  title,
  connected,
  connectedLabel,
  disconnectedLabel,
  details,
  loading,
}: StatusCardProps) {
  return (
    <div className="bg-card rounded-xl border p-4 flex items-start gap-3">
      <div className="rounded-lg bg-muted p-2 text-muted-foreground">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        {loading ? (
          <div className="flex items-center gap-1.5 mt-1">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
          </div>
        ) : connected === null ? (
          <span className="text-sm text-muted-foreground">—</span>
        ) : connected ? (
          <div className="flex items-center gap-1.5 mt-0.5">
            <CircleCheck className="w-4 h-4 text-green-600" />
            <span className="text-sm font-semibold text-green-600">
              {connectedLabel}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 mt-0.5">
            <CircleX className="w-4 h-4 text-red-500" />
            <span className="text-sm font-semibold text-red-500">
              {disconnectedLabel}
            </span>
          </div>
        )}
        {!loading && details && details.length > 0 && (
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1 text-xs text-muted-foreground">
            {details.map((d) => (
              <span key={d.label}>
                {d.label}:{' '}
                <span className="text-foreground font-mono">{d.value}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function SystemStatusCards() {
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

  const pluginConnected = pluginStatus
    ? pluginStatus.is_enable && pluginStatus.is_connected
    : null;

  const pluginDetails: { label: string; value: string }[] = [];
  if (pluginStatus && !pluginStatus.is_enable) {
    pluginDetails.push({
      label: t('monitoring.statusDetail'),
      value: t('monitoring.pluginDisabled'),
    });
  }

  const boxConnected = boxStatus ? boxStatus.available : null;

  const boxDetails: { label: string; value: string }[] = [];
  if (boxStatus) {
    if (boxStatus.backend) {
      boxDetails.push({
        label: t('monitoring.boxBackend'),
        value: `${boxStatus.backend.name}`,
      });
    }
    boxDetails.push({
      label: t('monitoring.boxProfile'),
      value: boxStatus.profile,
    });
    if (boxStatus.available && boxStatus.active_sessions !== undefined) {
      boxDetails.push({
        label: t('monitoring.boxSandboxes'),
        value: String(boxStatus.active_sessions),
      });
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <StatusCard
        icon={<Plug className="w-4 h-4" />}
        title={t('monitoring.pluginRuntime')}
        connected={pluginConnected}
        connectedLabel={t('monitoring.connected')}
        disconnectedLabel={
          pluginStatus && !pluginStatus.is_enable
            ? t('monitoring.disabled')
            : t('monitoring.disconnected')
        }
        details={pluginDetails}
        loading={loading}
      />
      <StatusCard
        icon={<Box className="w-4 h-4" />}
        title={t('monitoring.boxRuntime')}
        connected={boxConnected}
        connectedLabel={t('monitoring.connected')}
        disconnectedLabel={t('monitoring.disconnected')}
        details={boxDetails}
        loading={loading}
      />
    </div>
  );
}
