import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleCheck,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import type {
  UpgradeCheckItem,
  UpgradeChecksResponse,
} from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';

const k = (key: string) => `upgradeChecks.${key}`;

/** Actions that change data get a confirmation dialog first. */
const CONFIRMED_ACTIONS = new Set([
  'uninstall_essential',
  'remove_plugin',
  'promote_route_policy',
]);

/** Notify every mounted banner that the check list changed. */
const CHANGED_EVENT = 'langbot:upgrade-checks-changed';

function useUpgradeChecks() {
  const workspace = useCurrentWorkspace()?.workspace.uuid;
  const [data, setData] = useState<UpgradeChecksResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await backendClient.getUpgradeChecks());
    } catch {
      // Older Cores have no upgrade checks; the banner just stays hidden.
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    if (!workspace) return;
    void reload();
    const listener = () => void reload();
    window.addEventListener(CHANGED_EVENT, listener);
    return () => window.removeEventListener(CHANGED_EVENT, listener);
  }, [workspace, reload]);
  const changed = useCallback(() => {
    window.dispatchEvent(new Event(CHANGED_EVENT));
  }, []);
  return { data, loading, changed };
}

function errorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'msg' in error)
    return String((error as { msg: unknown }).msg);
  if (error instanceof Error) return error.message;
  return String(error);
}

/**
 * "Upgrade check" assistant: a banner on the bot and Chat pages that opens a
 * Sheet listing behavior changes from the message policy migration. Each item
 * can be acted on, acknowledged one by one, or all at once.
 */
