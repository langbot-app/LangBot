'use client';

import { useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import { PluginCardVO } from '@/app/home/plugins/plugin-installed/PluginCardVO';
import PluginCardComponent from '@/app/home/plugins/plugin-installed/plugin-card/PluginCardComponent';
import PluginForm from '@/app/home/plugins/plugin-installed/plugin-form/PluginForm';
import styles from '@/app/home/plugins/plugins.module.css';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export interface PluginInstalledComponentRef {
  refreshPluginList: () => void;
}

// eslint-disable-next-line react/display-name
const PluginInstalledComponent = forwardRef<PluginInstalledComponentRef>(
  (props, ref) => {
    const [pluginList, setPluginList] = useState<PluginCardVO[]>([]);
    const [modalOpen, setModalOpen] = useState<boolean>(false);
    const [selectedPlugin, setSelectedPlugin] = useState<PluginCardVO | null>(
      null,
    );

    useEffect(() => {
      initData();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    function initData() {
      getPluginList();
    }

    function getPluginList() {
      httpClient.getPlugins().then((value) => {
        setPluginList(
          value.plugins.map((plugin) => {
            return new PluginCardVO({
              author: plugin.author,
              description: plugin.description.zh_CN,
              enabled: plugin.enabled,
              name: plugin.name,
              version: plugin.version,
              status: plugin.status,
              tools: plugin.tools,
              event_handlers: plugin.event_handlers,
              repository: plugin.repository,
              priority: plugin.priority,
            });
          }),
        );
      });
    }

    useImperativeHandle(ref, () => ({
      refreshPluginList: getPluginList,
    }));

    function handlePluginClick(plugin: PluginCardVO) {
      setSelectedPlugin(plugin);
      setModalOpen(true);
    }

    return (
      <div className={`${styles.pluginListContainer}`}>
        <Dialog open={modalOpen} onOpenChange={setModalOpen}>
          <DialogContent className="w-[700px] max-h-[80vh] p-0 flex flex-col">
            <DialogHeader className="px-6 pt-6 pb-2">
              <DialogTitle>插件配置</DialogTitle>
            </DialogHeader>
            <div className="flex-1 overflow-y-auto px-6">
              {selectedPlugin && (
                <PluginForm
                  pluginAuthor={selectedPlugin.author}
                  pluginName={selectedPlugin.name}
                  onFormSubmit={() => {
                    setModalOpen(false);
                    getPluginList();
                  }}
                  onFormCancel={() => {
                    setModalOpen(false);
                  }}
                />
              )}
            </div>
          </DialogContent>
        </Dialog>

        {pluginList.map((vo, index) => {
          return (
            <div key={index}>
              <PluginCardComponent
                cardVO={vo}
                onCardClick={() => handlePluginClick(vo)}
              />
            </div>
          );
        })}
      </div>
    );
  },
);

export default PluginInstalledComponent;
