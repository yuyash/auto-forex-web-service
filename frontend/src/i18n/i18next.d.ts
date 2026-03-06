import 'react-i18next';
import common from './locales/en/common.json';
import strategy from './locales/en/strategy.json';
import backtest from './locales/en/backtest.json';
import settings from './locales/en/settings.json';
import dashboard from './locales/en/dashboard.json';
import trading from './locales/en/trading.json';
import configuration from './locales/en/configuration.json';

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
