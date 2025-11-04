# Dashboard Components

This directory contains components specific to the main trading dashboard.

## OpenOrdersPanel

An expandable panel component that displays pending orders with the ability to cancel them.

### Features

- Expandable/collapsible panel with order count badge
- Displays order details: ID, type, instrument, price, units, status
- Cancel button for each order
- Status chips with color coding (info for pending/open, success for filled, error for cancelled)
- Sortable and filterable columns
- Pagination support
- Empty state when no orders
- Loading state support
- Internationalization (English/Japanese)

### Usage

```tsx
import { OpenOrdersPanel } from '../components/dashboard';
import { Order } from '../types/chart';

const MyComponent = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);

  const handleCancelOrder = async (orderId: string) => {
    setLoading(true);
    try {
      // Call API to cancel order
      await cancelOrder(orderId);
      // Update orders list
      setOrders(orders.filter((o) => o.order_id !== orderId));
    } catch (error) {
      console.error('Failed to cancel order:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <OpenOrdersPanel
      orders={orders}
      onCancelOrder={handleCancelOrder}
      loading={loading}
    />
  );
};
```

### Props

| Prop            | Type                        | Required | Description                                        |
| --------------- | --------------------------- | -------- | -------------------------------------------------- |
| `orders`        | `Order[]`                   | Yes      | Array of order objects to display                  |
| `onCancelOrder` | `(orderId: string) => void` | Yes      | Callback function when cancel button is clicked    |
| `loading`       | `boolean`                   | No       | Disables cancel buttons when true (default: false) |

### Order Type

```typescript
interface Order {
  order_id: string;
  instrument: string;
  order_type: 'market' | 'limit' | 'stop' | 'oco';
  direction: 'long' | 'short';
  units: number;
  price?: number;
  take_profit?: number;
  stop_loss?: number;
  status: string;
  created_at: string;
}
```

### Styling

The component uses Material-UI components and follows the application theme. It includes:

- Hover effects on the header
- Color-coded status chips
- Responsive table layout
- Smooth collapse/expand animations

### Internationalization

The component uses the `dashboard` namespace for translations. Required translation keys:

- `orders.title` - Panel title
- `orders.noOrders` - Empty state message
- `orders.orderId` - Order ID column label
- `orders.type` - Type column label
- `orders.instrument` - Instrument column label
- `orders.price` - Price column label
- `orders.units` - Units column label
- `orders.status` - Status column label
- `orders.cancelOrder` - Cancel button text
- `orders.market`, `orders.limit`, `orders.stop`, `orders.oco` - Order type labels
