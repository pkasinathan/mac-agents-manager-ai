#!/bin/bash

################################################################################
# Stay Focus - Mac Application Manager
################################################################################
# This script manages Mac applications to help maintain focus during work hours
# Schedule:
#   10:10 AM - Close distracting apps (start deep work)
#   1:00 PM  - Open Slack for lunch break
#   1:10 PM  - Close Slack (back to work)
#   4:00 PM  - Open Slack for afternoon break
#   4:10 PM  - Close Slack (back to work)
#   5:00 PM  - Open all apps (end of workday)
################################################################################

# Get current time in format HHMM (e.g., 1010 for 10:10 AM)
CURRENT_TIME=$(date +%H%M)
CURRENT_HOUR=$(date +%H)
CURRENT_MIN=$(date +%M)

# Log function
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to send macOS notification
send_notification() {
    local title="$1"
    local message="$2"
    local sound="${3:-default}"
    
    osascript -e "display notification \"$message\" with title \"$title\" sound name \"$sound\"" 2>/dev/null
    log_message "📢 Notification: $title - $message"
}

# Function to find application path
find_app_path() {
    local app_name="$1"
    local app_path=""
    
    # Check common locations
    if [ -d "/Applications/${app_name}.app" ]; then
        app_path="/Applications/${app_name}.app"
    elif [ -d "/System/Applications/${app_name}.app" ]; then
        app_path="/System/Applications/${app_name}.app"
    elif [ -d "/Applications/Utilities/${app_name}.app" ]; then
        app_path="/Applications/Utilities/${app_name}.app"
    elif [ -d "/System/Applications/Utilities/${app_name}.app" ]; then
        app_path="/System/Applications/Utilities/${app_name}.app"
    else
        # Try using mdfind to locate the app
        app_path=$(mdfind "kMDItemKind == 'Application' && kMDItemFSName == '${app_name}.app'" 2>/dev/null | head -1)
    fi
    
    echo "$app_path"
}

# Function to check if app is running
is_app_running() {
    local app_name="$1"
    osascript -e "tell application \"System Events\" to (name of processes) contains \"$app_name\"" 2>/dev/null
}

# Function to close an application
close_app() {
    local app_name="$1"
    local app_path=$(find_app_path "$app_name")
    
    if [ -z "$app_path" ]; then
        log_message "✗ $app_name not found on system"
        return 1
    fi
    
    # Check if app is running
    local is_running=$(is_app_running "$app_name")
    if [ "$is_running" != "true" ]; then
        log_message "○ $app_name is not running, skipping"
        return 0
    fi
    
    log_message "Closing $app_name (${app_path})..."
    osascript -e "tell application \"$app_name\" to quit" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        log_message "✓ $app_name closed successfully"
        return 0
    else
        log_message "✗ Failed to close $app_name"
        return 1
    fi
}

# Function to open an application
open_app() {
    local app_name="$1"
    local app_path=$(find_app_path "$app_name")
    
    if [ -z "$app_path" ]; then
        log_message "✗ $app_name not found on system"
        return 1
    fi
    
    # Check if app is already running
    local is_running=$(is_app_running "$app_name")
    if [ "$is_running" == "true" ]; then
        log_message "○ $app_name is already running, bringing to front"
        osascript -e "tell application \"$app_name\" to activate" 2>/dev/null
        return 0
    fi
    
    log_message "Opening $app_name (${app_path})..."
    open -a "$app_path"
    
    if [ $? -eq 0 ]; then
        log_message "✓ $app_name opened successfully"
        return 0
    else
        log_message "✗ Failed to open $app_name"
        return 1
    fi
}

# Function to close all distracting apps
close_distracting_apps() {
    log_message "=== CLOSING DISTRACTING APPS IN 30 SECONDS ==="
    
    # Send warning notification
    send_notification "Stay Focus" "Apps will close in 30 seconds. Please save your work!" "Glass"
    
    # Countdown notifications
    sleep 20
    send_notification "Stay Focus" "Apps closing in 10 seconds..." "Ping"
    
    sleep 10
    log_message "=== NOW CLOSING APPS ==="
    send_notification "Stay Focus" "Closing apps now. Time to focus!" "Hero"
    
    # Social & Communication
    close_app "WhatsApp"
    close_app "Slack"
    
    # Browsers & Productivity
    close_app "Safari"
    
    # Apple System Apps
    close_app "Messages"
    close_app "Notes"
    close_app "Reminders"
    close_app "Find My"
    
    # iPhone Mirroring (macOS Sequoia+)
    close_app "iPhone Mirroring"
    
    log_message "=== ALL DISTRACTING APPS CLOSED ==="
}

