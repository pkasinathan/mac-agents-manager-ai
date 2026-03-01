#!/bin/bash

################################################################################
# Automation Services Manager
################################################################################
#
# PURPOSE:
#   General-purpose manager for macOS LaunchAgent automation services.
#   Auto-discovers services from config/ directory and manages them.
#
# FEATURES:
#   - Auto-discover services from config/*.plist files
#   - Interactive service selection menu
#   - Manage single or multiple services
#   - Install/start/stop/restart/status/logs/uninstall operations
#
# USAGE:
#   ./manage_services.sh list                    - List all services
#   ./manage_services.sh install [service|all]   - Install service(s)
#   ./manage_services.sh start [service|all]     - Start service(s)
#   ./manage_services.sh stop [service|all]      - Stop service(s)
#   ./manage_services.sh restart [service|all]   - Restart service(s)
#   ./manage_services.sh status [service|all]    - Check status
#   ./manage_services.sh logs <service>          - View logs
#   ./manage_services.sh uninstall [service|all] - Remove service(s)
#
# NAMING CONVENTION:
#   - Plist templates: config/user.automation.{name}.plist
#   - Scripts: scripts/{name}.sh
#   - Logs: /tmp/{name}.out, /tmp/{name}.log
#
# EXAMPLES:
#   ./manage_services.sh install               # Interactive menu
#   ./manage_services.sh install stay_focus    # Install single service
#   ./manage_services.sh install all           # Install all services
#   ./manage_services.sh start stay_focus,another  # Multiple services
#
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
CONFIG_DIR="$PROJECT_ROOT/config"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
LOGS_DIR="/tmp"

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_header() {
    echo -e "${CYAN}$1${NC}"
}

# Function to discover available services
discover_services() {
    local services=()
    
    # Find all user.automation.*.plist files in config/
    for plist in "$CONFIG_DIR"/user.automation.*.plist; do
        if [ -f "$plist" ]; then
            # Extract service name from filename
            local filename=$(basename "$plist")
            local service_name="${filename#user.automation.}"
            service_name="${service_name%.plist}"
            
            # Verify corresponding script exists
            if [ -f "$SCRIPTS_DIR/${service_name}.sh" ]; then
                services+=("$service_name")
            else
                print_warning "Service '$service_name' has plist but missing script: $SCRIPTS_DIR/${service_name}.sh"
            fi
        fi
    done
    
    echo "${services[@]}"
}

# Function to get service configuration
get_service_config() {
    local service_name="$1"
    local config_type="$2"
    
    case "$config_type" in
        plist_template)
            echo "$CONFIG_DIR/user.automation.${service_name}.plist"
            ;;
        plist_installed)
            echo "$LAUNCH_AGENTS_DIR/user.automation.${service_name}.plist"
            ;;
        script)
            echo "$SCRIPTS_DIR/${service_name}.sh"
            ;;
        label)
            echo "user.automation.${service_name}"
            ;;
        log_out)
            echo "$LOGS_DIR/${service_name}.out"
            ;;
        log_err)
            echo "$LOGS_DIR/${service_name}.log"
            ;;
    esac
}

# Function to check if service is loaded
is_service_loaded() {
    local service_name="$1"
    local label=$(get_service_config "$service_name" "label")
    launchctl list | grep -q "$label"
}

