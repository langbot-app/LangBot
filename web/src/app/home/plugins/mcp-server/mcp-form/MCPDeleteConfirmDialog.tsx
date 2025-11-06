'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { httpClient } from '@/app/infra/http/HttpClient';

interface MCPDeleteConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  serverName: string | null;
  onSuccess?: () => void;
}

export default function MCPDeleteConfirmDialog({
  open,
  onOpenChange,
  serverName,
  onSuccess,
}: MCPDeleteConfirmDialogProps) {
  const { t } = useTranslation();

  async function handleDelete() {
    if (!serverName) return;

    try {
      await httpClient.deleteMCPServer(serverName);
      toast.success(t('mcp.deleteSuccess'));

      onOpenChange(false);

      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      console.error('Failed to delete server:', error);
      toast.error(t('mcp.deleteFailed'));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('mcp.confirmDeleteTitle')}</DialogTitle>
        </DialogHeader>
        <DialogDescription>{t('mcp.confirmDeleteServer')}</DialogDescription>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button variant="destructive" onClick={handleDelete}>
            {t('common.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
