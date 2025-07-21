import { KnowledgeBaseVO } from '@/app/home/knowledge/components/kb-card/KBCardVO';
import { useTranslation } from 'react-i18next';
import styles from './KBCard.module.css';

export default function KBCard({ kbCardVO }: { kbCardVO: KnowledgeBaseVO }) {
  const { t } = useTranslation();
  return (
    <div className={`${styles.cardContainer}`}>
      <div className={`${styles.basicInfoContainer}`}>
        <div className={`${styles.basicInfoNameContainer}`}>
          <div className={`${styles.basicInfoNameText}  ${styles.bigText}`}>
            {kbCardVO.name}
          </div>
          <div className={`${styles.basicInfoDescriptionText}`}>
            {kbCardVO.description}
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
            {t('knowledge.updateTime')}
            {kbCardVO.lastUpdatedTimeAgo}
          </div>
        </div>
      </div>
    </div>
  );
}