# Function to display interactive service menu
show_service_menu() {
    local action="$1"
    local services=($(discover_services))
    
    if [ ${#services[@]} -eq 0 ]; then
        print_error "No services found in $CONFIG_DIR" >&2
        return 1
    fi
    
    # Print menu to stderr so it's visible to user (not captured by command substitution)
    echo "" >&2
    echo -e "${CYAN}Available Services:${NC}" >&2
    echo "" >&2
    
    local i=1
    for service in "${services[@]}"; do
        echo "  $i) $service" >&2
        ((i++))
    done
    echo "  $i) All services" >&2
    echo "" >&2
    
    # Prompt on stderr (read from stdin normally, output to stderr)
    echo -n "Select service(s) to $action (number, comma-separated, or 'all'): " >&2
    read selection
    
    # Parse selection
    local selected=()
    
    if [[ "$selection" == "all" ]] || [[ "$selection" == "$i" ]]; then
        selected=("${services[@]}")
    else
        IFS=',' read -ra NUMBERS <<< "$selection"
        for num in "${NUMBERS[@]}"; do
            num=$(echo "$num" | xargs) # trim whitespace
            if [[ "$num" =~ ^[0-9]+$ ]] && [ "$num" -ge 1 ] && [ "$num" -le "${#services[@]}" ]; then
                selected+=("${services[$((num-1))]}")
            else
                echo -e "${YELLOW}⚠${NC} Invalid selection: $num" >&2
            fi
        done
    fi
    
    if [ ${#selected[@]} -eq 0 ]; then
        echo -e "${RED}✗${NC} No valid services selected" >&2
        return 1
    fi
    
    # Only output the selected services to stdout (for capture)
    echo "${selected[@]}"
}

# Function to parse service arguments
parse_service_args() {
    local arg="$1"
    local services=($(discover_services))
    local selected=()
    
    if [ -z "$arg" ]; then
        # No argument - return empty to trigger interactive mode
        echo ""
        return
    fi
    
    if [[ "$arg" == "all" ]]; then
        selected=("${services[@]}")
    elif [[ "$arg" == *","* ]]; then
        # Comma-separated list
        IFS=',' read -ra SERVICE_LIST <<< "$arg"
        for service in "${SERVICE_LIST[@]}"; do
            service=$(echo "$service" | xargs) # trim whitespace
            if [[ " ${services[@]} " =~ " ${service} " ]]; then
                selected+=("$service")
            else
                print_warning "Unknown service: $service"
            fi
        done
    else
        # Single service
        if [[ " ${services[@]} " =~ " ${arg} " ]]; then
            selected+=("$arg")
        else
            print_error "Unknown service: $arg"
            print_info "Available services: ${services[*]}"
            return 1
        fi
    fi
    
    echo "${selected[@]}"
}

# Function to list all services
list_services() {
    local services=($(discover_services))
    
    echo ""
    echo "================================================"
    echo "  Available Automation Services"
    echo "================================================"
    echo ""
    
    if [ ${#services[@]} -eq 0 ]; then
        print_warning "No services found"
        print_info "Add services by creating:"
        echo "  - config/user.automation.{name}.plist"
        echo "  - scripts/{name}.sh"
        echo ""
        return
    fi
    
    for service in "${services[@]}"; do
        local label=$(get_service_config "$service" "label")
        local script=$(get_service_config "$service" "script")
        
        if is_service_loaded "$service"; then
            print_success "$service (loaded)"
        else
            echo -e "  ${CYAN}○${NC} $service (not loaded)"
        fi
        
        print_info "  Script: $script"
        print_info "  Label: $label"
        echo ""
    done
}

# Function to install a single service
install_single_service() {
    local service_name="$1"
    local plist_template=$(get_service_config "$service_name" "plist_template")
    local plist_installed=$(get_service_config "$service_name" "plist_installed")
    local script=$(get_service_config "$service_name" "script")
    local label=$(get_service_config "$service_name" "label")
    
    print_info "Installing service: $service_name"
    
    # Verify script exists and is executable
    if [ ! -f "$script" ]; then
        print_error "Script not found: $script"
        return 1
    fi
    
    if [ ! -x "$script" ]; then
        print_info "Making script executable..."
        chmod +x "$script"
    fi
    
    # Process plist template
    if [ ! -f "$plist_template" ]; then
        print_error "Plist template not found: $plist_template"
        return 1
    fi
    
    # Replace placeholders and install
    sed -e "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" \
        -e "s|{{HOME}}|$HOME|g" \
        "$plist_template" > "$plist_installed"
    
    if [ $? -ne 0 ]; then
        print_error "Failed to process plist template"
        return 1
    fi
    
    # Load service
    if launchctl load "$plist_installed" 2>&1 | grep -q "already loaded"; then
        print_warning "Service already loaded"
    else
        print_success "Service installed and loaded"
    fi
    
    return 0
}

# Function to install services
install_services() {
    local service_arg="$1"
    local services=()
    
    # Parse service argument or show interactive menu
    if [ -z "$service_arg" ]; then
        services=($(show_service_menu "install"))
        if [ $? -ne 0 ]; then
            return 1
        fi
    else
        services=($(parse_service_args "$service_arg"))
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi
    
    if [ ${#services[@]} -eq 0 ]; then
        print_error "No services to install"
        return 1
    fi
    
    echo ""
    echo "================================================"
    echo "  Installing Services"
    echo "================================================"
    echo ""
    
    # Create LaunchAgents directory if needed
    if [ ! -d "$LAUNCH_AGENTS_DIR" ]; then
        mkdir -p "$LAUNCH_AGENTS_DIR"
        print_info "Created $LAUNCH_AGENTS_DIR"
    fi
    
    # Install each service
    local success_count=0
    local fail_count=0
    
    for service in "${services[@]}"; do
        if install_single_service "$service"; then
            ((success_count++))
        else
            ((fail_count++))
        fi
    done
    
    echo ""
    print_info "Installation complete: $success_count succeeded, $fail_count failed"
    echo ""
}

# Function to start a single service
start_single_service() {
    local service_name="$1"
    local plist_installed=$(get_service_config "$service_name" "plist_installed")
    local label=$(get_service_config "$service_name" "label")
    
    if [ ! -f "$plist_installed" ]; then
        print_warning "Service not installed: $service_name"
        return 1
    fi
    
    if is_service_loaded "$service_name"; then
        print_warning "Service already running: $service_name"
        return 0
    fi
    
    launchctl load "$plist_installed" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Started: $service_name"
        return 0
    else
        print_error "Failed to start: $service_name"
        return 1
    fi
}

# Function to start services
start_services() {
    local service_arg="$1"
    local services=()
    
    if [ -z "$service_arg" ]; then
        services=($(show_service_menu "start"))
        if [ $? -ne 0 ]; then
            return 1
        fi
    else
        services=($(parse_service_args "$service_arg"))
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi
    
    echo ""
    echo "================================================"
    echo "  Starting Services"
    echo "================================================"
    echo ""
    
    for service in "${services[@]}"; do
        start_single_service "$service"
    done
    
    echo ""
}

# Function to stop a single service
stop_single_service() {
    local service_name="$1"
    local plist_installed=$(get_service_config "$service_name" "plist_installed")
    
    if [ ! -f "$plist_installed" ]; then
        print_warning "Service not installed: $service_name"
        return 1
    fi
    
    if ! is_service_loaded "$service_name"; then
        print_warning "Service not running: $service_name"
        return 0
    fi
    
    launchctl unload "$plist_installed" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "Stopped: $service_name"
        return 0
    else
        print_error "Failed to stop: $service_name"
        return 1
    fi
}

# Function to stop services
stop_services() {
    local service_arg="$1"
    local services=()
    
    if [ -z "$service_arg" ]; then
        services=($(show_service_menu "stop"))
        if [ $? -ne 0 ]; then
            return 1
        fi
    else
        services=($(parse_service_args "$service_arg"))
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi
    
    echo ""
    echo "================================================"
    echo "  Stopping Services"
    echo "================================================"
    echo ""
    
    for service in "${services[@]}"; do
        stop_single_service "$service"
    done
    
    echo ""
}

# Function to restart services
restart_services() {
    local service_arg="$1"
    
    stop_services "$service_arg"
    sleep 2
    start_services "$service_arg"
}

# Function to check status of a single service
status_single_service() {
    local service_name="$1"
    local label=$(get_service_config "$service_name" "label")
    local log_out=$(get_service_config "$service_name" "log_out")
    local log_err=$(get_service_config "$service_name" "log_err")
    
    echo ""
    print_header "Service: $service_name"
    echo "  Label: $label"
    
    if is_service_loaded "$service_name"; then
        print_success "Status: Loaded"
        
        # Get detailed status
        SERVICE_INFO=$(launchctl list "$label" 2>/dev/null)
        if [ $? -eq 0 ]; then
            PID=$(echo "$SERVICE_INFO" | grep "PID" | awk '{print $3}')
            EXIT_STATUS=$(echo "$SERVICE_INFO" | grep "LastExitStatus" | awk '{print $3}')
            
            if [ -n "$PID" ] && [ "$PID" != "-" ] && [ "$PID" != "0" ]; then
                print_info "  Currently running: PID $PID"
            else
                print_info "  Scheduled (waiting for next run time)"
            fi
            
            if [ -n "$EXIT_STATUS" ] && [ "$EXIT_STATUS" != "0" ]; then
                print_warning "  Last exit status: $EXIT_STATUS"
            fi
        fi
    else
        print_error "Status: Not loaded"
    fi
    
    echo "  Logs: $log_out, $log_err"
}

# Function to check status of services
check_status() {
    local service_arg="$1"
    local services=()
    
    if [ -z "$service_arg" ]; then
        # Show all services if no argument
        services=($(discover_services))
    else
        services=($(parse_service_args "$service_arg"))
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi
    
    echo ""
    echo "================================================"
    echo "  Service Status"
    echo "================================================"
    
    for service in "${services[@]}"; do
        status_single_service "$service"
    done
    
    echo ""
}

# Function to view logs
view_logs() {
    local service_name="$1"
    
    if [ -z "$service_name" ]; then
        print_error "Please specify a service name"
        print_info "Usage: $0 logs <service_name>"
        return 1
    fi
    
    local services=($(discover_services))
    if [[ ! " ${services[@]} " =~ " ${service_name} " ]]; then
        print_error "Unknown service: $service_name"
        return 1
    fi
    
    local log_out=$(get_service_config "$service_name" "log_out")
    local log_err=$(get_service_config "$service_name" "log_err")
    
    echo ""
    echo "================================================"
    echo "  Viewing Logs: $service_name"
    echo "================================================"
    echo ""
    
    print_info "Press Ctrl+C to exit log view"
    echo ""
    
    if [ ! -f "$log_out" ] && [ ! -f "$log_err" ]; then
        print_warning "Log files not found yet. Service may not have run."
        print_info "Logs will be created at:"
        echo "  - $log_out"
        echo "  - $log_err"
        return
    fi
    
    # Tail both log files if they exist
    if [ -f "$log_out" ] && [ -f "$log_err" ]; then
        tail -f "$log_out" "$log_err" 2>/dev/null
    elif [ -f "$log_out" ]; then
        tail -f "$log_out" 2>/dev/null
    elif [ -f "$log_err" ]; then
        tail -f "$log_err" 2>/dev/null
    fi
}

# Function to uninstall a single service
uninstall_single_service() {
    local service_name="$1"
    local plist_installed=$(get_service_config "$service_name" "plist_installed")
    
    if [ ! -f "$plist_installed" ]; then
        print_warning "Service not installed: $service_name"
        return 0
    fi
    
    # Unload if loaded
    if is_service_loaded "$service_name"; then
        launchctl unload "$plist_installed" 2>/dev/null
    fi
    
    # Remove plist
    rm -f "$plist_installed"
    print_success "Uninstalled: $service_name"
    
    return 0
}

# Function to uninstall services
uninstall_services() {
    local service_arg="$1"
    local services=()
    
    if [ -z "$service_arg" ]; then
        services=($(show_service_menu "uninstall"))
        if [ $? -ne 0 ]; then
            return 1
        fi
    else
        services=($(parse_service_args "$service_arg"))
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi
    
    echo ""
    echo "================================================"
    echo "  Uninstalling Services"
    echo "================================================"
    echo ""
    
    for service in "${services[@]}"; do
        uninstall_single_service "$service"
    done
    
    echo ""
    print_info "Log files preserved in: $LOGS_DIR"
    echo ""
}

# Main command handler
case "${1:-}" in
    list)
        list_services
        ;;
    install)
        install_services "$2"
        ;;
    start)
        start_services "$2"
        ;;
    stop)
        stop_services "$2"
        ;;
    restart)
        restart_services "$2"
        ;;
    status)
        check_status "$2"
        ;;
    logs)
        view_logs "$2"
        ;;
    uninstall)
        uninstall_services "$2"
        ;;
    *)
        echo ""
        echo "Automation Services Manager"
        echo ""
        echo "Usage: $0 {list|install|start|stop|restart|status|logs|uninstall} [service|all]"
        echo ""
        echo "Commands:"
        echo "  list                           - List all available services"
        echo "  install [service|all]          - Install service(s)"
        echo "  start [service|all]            - Start service(s)"
        echo "  stop [service|all]             - Stop service(s)"
        echo "  restart [service|all]          - Restart service(s)"
        echo "  status [service|all]           - Check service status"
        echo "  logs <service>                 - View service logs (live tail)"
        echo "  uninstall [service|all]        - Remove service(s)"
        echo ""
        echo "Service Selection:"
        echo "  - No argument: help"
        echo "  - 'all': All services"
        echo "  - 'service1,service2': Multiple services (comma-separated)"
        echo "  - 'service': Single service"
        echo ""
        echo "Examples:"
        echo "  $0 list                        # Show all services"
        echo "  $0 install                     # Interactive install"
        echo "  $0 install stay_focus          # Install single service"
        echo "  $0 install all                 # Install all services"
        echo "  $0 start stay_focus,backup     # Start multiple services"
        echo "  $0 status                      # Show status of all services"
        echo "  $0 logs stay_focus             # View logs"
        echo ""
        exit 1
        ;;
esac

exit 0
