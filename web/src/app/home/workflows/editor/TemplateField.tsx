import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Braces } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { parseTemplate, refToken } from '../lib/template';
import {
  formatSample,
  useRefLabel,
  useVariableGroups,
  type VariableGroup,
} from './variables';
import { STEP_META } from '../lib/catalog';

const CHIP =
  'mx-0.5 inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-1.5 align-baseline text-xs leading-5 text-blue-700 dark:border-blue-900 dark:bg-blue-950/50 dark:text-blue-300';
const CHIP_UNKNOWN =
  'mx-0.5 inline-flex items-center rounded-md border border-red-200 bg-red-50 px-1.5 align-baseline text-xs leading-5 text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300';

function escapeHtml(text: string) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>');
}

/** Serialize the editable DOM back into template text. */
function serialize(root: Node): string {
  let out = '';
  root.childNodes.forEach((child, index) => {
    if (child.nodeType === Node.TEXT_NODE) {
      out += (child.textContent ?? '').replace(/​/g, '');
    } else if (child instanceof HTMLElement) {
      if (child.dataset.ref) {
        out += refToken(child.dataset.ref);
      } else if (child.tagName === 'BR') {
        out += '\n';
      } else {
        // Chrome wraps new lines in <div>.
        if (index > 0 && (child.tagName === 'DIV' || child.tagName === 'P')) {
          out += '\n';
        }
        out += serialize(child);
      }
    }
  });
  return out;
}

export function VariableMenu({
  groups,
  onPick,
}: {
  groups: VariableGroup[];
  onPick: (path: string) => void;
}) {
  const { t } = useTranslation();
  if (!groups.length) {
    return (
      <p className="p-3 text-sm text-muted-foreground">
        {t('workflows.variables.none')}
      </p>
    );
  }
  return (
    <div className="max-h-80 overflow-y-auto p-1 text-sm">
      <p className="px-2 py-1.5 text-xs text-muted-foreground">
        {t('workflows.variables.hint')}
      </p>
      {groups.map((group) => {
        const Icon = group.step ? STEP_META[group.step.type]?.icon : Braces;
        return (
          <div key={group.key} className="pb-1">
            <div className="flex items-center gap-1.5 px-2 pt-1.5 pb-1 text-xs font-medium text-foreground/80">
              {Icon && <Icon className="size-3.5" />}
              <span className="truncate">{group.title}</span>
            </div>
            {group.options.map((option) => (
              <button
                type="button"
                key={option.path}
                className="flex w-full items-center justify-between gap-3 rounded-md py-1.5 pr-2 pl-7 text-left hover:bg-muted"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => onPick(option.path)}
              >
                <span className="truncate">{option.label}</span>
                <span className="max-w-[45%] truncate text-xs text-muted-foreground">
                  {formatSample(option.sample)}
                </span>
              </button>
            ))}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Text input where `{{ step.key }}` references render as chips. Users insert
 * them from the variable menu instead of typing names.
 */
export default function TemplateField({
  stepId,
  value,
  onChange,
  multiline = false,
  placeholder,
  className,
  invalid,
  ariaLabel,
}: {
  stepId: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  placeholder?: string;
  className?: string;
  invalid?: boolean;
  ariaLabel?: string;
}) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);
  const lastValue = useRef<string | null>(null);
  const range = useRef<Range | null>(null);
  const [open, setOpen] = useState(false);
  const [empty, setEmpty] = useState(!value);
  const groups = useVariableGroups(stepId);
  const label = useRefLabel();

  const chipHtml = (path: string) => {
    const info = label(path);
    return `<span contenteditable="false" data-ref="${escapeHtml(path)}" class="${info.known ? CHIP : CHIP_UNKNOWN}">${escapeHtml(info.text)}</span>`;
  };

  // Render from the value only when it changed outside this editor.
  useEffect(() => {
    const root = ref.current;
    if (!root || value === lastValue.current) return;
    root.innerHTML = parseTemplate(value)
      .map((segment) =>
        segment.kind === 'text'
          ? escapeHtml(segment.text)
          : chipHtml(segment.path),
      )
      .join('');
    lastValue.current = value;
    setEmpty(!value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const emit = () => {
    const root = ref.current;
    if (!root) return;
    const next = serialize(root);
    lastValue.current = next;
    setEmpty(!next);
    if (next !== value) onChange(next);
  };

  const saveRange = () => {
    const selection = window.getSelection();
    if (
      selection &&
      selection.rangeCount &&
      ref.current?.contains(selection.anchorNode)
    ) {
      range.current = selection.getRangeAt(0).cloneRange();
    }
  };

  const insert = (path: string) => {
    const root = ref.current;
    if (!root) return;
    const holder = document.createElement('span');
    holder.innerHTML = chipHtml(path);
    const chip = holder.firstChild!;
    const target = range.current;
    if (target && root.contains(target.startContainer)) {
      target.deleteContents();
      target.insertNode(chip);
      target.setStartAfter(chip);
      target.collapse(true);
    } else {
      root.appendChild(chip);
    }
    setOpen(false);
    emit();
    root.focus();
    const selection = window.getSelection();
    const after = document.createRange();
    after.setStartAfter(chip);
    after.collapse(true);
    selection?.removeAllRanges();
    selection?.addRange(after);
    range.current = after.cloneRange();
  };

  return (
    <div className={cn('relative', className)}>
      <div
        ref={ref}
        role="textbox"
        aria-label={ariaLabel}
        aria-multiline={multiline}
        contentEditable
        suppressContentEditableWarning
        data-testid="template-field"
        className={cn(
          'w-full rounded-md border bg-transparent px-3 py-1.5 pr-9 text-sm leading-6 shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:border-ring',
          multiline
            ? 'min-h-24 whitespace-pre-wrap break-words'
            : 'min-h-9 overflow-x-auto whitespace-nowrap',
          invalid && 'border-destructive',
        )}
        onInput={emit}
        onBlur={() => {
          saveRange();
          emit();
        }}
        onKeyUp={saveRange}
        onMouseUp={saveRange}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !multiline) event.preventDefault();
        }}
        onPaste={(event) => {
          event.preventDefault();
          const text = event.clipboardData.getData('text/plain');
          document.execCommand(
            'insertText',
            false,
            multiline ? text : text.replace(/\s*\n\s*/g, ' '),
          );
        }}
      />
      {empty && placeholder && (
        <span className="pointer-events-none absolute top-1.5 left-3 text-sm leading-6 text-muted-foreground">
          {placeholder}
        </span>
      )}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="absolute top-1 right-1 size-7 text-muted-foreground"
            aria-label={t('workflows.variables.insert')}
            title={t('workflows.variables.insert')}
            onMouseDown={(event) => {
              event.preventDefault();
              saveRange();
            }}
          >
            <Braces className="size-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-80 p-0">
          <VariableMenu groups={groups} onPick={insert} />
        </PopoverContent>
      </Popover>
    </div>
  );
}
