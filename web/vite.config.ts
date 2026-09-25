import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

// The Python backend (python_backend/launcher.py) serves both the API and the built UI.
// `npm run dev` is only for editing the interface: it proxies /api to that backend.
const BACKEND = `http://127.0.0.1:${process.env.EVENTWATCHER_PORT || 3847}`;

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      host: '127.0.0.1',
      proxy: {
        '/api': {
          target: BACKEND,
          changeOrigin: true,
          // The backend only accepts same-origin writes; present them as coming from itself.
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              if (proxyReq.getHeader('origin')) proxyReq.setHeader('origin', BACKEND);
            });
          },
        },
      },
    },
  };
});
