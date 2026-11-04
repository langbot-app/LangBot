import { useCallback, useEffect, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { backendClient } from '@/app/infra/http';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  permissionGrantRequest,
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
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('pluginPermissions.title')}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {state.compatibility_mode && (
          <div
            role="alert"
            className="rounded-md border border-amber-500 bg-amber-500/10 p-3 text-sm"
          >
            <Badge variant="outline">{t('pluginPermissions.undeclared')}</Badge>
            <p className="mt-2">
              {t('pluginPermissions.compatibilityWarning')}
            </p>
          </div>
        )}
        {state.pending_confirmation && (
          <p role="status" className="text-sm font-medium">
            {t('pluginPermissions.pending')}
          </p>
        )}
        {!canConfirm && (
          <p role="alert" className="text-sm text-muted-foreground">
            {t('pluginPermissions.managerRequired')}
          </p>
        )}
        <div className="max-h-96 space-y-3 overflow-y-auto">
          {state.permissions.map((item) => (
            <div
              key={`${item.category}:${item.id}`}
              className="space-y-1 rounded-md border p-2"
            >
              <div className="flex items-start gap-2">
                <Checkbox
                  id={`${inputPrefix}-${item.id}`}
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
                <label
                  htmlFor={`${inputPrefix}-${item.id}`}
                  className="flex-1 break-all font-mono text-xs"
                >
                  {item.id}
                </label>
                {item.granted && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy || !state.can_manage}
                    onClick={() => void save(false, item)}
                  >
                    {t('pluginPermissions.revoke')}
                  </Button>
                )}
              </div>
              {item.risk === 'dangerous' && (
                <Badge variant="destructive">
                  {t('pluginPermissions.dangerous')}
                </Badge>
              )}
              {item.id === 'bot.message.send' && (
                <Badge variant="outline">
                  {t('pluginPermissions.sendsMessages')}
                </Badge>
              )}
              {!item.grantable && !item.granted && (
                <p className="text-xs text-muted-foreground">
                  {t('pluginPermissions.requires', {
                    permissions: item.required_permissions.join(', '),
                  })}
                </p>
              )}
            </div>
          ))}
        </div>
        <Button
          disabled={busy || !canConfirm || compatibilityBlocked}
          onClick={() => setConfirming(true)}
        >
          {t('pluginPermissions.review')}
        </Button>
        <Dialog open={confirming} onOpenChange={setConfirming}>
          <DialogContent>
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
            <ul className="max-h-60 space-y-1 overflow-y-auto text-sm">
              {state.permissions
                .filter(
                  (item) =>
                    (state.compatibility_mode || selected.has(item.id)) &&
                    (item.risk === 'dangerous' ||
                      item.id === 'bot.message.send'),
                )
                .map((item) => (
                  <li key={item.id} className="font-mono text-destructive">
                    {item.id}
                  </li>
                ))}
            </ul>
            <DialogFooter>
              <Button disabled={busy} onClick={() => void save(true)}>
                {t('pluginPermissions.confirm')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
