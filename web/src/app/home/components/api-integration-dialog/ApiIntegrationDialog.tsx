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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
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

interface Webhook {
  id: number;
  name: string;
  url: string;
  description: string;
  enabled: boolean;
  created_at: string;
}

interface ApiIntegrationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function ApiIntegrationDialog({
  open,
  onOpenChange,
}: ApiIntegrationDialogProps) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('apikeys');
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyDescription, setNewKeyDescription] = useState('');
  const [createdKey, setCreatedKey] = useState<ApiKey | null>(null);
  const [deleteKeyId, setDeleteKeyId] = useState<number | null>(null);

  // Webhook state
  const [showCreateWebhookDialog, setShowCreateWebhookDialog] = useState(false);
  const [newWebhookName, setNewWebhookName] = useState('');
  const [newWebhookUrl, setNewWebhookUrl] = useState('');
  const [newWebhookDescription, setNewWebhookDescription] = useState('');
  const [newWebhookEnabled, setNewWebhookEnabled] = useState(true);
  const [deleteWebhookId, setDeleteWebhookId] = useState<number | null>(null);

  // 清理 body 样式，防止对话框关闭后页面无法交互
  useEffect(() => {
    if (!deleteKeyId && !deleteWebhookId) {
      const cleanup = () => {
        document.body.style.removeProperty('pointer-events');
      };

      cleanup();
      const timer = setTimeout(cleanup, 100);
      return () => clearTimeout(timer);
    }
  }, [deleteKeyId, deleteWebhookId]);

  useEffect(() => {
    if (open) {
      loadApiKeys();
      loadWebhooks();
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

  // Webhook methods
  const loadWebhooks = async () => {
    setLoading(true);
    try {
      const response = (await backendClient.get('/api/v1/webhooks')) as {
        webhooks: Webhook[];
      };
      setWebhooks(response.webhooks || []);
    } catch (error) {
      toast.error(`Failed to load webhooks: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateWebhook = async () => {
    if (!newWebhookName.trim()) {
      toast.error(t('common.webhookNameRequired'));
      return;
    }
    if (!newWebhookUrl.trim()) {
      toast.error(t('common.webhookUrlRequired'));
      return;
    }

    try {
      await backendClient.post('/api/v1/webhooks', {
        name: newWebhookName,
        url: newWebhookUrl,
        description: newWebhookDescription,
        enabled: newWebhookEnabled,
      });

      toast.success(t('common.webhookCreated'));
      setNewWebhookName('');
      setNewWebhookUrl('');
      setNewWebhookDescription('');
      setNewWebhookEnabled(true);
      setShowCreateWebhookDialog(false);
      loadWebhooks();
    } catch (error) {
      toast.error(`Failed to create webhook: ${error}`);
    }
  };

  const handleDeleteWebhook = async (webhookId: number) => {
    try {
      await backendClient.delete(`/api/v1/webhooks/${webhookId}`);
      toast.success(t('common.webhookDeleted'));
      loadWebhooks();
      setDeleteWebhookId(null);
    } catch (error) {
      toast.error(`Failed to delete webhook: ${error}`);
    }
  };

  const handleToggleWebhook = async (webhook: Webhook) => {
    try {
      await backendClient.put(`/api/v1/webhooks/${webhook.id}`, {
        enabled: !webhook.enabled,
      });
      loadWebhooks();
    } catch (error) {
      toast.error(`Failed to update webhook: ${error}`);
    }
  };

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(newOpen) => {
          // 如果删除确认框是打开的，不允许关闭主对话框
          if (!newOpen && (deleteKeyId || deleteWebhookId)) {
            return;
          }
          onOpenChange(newOpen);
        }}
      >
        <DialogContent className="sm:max-w-[800px]">
          <DialogHeader>
            <DialogTitle>{t('common.manageApiIntegration')}</DialogTitle>
          </DialogHeader>

          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="w-full"
          >
            <TabsList className="shadow-md py-3 bg-[#f0f0f0] dark:bg-[#2a2a2e]">
              <TabsTrigger className="px-5 py-4 cursor-pointer" value="apikeys">
                {t('common.apiKeys')}
              </TabsTrigger>
              <TabsTrigger
                className="px-5 py-4 cursor-pointer"
                value="webhooks"
              >
                {t('common.webhooks')}
              </TabsTrigger>
            </TabsList>

            {/* API Keys Tab */}
            <TabsContent value="apikeys" className="space-y-4">
              <div className="flex items-start gap-2 text-sm text-muted-foreground">
                {t('common.apiKeyHint')}
              </div>

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
            </TabsContent>

            {/* Webhooks Tab */}
            <TabsContent value="webhooks" className="space-y-4">
              <div className="flex items-start gap-2 text-sm text-muted-foreground">
                {t('common.webhookHint')}
              </div>

              <div className="flex justify-end">
                <Button
                  onClick={() => setShowCreateWebhookDialog(true)}
                  size="sm"
                  className="gap-2"
                >
                  <Plus className="h-4 w-4" />
                  {t('common.createWebhook')}
                </Button>
              </div>

              {loading ? (
                <div className="text-center py-8 text-muted-foreground">
                  {t('common.loading')}
                </div>
              ) : webhooks.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  {t('common.noWebhooks')}
                </div>
              ) : (
                <div className="border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('common.name')}</TableHead>
                        <TableHead>{t('common.webhookUrl')}</TableHead>
                        <TableHead className="w-[80px]">
                          {t('common.webhookEnabled')}
                        </TableHead>
                        <TableHead className="w-[100px]">
                          {t('common.actions')}
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {webhooks.map((webhook) => (
                        <TableRow key={webhook.id}>
                          <TableCell>
                            <div>
                              <div className="font-medium">{webhook.name}</div>
                              {webhook.description && (
                                <div className="text-sm text-muted-foreground">
                                  {webhook.description}
                                </div>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <code className="text-sm bg-muted px-2 py-1 rounded break-all">
                              {webhook.url}
                            </code>
                          </TableCell>
                          <TableCell>
                            <Switch
                              checked={webhook.enabled}
                              onCheckedChange={() =>
                                handleToggleWebhook(webhook)
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDeleteWebhookId(webhook.id)}
                              title={t('common.delete')}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </TabsContent>
          </Tabs>

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

      {/* Create Webhook Dialog */}
      <Dialog
        open={showCreateWebhookDialog}
        onOpenChange={setShowCreateWebhookDialog}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('common.createWebhook')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{t('common.name')}</label>
              <Input
                value={newWebhookName}
                onChange={(e) => setNewWebhookName(e.target.value)}
                placeholder={t('common.webhookName')}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">
                {t('common.webhookUrl')}
              </label>
              <Input
                value={newWebhookUrl}
                onChange={(e) => setNewWebhookUrl(e.target.value)}
                placeholder="https://example.com/webhook"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">
                {t('common.description')}
              </label>
              <Input
                value={newWebhookDescription}
                onChange={(e) => setNewWebhookDescription(e.target.value)}
                placeholder={t('common.description')}
                className="mt-1"
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={newWebhookEnabled}
                onCheckedChange={setNewWebhookEnabled}
              />
              <label className="text-sm font-medium">
                {t('common.webhookEnabled')}
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowCreateWebhookDialog(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button onClick={handleCreateWebhook}>{t('common.create')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete API Key Confirmation Dialog */}
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

      {/* Delete Webhook Confirmation Dialog */}
      <AlertDialog open={!!deleteWebhookId}>
        <AlertDialogPortal>
          <AlertDialogOverlay
            className="z-[60]"
            onClick={() => setDeleteWebhookId(null)}
          />
          <AlertDialogPrimitive.Content
            className="fixed left-[50%] top-[50%] z-[60] grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 sm:rounded-lg"
            onEscapeKeyDown={() => setDeleteWebhookId(null)}
          >
            <AlertDialogHeader>
              <AlertDialogTitle>{t('common.confirmDelete')}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('common.webhookDeleteConfirm')}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => setDeleteWebhookId(null)}>
                {t('common.cancel')}
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={() =>
                  deleteWebhookId && handleDeleteWebhook(deleteWebhookId)
                }
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
