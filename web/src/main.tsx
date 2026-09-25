import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
// Fonts are bundled into the app (open-source OFL licence); nothing loads from the internet.
import '@fontsource-variable/inter';
import '@fontsource-variable/playfair-display';
import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import App from './App.tsx';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
