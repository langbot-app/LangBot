'use client';

import { ReactNode } from 'react';
import '@/i18n';
import { I18nObject } from '@/app/infra/entities/common';
import i18n from 'i18next';

interface I18nProviderProps {
  children: ReactNode;
}

export default function I18nProvider({ children }: I18nProviderProps) {
  return <>{children}</>;
}
// export function extractI18nObject(i18nLabel: I18nObject): string {
//   const language = localStorage.getItem('langbot_language');
//   if ((language === 'zh-Hans' && i18nLabel.zh_Hans) || !i18nLabel.en_US) {
//     return i18nLabel.zh_Hans;
//   }
//   return i18nLabel.en_US;
// }

export const extractI18nObject = (i18nObject: I18nObject): string => {
  // 根据当前语言返回对应的值, fallback优先级：en_US、zh_Hans、zh_Hant、ja_JP
  const language = i18n.language.replace('-', '_');
  if (language === 'en_US' && i18nObject.en_US) return i18nObject.en_US;
  if (language === 'zh_Hans' && i18nObject.zh_Hans) return i18nObject.zh_Hans;
  if (language === 'zh_Hant' && i18nObject.zh_Hant) return i18nObject.zh_Hant;
  if (language === 'ja_JP' && i18nObject.ja_JP) return i18nObject.ja_JP;
  return (
    i18nObject.en_US ||
    i18nObject.zh_Hans ||
    i18nObject.zh_Hant ||
    i18nObject.ja_JP ||
    ''
  );
};

// 工具函数：将 i18n 语言代码转换为 API 语言代码
// i18n 使用：zh-Hans, en-US, ja-JP
// API 使用：zh_Hans, en, ja_JP
export const getAPILanguageCode = (): string => {
  const language = i18n.language;
  // zh-Hans -> zh_Hans
  if (language === 'zh-Hans') return 'zh_Hans';
  // zh-Hant -> zh_Hant
  if (language === 'zh-Hant') return 'zh_Hant';
  // en-US -> en
  if (language === 'en-US') return 'en';
  // ja-JP -> ja_JP
  if (language === 'ja-JP') return 'ja_JP';
  // 默认返回 en
  return 'en';
};
