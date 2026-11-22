import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Settings2, X } from 'lucide-react';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';

export default function CommandPrefixPopover({
  prefixes,
  onChange,
  disabled,
}: {
  prefixes: string[];
  onChange: (prefixes: string[]) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState('');

  function add() {
    const trimmed = draft.trim();
    if (!trimmed || /\s/.test(trimmed)) {
      toast.error(t('bots.pluginCommands.prefixInvalid'));
      return;
    }
    if (prefixes.includes(trimmed)) {
      toast.error(t('bots.pluginCommands.prefixDuplicate'));
      return;
    }
    onChange([...prefixes, trimmed]);
    setDraft('');
  }

  function remove(prefix: string) {
    if (prefixes.length <= 1) {
      toast.error(t('bots.pluginCommands.prefixInvalid'));
      return;
    }
    onChange(prefixes.filter((item) => item !== prefix));
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          className="h-7 gap-1 px-2 text-xs"
          data-testid="command-prefix-button"
          aria-label={t('bots.pluginCommands.prefixes')}
        >
          <Settings2 className="size-3.5" />
          <span className="font-mono">{prefixes.join(' ')}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 space-y-2 p-3">
        <Label className="text-xs font-medium">
          {t('bots.pluginCommands.prefixes')}
        </Label>
        <div className="flex flex-wrap items-center gap-1.5">
          {prefixes.map((prefix) => (
            <Badge
              key={prefix}
              variant="secondary"
              className="flex h-7 items-center gap-1 px-2 font-mono text-sm"
            >
              {prefix}
              {prefixes.length > 1 && (
                <button
                  type="button"
                  onClick={() => remove(prefix)}
                  className="rounded-full p-0.5 text-muted-foreground hover:text-foreground"
                  aria-label={`${t('common.remove')} ${prefix}`}
                >
                  <X className="size-3" />
                </button>
              )}
            </Badge>
          ))}
        </div>
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              add();
            }
          }}
          placeholder={t('bots.pluginCommands.prefixPlaceholder')}
          aria-label={t('bots.pluginCommands.addPrefix')}
          className="h-8 font-mono text-xs"
        />
      </PopoverContent>
    </Popover>
  );
}
