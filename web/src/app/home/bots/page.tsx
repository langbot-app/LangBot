'use client';

import { useEffect, useState } from 'react';
import styles from './botConfig.module.css';
import { BotCardVO } from '@/app/home/bots/components/bot-card/BotCardVO';
import BotForm from '@/app/home/bots/components/bot-form/BotForm';
import BotCard from '@/app/home/bots/components/bot-card/BotCard';
import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Bot, Adapter } from '@/app/infra/entities/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { i18nObj } from '@/i18n/I18nProvider';

export default function BotConfigPage() {
  const { t } = useTranslation();
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [botList, setBotList] = useState<BotCardVO[]>([]);
  const [isEditForm, setIsEditForm] = useState(false);
  const [nowSelectedBotUUID, setNowSelectedBotUUID] = useState<string>();

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
            adapterLabel:
              adapterList.find((item) => item.value === bot.adapter)?.label ||
              bot.adapter.substring(0, 10),
            usePipelineName: bot.use_pipeline_name || '',
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
    setIsEditForm(false);
    setNowSelectedBotUUID('');
    setModalOpen(true);
  }

  function selectBot(botUUID: string) {
    setNowSelectedBotUUID(botUUID);
    setIsEditForm(true);
    setModalOpen(true);
  }

  return (
    <div className={styles.configPageContainer}>
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="w-[700px] max-h-[80vh] p-0 flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-4">
            <DialogTitle>
              {isEditForm ? t('bots.editBot') : t('bots.createBot')}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto px-6">
            <BotForm
              initBotId={nowSelectedBotUUID}
              onFormSubmit={() => {
                getBotList();
                setModalOpen(false);
              }}
              onFormCancel={() => setModalOpen(false)}
              onBotDeleted={() => {
                getBotList();
                setModalOpen(false);
              }}
              onNewBotCreated={(botId) => {
                console.log('new bot created', botId);
                getBotList();
                selectBot(botId);
              }}
            />
          </div>
        </DialogContent>
      </Dialog>

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
              <BotCard botCardVO={cardVO} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
