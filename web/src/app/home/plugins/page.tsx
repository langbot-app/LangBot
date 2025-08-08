'use client';
import PluginInstalledComponent, {
  PluginInstalledComponentRef,
} from '@/app/home/plugins/plugin-installed/PluginInstalledComponent';
import PluginMarketComponent from '@/app/home/plugins/plugin-market/PluginMarketComponent';
import PluginSortDialog from '@/app/home/plugins/plugin-sort/PluginSortDialog';
import MCPComponent, {
  MCPComponentRef,
} from '@/app/home/plugins/mcp/MCPComponent';
import MCPMarketComponent from '@/app/home/plugins/mcp-market/MCPMarketComponent';
import styles from './plugins.module.css';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { PlusIcon } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { GithubIcon } from 'lucide-react';
import { useState, useRef } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

enum PluginInstallStatus {
  WAIT_INPUT = 'wait_input',
  INSTALLING = 'installing',
  ERROR = 'error',
}

export default function PluginConfigPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('installed');
  const [modalOpen, setModalOpen] = useState(false);
  const [sortModalOpen, setSortModalOpen] = useState(false);
  // const [mcpModalOpen, setMcpModalOpen] = useState(false);
  const [mcpMarketInstallModalOpen, setMcpMarketInstallModalOpen] =
    useState(false);
  const [pluginInstallStatus, setPluginInstallStatus] =
    useState<PluginInstallStatus>(PluginInstallStatus.WAIT_INPUT);
  const [mcpInstallStatus, setMcpInstallStatus] = useState<PluginInstallStatus>(
    PluginInstallStatus.WAIT_INPUT,
  );
  const [installError, setInstallError] = useState<string | null>(null);
  const [mcpInstallError, setMcpInstallError] = useState<string | null>(null);
  const [githubURL, setGithubURL] = useState('');
  const [mcpGithubURL, setMcpGithubURL] = useState('');
  const pluginInstalledRef = useRef<PluginInstalledComponentRef>(null);
  const mcpComponentRef = useRef<MCPComponentRef>(null);

  function handleModalConfirm() {
    installPlugin(githubURL);
  }

  function handleMcpModalConfirm() {
    installMcpServer(mcpGithubURL);
  }

  function installPlugin(url: string) {
    setPluginInstallStatus(PluginInstallStatus.INSTALLING);
    httpClient
      .installPluginFromGithub(url)
      .then((resp) => {
        const taskId = resp.task_id;

        let alreadySuccess = false;
        console.log('taskId:', taskId);

        // 每秒拉取一次任务状态
        const interval = setInterval(() => {
          httpClient.getAsyncTask(taskId).then((resp) => {
            console.log('task status:', resp);
            if (resp.runtime.done) {
              clearInterval(interval);
              if (resp.runtime.exception) {
                setInstallError(resp.runtime.exception);
                setPluginInstallStatus(PluginInstallStatus.ERROR);
              } else {
                // success
                if (!alreadySuccess) {
                  toast.success(t('plugins.installSuccess'));
                  alreadySuccess = true;
                }
                setGithubURL('');
                setModalOpen(false);
                pluginInstalledRef.current?.refreshPluginList();
              }
            }
          });
        }, 1000);
      })
      .catch((err) => {
        console.log('error when install plugin:', err);
        setInstallError(err.message);
        setPluginInstallStatus(PluginInstallStatus.ERROR);
      });
  }

  function installMcpServer(url: string) {
    setMcpInstallStatus(PluginInstallStatus.INSTALLING);
    httpClient
      .installMCPServerFromGithub(url)
      .then((resp) => {
        const taskId = resp.task_id;

        let alreadySuccess = false;
        console.log('taskId:', taskId);

        // 每秒拉取一次任务状态
        const interval = setInterval(() => {
          httpClient.getAsyncTask(taskId).then((resp) => {
            console.log('task status:', resp);
            if (resp.runtime.done) {
              clearInterval(interval);
              if (resp.runtime.exception) {
                setMcpInstallError(resp.runtime.exception);
                setMcpInstallStatus(PluginInstallStatus.ERROR);
              } else {
                // success
                if (!alreadySuccess) {
                  toast.success(t('mcp.installSuccess'));
                  alreadySuccess = true;
                }
                setMcpGithubURL('');
                setMcpMarketInstallModalOpen(false);
                mcpComponentRef.current?.refreshServerList();
              }
            }
          });
        }, 1000);
      })
      .catch((err) => {
        console.log('error when install mcp server:', err);
        setMcpInstallError(err.message);
        setMcpInstallStatus(PluginInstallStatus.ERROR);
      });
  }

  return (
    <div className={styles.pageContainer}>
      <Tabs
        defaultValue="installed"
        value={activeTab}
        onValueChange={setActiveTab}
        className="w-full"
      >
        <div className="flex flex-row justify-between items-center px-[0.8rem]">
          <TabsList className="shadow-md py-5 bg-[#f0f0f0]">
            <TabsTrigger value="installed" className="px-6 py-4 cursor-pointer">
              {t('plugins.installed')}
            </TabsTrigger>
            <TabsTrigger value="market" className="px-6 py-4 cursor-pointer">
              {t('plugins.marketplace')}
            </TabsTrigger>
            <TabsTrigger value="mcp" className="px-6 py-4 cursor-pointer">
              MCP
            </TabsTrigger>
            <TabsTrigger
              value="mcp-market"
              className="px-6 py-4 cursor-pointer"
            >
              {t('mcp.marketplace')}
            </TabsTrigger>
          </TabsList>

          <div className="flex flex-row justify-end items-center">
            {activeTab === 'installed' && (
              <Button
                variant="outline"
                className="px-6 py-4 cursor-pointer mr-2"
                onClick={() => {
                  setSortModalOpen(true);
                }}
              >
                {t('plugins.arrange')}
              </Button>
            )}
            {(activeTab === 'installed' || activeTab === 'market') && (
              <Button
                variant="default"
                className="px-6 py-4 cursor-pointer"
                onClick={() => {
                  setModalOpen(true);
                  setPluginInstallStatus(PluginInstallStatus.WAIT_INPUT);
                  setInstallError(null);
                }}
              >
                <PlusIcon className="w-4 h-4" />
                {t('plugins.install')}
              </Button>
            )}
            {activeTab === 'mcp' && (
              <Button
                variant="default"
                className="px-6 py-4 cursor-pointer"
                onClick={() => {
                  mcpComponentRef.current?.createServer();
                }}
              >
                <PlusIcon className="w-4 h-4" />
                {t('mcp.createServer')}
              </Button>
            )}
            {activeTab === 'mcp-market' && (
              <Button
                variant="default"
                className="px-6 py-4 cursor-pointer"
                onClick={() => {
                  setMcpMarketInstallModalOpen(true);
                  setMcpInstallStatus(PluginInstallStatus.WAIT_INPUT);
                  setMcpInstallError(null);
                }}
              >
                <PlusIcon className="w-4 h-4" />
                {t('mcp.install')}
              </Button>
            )}
          </div>
        </div>
        <TabsContent value="installed">
          <PluginInstalledComponent ref={pluginInstalledRef} />
        </TabsContent>
        <TabsContent value="market">
          <PluginMarketComponent
            askInstallPlugin={(githubURL) => {
              setGithubURL(githubURL);
              setModalOpen(true);
              setPluginInstallStatus(PluginInstallStatus.WAIT_INPUT);
              setInstallError(null);
            }}
          />
        </TabsContent>
        <TabsContent value="mcp">
          <MCPComponent ref={mcpComponentRef} />
        </TabsContent>
        <TabsContent value="mcp-market">
          <MCPMarketComponent
            askInstallServer={(githubURL) => {
              setMcpGithubURL(githubURL);
              setMcpMarketInstallModalOpen(true);
              setMcpInstallStatus(PluginInstallStatus.WAIT_INPUT);
              setMcpInstallError(null);
            }}
          />
        </TabsContent>
      </Tabs>

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="w-[500px] p-6">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-4">
              <GithubIcon className="size-6" />
              <span>{t('plugins.installFromGithub')}</span>
            </DialogTitle>
          </DialogHeader>
          {pluginInstallStatus === PluginInstallStatus.WAIT_INPUT && (
            <div className="mt-4">
              <p className="mb-2">{t('plugins.onlySupportGithub')}</p>
              <Input
                placeholder={t('plugins.enterGithubLink')}
                value={githubURL}
                onChange={(e) => setGithubURL(e.target.value)}
                className="mb-4"
              />
            </div>
          )}
          {pluginInstallStatus === PluginInstallStatus.INSTALLING && (
            <div className="mt-4">
              <p className="mb-2">{t('plugins.installing')}</p>
            </div>
          )}
          {pluginInstallStatus === PluginInstallStatus.ERROR && (
            <div className="mt-4">
              <p className="mb-2">{t('plugins.installFailed')}</p>
              <p className="mb-2 text-red-500">{installError}</p>
            </div>
          )}
          <DialogFooter>
            {pluginInstallStatus === PluginInstallStatus.WAIT_INPUT && (
              <>
                <Button variant="outline" onClick={() => setModalOpen(false)}>
                  {t('common.cancel')}
                </Button>
                <Button onClick={handleModalConfirm}>
                  {t('common.confirm')}
                </Button>
              </>
            )}
            {pluginInstallStatus === PluginInstallStatus.ERROR && (
              <Button variant="default" onClick={() => setModalOpen(false)}>
                {t('common.close')}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PluginSortDialog
        open={sortModalOpen}
        onOpenChange={setSortModalOpen}
        onSortComplete={() => {
          pluginInstalledRef.current?.refreshPluginList();
        }}
      />

      {/* MCP Server 安装对话框 */}
      <Dialog
        open={mcpMarketInstallModalOpen}
        onOpenChange={setMcpMarketInstallModalOpen}
      >
        <DialogContent className="w-[500px] p-6">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-4">
              <GithubIcon className="size-6" />
              <span>{t('mcp.installFromGithub')}</span>
            </DialogTitle>
          </DialogHeader>
          {mcpInstallStatus === PluginInstallStatus.WAIT_INPUT && (
            <div className="mt-4">
              <p className="mb-2">{t('mcp.onlySupportGithub')}</p>
              <Input
                placeholder={t('mcp.enterGithubLink')}
                value={mcpGithubURL}
                onChange={(e) => setMcpGithubURL(e.target.value)}
                className="mb-4"
              />
            </div>
          )}
          {mcpInstallStatus === PluginInstallStatus.INSTALLING && (
            <div className="mt-4">
              <p className="mb-2">{t('mcp.installing')}</p>
            </div>
          )}
          {mcpInstallStatus === PluginInstallStatus.ERROR && (
            <div className="mt-4">
              <p className="mb-2">{t('mcp.installFailed')}</p>
              <p className="mb-2 text-red-500">{mcpInstallError}</p>
            </div>
          )}
          <DialogFooter>
            {mcpInstallStatus === PluginInstallStatus.WAIT_INPUT && (
              <>
                <Button
                  variant="outline"
                  onClick={() => setMcpMarketInstallModalOpen(false)}
                >
                  {t('common.cancel')}
                </Button>
                <Button onClick={handleMcpModalConfirm}>
                  {t('common.confirm')}
                </Button>
              </>
            )}
            {mcpInstallStatus === PluginInstallStatus.ERROR && (
              <Button
                variant="default"
                onClick={() => setMcpMarketInstallModalOpen(false)}
              >
                {t('common.close')}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
