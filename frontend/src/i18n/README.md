# Internationalization (i18n) Setup

This directory contains the internationalization configuration and translation files for the Auto Forex Trader frontend.

## Structure

```
i18n/
├── config.ts           # i18next configuration
├── i18next.d.ts        # TypeScript type definitions
├── locales/
│   ├── en/             # English translations
│   │   ├── common.json
│   │   ├── dashboard.json
│   │   ├── strategy.json
│   └── ja/             # Japanese translations
│       ├── common.json
│       ├── dashboard.json
│       ├── strategy.json
└── README.md
```

## Supported Languages

- **English (en)**: Default language
- **Japanese (ja)**: Secondary language

## Namespaces

The translations are organized into four namespaces:

1. **common**: Shared translations used across the application
   - App name and branding
   - Navigation items
   - Authentication labels
   - Common actions (submit, cancel, save, etc.)
   - Status labels
   - Messages
   - Time-related labels
   - Language selector

2. **dashboard**: Dashboard-specific translations
   - Dashboard title and welcome message
   - Chart controls
   - Position information
   - Order information
   - Account details
   - Connection status
   - Strategy status

3. **strategy**: Trading strategy translations
   - Strategy types
   - Configuration parameters
   - Performance metrics
   - Control actions
   - Status messages

   - System health monitoring
   - User management
   - Strategy monitoring
   - Event logging
   - Security monitoring
   - Notifications
   - System settings

## Usage

### Basic Usage

```typescript
import { useTranslation } from 'react-i18next';

const MyComponent = () => {
  const { t } = useTranslation('common');

  return <h1>{t('app.name')}</h1>;
};
```

### Using Multiple Namespaces

```typescript
import { useTranslation } from 'react-i18next';

const MyComponent = () => {
  const { t } = useTranslation(['common', 'dashboard']);

  return (
    <div>
      <h1>{t('common:app.name')}</h1>
      <p>{t('dashboard:welcome')}</p>
    </div>
  );
};
```

### Changing Language

```typescript
import { useTranslation } from 'react-i18next';

const LanguageSwitcher = () => {
  const { i18n } = useTranslation();

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };

  return (
    <div>
      <button onClick={() => changeLanguage('en')}>English</button>
      <button onClick={() => changeLanguage('ja')}>日本語</button>
    </div>
  );
};
```

### Interpolation

```typescript
// Translation file
{
  "greeting": "Hello, {{name}}!"
}

// Component
const { t } = useTranslation();
<p>{t('greeting', { name: 'John' })}</p>
// Output: Hello, John!
```

## Language Selector Component

A pre-built `LanguageSelector` component is available at `src/components/common/LanguageSelector.tsx`. It provides a dropdown menu for switching between supported languages.

```typescript
import LanguageSelector from './components/common/LanguageSelector';

const Header = () => {
  return (
    <header>
      <LanguageSelector />
    </header>
  );
};
```

## Adding New Languages

1. Create a new directory under `locales/` with the language code (e.g., `fr` for French)
2. Copy the JSON files from an existing language directory
3. Translate all strings in the JSON files
4. Update `config.ts` to include the new language in the resources
5. Update the `LanguageSelector` component to include the new language option

## Adding New Translation Keys

1. Add the key-value pair to the appropriate JSON file in the `en` directory
2. Add the corresponding translation to the same file in other language directories
3. The TypeScript types will be automatically updated based on the English translations

## Best Practices

1. **Use namespaces**: Organize translations by feature or page to keep files manageable
2. **Consistent naming**: Use dot notation for nested keys (e.g., `auth.login`, `auth.register`)
3. **Avoid hardcoded strings**: Always use translation keys instead of hardcoded text
4. **Keep translations in sync**: When adding a key to one language, add it to all languages
5. **Use meaningful keys**: Choose descriptive key names that indicate the context
6. **Test both languages**: Verify that the UI works correctly in all supported languages

## TypeScript Support

The `i18next.d.ts` file provides TypeScript type safety for translation keys. This ensures that:

- You get autocomplete for translation keys
- TypeScript will warn you if you use a non-existent key
- You get type checking for interpolation parameters

## Testing

When writing tests, make sure to import the i18n configuration:

```typescript
import '../i18n/config';
```

This is already done in `src/test/setup.ts`, so all tests will have i18n available.
