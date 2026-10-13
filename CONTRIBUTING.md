# Contributing to Mac Agents Manager

Thank you for your interest in contributing to Mac Agents Manager! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/pkasinathan/mac-agents-manager-ai/issues) to avoid duplicates.
2. Use the **Bug Report** issue template.
3. Include your macOS version, Python version, and Ollama version (if using AI Chat).
4. Include relevant log output (`/tmp/mac_agents_manager.out`, `/tmp/mac_agents_manager.err`).

### Suggesting Features

1. Open an issue using the **Feature Request** template.
2. Describe the use case and expected behavior.
3. Explain how it fits the tool's local-first, single-user philosophy.

### Submitting Changes

1. Fork the repository and create a branch from `main`.
2. Follow the development setup below.
3. Make your changes with clear, focused commits.
4. Ensure all checks pass (`make check`).
5. Submit a pull request using the PR template.

## Development Setup

```bash
git clone https://github.com/pkasinathan/mac-agents-manager-ai.git
cd mac-agents-manager-ai
make dev
source venv/bin/activate
```

This installs the package in editable mode with all dev dependencies (pytest, ruff).

## Development Workflow

### Running Tests

```bash
make test            # Run test suite
```

### Code Quality

```bash
make lint            # Run ruff linter
make format          # Auto-format with ruff
make check           # All quality checks (lint + test)
```

### Project Structure

```
src/mac_agents_manager/     # Main package
tests/                      # Test suite
examples/                   # Example scripts and agents
```

## Coding Standards

- **Python 3.10+** — Use type hints.
- **Formatting** — Ruff handles formatting. Run `make format` before committing.
- **Line length** — 120 characters max.
- **Imports** — Sorted by ruff (isort rules). First-party imports from `mac_agents_manager`.
- **Logging** — Use `logging.getLogger(__name__)`, never `print()` in library code.
- **Error handling** — Catch specific exceptions. Use bare `except` only for fault-tolerant wrappers.
- **Comments** — Explain *why*, not *what*. Avoid redundant comments.
- **Tests** — Add tests for new functionality. Use `tmp_path` and mocking for system interactions.

## Commit Messages

Use clear, descriptive commit messages:

```
feat: add support for calendar interval agents
fix: prevent duplicate launchctl load on restart
docs: add Ollama troubleshooting section
test: add coverage for chat history cleanup
```

Prefixes: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR.
- Update `CHANGELOG.md` in the appropriate section for the target release.
- Add or update tests for any behavior changes.
- Ensure CI passes before requesting review.
- Reference related issues (e.g., "Fixes #42").

## License

By contributing, you agree that your contributions will be licensed under the [Apache-2.0 License](LICENSE).
