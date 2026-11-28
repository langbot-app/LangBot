import type React from 'react';
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

/** Admins (from the session monitor) and whether any command needs one. */
function useCommandAdmins(botId: string, settings: BotCommandSettings) {
  const { admins: botAdmins } = useBotAdmins(botId);
  const { commands } = useBuiltinCommands();
  const admins = botAdmins.filter((admin) => admin.launcher_type === 'person');
  const needsAdmins =
    admins.length === 0 &&
    ((commands ?? []).some((command) => {
      const state = builtinState(settings, command);
      return state.enabled && state.permission === 'admins';
    }) ||
      Object.values(settings.plugin_permissions ?? {}).includes('admins'));
  return { admins, needsAdmins };
}

function SettingLine({
  title,
  hint,
  action,
  children,
}: {
  title: string;
  hint?: React.ReactNode;
  action?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5 px-3 py-2.5">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{title}</p>
          {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

/**
 * Settings shared by system and plugin commands, as rows of the Commands
 * section: what a sender without permission gets, and who the admins are
 * (managed in the session monitor).
 */
export function CommandAccessRows({
  botId,
  settings,
  onChange,
  readOnly,
}: {
  botId: string;
  settings: BotCommandSettings;
  onChange: (patch: Partial<BotCommandSettings>) => void;
  readOnly?: boolean;
}) {
  const { t } = useTranslation();
  const { admins, needsAdmins } = useCommandAdmins(botId, settings);
  return (
    <>
      <SettingLine
        title={t(k('admins'))}
        hint={
          <>
            {admins.length
              ? t(k('adminsCount'), { count: admins.length })
              : t(k('adminsNone'))}{' '}
            {t(k('adminsWhere'))}
          </>
        }
        action={
          <Button
            asChild
            variant="outline"
            size="sm"
            className="h-7 shrink-0 text-xs"
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
        }
      >
        {needsAdmins && (
          <p
            className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400"
            data-testid="command-admins-warning"
          >
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
            {t(k('noAdmins'))}
          </p>
        )}
      </SettingLine>
      <SettingLine
        title={t(k('denied'))}
        hint={t(
          k(
            settings.denied_reply === 'notice'
              ? 'deniedNoticeHint'
              : 'deniedSilentHint',
          ),
        )}
        action={
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={settings.denied_reply ?? 'silent'}
            disabled={readOnly}
            onValueChange={(value) =>
              value && onChange({ denied_reply: value as 'silent' | 'notice' })
            }
          >
            <ToggleGroupItem value="silent" className="px-3 text-xs">
              {t(k('deniedSilent'))}
            </ToggleGroupItem>
            <ToggleGroupItem value="notice" className="px-3 text-xs">
              {t(k('deniedNotice'))}
            </ToggleGroupItem>
          </ToggleGroup>
        }
      />
    </>
  );
}

/** "系统命令 · 11/12" entry; its sheet lists only the built-in commands. */
export default function SystemCommandsSheet({
  settings,
  onChange,
  prefix,
  readOnly,
}: {
  settings: BotCommandSettings;
  onChange: (patch: Partial<BotCommandSettings>) => void;
  prefix: string;
  readOnly?: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const { commands, failed } = useBuiltinCommands();
  if (failed) return null;

  const states = (commands ?? []).map((command) => ({
    command,
    ...builtinState(settings, command),
  }));
  const enabledCount = states.filter((item) => item.enabled).length;

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
          </fieldset>
        </SheetContent>
      </Sheet>
    </>
  );
}

/** "设置权限" entry of the plugin commands row; lists only plugin commands. */
export function PluginCommandsSheet({
  settings,
  onChange,
  pluginCommands,
  prefix,
  readOnly,
}: {
  settings: BotCommandSettings;
  onChange: (patch: Partial<BotCommandSettings>) => void;
  pluginCommands: PluginCommandEntry[];
  prefix: string;
  readOnly?: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const pluginPermissions = settings.plugin_permissions ?? {};
  const restricted = pluginCommands.filter(
    (entry) => pluginPermissions[entry.key] === 'admins',
  ).length;

  function setPluginPermission(key: string, permission: CommandPermission) {
    const next = { ...pluginPermissions };
    // "everyone" is the default; keep the stored map small.
    if (permission === 'everyone') delete next[key];
    else next[key] = permission;
    onChange({ plugin_permissions: next });
  }

  if (pluginCommands.length === 0) return null;
  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-7 gap-1.5 px-2 text-xs"
        onClick={() => setOpen(true)}
        data-testid="plugin-commands-button"
      >
        <Lock className="size-3.5" />
        {restricted
          ? t(k('pluginEntryRestricted'), { count: restricted })
          : t(k('pluginEntry'))}
        <ChevronRight className="size-3.5 text-muted-foreground" />
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          className="w-full overflow-y-auto sm:max-w-xl"
          data-testid="plugin-commands-sheet"
        >
          <SheetHeader>
            <SheetTitle>{t(k('pluginCommands'))}</SheetTitle>
            <SheetDescription>
              {readOnly ? t(k('readOnly')) : t(k('pluginCommandsHint'))}
            </SheetDescription>
          </SheetHeader>
          <fieldset disabled={readOnly} className="px-4 pb-8">
            <ul className="divide-y rounded-lg border">
              {pluginCommands.map((entry) => {
                const name = `${prefix}${entry.command}`;
                const permission = pluginPermissions[entry.key] ?? 'everyone';
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
                    <PermissionSelect
                      value={permission}
                      disabled={readOnly}
                      label={t(k('permissionOf'), { command: name })}
                      onChange={(next) => setPluginPermission(entry.key, next)}
                    />
                  </li>
                );
              })}
            </ul>
          </fieldset>
        </SheetContent>
      </Sheet>
    </>
  );
}
