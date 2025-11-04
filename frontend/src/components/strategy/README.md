# Strategy Components

This directory contains components related to trading strategy management and configuration.

## Components

### StrategySelector

A component for displaying and selecting trading strategies.

**Features:**

- Display list of available strategies
- Show strategy descriptions and class names
- Support for dropdown and card-based layouts
- Visual feedback for selected strategy
- Hover effects for better UX
- Loading and disabled states
- Internationalization support

**Props:**

- `strategies`: Array of available strategies
- `selectedStrategy`: Currently selected strategy ID
- `onStrategyChange`: Callback when strategy selection changes
- `disabled`: Whether the selector is disabled (default: false)
- `loading`: Whether strategies are being loaded (default: false)
- `variant`: Display variant - 'dropdown' or 'cards' (default: 'dropdown')

**Usage:**

```tsx
import { StrategySelector } from '../components/strategy';

const MyComponent = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');

  return (
    <StrategySelector
      strategies={strategies}
      selectedStrategy={selectedStrategy}
      onStrategyChange={setSelectedStrategy}
      variant="cards"
    />
  );
};
```

**Variants:**

1. **Dropdown** (default): Traditional select dropdown with strategy names and descriptions
2. **Cards**: Grid-based card layout with hover effects and visual selection indicators
