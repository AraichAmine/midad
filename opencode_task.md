# Task Specification: Milestone 6 — Public API, Font Packaging & Documentation

## Target Deliverables:
1. `engine/src/midad.ts` & `engine/src/types.ts`: Vara.js-compatible public API, reset, ready, animationEnd, BiDi fallback.
2. `pipeline/src/packager.py`: Production font packaging pipeline with RDP simplification.
3. `fixtures/fonts/midad_naskh_50.json` & `engine/dist/fonts/noto_naskh_50.json`: Packaged 50-word font fixture (< 95 KB gzipped).
4. `engine/tests/api.test.ts`: Vitest test suite for Milestone 6 API and packaging size gates.
5. `README.md`: Comprehensive open-source documentation at repository root.
6. `progress.md`: Milestone 6 status tracking and log update.

## Test Verification Target:
Run the Vitest API suite and TypeScript compilation inside `engine/`:
```bash
cd /home/ubuntu/workspace/midad/engine
npx vitest run tests/api.test.ts
npm run typecheck
npm run build
```
Target checks:
- All unit tests in `tests/api.test.ts` pass (14+ tests).
- Production ES bundle `dist/midad.es.js` < 25 KB gzipped.
- Production UMD bundle `dist/midad.umd.js` < 25 KB gzipped.
- Packaged font `dist/fonts/noto_naskh_50.json` < 95 KB gzipped.
- TypeScript compilation `tsc --noEmit` exits with 0 errors.
