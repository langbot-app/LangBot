import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
export default defineConfig({
  plugins: [react()],
  cacheDir: '/tmp/411-reasoning-vite-cache',
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
});
