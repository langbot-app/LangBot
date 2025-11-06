'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { backendClient } from '@/app/infra/http';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Plus, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Plugin } from '@/app/infra/entities/plugin';
import PluginComponentList from '@/app/home/plugins/components/plugin-installed/PluginComponentList';

export default function PipelineExtension({
  pipelineId,
}: {
  pipelineId: string;
}) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [selectedPlugins, setSelectedPlugins] = useState<Plugin[]>([]);
  const [allPlugins, setAllPlugins] = useState<Plugin[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [tempSelectedIds, setTempSelectedIds] = useState<string[]>([]);

  useEffect(() => {
    loadExtensions();
  }, [pipelineId]);

  const getPluginId = (plugin: Plugin): string => {
    const author = plugin.manifest.manifest.metadata.author;
    const name = plugin.manifest.manifest.metadata.name;
    return `${author}/${name}`;
  };

  const loadExtensions = async () => {
    try {
      setLoading(true);
      const data = await backendClient.getPipelineExtensions(pipelineId);

      const boundPluginIds = new Set(
        data.bound_plugins.map((p) => `${p.author}/${p.name}`),
      );

      const selected = data.available_plugins.filter((plugin) =>
        boundPluginIds.has(getPluginId(plugin)),
      );

      setSelectedPlugins(selected);
      setAllPlugins(data.available_plugins);
    } catch (error) {
      console.error('Failed to load extensions:', error);
      toast.error(t('pipelines.extensions.loadError'));
    } finally {
      setLoading(false);
    }
  };

  const saveToBackend = async (plugins: Plugin[]) => {
    try {
      const boundPluginsArray = plugins.map((plugin) => {
        const metadata = plugin.manifest.manifest.metadata;
        return {
          author: metadata.author || '',
          name: metadata.name,
        };
      });

      await backendClient.updatePipelineExtensions(
        pipelineId,
        boundPluginsArray,
      );
      toast.success(t('pipelines.extensions.saveSuccess'));
    } catch (error) {
      console.error('Failed to save extensions:', error);
      toast.error(t('pipelines.extensions.saveError'));
      // Reload on error to restore correct state
      loadExtensions();
    }
  };

  const handleRemovePlugin = async (pluginId: string) => {
    const newPlugins = selectedPlugins.filter(
      (p) => getPluginId(p) !== pluginId,
    );
    setSelectedPlugins(newPlugins);
    await saveToBackend(newPlugins);
  };

  const handleOpenDialog = () => {
    setTempSelectedIds(selectedPlugins.map((p) => getPluginId(p)));
    setDialogOpen(true);
  };

  const handleTogglePlugin = (pluginId: string) => {
    setTempSelectedIds((prev) =>
      prev.includes(pluginId)
        ? prev.filter((id) => id !== pluginId)
        : [...prev, pluginId],
    );
  };

  const handleConfirmSelection = async () => {
    const newSelected = allPlugins.filter((p) =>
      tempSelectedIds.includes(getPluginId(p)),
    );
    setSelectedPlugins(newSelected);
    setDialogOpen(false);
    await saveToBackend(newSelected);
  };

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
    <div className="space-y-4">
      <div className="space-y-2">
        {selectedPlugins.length === 0 ? (
          <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border">
            <p className="text-sm text-muted-foreground">
              {t('pipelines.extensions.noPluginsSelected')}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {selectedPlugins.map((plugin) => {
              const pluginId = getPluginId(plugin);
              const metadata = plugin.manifest.manifest.metadata;
              return (
                <div
                  key={pluginId}
                  className="flex items-center justify-between rounded-lg border p-3 hover:bg-accent"
                >
                  <div className="flex-1 flex items-center gap-3">
                    <img
                      src={backendClient.getPluginIconURL(
                        metadata.author || '',
                        metadata.name,
                      )}
                      alt={metadata.name}
                      className="w-10 h-10 rounded-lg border bg-muted object-cover flex-shrink-0"
                    />
                    <div className="flex-1">
                      <div className="font-medium">{metadata.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {metadata.author} • v{metadata.version}
                      </div>
                      <div className="flex gap-1 mt-1">
                        <PluginComponentList
                          components={plugin.components}
                          showComponentName={true}
                          showTitle={false}
                          useBadge={true}
                          t={t}
                        />
                      </div>
                    </div>
                    {!plugin.enabled && (
                      <Badge variant="secondary">
                        {t('pipelines.extensions.disabled')}
                      </Badge>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemovePlugin(pluginId)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <Button onClick={handleOpenDialog} variant="outline" className="w-full">
        <Plus className="mr-2 h-4 w-4" />
        {t('pipelines.extensions.addPlugin')}
      </Button>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>{t('pipelines.extensions.selectPlugins')}</DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto space-y-2 pr-2">
            {allPlugins.map((plugin) => {
              const pluginId = getPluginId(plugin);
              const metadata = plugin.manifest.manifest.metadata;
              const isSelected = tempSelectedIds.includes(pluginId);
              return (
                <div
                  key={pluginId}
                  className="flex items-center gap-3 rounded-lg border p-3 hover:bg-accent cursor-pointer"
                  onClick={() => handleTogglePlugin(pluginId)}
                >
                  <Checkbox checked={isSelected} />
                  <img
                    src={backendClient.getPluginIconURL(
                      metadata.author || '',
                      metadata.name,
                    )}
                    alt={metadata.name}
                    className="w-10 h-10 rounded-lg border bg-muted object-cover flex-shrink-0"
                  />
                  <div className="flex-1">
                    <div className="font-medium">{metadata.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {metadata.author} • v{metadata.version}
                    </div>
                    <div className="flex gap-1 mt-1">
                      <PluginComponentList
                        components={plugin.components}
                        showComponentName={true}
                        showTitle={false}
                        useBadge={true}
                        t={t}
                      />
                    </div>
                  </div>
                  {!plugin.enabled && (
                    <Badge variant="secondary">
                      {t('pipelines.extensions.disabled')}
                    </Badge>
                  )}
                </div>
              );
            })}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleConfirmSelection}>
              {t('common.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
