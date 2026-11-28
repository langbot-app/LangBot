import type { TFunction } from 'i18next';
import { toast } from 'sonner';
import { httpClient } from '@/app/infra/http/HttpClient';
import { selectionIncludes } from '@/app/home/bots/components/bot-form/message-policy';

const BOT_FACING_KINDS = new Set(['Command', 'EventListener']);

/**
 * After a plugin with commands or listeners is installed, tell the user on
 * how many bots it is already enabled, or point them to enabling it.
 */
export async function showPluginEnablementHint(
  pluginId: string,
  t: TFunction,
  openBots: () => void,
): Promise<void> {
  const [author, name] = pluginId.split('/');
  if (!author || !name) return;
  const [{ plugin }, { bots }] = await Promise.all([
    httpClient.getPlugin(author, name),
    httpClient.getBots(),
  ]);
  const botFacing = (plugin.components ?? []).some((component) =>
    BOT_FACING_KINDS.has(component.manifest?.manifest?.kind),
  );
  if (!botFacing || bots.length === 0) return;
  const enabledOn = bots.filter((bot) =>
    selectionIncludes(bot.message_policy?.plugins, pluginId),
  ).length;
  if (enabledOn > 0) {
    toast.info(t('plugins.enabledOnBots', { count: enabledOn }));
    return;
  }
  toast.info(t('plugins.notEnabledOnBots'), {
    action: { label: t('plugins.goEnable'), onClick: openBots },
  });
}
