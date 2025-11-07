'use client';

import * as React from 'react';
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Copy, Trash2, Plus } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogPortal,
  AlertDialogOverlay,
} from '@/components/ui/alert-dialog';
import * as AlertDialogPrimitive from '@radix-ui/react-alert-dialog';
import { backendClient } from '@/app/infra/http';

interface ApiKey {
  id: number;
  name: string;
  key: string;
  description: string;
  created_at: string;
}

interface ApiKeyManagementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function ApiKeyManagementDialog({
  open,
  onOpenChange,
}: ApiKeyManagementDialogProps) {
  const { t } = useTranslation();
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyDescription, setNewKeyDescription] = useState('');
  const [createdKey, setCreatedKey] = useState<ApiKey | null>(null);
  const [deleteKeyId, setDeleteKeyId] = useState<number | null>(null);

  // 清理 body 样式，防止对话框关闭后页面无法交互
  useEffect(() => {
    if (!deleteKeyId) {
      const cleanup = () => {
        document.body.style.removeProperty('pointer-events');
      };

      cleanup();
      const timer = setTimeout(cleanup, 100);
      return () => clearTimeout(timer);
    }
  }, [deleteKeyId]);

  useEffect(() => {
    if (open) {
      loadApiKeys();
    }
  }, [open]);

  const loadApiKeys = async () => {
    setLoading(true);
    try {
      const response = (await backendClient.get('/api/v1/apikeys')) as {
        keys: ApiKey[];
      };
      setApiKeys(response.keys || []);
    } catch (error) {
      toast.error(`Failed to load API keys: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateApiKey = async () => {
    if (!newKeyName.trim()) {
      toast.error(t('common.apiKeyNameRequired'));
      return;
    }

    try {
      const response = (await backendClient.post('/api/v1/apikeys', {
        name: newKeyName,
        description: newKeyDescription,
      })) as { key: ApiKey };

      setCreatedKey(response.key);
      toast.success(t('common.apiKeyCreated'));
      setNewKeyName('');
      setNewKeyDescription('');
      setShowCreateDialog(false);
      loadApiKeys();
    } catch (error) {
      toast.error(`Failed to create API key: ${error}`);
    }
  };

  const handleDeleteApiKey = async (keyId: number) => {
    try {
      await backendClient.delete(`/api/v1/apikeys/${keyId}`);
      toast.success(t('common.apiKeyDeleted'));
      loadApiKeys();
      setDeleteKeyId(null);
    } catch (error) {
      toast.error(`Failed to delete API key: ${error}`);
    }
  };

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    toast.success(t('common.apiKeyCopied'));
  };

  const maskApiKey = (key: string) => {
    if (key.length <= 8) return key;
    return `${key.substring(0, 8)}...${key.substring(key.length - 4)}`;
  };

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(newOpen) => {
          // 如果删除确认框是打开的，不允许关闭主对话框
          if (!newOpen && deleteKeyId) {
            return;
          }
          onOpenChange(newOpen);
        }}
      >
        <DialogContent className="sm:max-w-[700px]">
          <DialogHeader>
            <DialogTitle>{t('common.manageApiKeys')}</DialogTitle>
            <DialogDescription>{t('common.apiKeyHint')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="flex justify-end">
              <Button
                onClick={() => setShowCreateDialog(true)}
                size="sm"
                className="gap-2"
              >
                <Plus className="h-4 w-4" />
                {t('common.createApiKey')}
              </Button>
            </div>

            {loading ? (
              <div className="text-center py-8 text-muted-foreground">
                {t('common.loading')}
              </div>
            ) : apiKeys.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {t('common.noApiKeys')}
              </div>
            ) : (
              <div className="border rounded-md">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('common.name')}</TableHead>
                      <TableHead>{t('common.apiKeyValue')}</TableHead>
                      <TableHead className="w-[100px]">
                        {t('common.actions')}
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {apiKeys.map((key) => (
                      <TableRow key={key.id}>
                        <TableCell>
                          <div>
                            <div className="font-medium">{key.name}</div>
                            {key.description && (
                              <div className="text-sm text-muted-foreground">
                                {key.description}
                              </div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <code className="text-sm bg-muted px-2 py-1 rounded">
                            {maskApiKey(key.key)}
                          </code>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleCopyKey(key.key)}
                              title={t('common.copyApiKey')}
                            >
                              <Copy className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDeleteKeyId(key.id)}
                              title={t('common.delete')}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              {t('common.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create API Key Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('common.createApiKey')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{t('common.name')}</label>
              <Input
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                placeholder={t('common.name')}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">
                {t('common.description')}
              </label>
              <Input
                value={newKeyDescription}
                onChange={(e) => setNewKeyDescription(e.target.value)}
                placeholder={t('common.description')}
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowCreateDialog(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button onClick={handleCreateApiKey}>{t('common.create')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Show Created Key Dialog */}
      <Dialog open={!!createdKey} onOpenChange={() => setCreatedKey(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('common.apiKeyCreated')}</DialogTitle>
            <DialogDescription>
              {t('common.apiKeyCreatedMessage')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">
                {t('common.apiKeyValue')}
              </label>
              <div className="flex gap-2 mt-1">
                <Input value={createdKey?.key || ''} readOnly />
                <Button
                  onClick={() => createdKey && handleCopyKey(createdKey.key)}
                  variant="outline"
                  size="icon"
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setCreatedKey(null)}>
              {t('common.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteKeyId}>
        <AlertDialogPortal>
          <AlertDialogOverlay
            className="z-[60]"
            onClick={() => setDeleteKeyId(null)}
          />
          <AlertDialogPrimitive.Content
            className="fixed left-[50%] top-[50%] z-[60] grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 sm:rounded-lg"
            onEscapeKeyDown={() => setDeleteKeyId(null)}
          >
            <AlertDialogHeader>
              <AlertDialogTitle>{t('common.confirmDelete')}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('common.apiKeyDeleteConfirm')}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => setDeleteKeyId(null)}>
                {t('common.cancel')}
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={() => deleteKeyId && handleDeleteApiKey(deleteKeyId)}
              >
                {t('common.delete')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogPrimitive.Content>
        </AlertDialogPortal>
      </AlertDialog>
    </>
  );
}
