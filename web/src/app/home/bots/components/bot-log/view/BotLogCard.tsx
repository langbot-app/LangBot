'use client';

import { BotLog } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';
import styles from './botLog.module.css';
import { httpClient } from '@/app/infra/http/HttpClient';
import { PhotoProvider } from 'react-photo-view';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

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
    return strArr;
  }
  return (
    <div className={`${styles.botLogCardContainer}`}>
      {/* 头部标签，时间 */}
      <div className={`${styles.cardTitleContainer}`}>
        <div className={`flex flex-row gap-4`}>
          <div className={`${styles.tag}`}>{botLog.level}</div>
          {botLog.message_session_id && (
            <div
              className={`${styles.tag} ${styles.chatTag}`}
              onClick={() => {
                navigator.clipboard
                  .writeText(botLog.message_session_id)
                  .then(() => {
                    toast.success(t('common.copySuccess'));
                  });
              }}
            >
              <svg
                className="icon"
                viewBox="0 0 1024 1024"
                version="1.1"
                xmlns="http://www.w3.org/2000/svg"
                p-id="1664"
                width="20"
                height="20"
                fill="currentColor"
              >
                <path
                  d="M96.1 575.7a32.2 32.1 0 1 0 64.4 0 32.2 32.1 0 1 0-64.4 0Z"
                  p-id="1665"
                  fill="currentColor"
                ></path>
                <path
                  d="M742.1 450.7l-269.5-2.1c-14.3-0.1-26 13.8-26 31s11.7 31.3 26 31.4l269.5 2.1c14.3 0.1 26-13.8 26-31s-11.7-31.3-26-31.4zM742.1 577.7l-269.5-2.1c-14.3-0.1-26 13.8-26 31s11.7 31.3 26 31.4l269.5 2.1c14.3 0.2 26-13.8 26-31s-11.7-31.3-26-31.4z"
                  p-id="1666"
                  fill="currentColor"
                ></path>
                <path
                  d="M736.1 63.9H417c-70.4 0-128 57.6-128 128h-64.9c-70.4 0-128 57.6-128 128v128c-0.1 17.7 14.4 32 32.2 32 17.8 0 32.2-14.4 32.2-32.1V320c0-35.2 28.8-64 64-64H289v447.8c0 70.4 57.6 128 128 128h255.1c-0.1 35.2-28.8 63.8-64 63.8H224.5c-35.2 0-64-28.8-64-64V703.5c0-17.7-14.4-32.1-32.2-32.1-17.8 0-32.3 14.4-32.3 32.1v128.3c0 70.4 57.6 128 128 128h384.1c70.4 0 128-57.6 128-128h65c70.4 0 128-57.6 128-128V255.9l-193-192z m0.1 63.4l127.7 128.3H800c-35.2 0-64-28.8-64-64v-64.3h0.2z m64 641H416.1c-35.2 0-64-28.8-64-64v-513c0-35.2 28.8-64 64-64H671V191c0 70.4 57.6 128 128 128h65.2v385.3c0 35.2-28.8 64-64 64z"
                  p-id="1667"
                  fill="currentColor"
                ></path>
              </svg>
              {/* 会话ID */}

              <span className={`${styles.chatId}`}>
                {getSubChatId(botLog.message_session_id)}
              </span>
            </div>
          )}
        </div>
        <div>{formatTime(botLog.timestamp)}</div>
      </div>
      <div className={`${styles.cardTitleContainer} ${styles.cardText}`}>
        {botLog.text}
      </div>
      <PhotoProvider className={``}>
        <div className={`w-50 mt-2`}>
          {botLog.images.map((item) => (
            <img
              key={item}
              src={`${baseURL}/api/v1/files/image/${item}`}
              alt=""
            />
          ))}
        </div>
      </PhotoProvider>
    </div>
  );
}
