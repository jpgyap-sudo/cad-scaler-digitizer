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
      '/py-api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/py-api/, ''),
      },
    },
  },
});
