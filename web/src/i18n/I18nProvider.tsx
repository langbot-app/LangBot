'use client';

import { ReactNode } from 'react';
import '@/i18n';
import { I18nLabel } from '@/app/infra/entities/common';

interface I18nProviderProps {
  children: ReactNode;
}

export default function I18nProvider({ children }: I18nProviderProps) {
  return <>{children}</>;
}
export function i18nObj(i18nLabel: I18nLabel): string {
  const language = localStorage.getItem('langbot_language');
  if ((language === 'zh-Hans' && i18nLabel.zh_Hans) || !i18nLabel.en_US) {
    return i18nLabel.zh_Hans;
  }
  return i18nLabel.en_US;
}
