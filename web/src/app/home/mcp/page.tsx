'use client';

import MCPServerComponent from '@/app/home/plugins/mcp-server/MCPServerComponent';
import MCPFormDialog from '@/app/home/plugins/mcp-server/mcp-form/MCPFormDialog';
import MCPDeleteConfirmDialog from '@/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog';
import { Button } from '@/components/ui/button';
import { PlusIcon } from 'lucide-react';
import React, { useState } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { systemInfo } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

export default function MCPPage() {
  const { t } = useTranslation();
  const [mcpFormOpen, setMcpFormOpen] = useState(false);
  const [editingServerName, setEditingServerName] = useState<string | null>(
    null,
  );
  const [isEditMode, setIsEditMode] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);

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

  return (
    <div className="h-full flex flex-col">
      <div className="flex flex-row justify-end items-center px-[0.8rem] pb-4 flex-shrink-0">
        <Button
          variant="default"
          className="px-6 py-4 cursor-pointer"
          onClick={async () => {
            if (!(await checkExtensionsLimit())) return;
            setIsEditMode(false);
            setEditingServerName(null);
            setMcpFormOpen(true);
          }}
        >
          <PlusIcon className="w-4 h-4" />
          {t('mcp.add')}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <MCPServerComponent
          key={refreshKey}
          onEditServer={(serverName) => {
            setEditingServerName(serverName);
            setIsEditMode(true);
            setMcpFormOpen(true);
          }}
        />
      </div>

      <MCPFormDialog
        open={mcpFormOpen}
        onOpenChange={setMcpFormOpen}
        serverName={editingServerName}
        isEditMode={isEditMode}
        onSuccess={() => {
          setEditingServerName(null);
          setIsEditMode(false);
          setRefreshKey((prev) => prev + 1);
        }}
        onDelete={() => {
          setShowDeleteConfirmModal(true);
        }}
      />

      <MCPDeleteConfirmDialog
        open={showDeleteConfirmModal}
        onOpenChange={setShowDeleteConfirmModal}
        serverName={editingServerName}
        onSuccess={() => {
          setMcpFormOpen(false);
          setEditingServerName(null);
          setIsEditMode(false);
          setRefreshKey((prev) => prev + 1);
        }}
      />
    </div>
  );
}
