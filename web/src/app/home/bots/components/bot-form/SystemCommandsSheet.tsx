import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  ChevronRight,
  Command,
  ExternalLink,
  Lock,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useBotAdmins } from '@/app/home/bots/components/bot-admins/BotAdminsDialog';
import type {
  BotCommandSettings,
  BuiltinCommandDescriptor,
  CommandPermission,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

const k = (key: string) => `bots.systemCommands.${key}`;
const GROUPS = ['session', 'info', 'admin'] as const;

/** A plugin command that can be given a permission. */
export interface PluginCommandEntry {
  /** `author/plugin/command` */
  key: string;
  command: string;
  pluginLabel: string;
}

/** Effective state of a built-in command: stored override or its default. */
export function builtinState(
  settings: BotCommandSettings,
  command: BuiltinCommandDescriptor,
) {
  const stored = settings.builtin?.[command.name];
  return {
    enabled: stored?.enabled ?? command.default_enabled,
    permission: stored?.permission ?? command.default_permission,
  };
}

let cached: BuiltinCommandDescriptor[] | null = null;

/** Built-in command catalogue (static per Core version, cached per page). */
export function useBuiltinCommands() {
  const [commands, setCommands] = useState<BuiltinCommandDescriptor[] | null>(
    cached,
  );
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (cached) return;
    let cancelled = false;
    httpClient
      .getBuiltinCommands()
      .then(({ commands: list }) => {
        cached = list;
        if (!cancelled) setCommands(list);
      })
      .catch(() => {
        // Older Core without system commands: the entry stays hidden.
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return { commands, failed };
}

function PermissionSelect({
  value,
  onChange,
  disabled,
  label,
}: {
  value: CommandPermission;
  onChange: (value: CommandPermission) => void;
  disabled?: boolean;
  label: string;
}) {
  const { t } = useTranslation();
  return (
    <Select
      value={value}
      disabled={disabled}
      onValueChange={(next) => onChange(next as CommandPermission)}
    >
      <SelectTrigger size="sm" className="h-7 w-28 text-xs" aria-label={label}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="everyone">{t(k('everyone'))}</SelectItem>
        <SelectItem value="admins">{t(k('adminsOnly'))}</SelectItem>
      </SelectContent>
    </Select>
  );
}

/**
 * Small entry in the command bar ("系统命令 · 10/12") that opens a side
 * sheet with the admin list, the no-permission reply and every built-in and
 * plugin command's switch and permission.
 */
export default function SystemCommandsSheet({
  botId,
  settings,
  onChange,
  pluginCommands,
  prefix,
  readOnly,
}: {
  botId: string;
  settings: BotCommandSettings;
  onChange: (patch: Partial<BotCommandSettings>) => void;
  pluginCommands: PluginCommandEntry[];
  prefix: string;
  readOnly?: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const { commands, failed } = useBuiltinCommands();
  // Admins live in the bot admin list, managed from the session monitor.
  const { admins: botAdmins } = useBotAdmins(botId);
  if (failed) return null;

  const states = (commands ?? []).map((command) => ({
    command,
    ...builtinState(settings, command),
  }));
  const enabledCount = states.filter((item) => item.enabled).length;
  const admins = botAdmins.filter((admin) => admin.launcher_type === 'person');
  const pluginPermissions = settings.plugin_permissions ?? {};
  const needsAdmins =
    admins.length === 0 &&
    (states.some((item) => item.enabled && item.permission === 'admins') ||
      Object.values(pluginPermissions).includes('admins'));

  function setBuiltin(
    command: BuiltinCommandDescriptor,
    patch: Partial<{ enabled: boolean; permission: CommandPermission }>,
  ) {
    onChange({
      builtin: {
        ...(settings.builtin ?? {}),
        [command.name]: { ...builtinState(settings, command), ...patch },
      },
    });
  }
  function setPluginPermission(key: string, permission: CommandPermission) {
    const next = { ...pluginPermissions };
    // "everyone" is the default; keep the stored map small.
    if (permission === 'everyone') delete next[key];
    else next[key] = permission;
    onChange({ plugin_permissions: next });
  }

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-7 gap-1.5 px-2 text-xs"
        onClick={() => setOpen(true)}
        data-testid="system-commands-button"
        disabled={commands === null}
      >
        <Command className="size-3.5" />
        {commands === null
          ? t(k('title'))
          : t(k('entry'), { enabled: enabledCount, total: states.length })}
        {needsAdmins && (
          <AlertTriangle className="size-3.5 text-amber-600 dark:text-amber-400" />
        )}
        <ChevronRight className="size-3.5 text-muted-foreground" />
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          className="w-full overflow-y-auto sm:max-w-xl"
          data-testid="system-commands-sheet"
        >
          <SheetHeader>
            <SheetTitle>{t(k('title'))}</SheetTitle>
            <SheetDescription>
              {readOnly ? t(k('readOnly')) : t(k('description'))}
            </SheetDescription>
          </SheetHeader>
          <fieldset disabled={readOnly} className="space-y-6 px-4 pb-8">
            <section className="space-y-2" data-testid="system-commands-admins">
              <h3 className="text-sm font-semibold">{t(k('admins'))}</h3>
              <div className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5">
                <p className="text-xs text-muted-foreground">
                  {admins.length
                    ? t(k('adminsCount'), { count: admins.length })
                    : t(k('adminsNone'))}{' '}
                  {t(k('adminsWhere'))}
                </p>
                <Button
                  asChild
                  variant="outline"
                  size="sm"
                  className="shrink-0"
                >
                  <Link
                    to={`/home/bots?id=${encodeURIComponent(botId)}&tab=sessions`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t(k('openSessions'))}
                    <ExternalLink className="size-3.5" />
                  </Link>
                </Button>
              </div>
              {needsAdmins && (
                <p className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                  {t(k('noAdmins'))}
                </p>
              )}
            </section>

            <section className="space-y-2">
              <h3 className="text-sm font-semibold">{t(k('denied'))}</h3>
              <ToggleGroup
                type="single"
                variant="outline"
                size="sm"
                value={settings.denied_reply ?? 'silent'}
                disabled={readOnly}
                onValueChange={(value) =>
                  value &&
                  onChange({ denied_reply: value as 'silent' | 'notice' })
                }
              >
                <ToggleGroupItem value="silent" className="px-3">
                  {t(k('deniedSilent'))}
                </ToggleGroupItem>
                <ToggleGroupItem value="notice" className="px-3">
                  {t(k('deniedNotice'))}
                </ToggleGroupItem>
              </ToggleGroup>
              <p className="text-xs text-muted-foreground">
                {t(
                  k(
                    settings.denied_reply === 'notice'
                      ? 'deniedNoticeHint'
                      : 'deniedSilentHint',
                  ),
                )}
              </p>
            </section>

            {commands === null ? (
              <Skeleton className="h-40 w-full" />
            ) : (
              GROUPS.map((group) => {
                const items = states.filter(
                  (item) => item.command.group === group,
                );
                if (items.length === 0) return null;
                return (
                  <section key={group} className="space-y-2">
                    <h3 className="text-sm font-semibold">
                      {t(k(`groups.${group}`))}
                    </h3>
                    <ul className="divide-y rounded-lg border">
                      {items.map(({ command, enabled, permission }) => {
                        const name = `${prefix}${command.name}`;
                        return (
                          <li
                            key={command.name}
                            data-builtin-command={command.name}
                            className="flex items-center gap-3 px-3 py-2"
                          >
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-baseline gap-x-2">
                                <code className="font-mono text-sm">
                                  {name}
                                </code>
                                {command.aliases.length > 0 && (
                                  <span className="font-mono text-xs text-muted-foreground">
                                    {command.aliases
                                      .map((alias) => `${prefix}${alias}`)
                                      .join(' ')}
                                  </span>
                                )}
                              </div>
                              <p className="truncate text-xs text-muted-foreground">
                                {extractI18nObject(command.description)}
                              </p>
                            </div>
                            <PermissionSelect
                              value={permission}
                              disabled={readOnly || !enabled}
                              label={t(k('permissionOf'), { command: name })}
                              onChange={(next) =>
                                setBuiltin(command, { permission: next })
                              }
                            />
                            <Switch
                              checked={enabled}
                              disabled={readOnly}
                              aria-label={t(k('enableCommand'), {
                                command: name,
                              })}
                              onCheckedChange={(next) =>
                                setBuiltin(command, { enabled: next })
                              }
                            />
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })
            )}

            <section className="space-y-2">
              <h3 className="text-sm font-semibold">
                {t(k('pluginCommands'))}
              </h3>
              <p className="text-xs text-muted-foreground">
                {t(k('pluginCommandsHint'))}
              </p>
              {pluginCommands.length === 0 ? (
                <p className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
                  {t(k('noPluginCommands'))}
                </p>
              ) : (
                <ul className="divide-y rounded-lg border">
                  {pluginCommands.map((entry) => {
                    const name = `${prefix}${entry.command}`;
                    const permission =
                      pluginPermissions[entry.key] ?? 'everyone';
                    return (
                      <li
                        key={entry.key}
                        data-plugin-command={entry.key}
                        className="flex items-center gap-3 px-3 py-2"
                      >
                        <div className="min-w-0 flex-1">
                          <code className="font-mono text-sm">{name}</code>
                          <p className="truncate text-xs text-muted-foreground">
                            {entry.pluginLabel}
                          </p>
                        </div>
                        {permission === 'admins' && (
                          <Lock className="size-3.5 text-muted-foreground" />
                        )}
                        <PermissionSelect
                          value={permission}
                          disabled={readOnly}
                          label={t(k('permissionOf'), { command: name })}
                          onChange={(next) =>
                            setPluginPermission(entry.key, next)
                          }
                        />
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </fieldset>
        </SheetContent>
      </Sheet>
    </>
  );
}
