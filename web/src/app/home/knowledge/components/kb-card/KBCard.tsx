import { KnowledgeBaseVO } from '@/app/home/knowledge/components/kb-card/KBCardVO';
import { useTranslation } from 'react-i18next';
import styles from './KBCard.module.css';
import { Clock } from 'lucide-react';

export default function KBCard({ kbCardVO }: { kbCardVO: KnowledgeBaseVO }) {
  const { t } = useTranslation();

  return (
    <div className={`${styles.cardContainer}`}>
      <div className={`${styles.basicInfoContainer}`}>
        <div className={`${styles.iconBasicInfoContainer}`}>
          <div className={`${styles.iconEmoji}`}>{kbCardVO.emoji || '📚'}</div>
          <div className={`${styles.basicInfoNameContainer}`}>
            <div className="flex items-center gap-2">
              <div className={`${styles.basicInfoNameText} ${styles.bigText}`}>
                {kbCardVO.name}
              </div>
              {/* Engine badge */}
              <span className={styles.engineBadge}>
                {kbCardVO.getEngineName()}
              </span>
            </div>
            <div className={`${styles.basicInfoDescriptionText}`}>
              {kbCardVO.description}
            </div>
          </div>
        </div>

        <div className={`${styles.basicInfoLastUpdatedTimeContainer}`}>
          <Clock className={`${styles.basicInfoUpdateTimeIcon}`} />
          <div className={`${styles.basicInfoUpdateTimeText}`}>
            {t('knowledge.updateTime')}
            {kbCardVO.lastUpdatedTimeAgo}
          </div>
        </div>
      </div>
    </div>
  );
}
