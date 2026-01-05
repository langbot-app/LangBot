'use client';

import { useState } from 'react';
import { BotLog } from '@/app/infra/http/requestParam/bots/GetBotLogsResponse';
import styles from './botLog.module.css';
import { httpClient } from '@/app/infra/http/HttpClient';
import { PhotoProvider } from 'react-photo-view';
import { useTranslation } from 'react-i18next';
import { Check, ChevronDown, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';

export function BotLogCard({ botLog }: { botLog: BotLog }) {
  const { t } = useTranslation();
  const baseURL = httpClient.getBaseUrl();
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  // Fallback 复制方法，用于不支持 clipboard API 的环境
  function fallbackCopy(text: string) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    textArea.style.top = '-9999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
      toast.success(t('common.copySuccess'));
    } catch {
      toast.error(t('common.copyFailed'));
    }
    document.body.removeChild(textArea);
  }

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

  // 根据日志级别返回对应的样式类
  function getLevelStyles(level: string) {
    switch (level.toLowerCase()) {
      case 'error':
        return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
      case 'warning':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400';
      case 'info':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400';
      case 'debug':
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400';
    }
  }

  // 截取文本的简短版本
  function getShortText(text: string, maxLength: number = 100) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  }

  // 判断是否需要展开按钮
  const needsExpand = botLog.text.length > 100 || botLog.images.length > 0;

  return (
    <div className={`${styles.botLogCardContainer}`}>
      {/* 头部标签，时间 */}
      <div className={`${styles.cardTitleContainer}`}>
        <div className={`flex flex-row gap-2 items-center`}>
          <div
            className={`px-2 py-1 rounded text-xs font-medium uppercase ${getLevelStyles(
              botLog.level,
            )}`}
          >
            {botLog.level}
          </div>
          {botLog.message_session_id && (
            <div
              className={`${styles.tag} ${styles.chatTag} relative`}
              onClick={(e) => {
                e.stopPropagation();
                // 兼容性更好的复制方法
                if (navigator.clipboard && navigator.clipboard.writeText) {
                  navigator.clipboard
                    .writeText(botLog.message_session_id)
                    .then(() => {
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                      toast.success(t('common.copySuccess'));
                    })
                    .catch(() => {
                      // fallback
                      fallbackCopy(botLog.message_session_id);
                    });
                } else {
                  fallbackCopy(botLog.message_session_id);
                }
              }}
              title={t('common.clickToCopy')}
            >
              {copied ? (
                <Check className="w-4 h-4 text-green-600" />
              ) : (
                <svg
                  className="icon"
                  viewBox="0 0 1024 1024"
                  version="1.1"
                  xmlns="http://www.w3.org/2000/svg"
                  p-id="1664"
                  width="16"
                  height="16"
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
              )}

              <span className={`${styles.chatId}`}>
                {getSubChatId(botLog.message_session_id)}
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {needsExpand && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors"
            >
              {expanded ? (
                <>
                  <ChevronDown className="w-3 h-3" />
                  {t('bots.collapse')}
                </>
              ) : (
                <>
                  <ChevronRight className="w-3 h-3" />
                  {t('bots.viewDetails')}
                </>
              )}
            </button>
          )}
          <div className={`${styles.timestamp}`}>
            {formatTime(botLog.timestamp)}
          </div>
        </div>
      </div>

      {/* 日志内容 - 简化显示 */}
      <div className={`${styles.cardText}`}>
        {expanded ? botLog.text : getShortText(botLog.text)}
      </div>

      {/* 图片 - 只在展开时显示 */}
      {expanded && botLog.images.length > 0 && (
        <PhotoProvider>
          <div className={`flex flex-wrap gap-2 mt-3`}>
            {botLog.images.map((item) => (
              <img
                key={item}
                src={`${baseURL}/api/v1/files/image/${item}`}
                alt=""
                className="max-w-xs rounded cursor-pointer hover:opacity-90 transition-opacity"
              />
            ))}
          </div>
        </PhotoProvider>
      )}

      {/* 图片数量提示 - 未展开时显示 */}
      {!expanded && botLog.images.length > 0 && (
        <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          📷 {botLog.images.length} {t('bots.imagesAttached')}
        </div>
      )}
    </div>
  );
}
