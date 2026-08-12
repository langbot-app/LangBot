import { BrainCircuit, ChevronDown, ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ReasoningLevel } from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Slider } from '@/components/ui/slider';

export const REASONING_LEVELS: ReasoningLevel[] = [
  'provider_default',
  'disabled',
  'enabled',
  'minimal',
  'low',
  'medium',
  'high',
  'xhigh',
  'max',
];

export const REASONING_LEVEL_LABEL_KEYS: Record<ReasoningLevel, string> = {
  provider_default: 'models.reasoningLevels.providerDefault',
  disabled: 'models.reasoningLevels.disabled',
  enabled: 'models.reasoningLevels.enabled',
  minimal: 'models.reasoningLevels.minimal',
  low: 'models.reasoningLevels.low',
  medium: 'models.reasoningLevels.medium',
  high: 'models.reasoningLevels.high',
  xhigh: 'models.reasoningLevels.xhigh',
  max: 'models.reasoningLevels.max',
};

interface ReasoningLevelPickerProps {
  value: ReasoningLevel;
  levels: ReasoningLevel[];
  disabled?: boolean;
  onChange: (value: ReasoningLevel) => void;
}

export default function ReasoningLevelPicker({
  value,
  levels,
  disabled = false,
  onChange,
}: ReasoningLevelPickerProps) {
  const { t } = useTranslation();
  const safeLevels: ReasoningLevel[] =
    levels.length > 0 ? levels : ['provider_default'];
  const safeValue: ReasoningLevel = safeLevels.includes(value)
    ? value
    : safeLevels[0];
  const currentLabel = t(REASONING_LEVEL_LABEL_KEYS[safeValue]);
  const isExplicit = safeValue !== 'provider_default';
  const currentIndex = Math.max(0, safeLevels.indexOf(safeValue));

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled || safeLevels.length <= 1}
          aria-label={`${t('models.reasoningLevel')}: ${currentLabel}`}
          className="h-9 w-9 shrink-0 gap-1.5 px-2.5 text-xs font-normal sm:w-auto sm:max-w-36"
        >
          <BrainCircuit
            className={`size-4 shrink-0 ${isExplicit ? 'text-primary' : 'text-muted-foreground'}`}
          />
          <span className="hidden min-w-0 truncate sm:block">
            {currentLabel}
          </span>
          <ChevronDown className="hidden size-3.5 shrink-0 text-muted-foreground sm:block" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[272px] p-4">
        <div className="flex h-5 items-center gap-0.5 text-sm text-muted-foreground">
          <span>{currentLabel}</span>
          <ChevronRight className="size-3.5" />
        </div>
        <Slider
          className="mt-5"
          min={0}
          max={Math.max(0, safeLevels.length - 1)}
          step={1}
          value={[currentIndex]}
          aria-label={t('models.reasoningLevel')}
          aria-valuetext={currentLabel}
          onValueChange={([index]) => onChange(safeLevels[index])}
        />
      </PopoverContent>
    </Popover>
  );
}
