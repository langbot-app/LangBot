import { useEffect, useSyncExternalStore } from 'react';
import { Star } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import { Button } from '@/components/ui/button';

const records = new Map<string, { uuid: string | null; busy: boolean; loaded: boolean }>();
const listeners = new Set<() => void>();
const pending = new Map<string, Promise<void>>();
const empty = { uuid: null, busy: false, loaded: false };
const subscribe = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; };
function update(workspace: string, value: typeof empty | { uuid: string | null; busy: boolean; loaded: boolean }) {
  records.set(workspace, value);
  listeners.forEach((listener) => listener());
}

export default function ModelStar({ uuid, disabled }: { uuid: string; disabled: boolean }) {
  const workspace = useCurrentWorkspace()?.workspace.uuid ?? '';
  const { t } = useTranslation();
  const state = useSyncExternalStore(subscribe, () => records.get(workspace) ?? empty);
  useEffect(() => {
    if (!workspace || pending.has(workspace)) return;
    const request = backendClient.getStarredModel().then((result) => {
      update(workspace, { uuid: result.uuid, busy: false, loaded: true });
    }).catch(() => { update(workspace, { uuid: null, busy: false, loaded: false }); })
      .finally(() => pending.delete(workspace));
    pending.set(workspace, request);
  }, [workspace]);
  const starred = state.uuid === uuid;
  return <Button type="button" variant="ghost" size="icon" className={`size-7 shrink-0 ${starred ? 'text-amber-500 hover:text-amber-600' : 'text-muted-foreground'}`}
    disabled={disabled || state.busy || !state.loaded}
    aria-pressed={starred} aria-label={t(starred ? 'models.unstarModel' : 'models.starModel')}
    title={t(starred ? 'models.unstarModel' : 'models.starModel')}
    onPointerDown={(event) => event.stopPropagation()}
    onClick={async (event) => {
      event.stopPropagation();
      const next = starred ? null : uuid;
      update(workspace, { ...state, busy: true });
      try {
        await backendClient.setStarredModel(next);
        update(workspace, { uuid: next, busy: false, loaded: true });
      } catch {
        update(workspace, { ...state, busy: false });
        toast.error(t('models.starModelFailed'));
      }
    }}><Star className={`size-3.5 ${starred ? 'fill-current' : ''}`} /></Button>;
}
