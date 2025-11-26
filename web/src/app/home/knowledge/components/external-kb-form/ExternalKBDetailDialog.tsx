import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useTranslation } from 'react-i18next';
import ExternalKBForm from './ExternalKBForm';

interface ExternalKBDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  kbId?: string;
  onKBDeleted: () => void;
  onNewKBCreated: (kbId: string) => void;
}

export default function ExternalKBDetailDialog({
  open,
  onOpenChange,
  kbId,
  onKBDeleted,
  onNewKBCreated,
}: ExternalKBDetailDialogProps) {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {kbId
              ? t('knowledge.editKnowledgeBase')
              : t('knowledge.addExternal')}
          </DialogTitle>
        </DialogHeader>

        <ExternalKBForm
          initKBId={kbId}
          onFormSubmit={() => {
            onOpenChange(false);
          }}
          onKBDeleted={() => {
            onKBDeleted();
            onOpenChange(false);
          }}
          onNewKBCreated={(newKbId) => {
            onNewKBCreated(newKbId);
          }}
        />

        <div className="flex justify-end gap-2 pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="external-kb-form">
            {t('common.save')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
