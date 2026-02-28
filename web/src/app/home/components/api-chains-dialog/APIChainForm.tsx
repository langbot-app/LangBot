'use client';

import { useState, useEffect } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  APIChain,
  APIChainItem,
  APIChainModelConfig,
  LLMModel,
  ModelProvider,
} from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Plus, Trash2, GripVertical, ChevronDown, ChevronRight } from 'lucide-react';

interface APIChainFormProps {
  chainId?: string;
  providers: ModelProvider[];
  llmModels: LLMModel[];
  onFormSubmit: () => void;
  onFormCancel: () => void;
}

export default function APIChainForm({
  chainId,
  providers,
  llmModels,
  onFormSubmit,
  onFormCancel,
}: APIChainFormProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [chainConfig, setChainConfig] = useState<APIChainItem[]>([]);
  const [healthCheckEnabled, setHealthCheckEnabled] = useState(true);
  const [healthCheckInterval, setHealthCheckInterval] = useState(300);
  /** Track which provider item has model_configs expanded */
  const [expandedModelConfigs, setExpandedModelConfigs] = useState<Set<number>>(new Set());
  /** Track which provider item has advanced config expanded */
  const [expandedAdvanced, setExpandedAdvanced] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (chainId) {
      loadChain();
    } else {
      setChainConfig([
        {
          provider_uuid: '',
          priority: 1,
          is_aggregated: false,
          max_retries: 3,
          timeout_ms: 30000,
          model_configs: [],
        },
      ]);
    }
  }, [chainId]);

  async function loadChain() {
    try {
      setLoading(true);
      const resp = await httpClient.getAPIChain(chainId!);
      setName(resp.chain.name);
      setDescription(resp.chain.description || '');
      setChainConfig(resp.chain.chain_config);
      setHealthCheckEnabled(resp.chain.health_check_enabled);
      setHealthCheckInterval(resp.chain.health_check_interval);
    } catch (err) {
      toast.error(t('apiChains.loadError') + ': ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  /** Return models belonging to the given provider */
  function modelsForProvider(providerUuid: string): LLMModel[] {
    return llmModels.filter((m) => m.provider_uuid === providerUuid);
  }

  // ---- Provider item CRUD ----

  function addProvider() {
    const maxPriority = Math.max(...chainConfig.map((c) => c.priority), 0);
    setChainConfig([
      ...chainConfig,
      {
        provider_uuid: '',
        priority: maxPriority + 1,
        is_aggregated: false,
        max_retries: 3,
        timeout_ms: 30000,
        model_configs: [],
      },
    ]);
  }

  function removeProvider(index: number) {
    const newConfig = chainConfig.filter((_, i) => i !== index);
    newConfig.forEach((c, i) => { c.priority = i + 1; });
    setChainConfig(newConfig);
    setExpandedModelConfigs((prev) => {
      const next = new Set<number>();
      prev.forEach((v) => { if (v < index) next.add(v); else if (v > index) next.add(v - 1); });
      return next;
    });
    setExpandedAdvanced((prev) => {
      const next = new Set<number>();
      prev.forEach((v) => { if (v < index) next.add(v); else if (v > index) next.add(v - 1); });
      return next;
    });
  }

  function updateProvider(index: number, field: keyof APIChainItem, value: any) {
    const newConfig = [...chainConfig];
    newConfig[index] = { ...newConfig[index], [field]: value };
    // If provider changes, reset model_configs
    if (field === 'provider_uuid') {
      newConfig[index].model_configs = [];
    }
    setChainConfig(newConfig);
  }

  function moveProvider(index: number, direction: 'up' | 'down') {
    if ((direction === 'up' && index === 0) || (direction === 'down' && index === chainConfig.length - 1)) return;
    const newConfig = [...chainConfig];
    const target = direction === 'up' ? index - 1 : index + 1;
    [newConfig[index], newConfig[target]] = [newConfig[target], newConfig[index]];
    newConfig.forEach((c, i) => { c.priority = i + 1; });
    setChainConfig(newConfig);
  }

  // ---- Model config CRUD ----

  function addModelConfig(providerIndex: number) {
    const newConfig = [...chainConfig];
    const existing = newConfig[providerIndex].model_configs ?? [];
    const maxPriority = Math.max(...existing.map((m) => m.priority), 0);
    newConfig[providerIndex] = {
      ...newConfig[providerIndex],
      model_configs: [
        ...existing,
        { model_name: '', priority: maxPriority + 1 },
      ],
    };
    setChainConfig(newConfig);
  }

  function removeModelConfig(providerIndex: number, modelIndex: number) {
    const newConfig = [...chainConfig];
    const existing = (newConfig[providerIndex].model_configs ?? []).filter((_, i) => i !== modelIndex);
    existing.forEach((m, i) => { m.priority = i + 1; });
    newConfig[providerIndex] = { ...newConfig[providerIndex], model_configs: existing };
    setChainConfig(newConfig);
  }

  function updateModelConfig(providerIndex: number, modelIndex: number, field: keyof APIChainModelConfig, value: any) {
    const newConfig = [...chainConfig];
    const models = [...(newConfig[providerIndex].model_configs ?? [])];
    models[modelIndex] = { ...models[modelIndex], [field]: value };
    newConfig[providerIndex] = { ...newConfig[providerIndex], model_configs: models };
    setChainConfig(newConfig);
  }

  function moveModelConfig(providerIndex: number, modelIndex: number, direction: 'up' | 'down') {
    const models = [...(chainConfig[providerIndex].model_configs ?? [])];
    if ((direction === 'up' && modelIndex === 0) || (direction === 'down' && modelIndex === models.length - 1)) return;
    const target = direction === 'up' ? modelIndex - 1 : modelIndex + 1;
    [models[modelIndex], models[target]] = [models[target], models[modelIndex]];
    models.forEach((m, i) => { m.priority = i + 1; });
    const newConfig = [...chainConfig];
    newConfig[providerIndex] = { ...newConfig[providerIndex], model_configs: models };
    setChainConfig(newConfig);
  }

  // ---- Submit ----

  async function handleSubmit() {
    if (!name.trim()) { toast.error(t('apiChains.nameRequired')); return; }
    if (chainConfig.length === 0) { toast.error(t('apiChains.atLeastOneProvider')); return; }
    for (const config of chainConfig) {
      if (!config.provider_uuid) { toast.error(t('apiChains.selectAllProviders')); return; }
      for (const mc of config.model_configs ?? []) {
        if (!mc.model_name) { toast.error(t('apiChains.selectAllModels')); return; }
      }
    }

    setLoading(true);
    try {
      const data = {
        name,
        description: description || undefined,
        chain_config: chainConfig,
        health_check_enabled: healthCheckEnabled,
        health_check_interval: healthCheckInterval,
      };

      if (chainId) {
        await httpClient.updateAPIChain(chainId, data);
        toast.success(t('apiChains.updateSuccess'));
      } else {
        await httpClient.createAPIChain(data);
        toast.success(t('apiChains.createSuccess'));
      }
      onFormSubmit();
    } catch (err) {
      toast.error(
        t(chainId ? 'apiChains.updateError' : 'apiChains.createError') + ': ' + (err as Error).message,
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Name */}
      <div className="space-y-2">
        <Label htmlFor="name">{t('apiChains.name')}<span className="text-red-500 ml-1">*</span></Label>
        <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder={t('apiChains.namePlaceholder')} />
      </div>

      {/* Description */}
      <div className="space-y-2">
        <Label htmlFor="description">{t('apiChains.description')}</Label>
        <Textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder={t('apiChains.descriptionPlaceholder')} className="min-h-[60px]" />
      </div>

      {/* Provider Chain */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>{t('apiChains.providers')}<span className="text-red-500 ml-1">*</span></Label>
          <Button type="button" size="sm" variant="outline" onClick={addProvider}>
            <Plus className="h-4 w-4 mr-1" />
            {t('apiChains.addProvider')}
          </Button>
        </div>

        <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
          {chainConfig.map((config, idx) => {
            const providerModels = modelsForProvider(config.provider_uuid);
            const modelConfigsExpanded = expandedModelConfigs.has(idx);

            return (
              <div key={idx} className="border rounded-lg p-3 space-y-3 bg-accent/30">
                {/* Provider row */}
                <div className="flex items-start gap-2">
                  {/* Up/Down buttons */}
                  <div className="flex flex-col gap-0.5 pt-1">
                    <button type="button" onClick={() => moveProvider(idx, 'up')} disabled={idx === 0} className="p-0.5 hover:bg-accent rounded disabled:opacity-30">
                      <GripVertical className="h-3 w-3" />
                    </button>
                    <button type="button" onClick={() => moveProvider(idx, 'down')} disabled={idx === chainConfig.length - 1} className="p-0.5 hover:bg-accent rounded disabled:opacity-30">
                      <GripVertical className="h-3 w-3" />
                    </button>
                  </div>

                  <div className="flex-1 space-y-2">
                    {/* Provider selector */}
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium w-6">#{idx + 1}</span>
                      <Select value={config.provider_uuid} onValueChange={(v) => updateProvider(idx, 'provider_uuid', v)}>
                        <SelectTrigger className="flex-1">
                          <SelectValue placeholder={t('apiChains.selectProvider')} />
                        </SelectTrigger>
                        <SelectContent>
                          {providers.map((p) => (
                            <SelectItem key={p.uuid} value={p.uuid}>{p.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {/* Advanced config expander */}
                    <button
                      type="button"
                      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                      onClick={() =>
                        setExpandedAdvanced((prev) => {
                          const next = new Set(prev);
                          next.has(idx) ? next.delete(idx) : next.add(idx);
                          return next;
                        })
                      }
                    >
                      {expandedAdvanced.has(idx) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      {t('apiChains.advanced')}
                    </button>

                    {expandedAdvanced.has(idx) && (
                      <div className="space-y-2 pl-2 border-l-2 border-border">
                        {/* Retries / Timeout */}
                        <div className="grid grid-cols-2 gap-2">
                          <div className="space-y-1">
                            <Label className="text-xs">{t('apiChains.maxRetries')}</Label>
                            <Input type="number" min="0" value={config.max_retries} onChange={(e) => updateProvider(idx, 'max_retries', Number(e.target.value))} />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">{t('apiChains.timeout')}</Label>
                            <Input type="number" min="1000" step="1000" value={config.timeout_ms} onChange={(e) => updateProvider(idx, 'timeout_ms', Number(e.target.value))} />
                          </div>
                        </div>

                        {/* Aggregation toggle */}
                        <div className="flex items-center gap-2">
                          <Switch checked={config.is_aggregated} onCheckedChange={(v) => updateProvider(idx, 'is_aggregated', v)} />
                          <Label className="text-xs">{t('apiChains.aggregation')}</Label>
                        </div>
                      </div>
                    )}

                    {/* Model configs expander */}
                    {config.provider_uuid && (
                      <div className="mt-1">
                        <button
                          type="button"
                          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                          onClick={() =>
                            setExpandedModelConfigs((prev) => {
                              const next = new Set(prev);
                              next.has(idx) ? next.delete(idx) : next.add(idx);
                              return next;
                            })
                          }
                        >
                          {modelConfigsExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                          {t('apiChains.modelConfigs')}
                          {(config.model_configs?.length ?? 0) > 0 && (
                            <span className="ml-1 bg-primary/10 text-primary px-1.5 py-0.5 rounded text-[10px]">
                              {config.model_configs!.length}
                            </span>
                          )}
                        </button>

                        {modelConfigsExpanded && (
                          <div className="mt-2 space-y-2 pl-2 border-l-2 border-border">
                            <p className="text-xs text-muted-foreground">{t('apiChains.modelConfigsHint')}</p>

                            {(config.model_configs ?? []).map((mc, mi) => (
                              <div key={mi} className="border rounded p-2 space-y-2 bg-background">
                                {/* Model selector + move + delete */}
                                <div className="flex items-center gap-1">
                                  <div className="flex flex-col gap-0.5">
                                    <button type="button" onClick={() => moveModelConfig(idx, mi, 'up')} disabled={mi === 0} className="p-0.5 hover:bg-accent rounded disabled:opacity-30">
                                      <GripVertical className="h-3 w-3" />
                                    </button>
                                    <button type="button" onClick={() => moveModelConfig(idx, mi, 'down')} disabled={mi === (config.model_configs?.length ?? 0) - 1} className="p-0.5 hover:bg-accent rounded disabled:opacity-30">
                                      <GripVertical className="h-3 w-3" />
                                    </button>
                                  </div>
                                  <span className="text-xs font-medium w-5">#{mi + 1}</span>
                                  <Select value={mc.model_name} onValueChange={(v) => updateModelConfig(idx, mi, 'model_name', v)}>
                                    <SelectTrigger className="flex-1 h-8 text-xs">
                                      <SelectValue placeholder={t('apiChains.selectModel')} />
                                    </SelectTrigger>
                                    <SelectContent>
                                      {providerModels.map((m) => (
                                        <SelectItem key={m.uuid} value={m.name}>{m.name}</SelectItem>
                                      ))}
                                    </SelectContent>
                                  </Select>
                                  <Button type="button" variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => removeModelConfig(idx, mi)}>
                                    <Trash2 className="h-3 w-3" />
                                  </Button>
                                </div>
                              </div>
                            ))}

                            <Button type="button" variant="outline" size="sm" className="h-7 text-xs" onClick={() => addModelConfig(idx)}>
                              <Plus className="h-3 w-3 mr-1" />
                              {t('apiChains.addModelConfig')}
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeProvider(idx)}
                    disabled={chainConfig.length === 1}
                    className="text-destructive hover:text-destructive mt-0.5"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Health Check */}
      <div className="space-y-3 border-t pt-3">
        <div className="flex items-center justify-between">
          <Label>{t('apiChains.healthCheck')}</Label>
          <Switch checked={healthCheckEnabled} onCheckedChange={setHealthCheckEnabled} />
        </div>
        {healthCheckEnabled && (
          <div className="space-y-2">
            <Label htmlFor="interval">{t('apiChains.healthCheckInterval')}</Label>
            <Input id="interval" type="number" min="60" value={healthCheckInterval} onChange={(e) => setHealthCheckInterval(Number(e.target.value))} />
            <p className="text-xs text-muted-foreground">{t('apiChains.healthCheckIntervalHint')}</p>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="outline" onClick={onFormCancel} disabled={loading}>{t('common.cancel')}</Button>
        <Button onClick={handleSubmit} disabled={loading}>{loading ? t('common.saving') : t('common.save')}</Button>
      </div>
    </div>
  );
}
