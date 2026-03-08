'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useAsyncTask, AsyncTaskStatus } from '@/hooks/useAsyncTask';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';

interface KBMigrationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  internalKbCount: number;
  externalKbCount: number;
  onMigrationComplete: () => void;
}

export default function KBMigrationDialog({
  open,
  onOpenChange,
  internalKbCount,
  externalKbCount,
  onMigrationComplete,
}: KBMigrationDialogProps) {
  const { t } = useTranslation();
  const [dismissing, setDismissing] = useState(false);

  const asyncTask = useAsyncTask({
    onSuccess: () => {
      toast.success(t('knowledge.migration.success'));
      onOpenChange(false);
      onMigrationComplete();
    },
    onError: (error) => {
      toast.error(`${t('knowledge.migration.error')}${error}`);
    },
  });

  const handleMigration = async (installPlugin: boolean) => {
    try {
      const resp = await httpClient.executeRagMigration(installPlugin);
      asyncTask.startTask(resp.task_id);
    } catch {
      toast.error(t('knowledge.migration.error'));
    }
  };

  const handleDismiss = async () => {
    setDismissing(true);
    try {
      await httpClient.dismissRagMigration();
      onOpenChange(false);
    } catch {
      toast.error(t('knowledge.migration.dismissError'));
    } finally {
      setDismissing(false);
    }
  };

  const isRunning = asyncTask.status === AsyncTaskStatus.RUNNING;
  const isError = asyncTask.status === AsyncTaskStatus.ERROR;
  const totalCount = internalKbCount + externalKbCount;

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!isRunning) onOpenChange(v);
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('knowledge.migration.title')}</DialogTitle>
          <DialogDescription>
            {t('knowledge.migration.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="py-4 space-y-3">
          {!isRunning && !isError && (
            <p className="text-sm text-muted-foreground">
              {t('knowledge.migration.detected', {
                total: totalCount,
                internal: internalKbCount,
                external: externalKbCount,
              })}
            </p>
          )}

          {isRunning && (
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <p className="text-sm">{t('knowledge.migration.running')}</p>
            </div>
          )}

          {isError && (
            <div className="space-y-2">
              <p className="text-sm text-destructive">
                {t('knowledge.migration.error')}
              </p>
              {asyncTask.error && (
                <p className="text-xs text-muted-foreground bg-muted p-2 rounded">
                  {asyncTask.error}
                </p>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="flex flex-col gap-2 sm:flex-col">
          {!isRunning && !isError && (
            <>
              <Button onClick={() => handleMigration(true)} className="w-full">
                {t('knowledge.migration.startWithInstall')}
              </Button>
              <Button
                variant="outline"
                onClick={() => handleMigration(false)}
                className="w-full"
              >
                {t('knowledge.migration.startDataOnly')}
              </Button>
              <p className="text-xs text-muted-foreground text-center">
                {t('knowledge.migration.dataOnlyHint')}
              </p>
            </>
          )}
          {isError && (
            <Button onClick={() => handleMigration(true)} className="w-full">
              {t('knowledge.migration.retry')}
            </Button>
          )}
          {!isRunning && (
            <Button
              variant="ghost"
              onClick={handleDismiss}
              disabled={dismissing}
              className="w-full"
            >
              {t('knowledge.migration.dismiss')}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
