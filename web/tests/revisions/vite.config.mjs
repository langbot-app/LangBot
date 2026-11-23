import path from 'node:path';
import tailwind from '@tailwindcss/postcss';
import { fileURLToPath } from 'node:url';
const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../..',
);
export default {
  root,
  resolve: { alias: { '@': path.join(root, 'src') } },
  esbuild: { jsx: 'automatic' },
  css: { postcss: { plugins: [tailwind({ base: root })] } },
  server: { host: '127.0.0.1', port: 4186, strictPort: true },
};
