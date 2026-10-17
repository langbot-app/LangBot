import { useEffect, useState } from 'react';
import { Loader2, SlidersHorizontal, Timer } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import type {
  OperationGovernance,
  OperationLevel,
} from '@/app/infra/entities/operation-log';

export interface OperationTraceCollectionSettings {
  level: OperationLevel;
  retentionDays: number;
  maxRows: number;
  dedupeSeconds: number;
}

export interface OperationTraceCollectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  governance: OperationGovernance | null;
  canConfigure: boolean;
  saving: boolean;
  onSave: (settings: OperationTraceCollectionSettings) => void;
}

/**
 * Collection settings for the operation log: capture level and retention.
 *
 * Edits stay local until Save is pressed, so a click on a level card never
 * changes what the instance collects. The Save button stays disabled while the
 * draft matches the persisted policy.
 */
export default function OperationTraceCollectionDialog({
  open,
  onOpenChange,
  governance,
  canConfigure,
  saving,
  onSave,
}: OperationTraceCollectionDialogProps) {
  const { t } = useTranslation();
  const [level, setLevel] = useState<OperationLevel>(0);
  const [retentionDays, setRetentionDays] = useState<number>(30);
  const [maxRows, setMaxRows] = useState<number>(20000);
  const [dedupeSeconds, setDedupeSeconds] = useState<number>(60);

  // Every open starts from the persisted policy, so a dialog dismissed with
  // unsaved edits never leaks them into a later session.
  useEffect(() => {
    if (!open || !governance) {
      return;
    }
    setLevel(governance.configured_level);
    setRetentionDays(governance.retention_days);
    setMaxRows(governance.max_rows);
    setDedupeSeconds(governance.dedupe_window_seconds);
  }, [open, governance]);

  const levelOptions = governance?.supported_levels ?? [];
  const dirty =
    governance !== null &&
    (level !== governance.configured_level ||
      retentionDays !== governance.retention_days ||
      maxRows !== governance.max_rows ||
      dedupeSeconds !== governance.dedupe_window_seconds);

  function resetDraft() {
    if (!governance) {
      return;
    }
    setLevel(governance.configured_level);
    setRetentionDays(governance.retention_days);
    setMaxRows(governance.max_rows);
    setDedupeSeconds(governance.dedupe_window_seconds);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('operationTrace.collectionSettings')}</DialogTitle>
          <DialogDescription>
            {t('operationTrace.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="size-4" />
              <h3 className="text-sm font-semibold">
                {t('operationTrace.captureLevel')}
              </h3>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              {levelOptions.map((option) => {
                const selected = level === option.level;
                return (
                  <button
                    key={option.level}
                    type="button"
                    disabled={!canConfigure || saving}
                    onClick={() => setLevel(option.level)}
                    className={`rounded-lg border p-3 text-left transition-colors disabled:opacity-60 ${
                      selected
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-muted/50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">
                        {t(`${option.i18n_key}.label`)}
                      </span>
                      <Badge variant={selected ? 'default' : 'outline'}>
                        L{option.level}
                      </Badge>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <Timer className="size-4" />
              <h3 className="text-sm font-semibold">
                {t('operationTrace.retention')}
              </h3>
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">
                  {t('operationTrace.retentionDays')}
                </span>
                <Input
                  type="number"
                  className="w-28"
                  min={governance?.limits.min_retention_days ?? 1}
                  max={governance?.limits.max_retention_days ?? 3650}
                  value={retentionDays}
                  disabled={!canConfigure}
                  onChange={(event) =>
                    setRetentionDays(Number(event.target.value))
                  }
                />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">
                  {t('operationTrace.maxRows')}
                </span>
                <Input
                  type="number"
                  className="w-32"
                  min={governance?.limits.min_max_rows ?? 100}
                  max={governance?.limits.max_max_rows ?? 500000}
                  value={maxRows}
                  disabled={!canConfigure}
                  onChange={(event) => setMaxRows(Number(event.target.value))}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">
                  {t('operationTrace.dedupeWindow')}
                </span>
                <Input
                  type="number"
                  className="w-28"
                  min={governance?.limits.min_dedupe_window_seconds ?? 0}
                  max={governance?.limits.max_dedupe_window_seconds ?? 3600}
                  value={dedupeSeconds}
                  disabled={!canConfigure}
                  onChange={(event) =>
                    setDedupeSeconds(Number(event.target.value))
                  }
                />
              </label>
            </div>
          </section>
        </div>

        <DialogFooter className="gap-2 sm:justify-end">
          <Button
            variant="outline"
            size="sm"
            onClick={resetDraft}
            disabled={!dirty || saving}
          >
            {t('operationTrace.reset')}
          </Button>
          <Button
            size="sm"
            onClick={() =>
              onSave({ level, retentionDays, maxRows, dedupeSeconds })
            }
            disabled={!dirty || saving || !canConfigure}
          >
            {saving ? <Loader2 className="size-3.5 animate-spin" /> : null}
            {t('operationTrace.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
