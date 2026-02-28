'use client';

import { APIChain, APIChainStatus, LLMModel, ModelProvider } from '@/app/infra/entities/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Edit, Trash2, ChevronDown, ChevronRight, AlertCircle, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';

interface APIChainCardProps {
  chain: APIChain;
  providers: ModelProvider[];
  llmModels: LLMModel[];
  onEdit: () => void;
  onDelete: () => void;
}

function calculateHealthPercentage(statuses: APIChainStatus[] | undefined, totalProviders: number): number {
  if (!statuses || statuses.length === 0 || totalProviders === 0) return 100;
  const healthyCount = statuses.filter(s => s.is_healthy).length;
  return Math.round((healthyCount / statuses.length) * 100);
}

function getErrorStats(statuses: APIChainStatus[] | undefined): { totalFailures: number } {
  if (!statuses || statuses.length === 0) return { totalFailures: 0 };
  return { totalFailures: statuses.reduce((sum, s) => sum + (s.failure_count || 0), 0) };
}

function getHealthColorClass(healthPercentage: number): string {
  if (healthPercentage === 0) return 'border-destructive bg-destructive/5';
  if (healthPercentage < 50) return 'border-yellow-500 bg-yellow-500/5';
  return '';
}

function getHealthIcon(healthPercentage: number) {
  if (healthPercentage === 0) return <AlertCircle className="h-4 w-4 text-destructive" />;
  if (healthPercentage < 50) return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
  return <CheckCircle2 className="h-4 w-4 text-green-500" />;
}

