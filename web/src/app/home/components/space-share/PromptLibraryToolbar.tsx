import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Library, Share2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type {
  PromptKind,
  PromptMessage,
} from '@/app/infra/entities/space-share';
import PromptLibraryDialog from './PromptLibraryDialog';
import SharePromptDialog from './SharePromptDialog';

/**
 * Compact entry points above a prompt-editor field: open the Space prompt
 * library or share the current prompt (LANG-439).
 */
export default function PromptLibraryToolbar({
  kind,
  value,
  onChange,
}: {
  kind: PromptKind;
  value: PromptMessage[];
  onChange: (value: PromptMessage[]) => void;
}) {
  const { t } = useTranslation();
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const hasContent = value.some((m) => (m.content || '').trim() !== '');

  const apply = (messages: PromptMessage[], mode: 'replace' | 'append') => {
    if (mode === 'replace' || !hasContent) {
      onChange(messages);
      return;
    }
    // Append: the library system prompt extends the current one, extra
    // few-shot turns are added at the end.
    const [current, ...rest] = value;
    const [incoming, ...incomingRest] = messages;
    const system = {
      role: 'system',
      content: [current?.content || '', incoming?.content || '']
        .filter((s) => s.trim())
        .join('\n\n'),
    };
    onChange([system, ...rest, ...incomingRest]);
  };

  return (
    <div className="flex flex-wrap items-center justify-end gap-1.5">
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-7 gap-1 px-2 text-xs"
        onClick={() => setLibraryOpen(true)}
      >
        <Library className="size-3.5" />
        {t('promptLibrary.open')}
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-7 gap-1 px-2 text-xs"
        disabled={!hasContent}
        onClick={() => setShareOpen(true)}
      >
        <Share2 className="size-3.5" />
        {t('spaceShare.shareShort')}
      </Button>
      <PromptLibraryDialog
        open={libraryOpen}
        onOpenChange={setLibraryOpen}
        defaultKind={kind}
        hasCurrentContent={hasContent}
        onApply={apply}
      />
      {shareOpen && (
        <SharePromptDialog
          open={shareOpen}
          onOpenChange={setShareOpen}
          kind={kind}
          messages={value}
        />
      )}
    </div>
  );
}
