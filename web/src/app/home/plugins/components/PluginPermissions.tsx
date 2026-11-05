import { useCallback, useEffect, useId, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  ChevronDown,
  Loader2,
  Search,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';
import { backendClient } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import {
  initialPermissionSelection,
  permissionGrantRequest,
  permissionSelectionDiff,
  type PermissionCategory,
  type PluginPermissionItem,
  type PluginPermissionState,
} from './permission-grants';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';

const CATEGORIES: PermissionCategory[] = [
  'capabilities',
  'workspace_operations',
];

const CAPABILITY_GROUPS: Record<string, string> = {
  'bot.read': 'bot',
  'bot.message.send': 'bot',
  'bot.platform_api': 'bot',
  'models.read': 'models',
  'models.invoke': 'models',
  'knowledge.read': 'knowledge',
  'knowledge.vector': 'knowledge',
  'knowledge.parser': 'knowledge',
  'storage.plugin': 'storage',
  'storage.workspace': 'storage',
  'plugin.read': 'extensions',
  plugin_tools: 'extensions',
  mcp: 'extensions',
  sandbox: 'runtime',
  'langbot.info': 'runtime',
  'config.read': 'runtime',
};
const CAPABILITY_GROUP_ORDER = [
  'bot',
  'models',
  'knowledge',
  'storage',
  'extensions',
  'runtime',
  'other',
];

function needsAttention(item: PluginPermissionItem) {
  return item.risk === 'dangerous' || item.id === 'bot.message.send';
}

/**
 * Collapsible permission panel for a plugin installation.
 *
 * Permissions are edited as a draft: grouped by capability area or workspace
 * domain, searchable, with per-group select-all. Removing grants saves
 * directly; adding grants (or confirming a pending install) goes through a
 * confirmation dialog.
 */
export default function PluginPermissions({
  author,
  name,
  onChange,
}: {
  author: string;
  name: string;
  onChange: () => void;
}) {
  const { t } = useTranslation();
  const inputPrefix = useId();
  const [state, setState] = useState<PluginPermissionState | null>(null);
  const [draft, setDraft] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<PermissionCategory>('capabilities');
  const [query, setQuery] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const path = `/api/v1/plugins/${encodeURIComponent(author)}/${encodeURIComponent(name)}/permissions`;
  const load = useCallback(async () => {
    setFailed(false);
    try {
      const value = await backendClient.get<PluginPermissionState>(path);
      setState(value);
      setDraft(initialPermissionSelection(value));
    } catch {
      setFailed(true);
    }
  }, [path]);
  useEffect(() => {
    void load();
  }, [load]);

  const labelFor = useCallback(
    (item: PluginPermissionItem) => {
      if (item.category === 'capabilities') {
        const key = `pluginPermissions.capability.${item.id.replace(/\./g, '_')}`;
        return {
          label: t(`${key}.label`, { defaultValue: item.id }),
          description: t(`${key}.description`, { defaultValue: '' }),
        };
      }
      return {
        label: item.label
          ? extractI18nObject(
              item.label as unknown as Parameters<typeof extractI18nObject>[0],
            ) || item.id
          : item.id,
        description: item.summary ?? '',
      };
    },
    [t],
  );

  const groupOf = useCallback(
    (item: PluginPermissionItem) =>
      item.category === 'capabilities'
        ? (CAPABILITY_GROUPS[item.id] ?? 'other')
        : (item.domain ?? item.id.split('.')[0]),
    [],
  );

  const groupLabel = (group: string) => {
    if (category === 'capabilities')
      return t(`pluginPermissions.capabilityGroup.${group}`);
    const meta = state?.domains?.find((item) => item.domain === group);
    return meta
      ? extractI18nObject(
          meta.label as unknown as Parameters<typeof extractI18nObject>[0],
        ) || group
      : group;
  };

  const counts = useMemo(
    () =>
      Object.fromEntries(
        CATEGORIES.map((key) => [
          key,
          state?.permissions.filter((item) => item.category === key).length ??
            0,
        ]),
      ) as Record<PermissionCategory, number>,
    [state],
  );
  const visibleCategories = CATEGORIES.filter((key) => counts[key] > 0);
  const activeCategory = visibleCategories.includes(category)
    ? category
    : (visibleCategories[0] ?? 'capabilities');

  const groups = useMemo(() => {
    if (!state) return [];
    const needle = query.trim().toLocaleLowerCase();
    const map = new Map<string, PluginPermissionItem[]>();
    for (const item of state.permissions) {
      if (item.category !== activeCategory) continue;
      const { label, description } = labelFor(item);
      if (
        needle &&
        ![item.id, label, description]
          .join(' ')
          .toLocaleLowerCase()
          .includes(needle)
      )
        continue;
      const group = groupOf(item);
      if (!map.has(group)) map.set(group, []);
      map.get(group)!.push(item);
    }
    const order = (group: string) =>
      activeCategory === 'capabilities'
        ? CAPABILITY_GROUP_ORDER.indexOf(group)
        : 0;
    return [...map.entries()].sort(
      ([a], [b]) => order(a) - order(b) || a.localeCompare(b),
    );
  }, [activeCategory, groupOf, labelFor, query, state]);

  if (failed)
    return (
      <Button variant="outline" onClick={() => void load()}>
        {t('pluginPermissions.retry')}
      </Button>
    );
  if (!state) return null;

  const pending = state.pending_confirmation;
  const total = state.permissions.length;
  const grantedCount = state.permissions.filter((item) => item.granted).length;
  const compatibilityBlocked =
    state.compatibility_mode &&
    state.permissions.some((item) => !item.grantable);
  const canConfirm =
    state.can_confirm &&
    !compatibilityBlocked &&
    (total === 0 || state.permissions.some((item) => item.grantable));
  const { added, removed } = permissionSelectionDiff(state, draft);
  const dirty = !pending && (added.length > 0 || removed.length > 0);
  // Confirming compatibility mode always grants every legacy capability.
  const toGrant = state.compatibility_mode
    ? state.permissions.filter((item) => pending || !item.granted)
    : added;
  const attention = toGrant.filter(needsAttention);
  const locked =
    busy || !state.can_manage || (pending && state.compatibility_mode);

  const selectable = (item: PluginPermissionItem) =>
    !locked && (item.granted || item.grantable);
  const setItems = (items: PluginPermissionItem[], checked: boolean) =>
    setDraft((previous) => {
      const next = new Set(previous);
      for (const item of items.filter(selectable)) {
        if (checked) next.add(item.id);
        else next.delete(item.id);
      }
      return next;
    });
  const checkState = (items: PluginPermissionItem[]) =>
    items.every((item) => draft.has(item.id))
      ? true
      : items.some((item) => draft.has(item.id))
        ? 'indeterminate'
        : false;

  async function save(confirm: boolean) {
    if (!state || !state.can_manage) return;
    setBusy(true);
    try {
      await backendClient.put(
        path,
        permissionGrantRequest(state, draft, confirm),
      );
      setConfirming(false);
      await load();
      onChange();
      toast.success(t('pluginPermissions.saved'));
    } catch {
      toast.error(t('pluginPermissions.failed'));
    } finally {
      setBusy(false);
    }
  }

  function submit() {
    if (pending || added.length > 0) setConfirming(true);
    else void save(false);
  }

  const status = pending
    ? t('pluginPermissions.statusPending')
    : total === 0
      ? t('pluginPermissions.statusNone')
      : t('pluginPermissions.grantedCount', { granted: grantedCount, total });
  const visibleItems = groups.flatMap(([, items]) => items);

  return (
    <Card className="gap-0 py-0">
      <Collapsible open={open} onOpenChange={setOpen}>
        <div className="flex items-center gap-2 px-4 py-3">
          <CollapsibleTrigger asChild>
            <button
              type="button"
              className="flex min-w-0 flex-1 items-center gap-2 text-left"
            >
              {pending ? (
                <ShieldAlert className="size-4 shrink-0 text-amber-600" />
              ) : (
                <ShieldCheck className="size-4 shrink-0 text-emerald-600" />
              )}
              <span className="text-sm font-medium">
                {t('pluginPermissions.title')}
              </span>
              <span
                className={cn(
                  'truncate text-xs tabular-nums',
                  pending
                    ? 'text-amber-700 dark:text-amber-400'
                    : 'text-muted-foreground',
                )}
              >
                {status}
              </span>
              <ChevronDown
                className={cn(
                  'ml-auto size-4 shrink-0 text-muted-foreground transition-transform',
                  open && 'rotate-180',
                )}
              />
            </button>
          </CollapsibleTrigger>
          {pending && canConfirm && (
            <Button
              size="sm"
              className="h-7 shrink-0 px-2.5 text-xs"
              disabled={busy}
              onClick={submit}
            >
              {t('pluginPermissions.grant')}
            </Button>
          )}
        </div>
        {pending && (
          <p className="-mt-1.5 px-4 pb-3 pl-10 text-xs text-muted-foreground">
            {t('pluginPermissions.pendingHint')}
          </p>
        )}
        <CollapsibleContent>
          <div className="space-y-3 border-t px-4 pb-3 pt-3">
            {state.compatibility_mode && total > 0 && (
              <p className="text-xs text-muted-foreground">
                {t('pluginPermissions.compatibilityNote')}
              </p>
            )}
            {!state.can_manage && (
              <p className="text-xs text-muted-foreground">
                {t('pluginPermissions.managerRequired')}
              </p>
            )}
            {total === 0 ? (
              <p className="text-xs text-muted-foreground">
                {t('pluginPermissions.empty')}
              </p>
            ) : (
              <>
                {visibleCategories.length > 1 && (
                  <div className="inline-flex w-full rounded-lg bg-muted p-1">
                    {visibleCategories.map((key) => (
                      <button
                        key={key}
                        type="button"
                        aria-pressed={activeCategory === key}
                        onClick={() => setCategory(key)}
                        className={cn(
                          'flex-1 rounded-md px-2.5 py-1.5 text-sm transition-colors active:scale-[0.98]',
                          activeCategory === key
                            ? 'bg-background font-medium shadow-sm'
                            : 'text-muted-foreground hover:text-foreground',
                        )}
                      >
                        {t(
                          key === 'capabilities'
                            ? 'pluginPermissions.capabilities'
                            : 'pluginPermissions.workspaceOperations',
                        )}
                        <span className="ml-1.5 text-xs tabular-nums text-muted-foreground">
                          {
                            state.permissions.filter(
                              (item) =>
                                item.category === key && draft.has(item.id),
                            ).length
                          }
                          /{counts[key]}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <div className="relative min-w-0 flex-1">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder={t('pluginPermissions.searchPlaceholder')}
                      className="h-8 pl-8 text-sm"
                    />
                  </div>
                  <label className="flex shrink-0 cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
                    <Checkbox
                      checked={checkState(visibleItems)}
                      disabled={!visibleItems.some(selectable)}
                      onCheckedChange={(checked) =>
                        setItems(visibleItems, checked === true)
                      }
                    />
                    {t('pluginPermissions.selectAll')}
                  </label>
                </div>
                {groups.length === 0 ? (
                  <p className="rounded-md border border-dashed px-3 py-6 text-center text-xs text-muted-foreground">
                    {t('pluginPermissions.noResults')}
                  </p>
                ) : (
                  <div className="max-h-[26rem] overflow-y-auto rounded-md border">
                    {groups.map(([group, items], index) => (
                      <section
                        key={group}
                        className={cn(index > 0 && 'border-t')}
                      >
                        <div className="sticky top-0 z-10 flex items-center justify-between gap-2 bg-muted px-3 py-1.5 text-xs font-medium text-muted-foreground">
                          <span className="truncate">
                            {groupLabel(group)}
                            <span className="ml-1.5 font-normal tabular-nums">
                              {
                                items.filter((item) => draft.has(item.id))
                                  .length
                              }
                              /{items.length}
                            </span>
                          </span>
                          <Checkbox
                            checked={checkState(items)}
                            disabled={!items.some(selectable)}
                            onCheckedChange={(checked) =>
                              setItems(items, checked === true)
                            }
                            aria-label={`${groupLabel(group)} · ${t('pluginPermissions.selectAll')}`}
                          />
                        </div>
                        <ul className="divide-y">
                          {items.map((item) => {
                            const { label, description } = labelFor(item);
                            const inputId = `${inputPrefix}-${item.id}`;
                            const checked = draft.has(item.id);
                            const change = pending
                              ? null
                              : checked && !item.granted
                                ? 'add'
                                : !checked && item.granted
                                  ? 'remove'
                                  : null;
                            return (
                              <li
                                key={item.id}
                                data-permission-id={item.id}
                                className="flex items-start gap-2.5 px-3 py-2"
                              >
                                <Checkbox
                                  id={inputId}
                                  className="mt-0.5"
                                  checked={checked}
                                  disabled={!selectable(item)}
                                  onCheckedChange={(next) =>
                                    setItems([item], next === true)
                                  }
                                />
                                <label
                                  htmlFor={inputId}
                                  className="min-w-0 flex-1"
                                  title={description || item.id}
                                >
                                  <span className="block truncate text-sm leading-5">
                                    {label}
                                  </span>
                                  <span className="block truncate font-mono text-[11px] text-muted-foreground">
                                    {item.id}
                                  </span>
                                  {!item.grantable && !item.granted && (
                                    <span className="block text-xs text-amber-700 dark:text-amber-400">
                                      {t('pluginPermissions.requires', {
                                        permissions:
                                          item.required_permissions.join(', '),
                                      })}
                                    </span>
                                  )}
                                </label>
                                <span
                                  className={cn(
                                    'shrink-0 pt-0.5 text-xs',
                                    change === 'add'
                                      ? 'text-emerald-600 dark:text-emerald-400'
                                      : change === 'remove'
                                        ? 'text-destructive'
                                        : item.risk === 'dangerous'
                                          ? 'text-amber-700 dark:text-amber-400'
                                          : 'text-muted-foreground',
                                  )}
                                >
                                  {change
                                    ? t(
                                        change === 'add'
                                          ? 'pluginPermissions.willGrant'
                                          : 'pluginPermissions.willRevoke',
                                      )
                                    : t(`agents.apiToolRisk.${item.risk}`)}
                                </span>
                              </li>
                            );
                          })}
                        </ul>
                      </section>
                    ))}
                  </div>
                )}
                {(dirty || pending) && state.can_manage && (
                  <div className="flex items-center justify-end gap-2">
                    <span className="mr-auto text-xs text-muted-foreground">
                      {pending
                        ? t('pluginPermissions.selectedCount', {
                            count: draft.size,
                          })
                        : t('pluginPermissions.pendingChanges', {
                            added: added.length,
                            removed: removed.length,
                          })}
                    </span>
                    {dirty && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 px-2.5 text-xs"
                        disabled={busy}
                        onClick={() =>
                          setDraft(initialPermissionSelection(state))
                        }
                      >
                        {t('common.cancel')}
                      </Button>
                    )}
                    <Button
                      size="sm"
                      className="h-7 px-2.5 text-xs"
                      disabled={
                        busy || ((pending || added.length > 0) && !canConfirm)
                      }
                      onClick={submit}
                    >
                      {busy && <Loader2 className="size-3.5 animate-spin" />}
                      {pending
                        ? t('pluginPermissions.grant')
                        : t('common.save')}
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('pluginPermissions.confirmTitle')}</DialogTitle>
            <DialogDescription>
              {t(
                state.compatibility_mode
                  ? 'pluginPermissions.compatibilityNote'
                  : 'pluginPermissions.confirmDescription',
              )}
            </DialogDescription>
          </DialogHeader>
          {attention.length > 0 && (
            <div className="flex gap-2 rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-xs text-amber-800 dark:text-amber-300">
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
              <p>
                {t('pluginPermissions.highlightedList', {
                  items: attention
                    .map((item) => labelFor(item).label)
                    .join(t('pluginPermissions.listSeparator')),
                })}
              </p>
            </div>
          )}
          <p className="text-sm font-medium">
            {t('pluginPermissions.newGrants', { count: toGrant.length })}
          </p>
          <ul className="max-h-60 divide-y overflow-y-auto rounded-md border text-sm">
            {toGrant.map((item) => (
              <li key={item.id} className="flex items-center gap-2 px-3 py-1.5">
                <span className="min-w-0 flex-1 truncate">
                  {labelFor(item).label}
                </span>
                <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
                  {item.id}
                </span>
              </li>
            ))}
          </ul>
          {!state.compatibility_mode && removed.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {t('pluginPermissions.alsoRevoking', { count: removed.length })}
            </p>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setConfirming(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button disabled={busy} onClick={() => void save(true)}>
              {busy && <Loader2 className="size-4 animate-spin" />}
              {t('pluginPermissions.grantCount', { count: toGrant.length })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