# Function to open all apps (end of day)
open_all_apps() {
    log_message "=== OPENING ALL APPS (END OF DAY) ==="
    
    send_notification "Stay Focus" "Work day complete! Opening all apps." "Glass"
    
    # Social & Communication
    open_app "WhatsApp"
    open_app "Slack"
    
    # Browsers & Productivity
    open_app "Safari"
    
    # Apple System Apps
    open_app "Messages"
    open_app "Notes"
    open_app "Reminders"
    open_app "Find My"
    
    # iPhone Mirroring (macOS Sequoia+)
    open_app "iPhone Mirroring"
    
    log_message "=== ALL APPS OPENED ==="
}

# Function to display usage
show_usage() {
    cat << EOF
Usage: $0 [COMMAND] [APP_NAME]

Commands:
  openall              Open all managed apps
  closeall             Close all managed apps (with 30-second warning)
  open <app_name>      Open a specific application
  close <app_name>     Close a specific application
  
  (No arguments)       Run in scheduled mode (checks current time)

Examples:
  $0 openall                    # Open all apps
  $0 closeall                   # Close all apps with warning
  $0 open Safari                # Open Safari
  $0 close Slack                # Close Slack
  $0                            # Run scheduled tasks based on current time

Managed Applications:
  WhatsApp, Slack, Safari, Messages, Notes, 
  Reminders, Find My, iPhone Mirroring

Scheduled Times:
  10:10 AM - Close all apps (start focus time)
  1:00 PM  - Open Slack (lunch break)
  1:10 PM  - Close Slack (back to work)
  4:00 PM  - Open Slack (afternoon break)
  4:10 PM  - Close Slack (back to work)
  5:00 PM  - Open all apps (end of day)
EOF
    exit 0
}

# Main execution logic
log_message "Stay Focus Script Started - Current Time: $(date '+%H:%M')"

# Check if command-line arguments are provided
if [ $# -gt 0 ]; then
    COMMAND="$1"
    APP_NAME="$2"
    
    case "$COMMAND" in
        openall)
            log_message "=== MANUAL COMMAND: Open All Apps ==="
            open_all_apps
            ;;
        closeall)
            log_message "=== MANUAL COMMAND: Close All Apps ==="
            close_distracting_apps
            ;;
        open)
            if [ -z "$APP_NAME" ]; then
                echo "Error: Please specify an app name"
                echo "Usage: $0 open <app_name>"
                exit 1
            fi
            log_message "=== MANUAL COMMAND: Open $APP_NAME ==="
            open_app "$APP_NAME"
            ;;
        close)
            if [ -z "$APP_NAME" ]; then
                echo "Error: Please specify an app name"
                echo "Usage: $0 close <app_name>"
                exit 1
            fi
            log_message "=== MANUAL COMMAND: Close $APP_NAME ==="
            close_app "$APP_NAME"
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            echo "Error: Unknown command '$COMMAND'"
            echo "Run '$0 help' for usage information"
            exit 1
            ;;
    esac
else
    # Scheduled mode - run based on current time
    log_message "=== RUNNING IN SCHEDULED MODE ==="
    
    case "$CURRENT_TIME" in
        1010)
            # 10:10 AM - Close all distracting apps
            close_distracting_apps
            ;;
        1300)
            # 1:00 PM - Open Slack for lunch break
            log_message "=== LUNCH BREAK - Opening Slack ==="
            send_notification "Stay Focus" "Lunch break! Slack is now available." "Submarine"
            open_app "Slack"
            ;;
        1310)
            # 1:10 PM - Close Slack (back to work)
            log_message "=== BACK TO WORK - Closing Slack ==="
            send_notification "Stay Focus" "Break over. Closing Slack in 10 seconds..." "Ping"
            sleep 10
            close_app "Slack"
            send_notification "Stay Focus" "Back to focused work!" "Hero"
            ;;
        1600)
            # 4:00 PM - Open Slack for afternoon break
            log_message "=== AFTERNOON BREAK - Opening Slack ==="
            send_notification "Stay Focus" "Afternoon break! Slack is now available." "Submarine"
            open_app "Slack"
            ;;
        1610)
            # 4:10 PM - Close Slack (back to work)
            log_message "=== BACK TO WORK - Closing Slack ==="
            send_notification "Stay Focus" "Break over. Closing Slack in 10 seconds..." "Ping"
            sleep 10
            close_app "Slack"
            send_notification "Stay Focus" "Back to focused work!" "Hero"
            ;;
        1700)
            # 5:00 PM - Open all apps (end of day)
            open_all_apps
            ;;
        *)
            log_message "No scheduled action for current time ($CURRENT_TIME)"
            log_message "Scheduled times: 10:10, 13:00, 13:10, 16:00, 16:10, 17:00"
            ;;
    esac
fi

log_message "Stay Focus Script Completed"
exit 0

