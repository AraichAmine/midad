## Description
Please include a summary of the changes and the related issue/feature.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Mathematical Invariants Checklist
- [ ] Single-`M` Invariant: 100% of PAW baselines have exactly one `M` command.
- [ ] $C^0$ Positional Continuity: Joint gap distance $\Delta < 0.05$ font units.
- [ ] $G^1$ Tangent Continuity: Joint tangent angle $\Delta \theta < 12^\circ$.
- [ ] Temporal Causality: Delayed marks start strictly after parent PAW completes.
- [ ] Size Gates: Engine bundle $< 25\text{ KB}$ gz, font package $< 95\text{ KB}$ gz.

## Testing & Verification
- [ ] `npm run typecheck` passes with 0 errors.
- [ ] `npm test` (Vitest unit tests) passes 100%.
- [ ] Python test suites pass (`pytest pipeline/tests/`).
