import { ExternalKBCardVO } from '@/app/home/knowledge/components/external-kb-card/ExternalKBCardVO';
import { useTranslation } from 'react-i18next';
import styles from '../kb-card/KBCard.module.css';
import { httpClient } from '@/app/infra/http/HttpClient';

export default function ExternalKBCard({
  kbCardVO,
}: {
  kbCardVO: ExternalKBCardVO;
}) {
  const { t } = useTranslation();
  return (
    <div className={`${styles.cardContainer}`}>
      <div className="w-full h-full flex flex-row items-start gap-3">
        {/* Icon */}
        <img
          src={httpClient.getPluginIconURL(
            kbCardVO.pluginAuthor,
            kbCardVO.pluginName,
          )}
          alt="plugin icon"
          className="w-16 h-16 mt-1 rounded-[8%] flex-shrink-0"
        />

        {/* Info Column */}
        <div className="flex flex-col flex-1 min-w-0 h-full">
          {/* Top section: Name, Description and Plugin Info */}
          <div className="flex flex-col gap-0">
            {/* Name and Description */}
            <div className={`${styles.basicInfoNameContainer}`}>
              <div className={`${styles.basicInfoNameText} ${styles.bigText}`}>
                {kbCardVO.name}
              </div>
              <div className={`${styles.basicInfoDescriptionText}`}>
                {kbCardVO.description}
              </div>
            </div>

            {/* Plugin Info */}
            <div className="flex flex-row gap-2 items-center mt-1">
              <svg
                className="w-5 h-5 text-gray-500 dark:text-gray-400"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M7 5C7 2.79086 8.79086 1 11 1C13.2091 1 15 2.79086 15 5H18C18.5523 5 19 5.44772 19 6V9C21.2091 9 23 10.7909 23 13C23 15.2091 21.2091 17 19 17V20C19 20.5523 18.5523 21 18 21H4C3.44772 21 3 20.5523 3 20V6C3 5.44772 3.44772 5 4 5H7ZM11 3C9.89543 3 9 3.89543 9 5C9 5.23554 9.0403 5.45952 9.11355 5.66675C9.22172 5.97282 9.17461 6.31235 8.98718 6.57739C8.79974 6.84243 8.49532 7 8.17071 7H5V19H17V15.8293C17 15.5047 17.1576 15.2003 17.4226 15.0128C17.6877 14.8254 18.0272 14.7783 18.3332 14.8865C18.5405 14.9597 18.7645 15 19 15C20.1046 15 21 14.1046 21 13C21 11.8954 20.1046 11 19 11C18.7645 11 18.5405 11.0403 18.3332 11.1135C18.0272 11.2217 17.6877 11.1746 17.4226 10.9872C17.1576 10.7997 17 10.4953 17 10.1707V7H13.8293C13.5047 7 13.2003 6.84243 13.0128 6.57739C12.8254 6.31235 12.7783 5.97282 12.8865 5.66675C12.9597 5.45952 13 5.23555 13 5C13 3.89543 12.1046 3 11 3Z"></path>
              </svg>
              <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                {kbCardVO.pluginAuthor} / {kbCardVO.pluginName}
              </span>
            </div>
          </div>

          {/* Bottom section: Update Time */}
          <div className="flex flex-row gap-2 items-center mt-auto">
            <svg
              className="w-5 h-5 text-gray-500 dark:text-gray-400"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22ZM12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM13 12H17V14H11V7H13V12Z"></path>
            </svg>
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              {t('knowledge.updateTime')}
              {kbCardVO.lastUpdatedTimeAgo}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
