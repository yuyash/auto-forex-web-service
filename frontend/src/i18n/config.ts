import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import commonEN from './locales/en/common.json';
import commonJA from './locales/ja/common.json';
import dashboardEN from './locales/en/dashboard.json';
import dashboardJA from './locales/ja/dashboard.json';
import strategyEN from './locales/en/strategy.json';
import strategyJA from './locales/ja/strategy.json';
import adminEN from './locales/en/admin.json';
import adminJA from './locales/ja/admin.json';
import ordersEN from './locales/en/orders.json';
import ordersJA from './locales/ja/orders.json';
import positionsEN from './locales/en/positions.json';
import positionsJA from './locales/ja/positions.json';
import backtestEN from './locales/en/backtest.json';
import backtestJA from './locales/ja/backtest.json';

// Initialize i18next
i18n
  .use(initReactI18next) // Passes i18n down to react-i18next
  .init({
    resources: {
      en: {
        common: commonEN,
        dashboard: dashboardEN,
        strategy: strategyEN,
        admin: adminEN,
        orders: ordersEN,
        positions: positionsEN,
        backtest: backtestEN,
      },
      ja: {
        common: commonJA,
        dashboard: dashboardJA,
        strategy: strategyJA,
        admin: adminJA,
        orders: ordersJA,
        positions: positionsJA,
        backtest: backtestJA,
      },
    },
    lng: 'en', // Default language
    fallbackLng: 'en', // Fallback language if translation is missing
    defaultNS: 'common', // Default namespace
    ns: [
      'common',
      'dashboard',
      'strategy',
      'admin',
      'orders',
      'positions',
      'backtest',
    ], // Available namespaces
    interpolation: {
      escapeValue: false, // React already escapes values
    },
    react: {
      useSuspense: false, // Disable suspense for now
    },
  });

export default i18n;
