import { resolve } from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      name: 'Midad',
      formats: ['es', 'umd'],
      fileName: (format) => `midad.${format}.js`,
    },
    outDir: 'dist',
    emptyOutDir: false,
    sourcemap: true,
  },
});
