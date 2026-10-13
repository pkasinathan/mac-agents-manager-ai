#!/bin/bash

# Mac Agents Manager Installation Script

echo "=========================================="
echo "  Mac Agents Manager Installation"
echo "=========================================="
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
# Remove stale venv if it contains old absolute paths
if [ -d "venv" ]; then
    echo "Removing existing virtual environment (stale paths)..."
    rm -rf venv
fi
python3 -m venv venv
if [ $? -eq 0 ]; then
    echo "✓ Virtual environment created"
else
    echo "❌ Error creating virtual environment"
    exit 1
fi

# Install the package (editable mode for dev, includes Flask dependency)
echo "Installing mac-agents-manager-ai..."
source venv/bin/activate
pip install -e . --quiet
if [ $? -eq 0 ]; then
    echo "✓ Package installed successfully"
else
    echo "❌ Error installing package"
    exit 1
fi
deactivate

# Make the start script executable
chmod +x scripts/start.sh
echo "✓ Start script is executable"

# Check if LaunchAgent already exists
LAUNCH_AGENT="$HOME/Library/LaunchAgents/user.productivity.mac_agents_manager.plist"

if [ -f "$LAUNCH_AGENT" ]; then
    echo ""
    echo "⚠️  LaunchAgent already exists. Unloading existing service..."
    launchctl unload "$LAUNCH_AGENT" 2>/dev/null
fi

# Generate the LaunchAgent plist dynamically for this user and path
echo "Generating LaunchAgent plist..."
LABEL="user.productivity.mac_agents_manager"

# Build environment variables for launchd (avoid venv paths)
USER_NAME="${USER:-$(whoami)}"
HOME_DIR="${HOME:-/Users/${USER_NAME}}"
PATH_VAR="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"
if [ -d "$HOME_DIR/.pyenv/shims" ]; then
    PATH_VAR="$PATH_VAR:$HOME_DIR/.pyenv/shims"
fi
cat > "$LAUNCH_AGENT" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_DIR}/scripts/start.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>${HOME_DIR}</string>
        <key>PATH</key>
        <string>${PATH_VAR}</string>
        <key>USER</key>
        <string>${USER_NAME}</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/mac_agents_manager.out</string>
    <key>StandardErrorPath</key>
    <string>/tmp/mac_agents_manager.err</string>
    <key>Description</key>
    <string>Mac Agents Manager web interface</string>
</dict>
</plist>
PLIST

chmod 644 "$LAUNCH_AGENT"
echo "✓ LaunchAgent plist written to ~/Library/LaunchAgents/"

# Load the LaunchAgent
echo ""
echo "Loading LaunchAgent..."
launchctl load "$LAUNCH_AGENT"

if [ $? -eq 0 ]; then
    echo "✓ LaunchAgent loaded successfully"
else
    echo "❌ Error loading LaunchAgent"
    exit 1
fi

# Wait a moment for the service to start
echo ""
echo "Starting Mac Agents Manager..."
sleep 2

# Try to detect the port (check logs)
if [ -f "/tmp/mac_agents_manager.out" ]; then
    PORT=$(grep "Mac Agents Manager starting" /tmp/mac_agents_manager.out | grep -o "http://localhost:[0-9]*" | grep -o "[0-9]*$" | tail -1)
else
    PORT=8081
fi

if [ -z "$PORT" ]; then
    PORT=8081
fi

echo ""
echo "=========================================="
echo "  🎬 Installation Complete!"
echo "=========================================="
echo ""
echo "Mac Agents Manager is now running at:"
echo ""
echo "    http://localhost:$PORT"
echo ""
echo "To view logs:"
echo "    tail -f /tmp/mac_agents_manager.out"
echo "    tail -f /tmp/mac_agents_manager.err"
echo ""
echo "To stop the service:"
echo "    launchctl unload ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist"
echo ""
echo "To start the service:"
echo "    launchctl load ~/Library/LaunchAgents/user.productivity.mac_agents_manager.plist"
echo ""
echo "=========================================="

