import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // VITE_GEMINI_API_KEY is loaded automatically by Vite from frontend/.env
});
