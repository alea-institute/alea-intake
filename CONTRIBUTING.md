# Contributing to ALEA Intake

Thank you for your interest in improving legal intake technology for access to justice. Contributions are welcome from everyone.

## No CLA Required

This project is MIT-licensed. By submitting a pull request, you agree that your contributions are licensed under the same MIT license. No Contributor License Agreement is needed.

## Reporting Bugs

1. Search [existing issues](https://github.com/alea-institute/alea-intake/issues) to check if the bug has already been reported.
2. If not, [open a new issue](https://github.com/alea-institute/alea-intake/issues/new) with:
   - A clear, descriptive title.
   - Steps to reproduce the problem.
   - Expected behavior vs. actual behavior.
   - Your environment (OS, Python version, Node version, database backend).
   - Relevant logs or error messages.

**Security vulnerabilities** should be reported privately. See [SECURITY.md](SECURITY.md) for instructions.

## Proposing Features

1. Open a [GitHub Discussion](https://github.com/alea-institute/alea-intake/discussions) in the "Ideas" category to describe your proposal.
2. Include: the problem you're solving, who benefits, and a rough approach.
3. Wait for feedback before investing significant implementation effort.

For small improvements (typo fixes, documentation clarifications), skip the discussion and open a PR directly.

## Development Setup

### Backend (Python)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install uv
uv sync
pytest
```

### Frontend (React/TypeScript)

```bash
cd frontend
pnpm install
pnpm test:run
pnpm build
```

### Running the Full Stack

```bash
# Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && pnpm dev
```

## Pull Request Process

1. **Branch from `master`:** Create a descriptive branch name.
   - Features: `feat/short-description`
   - Fixes: `fix/short-description`
   - Docs: `docs/short-description`
2. **Write tests** for new functionality. Existing tests must continue to pass.
3. **Follow existing code style.** The backend uses Ruff for linting. The frontend uses TypeScript strict mode.
4. **Keep PRs focused.** One logical change per PR. Split large changes into smaller PRs.
5. **Write a clear PR description** explaining what changed and why.

### Commit Message Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add multilingual consent templates
fix: resolve tenant isolation race condition
docs: update deployment configuration reference
test: add integration tests for CMS sync
refactor: extract encryption context from middleware
```

### Review Expectations

- PRs are reviewed by maintainers. Response time varies but we aim for initial review within one week.
- Be prepared for feedback and iteration. This is normal and collaborative.
- All CI checks must pass before merge.

## Where to Discuss

| Topic | Where |
|-------|-------|
| Bug reports | [GitHub Issues](https://github.com/alea-institute/alea-intake/issues) |
| Feature proposals | [GitHub Discussions](https://github.com/alea-institute/alea-intake/discussions) |
| Design decisions | [GitHub Discussions](https://github.com/alea-institute/alea-intake/discussions) |
| Security vulnerabilities | [SECURITY.md](SECURITY.md) (private reporting) |
| General questions | [GitHub Discussions](https://github.com/alea-institute/alea-intake/discussions) |

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.
