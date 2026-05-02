import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import enUS from './locales/en-US';
import zhHans from './locales/zh-Hans';
import zhHant from './locales/zh-Hant';
import jaJP from './locales/ja-JP';
import thTH from './locales/th-TH';
import viVN from './locales/vi-VN';
import esES from './locales/es-ES';
import ruRU from './locales/ru-RU';

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
      'th-TH': {
        translation: thTH,
      },
      'vi-VN': {
        translation: viVN,
      },
      'es-ES': {
        translation: esES,
      },
      'ru-RU': {
        translation: ruRU,
      },
    },
    fallbackLng: 'zh-Hans',
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
