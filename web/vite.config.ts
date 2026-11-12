import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { gzipSync } from 'node:zlib';
import { readFile, writeFile } from 'node:fs/promises';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:5300';

  return {
    plugins: [
      react(),
      {
        name: 'precompressed-assets',
        apply: 'build',
        async writeBundle(options, bundle) {
          for (const file of Object.values(bundle)) {
            if (!/\.(js|css)$/.test(file.fileName)) continue;
            const filename = path.resolve(options.dir ?? 'dist', file.fileName);
            await writeFile(
              `${filename}.gz`,
              gzipSync(await readFile(filename), { level: 9 }),
            );
          }
        },
      },
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port: 3000,
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
          ws: true,
        },
        '/mcp': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        '/bots': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
    },
  };
});
