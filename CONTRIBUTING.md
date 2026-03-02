# Contributing to Mac Agents Manager

Thank you for considering contributing! Here's how to get started.

## Reporting Bugs

Open a [GitHub issue](https://github.com/pkasinathan/mac-agents-manager/issues) with:

- macOS version and Python version
- Steps to reproduce
- Expected vs. actual behavior
- Relevant log output (`/tmp/mac_agents_manager.out`, `/tmp/mac_agents_manager.err`)

## Suggesting Features

Open a GitHub issue with the **enhancement** label describing the use case and proposed behavior.

## Development Setup

```bash
git clone https://github.com/pkasinathan/mac-agents-manager.git
cd mac-agents-manager
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Running Checks

```bash
make lint    # ruff check src/
make test    # pytest tests/
```

All pull requests must pass lint and tests before merging.

## Pull Requests

1. Fork the repo and create a feature branch from `main`.
2. Keep changes focused — one feature or fix per PR.
3. Add or update tests for any changed behavior.
4. Run `make lint` and `make test` before submitting.
5. Write a clear PR description explaining **what** and **why**.

## Code Style

- Python code is checked with [Ruff](https://docs.astral.sh/ruff/).
- Follow existing patterns in the codebase.
- Avoid adding comments that merely narrate what the code does.

## License

By contributing, you agree that your contributions will be licensed under the [Apache-2.0 License](LICENSE).
