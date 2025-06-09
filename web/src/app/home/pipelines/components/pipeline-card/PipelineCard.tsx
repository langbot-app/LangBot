import styles from './pipelineCard.module.css';
import { PipelineCardVO } from '@/app/home/pipelines/components/pipeline-card/PipelineCardVO';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

export default function PipelineCard({
  cardVO,
  onDebug,
}: {
  cardVO: PipelineCardVO;
  onDebug: (pipelineId: string) => void;
}) {
  const { t } = useTranslation();

  const handleDebugClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDebug(cardVO.id);
  };

  return (
    <div className={`${styles.cardContainer}`}>
      <div className={`${styles.basicInfoContainer}`}>
        <div className={`${styles.basicInfoNameContainer}`}>
          <div className={`${styles.basicInfoNameText}  ${styles.bigText}`}>
            {cardVO.name}
          </div>
          <div className={`${styles.basicInfoDescriptionText}`}>
            {cardVO.description}
          </div>
        </div>

        <div className={`${styles.basicInfoLastUpdatedTimeContainer}`}>
          <svg
            className={`${styles.basicInfoUpdateTimeIcon}`}
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path d="M12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22ZM12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM13 12H17V14H11V7H13V12Z"></path>
          </svg>
          <div className={`${styles.basicInfoUpdateTimeText}`}>
            {t('pipelines.updateTime')}
            {cardVO.lastUpdatedTimeAgo}
          </div>
        </div>
      </div>

      <div className={styles.operationContainer}>
        {cardVO.isDefault && (
          <div className={styles.operationDefaultBadge}>
            <svg
              className={styles.operationDefaultBadgeIcon}
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12.0006 18.26L4.94715 22.2082L6.52248 14.2799L0.587891 8.7918L8.61493 7.84006L12.0006 0.5L15.3862 7.84006L23.4132 8.7918L17.4787 14.2799L19.054 22.2082L12.0006 18.26Z"></path>
            </svg>
            <div className={styles.operationDefaultBadgeText}>
              {t('pipelines.defaultBadge')}
            </div>
          </div>
        )}
        <Button
          variant="outline"
          onClick={handleDebugClick}
          title={t('pipelines.chat')}
          className="mt-auto"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className={styles.debugButtonIcon}
          >
            <path d="M13 19.9C15.2822 19.4367 17 17.419 17 15V12C17 11.299 16.8564 10.6219 16.5846 10H7.41538C7.14358 10.6219 7 11.299 7 12V15C7 17.419 8.71776 19.4367 11 19.9V14H13V19.9ZM5.5358 17.6907C5.19061 16.8623 5 15.9534 5 15H2V13H5V12C5 11.3573 5.08661 10.7348 5.2488 10.1436L3.0359 8.86602L4.0359 7.13397L6.05636 8.30049C6.11995 8.19854 6.18609 8.09835 6.25469 8H17.7453C17.8139 8.09835 17.88 8.19854 17.9436 8.30049L19.9641 7.13397L20.9641 8.86602L18.7512 10.1436C18.9134 10.7348 19 11.3573 19 12V13H22V15H19C19 15.9534 18.8094 16.8623 18.4642 17.6907L20.9641 19.134L19.9641 20.866L17.4383 19.4077C16.1549 20.9893 14.1955 22 12 22C9.80453 22 7.84512 20.9893 6.56171 19.4077L4.0359 20.866L3.0359 19.134L5.5358 17.6907ZM8 6C8 3.79086 9.79086 2 12 2C14.2091 2 16 3.79086 16 6H8Z"></path>
          </svg>
          {t('pipelines.chat')}
        </Button>
      </div>
    </div>
  );
}
