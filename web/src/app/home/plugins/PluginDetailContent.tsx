

import { useEffect } from 'react';
import PluginForm from '@/app/home/plugins/components/plugin-installed/plugin-form/PluginForm';
import PluginReadme from '@/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Bug } from 'lucide-react';

/**
 * Plugin detail page content.
 * The `id` prop is the composite key "author/name".
 */
export default function PluginDetailContent({ id }: { id: string }) {
  const { t } = useTranslation();
  const { plugins, setDetailEntityName, refreshPlugins } = useSidebarData();

  // Parse "author/name" composite key
  const slashIndex = id.indexOf('/');
  const pluginAuthor = slashIndex >= 0 ? id.substring(0, slashIndex) : '';
  const pluginName = slashIndex >= 0 ? id.substring(slashIndex + 1) : id;

  const plugin = plugins.find((p) => p.id === id);

  // Set breadcrumb entity name
  useEffect(() => {
    setDetailEntityName(plugin?.name ?? `${pluginAuthor}/${pluginName}`);
    return () => setDetailEntityName(null);
  }, [plugin, pluginAuthor, pluginName, setDetailEntityName]);

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
        <h1 className="text-xl font-semibold">
          {pluginAuthor}/{pluginName}
        </h1>
        {plugin?.debug ? (
          <Badge
            variant="outline"
            className="text-[0.7rem] border-orange-400 text-orange-400"
          >
            <Bug className="size-3.5" />
            {t('plugins.debugging')}
          </Badge>
        ) : plugin?.installSource === 'github' ? (
          <Badge
            variant="outline"
            className="text-[0.7rem] border-blue-400 text-blue-400"
          >
            {t('plugins.fromGithub')}
          </Badge>
        ) : plugin?.installSource === 'local' ? (
          <Badge
            variant="outline"
            className="text-[0.7rem] border-green-400 text-green-400"
          >
            {t('plugins.fromLocal')}
          </Badge>
        ) : plugin?.installSource === 'marketplace' ? (
          <Badge
            variant="outline"
            className="text-[0.7rem] border-purple-400 text-purple-400"
          >
            {t('plugins.fromMarketplace')}
          </Badge>
        ) : null}
      </div>

      <div className="flex flex-1 flex-col md:flex-row overflow-hidden min-h-0 gap-6 max-w-full">
        {/* Left side - Config */}
        <div className="md:w-[380px] md:flex-shrink-0 overflow-y-auto overflow-x-hidden">
          <PluginForm
            pluginAuthor={pluginAuthor}
            pluginName={pluginName}
            onFormSubmit={handleFormSubmit}
          />
        </div>
        {/* Divider */}
        <div className="hidden md:block w-px bg-border shrink-0" />
        {/* Right side - Readme */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden min-w-0">
          <PluginReadme pluginAuthor={pluginAuthor} pluginName={pluginName} />
        </div>
      </div>
    </div>
  );
}
