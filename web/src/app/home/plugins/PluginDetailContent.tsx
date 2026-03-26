'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import PluginForm from '@/app/home/plugins/components/plugin-installed/plugin-form/PluginForm';
import PluginReadme from '@/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { ArrowLeft } from 'lucide-react';

/**
 * Plugin detail page content.
 * The `id` prop is the composite key "author/name".
 */
export default function PluginDetailContent({ id }: { id: string }) {
  const router = useRouter();
  const { t } = useTranslation();
  const { plugins, setDetailEntityName, refreshPlugins } = useSidebarData();

  // Parse "author/name" composite key
  const slashIndex = id.indexOf('/');
  const pluginAuthor = slashIndex >= 0 ? id.substring(0, slashIndex) : '';
  const pluginName = slashIndex >= 0 ? id.substring(slashIndex + 1) : id;

  // Set breadcrumb entity name
  useEffect(() => {
    const plugin = plugins.find((p) => p.id === id);
    setDetailEntityName(plugin?.name ?? `${pluginAuthor}/${pluginName}`);
    return () => setDetailEntityName(null);
  }, [id, plugins, pluginAuthor, pluginName, setDetailEntityName]);

  function handleBack() {
    router.push('/home/plugins');
  }

  function handleFormSubmit(timeout?: number) {
    if (timeout) {
      setTimeout(() => {
        refreshPlugins();
      }, timeout);
    } else {
      refreshPlugins();
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 pb-4 shrink-0">
        <Button variant="ghost" size="icon" onClick={handleBack}>
          <ArrowLeft className="size-4" />
        </Button>
        <h1 className="text-xl font-semibold">
          {pluginAuthor}/{pluginName}
        </h1>
      </div>

      <div className="flex flex-1 flex-row overflow-hidden min-h-0 gap-6 max-w-full">
        {/* Left side - Config */}
        <div className="w-[380px] flex-shrink-0 overflow-y-auto">
          <PluginForm
            pluginAuthor={pluginAuthor}
            pluginName={pluginName}
            onFormSubmit={handleFormSubmit}
            onFormCancel={handleBack}
          />
        </div>
        {/* Right side - Readme */}
        <div className="flex-1 overflow-y-auto min-w-0">
          <PluginReadme pluginAuthor={pluginAuthor} pluginName={pluginName} />
        </div>
      </div>
    </div>
  );
}
