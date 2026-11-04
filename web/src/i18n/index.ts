import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import enUS from './locales/en-US';
import botSetup from './locales/bot-setup';
import scenario from './locales/scenario';
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
        translation: {
          ...enUS,
          botSetup: botSetup['en-US'],
          scenario: scenario['en-US'],
        },
      },
      'zh-Hans': {
        translation: {
          ...zhHans,
          botSetup: botSetup['zh-Hans'],
          scenario: scenario['zh-Hans'],
        },
      },
      'zh-Hant': {
        translation: {
          ...zhHant,
          botSetup: botSetup['zh-Hant'],
          scenario: scenario['zh-Hant'],
        },
      },
      'ja-JP': {
        translation: {
          ...jaJP,
          botSetup: botSetup['ja-JP'],
          scenario: scenario['ja-JP'],
        },
      },
      'th-TH': {
        translation: {
          ...thTH,
          botSetup: botSetup['th-TH'],
          scenario: scenario['th-TH'],
        },
      },
      'vi-VN': {
        translation: {
          ...viVN,
          botSetup: botSetup['vi-VN'],
          scenario: scenario['vi-VN'],
        },
      },
      'es-ES': {
        translation: {
          ...esES,
          botSetup: botSetup['es-ES'],
          scenario: scenario['es-ES'],
        },
      },
      'ru-RU': {
        translation: {
          ...ruRU,
          botSetup: botSetup['ru-RU'],
          scenario: scenario['ru-RU'],
        },
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
