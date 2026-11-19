import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import type {
  BotCommandSettings,
  PlatformCommandCapability,
  PlatformCommandSync,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';

export default function PlatformCommandRegistration({
  value,
  onChange,
  capability,
  names,
  botId,
  dirty,
}: {
  value: BotCommandSettings;
  onChange: (value: BotCommandSettings) => void;
  capability: PlatformCommandCapability;
  names: string[];
  botId?: string;
  dirty?: boolean;
}) {
  const { t } = useTranslation();
  const [state, setState] = useState<PlatformCommandSync>({});
  const [busy, setBusy] = useState(false);
  const registration = value.platform_commands ?? {
    enabled: false,
    selected: [],
  };
  const load = useCallback(async () => {
    if (!botId || botId === 'new') return;
    try {
      const { bot } = await httpClient.getBot(botId);
      setState({
        ...bot.platform_command_sync,
        rejected: bot.platform_command_registration?.rejected,
        error:
          bot.platform_command_sync?.error ??
          bot.platform_command_registration?.error,
      });
    } catch {
      toast.error(t('bots.platformCommands.failed'));
    }
  }, [botId, t]);
  useEffect(() => {
    if (!dirty) void load();
  }, [load, dirty]);
  async function sync() {
    if (!botId || busy || dirty) return;
    setBusy(true);
    try {
      setState(await httpClient.syncBotPlatformCommands(botId));
    } catch {
      toast.error(t('bots.platformCommands.failed'));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="space-y-3 rounded-lg border p-3"
      aria-label={t('bots.platformCommands.title')}
    >
      <label className="flex items-center justify-between gap-3 text-sm font-medium">
        {t('bots.platformCommands.title')}
        <Switch
          checked={registration.enabled}
          onCheckedChange={(enabled) =>
            onChange({
              ...value,
              platform_commands: { ...registration, enabled },
            })
          }
        />
      </label>
      {registration.enabled && (
        <>
          <div className="space-y-1 text-xs">
            <p className="text-amber-700 dark:text-amber-400">
              {t('bots.platformCommands.overwrite')}
            </p>
            {!value.prefixes.includes('/') && (
              <p className="text-amber-700 dark:text-amber-400">
                {t('bots.platformCommands.prefixWarning')}
              </p>
            )}
            <p className="text-muted-foreground">
              {t('bots.platformCommands.limits', {
                count: capability.max_commands,
                length: capability.description_max_length,
              })}{' '}
              <code>{capability.name_pattern}</code>
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {names.map((name) => (
              <label
                key={name}
                className="flex cursor-pointer items-center gap-1.5 rounded-md border px-2 py-1 text-xs has-[[data-state=checked]]:border-primary/50 has-[[data-state=checked]]:bg-primary/5"
              >
                <Checkbox
                  className="size-3.5"
                  checked={registration.selected.includes(name)}
                  onCheckedChange={(checked) =>
                    onChange({
                      ...value,
                      platform_commands: {
                        ...registration,
                        selected: checked
                          ? [...registration.selected, name]
                          : registration.selected.filter(
                              (item) => item !== name,
                            ),
                      },
                    })
                  }
                />
                <code>/{name}</code>
              </label>
            ))}
          </div>
        </>
      )}
      {!!state.rejected?.length && (
        <ul className="space-y-0.5 text-xs text-amber-700 dark:text-amber-400">
          {state.rejected.map((item) => (
            <li key={item.name}>
              {item.name}: {t(`bots.platformCommands.reasons.${item.reason}`)}
            </li>
          ))}
        </ul>
      )}
      {state.error && (
        <p role="alert" className="text-xs text-destructive">
          {t('bots.platformCommands.failed')}: {state.error}
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground" role="status">
          {dirty
            ? t('bots.platformCommands.saveFirst')
            : state.synced_at
              ? t('bots.platformCommands.synced', { time: state.synced_at })
              : t('bots.platformCommands.notSynced')}
        </p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs"
          disabled={!botId || botId === 'new' || dirty || busy}
          onClick={() => void sync()}
        >
          {t('bots.platformCommands.sync')}
        </Button>
      </div>
    </section>
  );
}
