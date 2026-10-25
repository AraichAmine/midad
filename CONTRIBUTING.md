# Contributing to Midad (مداد)

Thank you for your interest in contributing to **Midad**! We welcome contributions from both human developers and AI assistants to advance Arabic digital calligraphy and cursive typography.

---

## Code of Conduct

All contributors are expected to adhere to our [Code of Conduct](file:///home/ubuntu/workspace/midad/CODE_OF_CONDUCT.md).

---

## Development Setup

### Prerequisites:
- **Node.js**: >= 20.0.0
- **Python**: >= 3.12
- **System Libraries (Linux/Ubuntu)**:
  ```bash
  sudo apt-get install -y libcairo2-dev libpango1.0-dev libharfbuzz-dev libfreetype6-dev fontconfig
  ```

### Getting Started:
1. Clone the repository:
   ```bash
   git clone https://github.com/midad-engine/midad.git
   cd midad
   ```
2. Install Engine dependencies:
   ```bash
   cd engine && npm install && cd ..
   ```
3. Set up Python virtual environment:
   ```bash
   cd pipeline
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt  # or install fonttools, uharfbuzz, shapely, scipy, numpy, pytest
   cd ..
   ```
4. Start the interactive development player:
   ```bash
   npm run dev
   # Opens http://localhost:5173/debugger/midad_player.html
   ```

---

## Verification & Testing

Before submitting a pull request, verify that all test suites pass:

```bash
# 1. Engine TypeScript typecheck & unit tests
npm run typecheck
npm test

# 2. Production build & packaging
npm run build

# 3. Python mathematical invariants
pipeline/.venv/bin/pytest pipeline/tests/test_milestone3_welding.py
```

---

## Pull Request Guidelines

1. **Create a topic branch**: `git checkout -b feat/my-enhancement`.
2. **Follow Invariants**: Review [AGENTS.md](file:///home/ubuntu/workspace/midad/AGENTS.md) for non-negotiable mathematical invariants ($C^0 < 0.05$, $G^1 < 12^\circ$, Single-`M` baseline, temporal causality).
3. **Write tests**: Add unit tests for any new features or bug fixes.
4. **Submit PR**: Open a PR against `main` using our PR template.