export default function UpgradeChecksBanner() {
  const { t } = useTranslation();
  const currentWorkspace = useCurrentWorkspace();
  const canManage =
    currentWorkspace?.permissions.includes('resource.manage') ?? false;
  const { data, loading, changed } = useUpgradeChecks();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [pending, setPending] = useState<{
    item: UpgradeCheckItem;
    action: string;
  } | null>(null);
  const [bots, setBots] = useState<Record<string, string>>({});

  const items = useMemo(() => data?.items ?? [], [data]);
  const openItems = items.filter((item) => !item.confirmed);
  const confirmedItems = items.filter((item) => item.confirmed);

  useEffect(() => {
    if (!open) return;
    let active = true;
    backendClient
      .getBots()
      .then((response) => {
        if (!active) return;
        setBots(
          Object.fromEntries(
            (response.bots ?? [])
              .filter((bot) => bot.uuid)
              .map((bot) => [bot.uuid as string, bot.name]),
          ),
        );
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [open]);

  if (openItems.length === 0 && !open) return null;

  const botName = (uuid?: string) => (uuid && bots[uuid]) || t(k('unknownBot'));

  const run = async (key: string, work: () => Promise<unknown>) => {
    setBusy(key);
    try {
      await work();
      changed();
      return true;
    } catch (error) {
      toast.error(t(k('failed'), { error: errorMessage(error) }));
      return false;
    } finally {
      setBusy(null);
    }
  };

  const act = async (item: UpgradeCheckItem, action: string) => {
    let taskStarted = false;
    const ok = await run(`${item.id}:${action}`, async () => {
      const result = await backendClient.runUpgradeCheckAction(item.id, action);
      taskStarted = result?.task_id != null;
    });
    if (ok)
      toast.success(
        t(k(taskStarted ? 'taskStarted' : 'actionDone'), {
          action: t(k(`actions.${action}`)),
        }),
      );
  };

  const confirmOne = (item: UpgradeCheckItem) =>
    run(`${item.id}:confirm`, () => backendClient.confirmUpgradeCheck(item.id));

  const confirmAll = async () => {
    if (await run('all', () => backendClient.confirmAllUpgradeChecks())) {
      toast.success(t(k('allConfirmed')));
      setOpen(false);
    }
  };

  const describe = (item: UpgradeCheckItem) => {
    const params = item.params ?? {};
    switch (item.code) {
      case 'command_prefix_changed':
        return t(k('items.command_prefix_changed.body'), {
          bot: botName(params.bot_uuid),
          prefixes: (params.original_prefixes ?? []).join(' '),
        });
      case 'plugin_command_collision':
        return t(
          k(
            params.essential_installed
              ? 'items.plugin_command_collision.bodyEssential'
              : 'items.plugin_command_collision.body',
          ),
          {
            names: (params.names ?? []).map((name) => `/${name}`).join(' '),
          },
        );
      case 'command_admin_missing':
        return t(k('items.command_admin_missing.body'), {
          bot: botName(params.bot_uuid),
        });
      case 'command_plugin_enabled':
        return t(k('items.command_plugin_enabled.body'), {
          bot: botName(params.bot_uuid),
          plugin: params.plugin,
          scope: (params.scopes ?? []).includes(null)
            ? t(k('scopeDefault'))
            : t(k('scopeRoutes'), { count: params.scopes?.length ?? 0 }),
        });
      case 'equivalent_route_policies':
        return t(k('items.equivalent_route_policies.body'), {
          bot: botName(params.bot_uuid),
          count: params.route_ids?.length ?? 0,
        });
      case 'chat_settings_moved':
        return t(k('items.chat_settings_moved.body'), {
          bot: botName(params.bot_uuid),
          count: params.routes?.length ?? 0,
        });
      default:
        return item.code;
    }
  };

  const links = (item: UpgradeCheckItem) => {
    const uuid = item.params?.bot_uuid;
    if (!uuid) return null;
    const base = `/home/bots?id=${encodeURIComponent(uuid)}`;
    const target =
      item.code === 'command_admin_missing'
        ? { href: `${base}&tab=sessions`, label: k('links.admins') }
        : item.code === 'chat_settings_moved' ||
            item.code === 'equivalent_route_policies'
          ? { href: `${base}&section=policy`, label: k('links.policy') }
          : { href: `${base}&section=plugins`, label: k('links.commands') };
    return (
      <Button asChild variant="ghost" size="sm" className="h-7 px-2">
        <Link to={target.href} onClick={() => setOpen(false)}>
          {t(target.label)}
          <ArrowUpRight className="size-3.5" />
        </Link>
      </Button>
    );
  };

  const renderItem = (item: UpgradeCheckItem) => (
    <li
      key={item.id}
      className="space-y-2 rounded-lg border bg-card p-3"
      data-testid={`upgrade-check-${item.code}`}
    >
      <div className="flex items-start gap-2">
        {item.confirmed ? (
          <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" />
        ) : (
          <span
            aria-hidden="true"
            className="mt-1.5 size-2 shrink-0 rounded-full bg-amber-500"
          />
        )}
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-sm font-medium">
            {t(k(`items.${item.code}.title`), { defaultValue: item.code })}
          </p>
          <p className="text-sm text-muted-foreground">{describe(item)}</p>
          {item.code === 'equivalent_route_policies' &&
            item.params?.changes_unrouted_commands && (
              <p className="text-xs text-amber-700 dark:text-amber-300">
                {t(k('items.equivalent_route_policies.unroutedCommands'))}
              </p>
            )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 pl-6">
        {canManage &&
          item.actions.map((action) => (
            <Button
              key={action}
              size="sm"
              variant="outline"
              className="h-7"
              disabled={busy !== null}
              onClick={() =>
                CONFIRMED_ACTIONS.has(action)
                  ? setPending({ item, action })
                  : void act(item, action)
              }
            >
              {busy === `${item.id}:${action}` && (
                <Loader2 className="size-3.5 animate-spin" />
              )}
              {t(k(`actions.${action}`), { defaultValue: action })}
            </Button>
          ))}
        {links(item)}
        {canManage && !item.confirmed && (
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto h-7"
            disabled={busy !== null}
            onClick={() => void confirmOne(item)}
          >
            {busy === `${item.id}:confirm` ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Check className="size-3.5" />
            )}
            {t(k(`items.${item.code}.keep`), {
              defaultValue: t(k('acknowledge')),
            })}
          </Button>
        )}
      </div>
    </li>
  );

  return (
    <>
      {openItems.length > 0 && (
        <div
          className="flex flex-wrap items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm dark:border-amber-900/60 dark:bg-amber-950/30"
          data-testid="upgrade-checks-banner"
        >
          <Sparkles className="size-4 shrink-0 text-amber-600" />
          <span className="min-w-0 flex-1">
            {t(k('banner'), { count: openItems.length })}
          </span>
          <Button
            size="sm"
            variant="outline"
            className="h-7 bg-background"
            onClick={() => setOpen(true)}
          >
            {t(k('review'))}
          </Button>
        </div>
      )}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-lg">
          <SheetHeader className="border-b p-5">
            <SheetTitle>{t(k('title'))}</SheetTitle>
            <SheetDescription>{t(k('description'))}</SheetDescription>
          </SheetHeader>
          <ScrollArea className="min-h-0 flex-1">
            <div className="space-y-4 p-5">
              {loading && !data && <Skeleton className="h-24 w-full" />}
              {openItems.length === 0 && data && (
                <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                  {t(k('empty'))}
                </p>
              )}
              <ul className="space-y-2">{openItems.map(renderItem)}</ul>
              {confirmedItems.length > 0 && (
                <Collapsible>
                  <CollapsibleTrigger className="group flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                    <ChevronRight className="size-3.5 transition-transform group-data-[state=open]:rotate-90" />
                    {t(k('confirmedSection'), {
                      count: confirmedItems.length,
                    })}
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <ul className="mt-2 space-y-2">
                      {confirmedItems.map(renderItem)}
                    </ul>
                  </CollapsibleContent>
                </Collapsible>
              )}
            </div>
          </ScrollArea>
          {canManage && openItems.length > 0 && (
            <SheetFooter className="border-t p-4">
              <Button disabled={busy !== null} onClick={confirmAll}>
                {busy === 'all' && <Loader2 className="size-4 animate-spin" />}
                {t(k('confirmAll'))}
              </Button>
            </SheetFooter>
          )}
        </SheetContent>
      </Sheet>
      <AlertDialog
        open={pending !== null}
        onOpenChange={(value) => {
          if (!value) setPending(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pending && t(k(`actions.${pending.action}`))}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pending &&
                t(k(`confirm.${pending.action}`), {
                  bot: botName(pending.item.params?.bot_uuid),
                  plugin: pending.item.params?.plugin,
                  count: pending.item.params?.route_ids?.length ?? 0,
                })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pending) void act(pending.item, pending.action);
                setPending(null);
              }}
            >
              {t('common.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
