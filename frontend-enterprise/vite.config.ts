import path from 'path';
import tailwindcss from '@tailwindcss/vite';
import { loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import svgr from 'vite-plugin-svgr';
import { defineConfig } from 'vitest/config';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react(), tailwindcss(), svgr()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@staffdeck/business-ui': path.resolve(__dirname, '../packages/staffdeck-business-ui/src'),
        react: path.resolve(__dirname, './node_modules/react'),
        'react-dom': path.resolve(__dirname, './node_modules/react-dom'),
        'react-router-dom': path.resolve(__dirname, './node_modules/react-router-dom'),
        'lucide-react': path.resolve(__dirname, './node_modules/lucide-react'),
        'radix-ui': path.resolve(__dirname, './node_modules/radix-ui'),
        cytoscape: path.resolve(__dirname, './node_modules/cytoscape'),
        clsx: path.resolve(__dirname, './node_modules/clsx'),
        'tailwind-merge': path.resolve(__dirname, './node_modules/tailwind-merge'),
      },
    },
    base: '/',
    test: {
      setupFiles: ['./src/test/setup.ts'],
      environmentOptions: {
        jsdom: {
          url: 'http://localhost/',
        },
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  };
});
