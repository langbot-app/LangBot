import styles from './pipelineCard.module.css';
import { PipelineCardVO } from '@/app/home/pipelines/components/pipeline-card/PipelineCardVO';
import { useTranslation } from 'react-i18next';
import { Clock, Star } from 'lucide-react';

export default function PipelineCard({ cardVO }: { cardVO: PipelineCardVO }) {
  const { t } = useTranslation();

  return (
    <div className={`${styles.cardContainer}`}>
      <div className={`${styles.basicInfoContainer}`}>
        <div className={`${styles.iconBasicInfoContainer}`}>
          <div className={`${styles.iconEmoji}`}>{cardVO.emoji || '⚙️'}</div>
          <div className={`${styles.basicInfoNameContainer}`}>
            <div className={`${styles.basicInfoNameText}  ${styles.bigText}`}>
              {cardVO.name}
            </div>
            <div className={`${styles.basicInfoDescriptionText}`}>
              {cardVO.description}
            </div>
          </div>
        </div>

        <div className={`${styles.basicInfoLastUpdatedTimeContainer}`}>
          <Clock className={`${styles.basicInfoUpdateTimeIcon}`} />
          <div className={`${styles.basicInfoUpdateTimeText}`}>
            {t('pipelines.updateTime')}
            {cardVO.lastUpdatedTimeAgo}
          </div>
        </div>
      </div>

      {cardVO.isDefault && (
        <div className={styles.operationContainer}>
          <div className={styles.operationDefaultBadge}>
            <Star className={styles.operationDefaultBadgeIcon} />
            <div className={styles.operationDefaultBadgeText}>
              {t('pipelines.defaultBadge')}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
