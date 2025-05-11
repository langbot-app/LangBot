'use client';
import PluginInstalledComponent, {
  PluginInstalledComponentRef,
} from '@/app/home/plugins/plugin-installed/PluginInstalledComponent';
import PluginMarketComponent from '@/app/home/plugins/plugin-market/PluginMarketComponent';
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
enum PluginInstallStatus {
  WAIT_INPUT = 'wait_input',
  INSTALLING = 'installing',
  ERROR = 'error',
}

export default function PluginConfigPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [pluginInstallStatus, setPluginInstallStatus] =
    useState<PluginInstallStatus>(PluginInstallStatus.WAIT_INPUT);
  const [installError, setInstallError] = useState<string | null>(null);
  const [githubURL, setGithubURL] = useState('');
  const pluginInstalledRef = useRef<PluginInstalledComponentRef>(null);

  function handleModalConfirm() {
    installPlugin(githubURL);
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
                  toast.success('插件安装成功');
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

  return (
    <div className={styles.pageContainer}>
      <Tabs defaultValue="installed" className="w-full">
        <div className="flex flex-row justify-between items-center px-[0.8rem]">
          <TabsList className="shadow-md py-5 bg-[#f0f0f0]">
            <TabsTrigger value="installed" className="px-6 py-4 cursor-pointer">
              已安装
            </TabsTrigger>
            <TabsTrigger value="market" className="px-6 py-4 cursor-pointer">
              插件市场
            </TabsTrigger>
          </TabsList>

          <div className="flex flex-row justify-end items-center">
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
              安装
            </Button>
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
      </Tabs>

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="w-[500px] p-6">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-4">
              <GithubIcon className="size-6" />
              <span>从 GitHub 安装插件</span>
            </DialogTitle>
          </DialogHeader>
          {pluginInstallStatus === PluginInstallStatus.WAIT_INPUT && (
            <div className="mt-4">
              <p className="mb-2">目前仅支持从 GitHub 安装</p>
              <Input
                placeholder="请输入插件的Github链接"
                value={githubURL}
                onChange={(e) => setGithubURL(e.target.value)}
                className="mb-4"
              />
            </div>
          )}
          {pluginInstallStatus === PluginInstallStatus.INSTALLING && (
            <div className="mt-4">
              <p className="mb-2">正在安装插件...</p>
            </div>
          )}
          {pluginInstallStatus === PluginInstallStatus.ERROR && (
            <div className="mt-4">
              <p className="mb-2">插件安装失败：</p>
              <p className="mb-2 text-red-500">{installError}</p>
            </div>
          )}
          <DialogFooter>
            {pluginInstallStatus === PluginInstallStatus.WAIT_INPUT && (
              <>
                <Button variant="outline" onClick={() => setModalOpen(false)}>
                  取消
                </Button>
                <Button onClick={handleModalConfirm}>确认</Button>
              </>
            )}
            {pluginInstallStatus === PluginInstallStatus.ERROR && (
              <Button variant="default" onClick={() => setModalOpen(false)}>
                关闭
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
