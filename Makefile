.PHONY: install dev lint format check test build publish clean start stop logs

install:
	pip install .

dev:
	pip install -e ".[dev]"

lint:
	ruff check src/

format:
	ruff format src/ tests/

check: lint test

test:
	pytest tests/

build: clean
	python -m build

publish: build
	twine upload dist/*

clean:
	rm -rf dist/ build/ *.egg-info/ src/*.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

start:
	launchctl load ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist

stop:
	launchctl unload ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist

restart: stop start

logs:
	tail -f /tmp/mac_agents_manager.out

open:
	open http://localhost:8081
