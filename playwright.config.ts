import engineConfig from './engine/playwright.config';

/**
 * Repository-level entry point so the documented invocation
 *
 *   npx --prefix /home/ubuntu/workspace/midad/engine playwright test
 *
 * works when executed from the repository root.  The canonical configuration
 * lives in engine/playwright.config.ts.
 */
export default {
  ...engineConfig,
  testDir: './engine/tests',
  testMatch: /.*\.spec\.ts$/,
  outputDir: './engine/test-results',
};
