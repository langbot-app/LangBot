'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import styles from './botConfig.module.css';
import { BotCardVO } from '@/app/home/bots/components/bot-card/BotCardVO';
import BotCard from '@/app/home/bots/components/bot-card/BotCard';
import CreateCardComponent from '@/app/infra/basic-component/create-card-component/CreateCardComponent';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Bot, Adapter } from '@/app/infra/entities/api';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { CustomApiError } from '@/app/infra/entities/common';
import { systemInfo } from '@/app/infra/http';
import BotDetailContent from './BotDetailContent';

export default function BotConfigPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const detailId = searchParams.get('id');
  const [botList, setBotList] = useState<BotCardVO[]>([]);

  useEffect(() => {
    if (!detailId) {
      getBotList();
    }
  }, [detailId]);

  async function getBotList() {
    const adapterListResp = await httpClient.getAdapters();
    const adapterList = adapterListResp.adapters.map((adapter: Adapter) => {
      return {
        label: extractI18nObject(adapter.label),
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
        toast.error(t('bots.getBotListError') + (err as CustomApiError).msg);
      });
  }

  function handleCreateBotClick() {
    const maxBots = systemInfo.limitation?.max_bots ?? -1;
    if (maxBots >= 0 && botList.length >= maxBots) {
      toast.error(t('limitation.maxBotsReached', { max: maxBots }));
      return;
    }
    router.push('/home/bots?id=new');
  }

  function selectBot(botUUID: string) {
    router.push(`/home/bots?id=${encodeURIComponent(botUUID)}`);
  }

  // Show detail/edit view when ?id= query param is present
  if (detailId) {
    return <BotDetailContent id={detailId} />;
  }

  return (
    <div className="h-full overflow-y-auto">
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
