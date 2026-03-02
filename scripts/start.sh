#!/bin/bash
# Start script for Mac Agents Manager

cd "$(dirname "$0")/.."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Use the installed CLI entry point if available, otherwise fall back to module
if command -v mam &> /dev/null; then
    mam
else
    python3 -m mac_agents_manager.cli
fi
