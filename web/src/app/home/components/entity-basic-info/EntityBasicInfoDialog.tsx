import { FormEvent, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import EmojiPicker from '@/components/ui/emoji-picker';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export interface EntityBasicInfoValues {
  name: string;
  description: string;
  emoji?: string;
}

interface EntityBasicInfoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  values: EntityBasicInfoValues;
  defaultEmoji?: string;
  showEmoji?: boolean;
  onSave: (values: EntityBasicInfoValues) => Promise<void>;
}

export default function EntityBasicInfoDialog({
  open,
  onOpenChange,
  values,
  defaultEmoji,
  showEmoji = true,
  onSave,
}: EntityBasicInfoDialogProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(values);
  const [isSaving, setIsSaving] = useState(false);
  const [nameError, setNameError] = useState(false);

  useEffect(() => {
    if (!open) return;
    setDraft({
      name: values.name,
      description: values.description,
      emoji: values.emoji || defaultEmoji,
    });
    setNameError(false);
  }, [defaultEmoji, open, values.description, values.emoji, values.name]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = draft.name.trim();
    if (!name) {
      setNameError(true);
      return;
    }

    setIsSaving(true);
    try {
      await onSave({
        name,
        description: draft.description.trim(),
        emoji: showEmoji ? draft.emoji || defaultEmoji : undefined,
      });
      onOpenChange(false);
    } catch {
      // The caller presents the entity-specific error message.
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{t('common.editBasicInfo')}</DialogTitle>
            <DialogDescription>
              {t(
                showEmoji
                  ? 'common.editBasicInfoDescription'
                  : 'common.editBasicInfoDescriptionNoIcon',
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-5">
            <div className="flex items-start gap-4">
              <div className="min-w-0 flex-1 space-y-2">
                <Label htmlFor="entity-basic-name">{t('common.name')}</Label>
                <Input
                  id="entity-basic-name"
                  value={draft.name}
                  aria-invalid={nameError}
                  onChange={(event) => {
                    setDraft((current) => ({
                      ...current,
                      name: event.target.value,
                    }));
                    if (event.target.value.trim()) setNameError(false);
                  }}
                  autoFocus
                />
                {nameError && (
                  <p className="text-sm text-destructive">
                    {t('common.fieldRequired')}
                  </p>
                )}
              </div>

              {showEmoji && (
                <div className="space-y-2">
                  <Label>{t('common.icon')}</Label>
                  <EmojiPicker
                    value={draft.emoji || defaultEmoji}
                    onChange={(emoji) =>
                      setDraft((current) => ({ ...current, emoji }))
                    }
                    ariaLabel={t('common.icon')}
                  />
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="entity-basic-description">
                {t('common.description')}
              </Label>
              <Input
                id="entity-basic-description"
                value={draft.description}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    description: event.target.value,
                  }))
                }
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSaving}
            >
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? t('common.saving') : t('common.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
