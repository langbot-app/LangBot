'use client';

import { BotLog } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';
import styles from './botLog.module.css';
import { httpClient } from '@/app/infra/http/HttpClient';
import { PhotoProvider, PhotoView } from 'react-photo-view';
import { useTranslation } from 'react-i18next';

export function BotLogCard({ botLog }: { botLog: BotLog }) {
  const { t } = useTranslation();
  const baseURL = httpClient.getBaseUrl();

  function formatTime(timestamp: number) {
    const now = new Date();
    const date = new Date(timestamp * 1000);

    // 获取各个时间部分
    const year = date.getFullYear();
    const month = date.getMonth() + 1; // 月份从0开始，需要+1
    const day = date.getDate();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');

    // 判断时间范围
    const isToday = now.toDateString() === date.toDateString();
    const isYesterday =
      new Date(now.setDate(now.getDate() - 1)).toDateString() ===
      date.toDateString();
    const isThisYear = now.getFullYear() === year;

    if (isToday) {
      return `${hours}:${minutes}`; // 今天的消息：小时:分钟
    } else if (isYesterday) {
      return `${t('bots.yesterday')} ${hours}:${minutes}`; // 昨天的消息：昨天 小时:分钟
    } else if (isThisYear) {
      return t('bots.dateFormat', { month, day }); // 本年消息：x月x日
    } else {
      return t('bots.earlier'); // 更早的消息：更久之前
    }
  }

  function getSubChatId(str: string) {
    const strArr = str.split('');
    return strArr.splice(-8).join('');
  }
  return (
    <div className={`${styles.botLogCardContainer}`}>
      {/* 头部标签，时间 */}
      <div className={`${styles.cardTitleContainer}`}>
        <div className={`flex flex-row gap-4`}>
          <div className={`${styles.tag}`}>{botLog.level}</div>
          <div className={`${styles.tag} ${styles.chatTag}`}>
            {t('bots.session')}-{getSubChatId(botLog.message_session_id)}
          </div>
        </div>
        <div>{formatTime(botLog.timestamp)}</div>
      </div>
      <div className={`${styles.cardTitleContainer} ${styles.cardText}`}>
        {botLog.text}
      </div>
      <PhotoProvider className={``}>
        <div className={`w-24`}>
          {botLog.images.map((item, index) => (
            <PhotoView
              key={index}
              src={`${baseURL}/api/v1/files/image/${item}`}
            >
              <img src={`${baseURL}/api/v1/files/image/${item}`} alt="" />
            </PhotoView>
          ))}
        </div>
      </PhotoProvider>
    </div>
  );
}
