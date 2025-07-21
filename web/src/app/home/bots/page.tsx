'use client';

import { useEffect, useState } from 'react';
import styles from './botConfig.module.css';
import { BotCardVO } from '@/app/home/bots/components/bot-card/BotCardVO';
import BotCard from '@/app/home/bots/components/bot-card/BotCard';
import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Bot, Adapter } from '@/app/infra/entities/api';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { i18nObj } from '@/i18n/I18nProvider';
import BotDetailDialog from '@/app/home/bots/BotDetailDialog';

export default function BotConfigPage() {
  const { t } = useTranslation();
  // 机器人详情dialog
  const [detailDialogOpen, setDetailDialogOpen] = useState<boolean>(false);
  const [botList, setBotList] = useState<BotCardVO[]>([]);
  const [selectedBotId, setSelectedBotId] = useState<string>('');

  useEffect(() => {
    getBotList();
  }, []);

  async function getBotList() {
    const adapterListResp = await httpClient.getAdapters();
    const adapterList = adapterListResp.adapters.map((adapter: Adapter) => {
      return {
        label: i18nObj(adapter.label),
        value: adapter.name,
      };
    });

    httpClient
      .getBots()
      .then((resp) => {
        const botList: BotCardVO[] = resp.bots.map((bot: Bot) => {
          return new BotCardVO({
            id: bot.uuid || '',
            iconURL: httpClient.getAdapterIconURL(bot.adapter),
            name: bot.name,
            description: bot.description,
            adapter: bot.adapter,
            adapterConfig: bot.adapter_config,
            adapterLabel:
              adapterList.find((item) => item.value === bot.adapter)?.label ||
              bot.adapter.substring(0, 10),
            usePipelineName: bot.use_pipeline_name || '',
            enable: bot.enable || false,
          });
        });
        setBotList(botList);
      })
      .catch((err) => {
        console.error('get bot list error', err);
        toast.error(t('bots.getBotListError') + err.message);
      })
      .finally(() => {
        // setIsLoading(false);
      });
  }

  function handleCreateBotClick() {
    setSelectedBotId('');
    setDetailDialogOpen(true);
  }

  function selectBot(botUUID: string) {
    setSelectedBotId(botUUID);
    setDetailDialogOpen(true);
  }

  function handleFormSubmit() {
    getBotList();
    // setDetailDialogOpen(false);
  }

  function handleFormCancel() {
    setDetailDialogOpen(false);
  }

  function handleBotDeleted() {
    getBotList();
    setDetailDialogOpen(false);
  }

  function handleNewBotCreated(botId: string) {
    console.log('new bot created', botId);
    getBotList();
    setSelectedBotId(botId);
  }

  return (
    <div>
      <BotDetailDialog
        open={detailDialogOpen}
        onOpenChange={setDetailDialogOpen}
        botId={selectedBotId || undefined}
        onFormSubmit={handleFormSubmit}
        onFormCancel={handleFormCancel}
        onBotDeleted={handleBotDeleted}
        onNewBotCreated={handleNewBotCreated}
      />

      {/* 注意：其余的返回内容需要保持在Spin组件外部 */}
      <div className={`${styles.botListContainer}`}>
        <CreateCardComponent
          width={'100%'}
          height={'10rem'}
          plusSize={'90px'}
          onClick={handleCreateBotClick}
        />
        {botList.map((cardVO) => {
          return (
            <div
              key={cardVO.id}
              onClick={() => {
                selectBot(cardVO.id);
              }}
            >
              <BotCard
                botCardVO={cardVO}
                setBotEnableCallback={(id, enable) => {
                  setBotList(
                    botList.map((bot) => {
                      if (bot.id === id) {
                        return { ...bot, enable: enable };
                      }
                      return bot;
                    }),
                  );
                }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
