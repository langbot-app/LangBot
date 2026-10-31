import { useTranslation } from 'react-i18next';
import type { Workflow } from '@/app/infra/entities/api';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import EmojiPicker from '@/components/ui/emoji-picker';

export default function WorkflowFormComponent({
  workflow,
  onWorkflowChange,
  onDelete,
}: {
  workflow: Workflow | null;
  onWorkflowChange: (workflow: Workflow) => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  if (!workflow) return null;
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <EmojiPicker
        value={workflow.emoji || '🔄'}
        onChange={(emoji) => onWorkflowChange({ ...workflow, emoji })}
      />
      <Label htmlFor="workflow-name">{t('common.name')}</Label>
      <Input
        id="workflow-name"
        value={workflow.name}
        onChange={(event) =>
          onWorkflowChange({ ...workflow, name: event.target.value })
        }
      />
      <Label htmlFor="workflow-description">{t('common.description')}</Label>
      <Textarea
        id="workflow-description"
        value={workflow.description || ''}
        onChange={(event) =>
          onWorkflowChange({ ...workflow, description: event.target.value })
        }
      />
      <div className="flex items-center gap-2">
        <Switch
          id="workflow-enabled"
          checked={workflow.is_enabled}
          onCheckedChange={(is_enabled) =>
            onWorkflowChange({ ...workflow, is_enabled })
          }
        />
        <Label htmlFor="workflow-enabled">{t('common.enabled')}</Label>
      </div>
      <Button
        variant="destructive"
        onClick={() => {
          if (window.confirm(t('workflows.deleteConfirmation'))) onDelete();
        }}
      >
        {t('common.delete')}
      </Button>
    </div>
  );
}
