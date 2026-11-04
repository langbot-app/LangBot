import { useCallback, useEffect, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Loader2, ShieldAlert, ShieldCheck, TriangleAlert } from 'lucide-react';
import { backendClient } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { cn } from '@/lib/utils';
import {
  permissionGrantRequest,
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
  'workspace_operations',
  'capabilities',
];

function needsAttention(item: PluginPermissionItem) {
  return item.risk === 'dangerous' || item.id === 'bot.message.send';
}

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
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const path = `/api/v1/plugins/${encodeURIComponent(author)}/${encodeURIComponent(name)}/permissions`;
  const load = useCallback(async () => {
    setFailed(false);
    try {
      const value = await backendClient.get<PluginPermissionState>(path);
      setState(value);
      setSelected(
        new Set(
          value.permissions
            .filter(
              (item) =>
                item.granted || (value.pending_confirmation && item.grantable),
            )
            .map((item) => item.id),
        ),
      );
    } catch {
      setFailed(true);
    }
  }, [path]);
  useEffect(() => {
    void load();
  }, [load]);

  async function save(confirm: boolean, revoked?: PluginPermissionItem) {
    if (!state || !state.can_manage) return;
    setBusy(true);
    try {
      await backendClient.put(
        path,
        permissionGrantRequest(state, selected, confirm, revoked),
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

  function labelFor(item: PluginPermissionItem) {
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
      description: '',
    };
  }

  if (failed)
    return (
      <Button variant="outline" onClick={() => void load()}>
        {t('pluginPermissions.retry')}
      </Button>
    );
  if (!state) return null;
  const compatibilityBlocked =
    state.compatibility_mode &&
    state.permissions.some((item) => !item.grantable);
  const canConfirm =
    state.can_confirm &&
    (state.permissions.length === 0 ||
      state.permissions.some((item) => item.grantable));
  const grantedCount = state.permissions.filter((item) => item.granted).length;
  const toGrant = state.permissions.filter(
    (item) => state.compatibility_mode || selected.has(item.id),
  );
  const attention = toGrant.filter(needsAttention);

  return (
    <Card className="gap-4">
      <CardHeader className="gap-1.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            {state.pending_confirmation ? (
              <ShieldAlert className="size-4 text-amber-600" />
            ) : (
              <ShieldCheck className="size-4 text-emerald-600" />
            )}
            {t('pluginPermissions.title')}
          </CardTitle>
          <div className="flex flex-wrap gap-1.5">
            {state.compatibility_mode && (
              <Badge
                variant="outline"
                className="border-amber-500/60 text-amber-700 dark:text-amber-400"
              >
                {t('pluginPermissions.undeclared')}
              </Badge>
            )}
          </div>
        </div>
        {state.permissions.length > 0 && (
          <CardDescription>
            {t('pluginPermissions.grantedCount', {
              granted: grantedCount,
              total: state.permissions.length,
            })}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {state.compatibility_mode && (
          <div
            role="alert"
            className="flex gap-2 rounded-md border border-amber-500/50 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-200"
          >
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            <p>{t('pluginPermissions.compatibilityWarning')}</p>
          </div>
        )}
        {state.pending_confirmation && (
          <p
            role="status"
            className="text-sm font-medium text-amber-700 dark:text-amber-400"
          >
            {t('pluginPermissions.pending')}
          </p>
        )}
        {!canConfirm && (
          <p role="alert" className="text-xs text-muted-foreground">
            {t('pluginPermissions.managerRequired')}
          </p>
        )}
        {state.permissions.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {t('pluginPermissions.empty')}
          </p>
        )}
        <div className="max-h-[28rem] space-y-4 overflow-y-auto pr-1">
          {CATEGORIES.map((category) => {
            const items = state.permissions.filter(
              (item) => item.category === category,
            );
            if (items.length === 0) return null;
            return (
              <section key={category} className="space-y-2">
                <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {t(
                    category === 'capabilities'
                      ? 'pluginPermissions.capabilities'
                      : 'pluginPermissions.workspaceOperations',
                  )}
                  <span className="ml-1 tabular-nums">({items.length})</span>
                </h4>
                <ul className="divide-y rounded-md border">
                  {items.map((item) => {
                    const { label, description } = labelFor(item);
                    const inputId = `${inputPrefix}-${item.id}`;
                    return (
                      <li
                        key={`${item.category}:${item.id}`}
                        data-permission-id={item.id}
                        className={cn(
                          'flex items-start gap-3 px-3 py-2.5',
                          item.risk === 'dangerous' && 'bg-destructive/5',
                        )}
                      >
                        <Checkbox
                          id={inputId}
                          className="mt-0.5"
                          checked={selected.has(item.id)}
                          disabled={
                            busy ||
                            !state.can_manage ||
                            state.compatibility_mode ||
                            !item.grantable
                          }
                          onCheckedChange={(checked) =>
                            setSelected((previous) => {
                              const next = new Set(previous);
                              if (checked) next.add(item.id);
                              else next.delete(item.id);
                              return next;
                            })
                          }
                        />
                        <div className="min-w-0 flex-1 space-y-0.5">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <label
                              htmlFor={inputId}
                              className="text-sm font-medium leading-5"
                            >
                              {label}
                              <span className="sr-only"> ({item.id})</span>
                            </label>
                            {item.risk === 'dangerous' && (
                              <Badge
                                variant="destructive"
                                className="h-5 px-1.5 text-[11px]"
                              >
                                {t('pluginPermissions.dangerous')}
                              </Badge>
                            )}
                            {item.id === 'bot.message.send' && (
                              <Badge
                                variant="outline"
                                className="h-5 border-amber-500/60 px-1.5 text-[11px] text-amber-700 dark:text-amber-400"
                              >
                                {t('pluginPermissions.sendsMessages')}
                              </Badge>
                            )}
                          </div>
                          {label !== item.id && (
                            <p className="break-all font-mono text-[11px] text-muted-foreground">
                              {item.id}
                            </p>
                          )}
                          {description && (
                            <p className="text-xs text-muted-foreground">
                              {description}
                            </p>
                          )}
                          {!item.grantable && !item.granted && (
                            <p className="text-xs text-amber-700 dark:text-amber-400">
                              {t('pluginPermissions.requires', {
                                permissions:
                                  item.required_permissions.join(', '),
                              })}
                            </p>
                          )}
                        </div>
                        {item.granted && (
                          <div className="flex shrink-0 items-center gap-1.5">
                            <Badge
                              variant="secondary"
                              className="h-5 px-1.5 text-[11px]"
                            >
                              {t('pluginPermissions.granted')}
                            </Badge>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 px-2 text-xs text-muted-foreground hover:text-destructive"
                              disabled={busy || !state.can_manage}
                              onClick={() => void save(false, item)}
                            >
                              {t('pluginPermissions.revoke')}
                            </Button>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}
        </div>
        <div className="flex justify-end">
          <Button
            disabled={busy || !canConfirm || compatibilityBlocked}
            onClick={() => setConfirming(true)}
          >
            {t('pluginPermissions.review')}
          </Button>
        </div>
        <Dialog open={confirming} onOpenChange={setConfirming}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>{t('pluginPermissions.confirm')}</DialogTitle>
              <DialogDescription>
                {t(
                  state.compatibility_mode
                    ? 'pluginPermissions.compatibilityWarning'
                    : 'pluginPermissions.confirmDescription',
                )}
              </DialogDescription>
            </DialogHeader>
            <p className="text-sm font-medium">
              {t('pluginPermissions.grantSummary', { count: toGrant.length })}
            </p>
            {attention.length > 0 && (
              <div className="space-y-1.5 rounded-md border border-destructive/40 bg-destructive/5 p-3">
                <p className="flex items-center gap-1.5 text-xs font-medium text-destructive">
                  <TriangleAlert className="size-3.5" />
                  {t('pluginPermissions.highlighted')}
                </p>
                <ul className="space-y-1 text-sm">
                  {attention.map((item) => (
                    <li key={item.id} className="flex items-baseline gap-2">
                      <span>{labelFor(item).label}</span>
                      <span className="font-mono text-xs text-destructive">
                        {item.id}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <ul className="max-h-48 space-y-1 overflow-y-auto text-sm text-muted-foreground">
              {toGrant
                .filter((item) => !needsAttention(item))
                .map((item) => (
                  <li key={item.id} className="flex items-baseline gap-2">
                    <span className="text-foreground">
                      {labelFor(item).label}
                    </span>
                    <span className="font-mono text-xs">{item.id}</span>
                  </li>
                ))}
            </ul>
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
                {t('pluginPermissions.confirm')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
