# Contributing Guidelines and Engineering Standards

Guidelines for collaborating on the Real Estate Legal RAG platform.

## 1. Branching Strategy

- **`main`**: Production-ready branch. Direct pushes to `main` are restricted.
- **`feat/<feature-name>`**: Used for discrete feature development and sprint tasks.
- **`fix/<bug-description>`**: Used for targeted bug resolutions.
- **`docs/<topic>`**: Used for documentation additions and updates.

---

## 2. Commit Message Convention

Commits follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
- `feat:` A new feature or capability.
- `fix:` A bug fix.
- `docs:` Documentation-only changes.
- `test:` Adding missing tests or correcting existing tests.
- `refactor:` Code change that neither fixes a bug nor adds a feature.
- `chore:` Build process, dependency updates, or auxiliary tool changes.

---

## 3. Pull Request Standards

Before submitting a Pull Request:
1. Ensure all backend tests pass:
   ```bash
   pytest
   ```
2. Ensure frontend type checking passes without errors:
   ```bash
   npm run build
   ```
3. Verify that all documentation references remain accurate and intact.
4. Link the relevant issue or sprint phase in the PR description.
