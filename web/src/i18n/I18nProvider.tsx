'use client';

import { ReactNode } from 'react';
import '@/i18n';
import { I18nText } from '@/app/infra/entities/api';

interface I18nProviderProps {
  children: ReactNode;
}

export default function I18nProvider({ children }: I18nProviderProps) {
  return <>{children}</>;
}
export function i18nObj(i18nText: I18nText): string {
  const language = localStorage.getItem('langbot_language');
  if ((language === 'zh-Hans' && i18nText.zh_Hans) || !i18nText.en_US) {
    return i18nText.zh_Hans;
  }
  return i18nText.en_US;
}
