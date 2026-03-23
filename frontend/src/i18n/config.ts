import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { z } from 'zod';
import commonEN from './locales/en/common.json';
import commonJA from './locales/ja/common.json';
import strategyEN from './locales/en/strategy.json';
import strategyJA from './locales/ja/strategy.json';
import backtestEN from './locales/en/backtest.json';
import backtestJA from './locales/ja/backtest.json';
import settingsEN from './locales/en/settings.json';
import settingsJA from './locales/ja/settings.json';
import dashboardEN from './locales/en/dashboard.json';
import dashboardJA from './locales/ja/dashboard.json';
import tradingEN from './locales/en/trading.json';
import tradingJA from './locales/ja/trading.json';
import configurationEN from './locales/en/configuration.json';
import configurationJA from './locales/ja/configuration.json';
import {
  readStoredStringValue,
  writeStoredStringValue,
} from '../utils/persistentState';

const languageSchema = z.enum(['en', 'ja']);
const savedLanguage = readStoredStringValue('i18nextLng', languageSchema, 'en');

// Initialize i18next
i18n
  .use(initReactI18next) // Passes i18n down to react-i18next
  .init({
    resources: {
      en: {
        common: commonEN,
        strategy: strategyEN,
        backtest: backtestEN,
        settings: settingsEN,
        dashboard: dashboardEN,
        trading: tradingEN,
        configuration: configurationEN,
      },
      ja: {
        common: commonJA,
        strategy: strategyJA,
        backtest: backtestJA,
        settings: settingsJA,
        dashboard: dashboardJA,
        trading: tradingJA,
        configuration: configurationJA,
      },
    },
    lng: savedLanguage, // Restore saved language
    fallbackLng: 'en', // Fallback language if translation is missing
    defaultNS: 'common', // Default namespace
    ns: [
      'common',
      'strategy',
      'backtest',
      'settings',
      'dashboard',
      'trading',
      'configuration',
    ], // Available namespaces
    interpolation: {
      escapeValue: false, // React already escapes values
    },
    react: {
      useSuspense: false, // Disable suspense for now
    },
  });

export default i18n;

i18n.on('languageChanged', (lng: string) => {
  writeStoredStringValue('i18nextLng', lng);
});
