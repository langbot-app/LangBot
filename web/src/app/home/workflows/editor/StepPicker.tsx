import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import type { WorkflowStepType } from '@/app/infra/entities/api';
import { PICKER_ORDER, STEP_META, type StepCategory } from '../lib/catalog';

const CATEGORIES: StepCategory[] = ['ai', 'logic', 'action'];

export default function StepPicker({
  available,
  allowTerminal,
  onPick,
}: {
  available: Set<string> | null;
  allowTerminal: boolean;
  onPick: (type: WorkflowStepType) => void;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const needle = query.trim().toLowerCase();
  const types = PICKER_ORDER.filter(
    (type) =>
      (!available || available.has(type)) &&
      (allowTerminal || !STEP_META[type].terminal) &&
      (!needle ||
        t(`workflows.steps.${type}`).toLowerCase().includes(needle) ||
        t(`workflows.stepDesc.${type}`).toLowerCase().includes(needle)),
  );
  return (
    <div className="w-[460px] p-2 text-sm" data-testid="step-picker">
      <div className="relative mb-1">
        <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
        <Input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('workflows.picker.search')}
          className="pl-8"
        />
      </div>
      {CATEGORIES.map((category) => {
        const items = types.filter(
          (type) => STEP_META[type].category === category,
        );
        if (!items.length) return null;
        return (
          <div key={category}>
            <p className="px-2 pt-2 pb-1 text-xs text-muted-foreground">
              {t(`workflows.picker.${category}`)}
            </p>
            <div className="grid grid-cols-2 gap-0.5">
              {items.map((type) => {
                const meta = STEP_META[type];
                const Icon = meta.icon;
                return (
                  <button
                    key={type}
                    type="button"
                    data-testid={`pick-${type}`}
                    className="flex gap-2.5 rounded-lg p-2 text-left hover:bg-muted"
                    onClick={() => onPick(type)}
                  >
                    <span
                      className={cn(
                        'grid size-8 shrink-0 place-items-center rounded-lg',
                        meta.tone,
                      )}
                    >
                      <Icon className="size-4" />
                    </span>
                    <span className="min-w-0">
                      <span className="block font-medium leading-5">
                        {t(`workflows.steps.${type}`)}
                      </span>
                      <span className="block text-xs leading-4 text-muted-foreground">
                        {t(`workflows.stepDesc.${type}`)}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
      {!types.length && (
        <p className="p-3 text-center text-muted-foreground">
          {t('workflows.picker.empty')}
        </p>
      )}
    </div>
  );
}
