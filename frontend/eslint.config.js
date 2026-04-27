import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'src/api/generated/**'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      '@typescript-eslint/consistent-type-imports': 'warn',
      '@typescript-eslint/no-explicit-any': 'warn',
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  },
  {
    files: [
      'src/components/common/DateRangeFilter.tsx',
      'src/components/common/TableFilterBar.tsx',
      'src/components/tasks/detail/ChartPanel.tsx',
      'src/components/tasks/detail/MetricsToolbar.tsx',
      'src/components/tasks/detail/Task*FilterBar.tsx',
      'src/components/tasks/detail/TaskMetricsTab.tsx',
      'src/components/tasks/detail/TaskPositionViewHeader.tsx',
      'src/hooks/useTaskMetrics.ts',
    ],
    rules: {
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/no-explicit-any': 'error',
    },
  }
);
