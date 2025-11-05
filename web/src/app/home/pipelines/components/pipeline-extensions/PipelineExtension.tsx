'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { backendClient } from '@/app/infra/http';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

interface Plugin {
  plugin_author: string;
  plugin_name: string;
  version: string;
  description: string;
  enabled: boolean;
}

interface BoundPlugin {
  author: string;
  name: string;
}

export default function PipelineExtension({
  pipelineId,
}: {
  pipelineId: string;
}) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [availablePlugins, setAvailablePlugins] = useState<Plugin[]>([]);
  const [boundPlugins, setBoundPlugins] = useState<Set<string>>(new Set());
  const [initialBoundPlugins, setInitialBoundPlugins] = useState<Set<string>>(
    new Set(),
  );

  useEffect(() => {
    loadExtensions();
  }, [pipelineId]);

  const loadExtensions = async () => {
    try {
      setLoading(true);
      const data = await backendClient.getPipelineExtensions(pipelineId);

      setAvailablePlugins(data.available_plugins);

      // Convert bound plugins to a Set for easy lookup
      const boundSet = new Set(
        data.bound_plugins.map((p) => `${p.author}/${p.name}`),
      );
      setBoundPlugins(boundSet);
      setInitialBoundPlugins(new Set(boundSet));
    } catch (error) {
      console.error('Failed to load extensions:', error);
      toast.error(t('pipelines.extensions.loadError'));
    } finally {
      setLoading(false);
    }
  };

  const handleTogglePlugin = (pluginKey: string) => {
    const newBoundPlugins = new Set(boundPlugins);
    if (newBoundPlugins.has(pluginKey)) {
      newBoundPlugins.delete(pluginKey);
    } else {
      newBoundPlugins.add(pluginKey);
    }
    setBoundPlugins(newBoundPlugins);
  };

  const handleSave = async () => {
    try {
      setSaving(true);

      // Convert Set back to array of objects
      const boundPluginsArray = Array.from(boundPlugins).map((key) => {
        const [author, name] = key.split('/');
        return { author, name };
      });

      await backendClient.updatePipelineExtensions(
        pipelineId,
        boundPluginsArray,
      );
      setInitialBoundPlugins(new Set(boundPlugins));
      toast.success(t('pipelines.extensions.saveSuccess'));
    } catch (error) {
      console.error('Failed to save extensions:', error);
      toast.error(t('pipelines.extensions.saveError'));
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setBoundPlugins(new Set(initialBoundPlugins));
  };

  const hasChanges =
    JSON.stringify(Array.from(boundPlugins).sort()) !==
    JSON.stringify(Array.from(initialBoundPlugins).sort());

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {availablePlugins.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <p className="text-center text-muted-foreground">
                {t('pipelines.extensions.noPluginsAvailable')}
              </p>
            </CardContent>
          </Card>
        ) : (
          availablePlugins.map((plugin) => {
            const pluginKey = `${plugin.plugin_author}/${plugin.plugin_name}`;
            const isBound = boundPlugins.has(pluginKey);

            return (
              <Card
                key={pluginKey}
                className={
                  isBound ? 'border-primary' : 'border-muted hover:border-border'
                }
              >
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-3">
                      <Checkbox
                        id={pluginKey}
                        checked={isBound}
                        onCheckedChange={() => handleTogglePlugin(pluginKey)}
                        className="mt-1"
                      />
                      <div className="flex-1">
                        <CardTitle className="text-base">
                          {plugin.plugin_name}
                        </CardTitle>
                        <CardDescription className="text-sm">
                          {plugin.plugin_author} • v{plugin.version}
                        </CardDescription>
                      </div>
                    </div>
                    {!plugin.enabled && (
                      <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
                        {t('pipelines.extensions.disabled')}
                      </span>
                    )}
                  </div>
                </CardHeader>
                {plugin.description && (
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {plugin.description}
                    </p>
                  </CardContent>
                )}
              </Card>
            );
          })
        )}
      </div>

      {hasChanges && (
        <div className="flex justify-end gap-2 pt-4 border-t sticky bottom-0 bg-white dark:bg-black z-10">
          <Button
            type="button"
            variant="outline"
            onClick={handleCancel}
            disabled={saving}
          >
            {t('common.cancel')}
          </Button>
          <Button type="button" onClick={handleSave} disabled={saving}>
            {saving ? t('common.saving') : t('common.save')}
          </Button>
        </div>
      )}
    </div>
  );
}
