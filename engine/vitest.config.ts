import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts', 'tests/**/*.test.ts'],
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/*.spec.ts',
      'tests/**/*.spec.ts',
      '**/fixtures/**',
      '**/pipeline/**',
      '**/.venv/**',
      '**/.opencode/**',
    ],
    pool: 'forks',
    poolOptions: {
      forks: {
        singleFork: true,
      },
    },
    watch: false,
    fileParallelism: false,
    teardownTimeout: 2000,
    testTimeout: 5000,
  },
});