export default function APIChainCard({ chain, providers, llmModels, onEdit, onDelete }: APIChainCardProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  const getProviderName = (uuid: string) => providers.find((p) => p.uuid === uuid)?.name ?? uuid;

  const sortedConfigs = [...chain.chain_config].sort((a, b) => a.priority - b.priority);

  const healthPercentage = useMemo(
    () => calculateHealthPercentage(chain.statuses, chain.chain_config.length),
    [chain.statuses, chain.chain_config.length],
  );

  const { totalFailures } = useMemo(() => getErrorStats(chain.statuses), [chain.statuses]);

  /** Get all status records for a given (provider, model_name, api_key_index) combination */
  function getStatus(
    providerUuid: string,
    modelName: string | null,
    apiKeyIndex: number | null,
  ): APIChainStatus | undefined {
    return chain.statuses?.find(
      (s) =>
        s.provider_uuid === providerUuid &&
        (s.model_name ?? null) === modelName &&
        (s.api_key_index ?? null) === apiKeyIndex,
    );
  }

  /** Get all status records for a provider (any granularity) */
  function getProviderStatuses(providerUuid: string): APIChainStatus[] {
    return chain.statuses?.filter((s) => s.provider_uuid === providerUuid) ?? [];
  }

  /** Compute provider-level health summary */
  function providerHealthSummary(providerUuid: string): { healthy: number; total: number } {
    const ss = getProviderStatuses(providerUuid);
    if (ss.length === 0) return { healthy: 1, total: 1 }; // assume healthy if no data
    return { healthy: ss.filter((s) => s.is_healthy).length, total: ss.length };
  }

  return (
    <Card className={cn('mb-3 transition-colors', getHealthColorClass(healthPercentage))}>
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <button onClick={() => setExpanded(!expanded)} className="p-0.5 hover:bg-accent rounded">
                {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              <h3 className="font-semibold text-base truncate">{chain.name}</h3>
              {getHealthIcon(healthPercentage)}
              <span className={cn(
                'text-xs px-2 py-0.5 rounded',
                healthPercentage === 0 ? 'bg-destructive/10 text-destructive' :
                healthPercentage < 50 ? 'bg-yellow-500/10 text-yellow-600' :
                'bg-green-500/10 text-green-600',
              )}>
                {healthPercentage}%
              </span>
            </div>
            {chain.description && (
              <p className="text-sm text-muted-foreground ml-6 mb-2">{chain.description}</p>
            )}
            <div className="text-xs text-muted-foreground ml-6">
              {t('apiChains.providerCount', { count: chain.chain_config.length })}
            </div>
          </div>
          <div className="flex gap-1 ml-2">
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onEdit}>
              <Edit className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={onDelete}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Expanded: per-provider / per-model / per-key health */}
        {expanded && (
          <div className="mt-3 ml-6 space-y-2 border-l-2 border-border pl-3">
            {sortedConfigs.map((config, index) => {
              const { healthy, total } = providerHealthSummary(config.provider_uuid);
              const providerHealthy = healthy === total;
              const modelConfigs = config.model_configs ?? [];

              return (
                <div
                  key={config.provider_uuid + index}
                  className={cn(
                    'text-sm p-2 rounded bg-accent/50 border-l-4',
                    providerHealthy ? 'border-l-green-500' : 'border-l-destructive',
                  )}
                >
                  {/* Provider row */}
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium">
                      {index + 1}. {getProviderName(config.provider_uuid)}
                    </span>
                    {config.is_aggregated && (
                      <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
                        {t('apiChains.aggregation')}
                      </span>
                    )}
                    <span className={cn(
                      'text-xs px-2 py-0.5 rounded',
                      providerHealthy ? 'bg-green-500/10 text-green-600' : 'bg-destructive/10 text-destructive',
                    )}>
                      {providerHealthy ? t('apiChains.healthy') : `${healthy}/${total}`}
                    </span>
                  </div>

                  {/* Per-model breakdown */}
                  {modelConfigs.length > 0 ? (
                    <div className="mt-1 space-y-1 pl-3 border-l border-border">
                      {[...modelConfigs].sort((a, b) => a.priority - b.priority).map((mc, mi) => {
                        const st = getStatus(config.provider_uuid, mc.model_name, null);
                        const modelHealthy = st ? st.is_healthy : true;
                        return (
                          <div key={mi} className="text-xs">
                            <div className="flex items-center gap-1.5">
                              <span className="text-muted-foreground">#{mi + 1}</span>
                              <span className="font-mono">{mc.model_name}</span>
                              <span className={cn(
                                'px-1.5 py-0.5 rounded',
                                modelHealthy ? 'bg-green-500/10 text-green-600' : 'bg-destructive/10 text-destructive',
                              )}>
                                {modelHealthy ? t('apiChains.healthy') : t('apiChains.unhealthy')}
                              </span>
                              {st && st.failure_count > 0 && (
                                <span className="text-destructive">{t('apiChains.failureCount')}: {st.failure_count}</span>
                              )}
                            </div>
                            {st?.last_error_message && (
                              <p className="text-destructive pl-4 truncate" title={st.last_error_message}>
                                {t('apiChains.lastError')}: {st.last_error_message}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    /* No model configs: show provider-level status detail */
                    <div className="text-xs text-muted-foreground space-y-0.5">
                      <div>{t('apiChains.maxRetries')}: {config.max_retries}</div>
                      <div>{t('apiChains.timeout')}: {config.timeout_ms}ms</div>
                      {(() => {
                        const st = getStatus(config.provider_uuid, null, null);
                        if (!st) return null;
                        return (
                          <>
                            {st.failure_count > 0 && (
                              <div className="text-destructive">
                                {t('apiChains.failureCount')}: {st.failure_count}
                              </div>
                            )}
                            {st.last_error_message && (
                              <div className="text-destructive truncate" title={st.last_error_message}>
                                {t('apiChains.lastError')}: {st.last_error_message}
                              </div>
                            )}
                          </>
                        );
                      })()}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Bottom summary */}
        <div className="flex justify-end mt-2 gap-4 text-xs text-muted-foreground">
          <span className={cn(totalFailures > 0 && 'text-destructive')}>
            {t('apiChains.errorCount')}: {totalFailures}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
