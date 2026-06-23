import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy /api requests to the Node.js backend (which forwards to Python engine)
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
    },
  },
  // VITE_GEMINI_API_KEY is loaded automatically by Vite from frontend/.env
});
