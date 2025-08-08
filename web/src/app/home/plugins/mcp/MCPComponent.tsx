'use client';

import { useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import { MCPCardVO } from '@/app/home/plugins/mcp/MCPCardVO';
import MCPCardComponent from '@/app/home/plugins/mcp/mcp-card/MCPCardComponent';
import MCPForm from '@/app/home/plugins/mcp/mcp-form/MCPForm';
import styles from '@/app/home/plugins/plugins.module.css';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

export interface MCPComponentRef {
  refreshServerList: () => void;
  createServer: () => void;
}

// eslint-disable-next-line react/display-name
const MCPComponent = forwardRef<MCPComponentRef>((props, ref) => {
  const { t } = useTranslation();
  const [serverList, setServerList] = useState<MCPCardVO[]>([]);
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [selectedServer, setSelectedServer] = useState<MCPCardVO | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState<boolean>(false);
  const [serverToDelete, setServerToDelete] = useState<MCPCardVO | null>(null);
  const [deleting, setDeleting] = useState<boolean>(false);

  useEffect(() => {
    initData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function initData() {
    getServerList();
  }

  function getServerList() {
    httpClient
      .getMCPServers()
      .then((value) => {
        setServerList(value.servers.map((server) => new MCPCardVO(server)));
      })
      .catch((error) => {
        toast.error(t('mcp.getServerListError') + error.message);
      });
  }

  useImperativeHandle(ref, () => ({
    refreshServerList: getServerList,
    createServer: () => {
      setSelectedServer(null);
      setModalOpen(true);
    },
  }));

  function handleServerClick(server: MCPCardVO) {
    setSelectedServer(server);
    setModalOpen(true);
  }

  function handleDeleteClick(server: MCPCardVO, e: React.MouseEvent) {
    e.stopPropagation();
    setServerToDelete(server);
    setDeleteDialogOpen(true);
  }

  async function confirmDelete() {
    if (!serverToDelete) return;

    setDeleting(true);
    try {
      const response = await httpClient.deleteMCPServer(serverToDelete.name);
      const taskId = response.task_id;

      // 监控任务状态
      const interval = setInterval(() => {
        httpClient.getAsyncTask(taskId).then((taskResp) => {
          if (taskResp.runtime.done) {
            clearInterval(interval);
            setDeleting(false);
            setDeleteDialogOpen(false);

            if (taskResp.runtime.exception) {
              toast.error(t('mcp.deleteError') + taskResp.runtime.exception);
            } else {
              toast.success(t('mcp.deleteSuccess'));
              getServerList();
            }
          }
        });
      }, 1000);
    } catch (error: unknown) {
      setDeleting(false);
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      toast.error(t('mcp.deleteError') + errorMessage);
    }
  }

  return (
    <>
      {serverList.length === 0 ? (
        <div className="flex flex-col items-center justify-center text-gray-500 h-[calc(100vh-16rem)] w-full gap-2">
          <svg
            className="h-[3rem] w-[3rem]"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path d="M13.5 2C13.5 2.82843 14.1716 3.5 15 3.5C15.8284 3.5 16.5 2.82843 16.5 2C16.5 1.17157 15.8284 0.5 15 0.5C14.1716 0.5 13.5 1.17157 13.5 2ZM8.5 8C8.5 8.82843 9.17157 9.5 10 9.5C10.8284 9.5 11.5 8.82843 11.5 8C11.5 7.17157 10.8284 6.5 10 6.5C9.17157 6.5 8.5 7.17157 8.5 8ZM1.5 14C1.5 14.8284 2.17157 15.5 3 15.5C3.82843 15.5 4.5 14.8284 4.5 14C4.5 13.1716 3.82843 12.5 3 12.5C2.17157 12.5 1.5 13.1716 1.5 14ZM19.5 14C19.5 14.8284 20.1716 15.5 21 15.5C21.8284 15.5 22.5 14.8284 22.5 14C22.5 13.1716 21.8284 12.5 21 12.5C20.1716 12.5 19.5 13.1716 19.5 14ZM8.5 20C8.5 20.8284 9.17157 21.5 10 21.5C10.8284 21.5 11.5 20.8284 11.5 20C11.5 19.1716 10.8284 19 10 19C9.17157 19 8.5 19.1716 8.5 20ZM2.5 8L6.5 8L6.5 10L2.5 10L2.5 8ZM13.5 8L17.5 8L17.5 10L13.5 10L13.5 8ZM8.5 2L8.5 6L10.5 6L10.5 2L8.5 2ZM8.5 14L8.5 18L10.5 18L10.5 14L8.5 14ZM2.5 14L6.5 14L6.5 16L2.5 16L2.5 14ZM13.5 14L17.5 14L17.5 16L13.5 16L13.5 14Z"></path>
          </svg>
          <div className="text-lg mb-2">{t('mcp.noServerInstalled')}</div>
        </div>
      ) : (
        <div className={`${styles.pluginListContainer}`}>
          {serverList.map((vo, index) => {
            return (
              <div key={index} className="relative group">
                <MCPCardComponent
                  cardVO={vo}
                  onCardClick={() => handleServerClick(vo)}
                  onRefresh={getServerList}
                />

                {/* 删除按钮 */}
                <button
                  className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 bg-red-500 hover:bg-red-600 text-white rounded-full p-1"
                  onClick={(e) => handleDeleteClick(vo, e)}
                >
                  <svg
                    className="w-4 h-4"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* 编辑配置对话框 */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="w-[700px] max-h-[80vh] p-0 flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-2">
            <DialogTitle>
              {selectedServer ? t('mcp.editServer') : t('mcp.createServer')}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto px-6 pb-6">
            <MCPForm
              serverName={selectedServer?.name}
              isEdit={!!selectedServer}
              onFormSubmit={() => {
                setModalOpen(false);
                getServerList();
              }}
              onFormCancel={() => {
                setModalOpen(false);
              }}
            />
          </div>
        </DialogContent>
      </Dialog>

      {/* 删除确认对话框 */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('mcp.deleteServer')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('mcp.confirmDeleteServer', { name: serverToDelete?.name })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>
              {t('common.cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              disabled={deleting}
              className="bg-red-600 hover:bg-red-700"
            >
              {deleting ? t('plugins.deleting') : t('common.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
});

export default MCPComponent;
