import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy /api requests to the Node.js backend (session management)
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      // Proxy /py-api requests directly to the Python CAD engine
      // /py-api/digitize → http://localhost:8000/api/digitize
      // /py-api/health  → http://localhost:8000/health
      // /py-api/download → http://localhost:8000/api/download
      '/py-api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => {
          // /py-api/health → /health (keep as-is)
          if (path.includes('/health')) return '/health';
          // /py-api/download/xxx → /api/download/xxx
          if (path.includes('/download')) return path.replace('/py-api', '/api');
          // /py-api/digitize → /api/digitize
          return path.replace('/py-api', '/api');
        },
      },
    },
  },
});
