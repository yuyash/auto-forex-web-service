import 'react-i18next';
import type common from './locales/en/common.json';
import type strategy from './locales/en/strategy.json';
import type backtest from './locales/en/backtest.json';
import type settings from './locales/en/settings.json';
import type dashboard from './locales/en/dashboard.json';
import type trading from './locales/en/trading.json';
import type configuration from './locales/en/configuration.json';

declare module 'react-i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common';
    resources: {
      common: typeof common;
      strategy: typeof strategy;
      backtest: typeof backtest;
      settings: typeof settings;
      dashboard: typeof dashboard;
      trading: typeof trading;
      configuration: typeof configuration;
    };
  }
}
