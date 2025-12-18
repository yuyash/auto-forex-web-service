import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import commonEN from './locales/en/common.json';
import commonJA from './locales/ja/common.json';
import strategyEN from './locales/en/strategy.json';
import strategyJA from './locales/ja/strategy.json';
import backtestEN from './locales/en/backtest.json';
import backtestJA from './locales/ja/backtest.json';
import settingsEN from './locales/en/settings.json';
import settingsJA from './locales/ja/settings.json';

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
      },
      ja: {
        common: commonJA,
        strategy: strategyJA,
        backtest: backtestJA,
        settings: settingsJA,
      },
    },
    lng: 'en', // Default language
    fallbackLng: 'en', // Fallback language if translation is missing
    defaultNS: 'common', // Default namespace
    ns: ['common', 'strategy', 'backtest', 'settings'], // Available namespaces
    interpolation: {
      escapeValue: false, // React already escapes values
    },
    react: {
      useSuspense: false, // Disable suspense for now
    },
  });

export default i18n;
