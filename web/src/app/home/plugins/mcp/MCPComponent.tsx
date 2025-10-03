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
            <path d="M4 18V14.3C4 13.4716 3.32843 12.8 2.5 12.8H2V11.2H2.5C3.32843 11.2 4 10.5284 4 9.7V6C4 4.34315 5.34315 3 7 3H8V5H7C6.44772 5 6 5.44772 6 6V10.1C6 10.9858 5.42408 11.7372 4.62623 12C5.42408 12.2628 6 13.0142 6 13.9V18C6 18.5523 6.44772 19 7 19H8V21H7C5.34315 21 4 19.6569 4 18ZM20 14.3V18C20 19.6569 18.6569 21 17 21H16V19H17C17.5523 19 18 18.5523 18 18V13.9C18 13.0142 18.5759 12.2628 19.3738 12C18.5759 11.7372 18 10.9858 18 10.1V6C18 5.44772 17.5523 5 17 5H16V3H17C18.6569 3 20 4.34315 20 6V9.7C20 10.5284 20.6716 11.2 21.5 11.2H22V12.8H21.5C20.6716 12.8 20 13.4716 20 14.3Z"></path>
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
