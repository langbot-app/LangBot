import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Workflow } from '@/app/infra/entities/api';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Trash2, AlertTriangle } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import EmojiPicker from '@/components/ui/emoji-picker';

interface WorkflowFormComponentProps {
  workflow: Workflow | null;
  onWorkflowChange: (workflow: Workflow) => void;
  onDelete: () => void;
}

export default function WorkflowFormComponent({
  workflow,
  onWorkflowChange,
  onDelete,
}: WorkflowFormComponentProps) {
  const { t } = useTranslation();
  const [name, setName] = useState(workflow?.name || '');
  const [description, setDescription] = useState(workflow?.description || '');
  const [emoji, setEmoji] = useState(workflow?.emoji || '🔄');
  const [isEnabled, setIsEnabled] = useState(workflow?.is_enabled ?? true);
  const isSyncingFromProp = useRef(false);

  // Sync with workflow prop
  useEffect(() => {
    if (workflow) {
      isSyncingFromProp.current = true;
      setName(workflow.name || '');
      setDescription(workflow.description || '');
      setEmoji(workflow.emoji || '🔄');
      setIsEnabled(workflow.is_enabled ?? true);
    }
  }, [workflow?.uuid, workflow?.version]);

  // Update parent when values change (skip if the change came from prop sync)
  useEffect(() => {
    if (isSyncingFromProp.current) {
      isSyncingFromProp.current = false;
      return;
    }
    if (workflow) {
      onWorkflowChange({
        ...workflow,
        name,
        description,
        emoji,
        is_enabled: isEnabled,
      });
    }
  }, [name, description, emoji, isEnabled]);

  if (!workflow) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground">
        {t('workflows.loading')}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Basic Info Card */}
      <Card>
        <CardHeader>
          <CardTitle>{t('workflows.basicInfo')}</CardTitle>
          <CardDescription>{t('workflows.basicInfoDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Name with Emoji */}
          <div className="space-y-2">
            <Label htmlFor="workflow-name">{t('workflows.name')}</Label>
            <div className="flex gap-2">
              <EmojiPicker value={emoji} onChange={setEmoji} />
              <Input
                id="workflow-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('workflows.namePlaceholder')}
                className="flex-1"
              />
            </div>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="workflow-description">
              {t('workflows.description')}
            </Label>
            <Textarea
              id="workflow-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t('workflows.descriptionPlaceholder')}
              rows={3}
            />
          </div>

          {/* Enabled toggle */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>{t('workflows.enabled')}</Label>
              <p className="text-sm text-muted-foreground">
                {t('workflows.enabledDesc')}
              </p>
            </div>
            <Switch checked={isEnabled} onCheckedChange={setIsEnabled} />
          </div>
        </CardContent>
      </Card>

      {/* Workflow Info */}
      <Card>
        <CardHeader>
          <CardTitle>{t('workflows.info')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">
                {t('workflows.uuid')}:
              </span>
              <span className="ml-2 font-mono">{workflow.uuid}</span>
            </div>
            <div>
              <span className="text-muted-foreground">
                {t('workflows.version')}:
              </span>
              <span className="ml-2">{workflow.version || 1}</span>
            </div>
            <div>
              <span className="text-muted-foreground">
                {t('workflows.createdAt')}:
              </span>
              <span className="ml-2">
                {workflow.created_at
                  ? new Date(workflow.created_at).toLocaleString()
                  : '-'}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">
                {t('workflows.updatedAt')}:
              </span>
              <span className="ml-2">
                {workflow.updated_at
                  ? new Date(workflow.updated_at).toLocaleString()
                  : '-'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="text-destructive flex items-center gap-2">
            <AlertTriangle className="size-5" />
            {t('workflows.dangerZone')}
          </CardTitle>
          <CardDescription>{t('workflows.dangerZoneDesc')}</CardDescription>
        </CardHeader>
        <CardContent>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive">
                <Trash2 className="size-4 mr-2" />
                {t('workflows.deleteWorkflow')}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>
                  {t('workflows.deleteConfirm')}
                </AlertDialogTitle>
                <AlertDialogDescription>
                  {t('workflows.deleteConfirmDesc', { name: workflow.name })}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                <AlertDialogAction onClick={onDelete}>
                  {t('common.delete')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </CardContent>
      </Card>
    </div>
  );
}
