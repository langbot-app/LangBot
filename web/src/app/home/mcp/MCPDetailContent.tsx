import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import MCPForm from '@/app/home/mcp/components/mcp-form/MCPForm';
import type { MCPFormHandle } from '@/app/home/mcp/components/mcp-form/MCPForm';
import { httpClient, systemInfo } from '@/app/infra/http/HttpClient';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { Trash2 } from 'lucide-react';
import { toast } from 'sonner';

export default function MCPDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { refreshMCPServers, mcpServers, setDetailEntityName } =
    useSidebarData();

  // Set breadcrumb entity name
  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('mcp.createServer'));
    } else {
      const server = mcpServers.find((s) => s.id === id);
      // Convert __ back to / for display (since / is used as separator in stored names)
      const displayName = (server?.name ?? id).replace(/__/g, '/');
      setDetailEntityName(displayName);
    }
    return () => setDetailEntityName(null);
  }, [id, isCreateMode, mcpServers, setDetailEntityName, t]);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Track whether the form has unsaved changes
  const [formDirty, setFormDirty] = useState(false);

  // Ref to MCPForm for triggering test from header
  const formRef = useRef<MCPFormHandle>(null);
  const [mcpTesting, setMcpTesting] = useState(false);

  // Enable state managed here so the header switch works
  const [serverEnabled, setServerEnabled] = useState(true);
  const [enableLoaded, setEnableLoaded] = useState(false);

  // Fetch server enable state
  useEffect(() => {
    if (!isCreateMode) {
      httpClient.getMCPServer(id).then((res) => {
        const server = res.server ?? res;
        setServerEnabled(server.enable ?? true);
        setEnableLoaded(true);
      });
    }
  }, [id, isCreateMode]);

  const handleEnableToggle = useCallback(
    async (checked: boolean) => {
      const prev = serverEnabled;
      setServerEnabled(checked);
      try {
        await httpClient.toggleMCPServer(id, checked);
        refreshMCPServers();
      } catch {
        setServerEnabled(prev);
        toast.error(t('mcp.modifyFailed'));
      }
    },
    [id, serverEnabled, refreshMCPServers, t],
  );

  function handleFormSubmit() {
    // Re-sync enable state after form save
    httpClient.getMCPServer(id).then((res) => {
      const server = res.server ?? res;
      setServerEnabled(server.enable ?? true);
    });
    refreshMCPServers();
  }

  function handleServerDeleted() {
    refreshMCPServers();
    navigate('/home/mcp');
  }

  function handleNewServerCreated(serverName: string) {
    refreshMCPServers();
    navigate(`/home/mcp?id=${encodeURIComponent(serverName)}`);
  }

  function confirmDelete() {
    httpClient
      .deleteMCPServer(id)
      .then(() => {
        setShowDeleteConfirm(false);
        toast.success(t('mcp.deleteSuccess'));
        handleServerDeleted();
      })
      .catch((err) => {
        toast.error(t('mcp.deleteFailed') + (err.msg || ''));
      });
  }

  // Check extensions limit before creating
  async function checkExtensionsLimit(): Promise<boolean> {
    const maxExtensions = systemInfo.limitation?.max_extensions ?? -1;
    if (maxExtensions < 0) return true;
    try {
      const [pluginsResp, mcpResp] = await Promise.all([
        httpClient.getPlugins(),
        httpClient.getMCPServers(),
      ]);
      const total =
        (pluginsResp.plugins?.length ?? 0) + (mcpResp.servers?.length ?? 0);
      if (total >= maxExtensions) {
        toast.error(
          t('limitation.maxExtensionsReached', { max: maxExtensions }),
        );
        return false;
      }
    } catch {
      // If we can't check, let backend handle it
    }
    return true;
  }

  // ==================== Create Mode ====================
  if (isCreateMode) {
    return (
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">{t('mcp.createServer')}</h1>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => formRef.current?.testMcp()}
              disabled={mcpTesting}
            >
              {t('common.test')}
            </Button>
            <Button
              type="submit"
              form="mcp-form"
              onClick={async (e) => {
                if (!(await checkExtensionsLimit())) {
                  e.preventDefault();
                }
              }}
            >
              {t('common.submit')}
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-3xl pb-8">
            <MCPForm
              ref={formRef}
              initServerName={undefined}
              onFormSubmit={handleFormSubmit}
              onNewServerCreated={handleNewServerCreated}
              onTestingChange={setMcpTesting}
            />
          </div>
        </div>
      </div>
    );
  }

  // ==================== Edit Mode ====================
  return (
    <>
      <div className="flex h-full flex-col">
        {/* Header: title + enable switch + save button */}
        <div className="flex items-center justify-between pb-4 shrink-0">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-semibold">{t('mcp.editServer')}</h1>
            {enableLoaded && (
              <div className="flex items-center gap-2">
                <Switch
                  id="mcp-enable-switch"
                  checked={serverEnabled}
                  onCheckedChange={handleEnableToggle}
                />
                <Label
                  htmlFor="mcp-enable-switch"
                  className="text-sm text-muted-foreground cursor-pointer"
                >
                  {t('common.enable')}
                </Label>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => formRef.current?.testMcp()}
              disabled={mcpTesting}
            >
              {t('common.test')}
            </Button>
            <Button type="submit" form="mcp-form" disabled={!formDirty}>
              {t('common.save')}
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-3xl space-y-6 pb-8">
            <MCPForm
              ref={formRef}
              initServerName={id}
              onFormSubmit={handleFormSubmit}
              onNewServerCreated={handleNewServerCreated}
              onDirtyChange={setFormDirty}
              onTestingChange={setMcpTesting}
            />

            {/* Card: Danger Zone */}
            <Card className="border-destructive/50">
              <CardHeader>
                <CardTitle className="text-destructive">
                  {t('mcp.dangerZone')}
                </CardTitle>
                <CardDescription>
                  {t('mcp.dangerZoneDescription')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">
                      {t('mcp.deleteMCPAction')}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {t('mcp.deleteMCPHint')}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    onClick={() => setShowDeleteConfirm(true)}
                  >
                    <Trash2 className="size-4 mr-1.5" />
                    {t('common.delete')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('mcp.confirmDeleteTitle')}</DialogTitle>
            <DialogDescription className="sr-only">
              {t('mcp.confirmDeleteServer')}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">{t('mcp.confirmDeleteServer')}</div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirm(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
