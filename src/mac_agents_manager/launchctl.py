"""LaunchCtl controller for managing services."""
import logging
import subprocess
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


class LaunchCtlController:
    """Handle launchctl operations for services."""

    @staticmethod
    def get_status(service_label: str) -> Dict[str, Any]:
        """Get the status of a service."""
        try:
            # Try to get service info
            result = subprocess.run(
                ['launchctl', 'list', service_label],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Service is loaded
                output = result.stdout

                # Parse PID from output (format: "PID" = 12345;)
                pid = None
                if '"PID" = ' in output:
                    try:
                        pid_line = [line for line in output.split('\n') if '"PID" = ' in line][0]
                        pid = pid_line.split('=')[1].strip().rstrip(';').strip()
                    except (IndexError, ValueError):
                        pid = None

                # Service is running if it has a valid PID
                is_running = pid is not None and pid.isdigit() and int(pid) > 0

                return {
                    'loaded': True,
                    'running': is_running,
                    'pid': pid if is_running else None,
                    'status_code': '0'
                }
            else:
                return {'loaded': False, 'running': False, 'pid': None, 'status_code': None}
        except Exception:
            logger.exception("Error checking service status for %s", service_label)
            return {'loaded': False, 'running': False, 'pid': None, 'error': 'status check failed'}

    @staticmethod
    def load(service_label: str, plist_path: str) -> Tuple[bool, str]:
        """
        Load a service.

        Returns:
            (success, message)
        """
        try:
            result = subprocess.run(
                ['launchctl', 'load', plist_path],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return True, f"Successfully loaded {service_label}"
            else:
                error = result.stderr or result.stdout
                return False, f"Failed to load: {error}"
        except Exception:
            logger.exception("Error loading service %s", service_label)
            return False, "Error loading service"

    @staticmethod
    def unload(service_label: str, plist_path: str) -> Tuple[bool, str]:
        """
        Unload a service.

        Returns:
            (success, message)
        """
        try:
            result = subprocess.run(
                ['launchctl', 'unload', plist_path],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return True, f"Successfully unloaded {service_label}"
            else:
                error = result.stderr or result.stdout
                return False, f"Failed to unload: {error}"
        except Exception:
            logger.exception("Error unloading service %s", service_label)
            return False, "Error unloading service"

    @staticmethod
    def start(service_label: str) -> Tuple[bool, str]:
        """
        Start a service.

        Returns:
            (success, message)
        """
        try:
            result = subprocess.run(
                ['launchctl', 'start', service_label],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return True, f"Successfully started {service_label}"
            else:
                error = result.stderr or result.stdout
                return False, f"Failed to start: {error}"
        except Exception:
            logger.exception("Error starting service %s", service_label)
            return False, "Error starting service"

    @staticmethod
    def stop(service_label: str) -> Tuple[bool, str]:
        """
        Stop a service.

        Returns:
            (success, message)
        """
        try:
            result = subprocess.run(
                ['launchctl', 'stop', service_label],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return True, f"Successfully stopped {service_label}"
            else:
                error = result.stderr or result.stdout
                return False, f"Failed to stop: {error}"
        except Exception:
            logger.exception("Error stopping service %s", service_label)
            return False, "Error stopping service"

    @staticmethod
    def restart(service_label: str, plist_path: str) -> Tuple[bool, str]:
        """
        Restart a service (stop and start).

        Returns:
            (success, message)
        """
        try:
            subprocess.run(['launchctl', 'stop', service_label],
                         capture_output=True, text=True, timeout=10)
            result = subprocess.run(
                ['launchctl', 'start', service_label],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return True, f"Successfully restarted {service_label}"
            else:
                error = result.stderr or result.stdout
                return False, f"Failed to restart: {error}"
        except Exception:
            logger.exception("Error restarting service %s", service_label)
            return False, "Error restarting service"

    @staticmethod
    def kickstart(service_label: str) -> Tuple[bool, str]:
        """
        Restart a service using launchctl kickstart -k (without unloading).
        This is safer for reloading the UI's own agent.
        """
        try:
            uid = subprocess.run(['id', '-u'], capture_output=True, text=True).stdout.strip()
            domain = f"gui/{uid}/{service_label}"
            result = subprocess.run(
                ['launchctl', 'kickstart', '-k', domain],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, f"Successfully restarted {service_label}"
            else:
                error = (result.stderr or result.stdout or '').strip()
                # Some macOS versions emit "label: unnecessary" even when restart is effective
                if 'unnecessary' in error.lower():
                    return True, "Restarted (kickstart reported: unnecessary)"
                return False, f"Failed to restart with kickstart: {error}"
        except Exception:
            logger.exception("Error kickstarting service %s", service_label)
            return False, "Error restarting service"

    @staticmethod
    def bootout(service_label: str) -> Tuple[bool, str]:
        """
        Bootout (remove) a service using newer launchctl syntax.

        Returns:
            (success, message)
        """
        try:
            domain = "gui/" + subprocess.run(['id', '-u'], capture_output=True, text=True).stdout.strip()
            result = subprocess.run(
                ['launchctl', 'bootout', domain + '/' + service_label],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return True, f"Successfully removed {service_label}"
            else:
                # Try unload as fallback
                return False, "Service not loaded or already removed"
        except Exception:
            logger.exception("Error removing service %s", service_label)
            return False, "Error removing service"


