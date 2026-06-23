import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // Disable HMR WebSocket to avoid Windows proxy blocking it
    hmr: false,
    proxy: {
      // Proxy /api requests to the Node.js backend (session management)
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      // Proxy /py-api requests directly to the Python CAD engine
      '/py-api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => {
          if (path.includes('/health')) return '/health';
          if (path.includes('/download')) return path.replace('/py-api', '/api');
          return path.replace('/py-api', '/api');
        },
      },
    },
  },
});
