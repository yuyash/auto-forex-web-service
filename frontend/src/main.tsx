// import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import './i18n/config';
import App from './App.tsx';

createRoot(document.getElementById('root')!).render(
  // StrictMode disabled to prevent WebSocket double-mounting issues in development
  // <StrictMode>
  <App />
  // </StrictMode>
);
