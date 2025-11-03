import 'react-i18next';
import common from './locales/en/common.json';
import dashboard from './locales/en/dashboard.json';
import strategy from './locales/en/strategy.json';
import admin from './locales/en/admin.json';

declare module 'react-i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common';
    resources: {
      common: typeof common;
      dashboard: typeof dashboard;
      strategy: typeof strategy;
      admin: typeof admin;
    };
  }
}
