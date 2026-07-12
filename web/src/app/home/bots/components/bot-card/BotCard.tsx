import { BotCardVO } from '@/app/home/bots/components/bot-card/BotCardVO';
import styles from './botCard.module.css';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Switch } from '@/components/ui/switch';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { MessageSquare, Workflow } from 'lucide-react';

export default function BotCard({
  botCardVO,
  setBotEnableCallback,
}: {
  botCardVO: BotCardVO;
  setBotEnableCallback: (id: string, enable: boolean) => void;
}) {
  const { t } = useTranslation();

  function setBotEnable(enable: boolean) {
    return httpClient.updateBot(botCardVO.id, {
      name: botCardVO.name,
      description: botCardVO.description,
      adapter: botCardVO.adapter,
      adapter_config: botCardVO.adapterConfig,
      enable: enable,
    });
  }

  return (
    <div className={`${styles.cardContainer}`}>
      <div className={`${styles.iconBasicInfoContainer}`}>
        <img
          className={`${styles.iconImage}`}
          src={botCardVO.iconURL}
          alt="icon"
        />

        <div className={`${styles.basicInfoContainer}`}>
          <div className={`${styles.basicInfoNameContainer}`}>
            <div className={`${styles.basicInfoName}`}>{botCardVO.name}</div>
            <div className={`${styles.basicInfoDescription}`}>
              {botCardVO.description}
            </div>
          </div>

          <div className={`${styles.basicInfoAdapterContainer}`}>
            <MessageSquare className={`${styles.basicInfoAdapterIcon}`} />
            <span className={`${styles.basicInfoAdapterLabel}`}>
              {botCardVO.adapterLabel}
            </span>
          </div>

          <div className={`${styles.basicInfoPipelineContainer}`}>
            <Workflow className={`${styles.basicInfoPipelineIcon}`} />
            <span className={`${styles.basicInfoPipelineLabel}`}>
              {botCardVO.usePipelineName}
            </span>
          </div>
        </div>

        <div className={`${styles.botOperationContainer}`}>
          <Switch
            checked={botCardVO.enable}
            onCheckedChange={(e) => {
              setBotEnable(e)
                .then(() => {
                  setBotEnableCallback(botCardVO.id, e);
                })
                .catch((err) => {
                  console.error(err);
                  toast.error(t('bots.setBotEnableError'));
                });
            }}
            onClick={(e) => {
              e.stopPropagation();
            }}
          />
        </div>
      </div>
    </div>
  );
}
