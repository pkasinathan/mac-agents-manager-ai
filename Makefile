.PHONY: help install dev test lint format check clean build publish start stop restart logs status open

VENV    := venv/bin
PYTHON  := $(VENV)/python
PIP     := $(VENV)/pip
RUFF    := $(VENV)/ruff
PYTEST  := $(VENV)/pytest

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────────────

install: ## Install runtime dependencies
	python3 -m venv venv
	$(PIP) install --upgrade pip -q
	$(PIP) install -e . -q
	@echo "\n✓ Installed. Run: source venv/bin/activate"

dev: install ## Install runtime + dev dependencies
	$(PIP) install -e ".[dev]" -q
	@echo "✓ Dev environment ready"

# ── Quality ──────────────────────────────────────────────────────────────────

lint: ## Run ruff linter
	$(RUFF) check src/mac_agents_manager/ tests/

format: ## Auto-format code with ruff
	$(RUFF) format src/mac_agents_manager/ tests/
	$(RUFF) check --fix src/mac_agents_manager/ tests/

check: lint test ## Run all quality checks (lint + test)
	@echo "\n✓ All checks passed"

# ── Testing ──────────────────────────────────────────────────────────────────

test: ## Run tests
	$(PYTEST)

# ── Build ────────────────────────────────────────────────────────────────────

build: clean ## Build distribution packages
	$(PYTHON) -m build

publish: build ## Publish to PyPI
	$(VENV)/twine upload dist/*

# ── Services ─────────────────────────────────────────────────────────────────

status: ## Show LaunchAgent status
	@launchctl list | grep mac_agents_manager || echo "Not loaded"

start: ## Start the LaunchAgent
	launchctl load ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist

stop: ## Stop the LaunchAgent
	launchctl unload ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist

restart: stop start ## Restart the LaunchAgent

logs: ## Tail LaunchAgent logs
	tail -f /tmp/mac_agents_manager.out

open: ## Open dashboard in browser
	open http://localhost:8081

# ── Housekeeping ─────────────────────────────────────────────────────────────

clean: ## Remove build/cache artifacts
	rm -rf build/ dist/ *.egg-info/ src/*.egg-info/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned"
