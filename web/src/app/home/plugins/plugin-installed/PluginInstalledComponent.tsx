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
import { useTranslation } from 'react-i18next';
import { i18nObj } from '@/i18n/I18nProvider';

export interface PluginInstalledComponentRef {
  refreshPluginList: () => void;
}

// eslint-disable-next-line react/display-name
const PluginInstalledComponent = forwardRef<PluginInstalledComponentRef>(
  (props, ref) => {
    const { t } = useTranslation();
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
              description: i18nObj(plugin.description),
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
      <>
        {pluginList.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-gray-500 h-[calc(100vh-16rem)] w-full gap-2">
            <svg
              className="h-[3rem] w-[3rem]"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M7 5C7 2.79086 8.79086 1 11 1C13.2091 1 15 2.79086 15 5H20C20.5523 5 21 5.44772 21 6V10.1707C21 10.4953 20.8424 10.7997 20.5774 10.9872C20.3123 11.1746 19.9728 11.2217 19.6668 11.1135C19.4595 11.0403 19.2355 11 19 11C17.8954 11 17 11.8954 17 13C17 14.1046 17.8954 15 19 15C19.2355 15 19.4595 14.9597 19.6668 14.8865C19.9728 14.7783 20.3123 14.8254 20.5774 15.0128C20.8424 15.2003 21 15.5047 21 15.8293V20C21 20.5523 20.5523 21 20 21H4C3.44772 21 3 20.5523 3 20V6C3 5.44772 3.44772 5 4 5H7ZM11 3C9.89543 3 9 3.89543 9 5C9 5.23554 9.0403 5.45952 9.11355 5.66675C9.22172 5.97282 9.17461 6.31235 8.98718 6.57739C8.79974 6.84243 8.49532 7 8.17071 7H5V19H19V17C16.7909 17 15 15.2091 15 13C15 10.7909 16.7909 9 19 9V7H13.8293C13.5047 7 13.2003 6.84243 13.0128 6.57739C12.8254 6.31235 12.7783 5.97282 12.8865 5.66675C12.9597 5.45952 13 5.23555 13 5C13 3.89543 12.1046 3 11 3Z"></path>
            </svg>
            <div className="text-lg mb-2">{t('plugins.noPluginInstalled')}</div>
          </div>
        ) : (
          <div className={`${styles.pluginListContainer}`}>
            <Dialog open={modalOpen} onOpenChange={setModalOpen}>
              <DialogContent className="w-[700px] max-h-[80vh] p-0 flex flex-col">
                <DialogHeader className="px-6 pt-6 pb-2">
                  <DialogTitle>{t('plugins.pluginConfig')}</DialogTitle>
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
        )}
      </>
    );
  },
);

export default PluginInstalledComponent;
