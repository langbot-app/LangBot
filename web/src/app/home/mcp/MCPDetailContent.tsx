import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
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
import { Server, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

type MCPRuntimeState = 'connected' | 'connecting' | 'error';
type MCPConnectionState =
  | 'connected'
  | 'connecting'
  | 'error'
  | 'disabled'
  | 'disconnected';

export default function MCPDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { refreshMCPServers, mcpServers, setDetailEntityName } =
    useSidebarData();
  const server = mcpServers.find((s) => s.id === id);
  const displayName = (server?.name ?? id).replace(/__/g, '/');

  // Set breadcrumb entity name
  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('mcp.createServer'));
    } else {
      setDetailEntityName(displayName);
    }
    return () => setDetailEntityName(null);
  }, [displayName, isCreateMode, setDetailEntityName, t]);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Track whether the form has unsaved changes
  const [formDirty, setFormDirty] = useState(false);

  // Ref to MCPForm for triggering test from header
  const formRef = useRef<MCPFormHandle>(null);
  const [mcpTesting, setMcpTesting] = useState(false);

  // Enable state managed here so the header switch works
  const [serverEnabled, setServerEnabled] = useState(true);
  const [enableLoaded, setEnableLoaded] = useState(false);
  const [detailRuntimeStatus, setDetailRuntimeStatus] =
    useState<MCPRuntimeState | null>(null);

  const runtimeStatus = detailRuntimeStatus ?? server?.runtimeStatus;

  const currentConnectionState: MCPConnectionState =
    (enableLoaded ? serverEnabled : server?.enabled) === false
      ? 'disabled'
      : runtimeStatus === 'connected' ||
          runtimeStatus === 'connecting' ||
          runtimeStatus === 'error'
        ? runtimeStatus
        : 'disconnected';

  const connectionStatusLabel: Record<MCPConnectionState, string> = {
    connected: t('mcp.statusConnected'),
    connecting: t('mcp.connecting'),
    error: t('mcp.statusError'),
    disabled: t('mcp.statusDisabled'),
    disconnected: t('mcp.statusDisconnected'),
  };

  const connectionStatusClassName: Record<MCPConnectionState, string> = {
    connected:
      'border-green-200 bg-green-50 text-green-700 dark:border-green-900/70 dark:bg-green-950/40 dark:text-green-300',
    connecting:
      'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300',
    error:
      'border-red-200 bg-red-50 text-red-700 dark:border-red-900/70 dark:bg-red-950/40 dark:text-red-300',
    disabled: 'border-muted-foreground/20 bg-muted text-muted-foreground',
    disconnected: 'border-muted-foreground/20 bg-muted text-muted-foreground',
  };

  const connectionDotClassName: Record<MCPConnectionState, string> = {
    connected: 'bg-green-500',
    connecting: 'bg-amber-500',
    error: 'bg-red-500',
    disabled: 'bg-muted-foreground/50',
    disconnected: 'bg-muted-foreground/50',
  };

  // Fetch server enable state
  useEffect(() => {
    if (!isCreateMode) {
      setDetailRuntimeStatus(null);
      httpClient.getMCPServer(id).then((res) => {
        const server = res.server ?? res;
        setServerEnabled(server.enable ?? true);
        setDetailRuntimeStatus(server.runtime_info?.status ?? null);
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
        <div className="flex shrink-0 flex-col gap-3 pb-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <h1 className="truncate text-xl font-semibold">
              {t('mcp.createServer')}
            </h1>
            <Badge variant="outline" className="shrink-0 text-[0.7rem]">
              <Server className="size-3.5" />
              {t('mcp.title')}
            </Badge>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate('/home/add-extension')}
            >
              {t('common.cancel')}
            </Button>
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

        <div className="min-h-0 flex-1">
          <MCPForm
            ref={formRef}
            initServerName={undefined}
            layout="split"
            onFormSubmit={handleFormSubmit}
            onNewServerCreated={handleNewServerCreated}
            onTestingChange={setMcpTesting}
          />
        </div>
      </div>
    );
  }

  const enableControl = enableLoaded && (
    <Card>
      <CardHeader>
        <CardTitle>{t('common.enable')}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <Label
            htmlFor="mcp-enable-switch"
            className="cursor-pointer text-sm font-medium"
          >
            {t('common.enable')}
          </Label>
          <Switch
            id="mcp-enable-switch"
            checked={serverEnabled}
            onCheckedChange={handleEnableToggle}
          />
        </div>
      </CardContent>
    </Card>
  );

  const editActions = (
    <Card className="border-destructive/50">
      <CardHeader>
        <CardTitle className="text-destructive">
          {t('mcp.dangerZone')}
        </CardTitle>
        <CardDescription>{t('mcp.dangerZoneDescription')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium">{t('mcp.deleteMCPAction')}</p>
            <p className="text-sm text-muted-foreground">
              {t('mcp.deleteMCPHint')}
            </p>
          </div>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => setShowDeleteConfirm(true)}
            className="shrink-0"
          >
            <Trash2 className="mr-1.5 size-4" />
            {t('common.delete')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  // ==================== Edit Mode ====================
  return (
    <>
      <div className="flex h-full flex-col">
        <div className="flex shrink-0 flex-col gap-3 pb-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <div className="flex min-w-0 items-center gap-3">
              <h1 className="truncate text-xl font-semibold">{displayName}</h1>
              <Badge variant="outline" className="shrink-0 text-[0.7rem]">
                <Server className="size-3.5" />
                {t('mcp.title')}
              </Badge>
              <Badge
                variant="outline"
                className={`shrink-0 gap-1.5 text-[0.7rem] ${connectionStatusClassName[currentConnectionState]}`}
              >
                <span
                  className={`size-1.5 rounded-full ${connectionDotClassName[currentConnectionState]}`}
                />
                {connectionStatusLabel[currentConnectionState]}
              </Badge>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
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

        <div className="min-h-0 flex-1">
          <MCPForm
            ref={formRef}
            initServerName={id}
            layout="split"
            sideHeader={enableControl}
            sideFooter={editActions}
            onFormSubmit={handleFormSubmit}
            onNewServerCreated={handleNewServerCreated}
            onDirtyChange={setFormDirty}
            onTestingChange={setMcpTesting}
            onRuntimeInfoChange={(runtimeInfo) =>
              setDetailRuntimeStatus(runtimeInfo?.status ?? null)
            }
          />
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
