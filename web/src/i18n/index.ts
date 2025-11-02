'use client';

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import enUS from './locales/en-US';
import zhHans from './locales/zh-Hans';
import zhHant from './locales/zh-Hant';
import jaJP from './locales/ja-JP';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      'en-US': {
        translation: enUS,
      },
      'zh-Hans': {
        translation: zhHans,
      },
      'zh-Hant': {
        translation: zhHant,
      },
      'ja-JP': {
        translation: jaJP,
      },
    },
    fallbackLng: 'en-US',
    debug: process.env.NODE_ENV === 'development',
    interpolation: {
      escapeValue: false, // React already escapes values
    },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'langbot_language',
      caches: ['localStorage'],
    },
  });

export default i18n;
