"""Models for parsing and generating LaunchAgent/LaunchDaemon plist files."""
import logging
import os
import plistlib
import re
import shlex
import subprocess
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ALLOWED_LOG_DIRS = ('/tmp/', '/private/tmp/', '/var/log/', '/private/var/log/',
                    '/var/folders/', '/private/var/folders/')

LABEL_RE = re.compile(r'^[a-zA-Z0-9._-]+$')
MAX_LABEL_LEN = 128


class LaunchService:
    """Represents a LaunchAgent service."""

    AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"

    def __init__(self, label: str, service_type: str = "agent"):
        self.label = label
        self.service_type = "agent"  # Always agent
        self.data = {}

    @staticmethod
    def _validate_label(label: str) -> None:
        """Reject labels that could escape AGENTS_DIR or contain shell metacharacters."""
        if not label or len(label) > MAX_LABEL_LEN:
            raise ValueError("Invalid label length")
        if not LABEL_RE.match(label):
            raise ValueError("Label contains invalid characters")
        if '..' in label:
            raise ValueError("Label must not contain '..'")

    @property
    def file_path(self) -> Path:
        """Get the full path to the plist file, validated against path traversal."""
        resolved = (self.AGENTS_DIR / f"{self.label}.plist").resolve()
        if not str(resolved).startswith(str(self.AGENTS_DIR.resolve()) + os.sep):
            raise ValueError("Invalid label: path escapes agents directory")
        return resolved

    @property
    def service_id(self) -> str:
        """Get a unique service ID."""
        return f"{self.service_type}:{self.label}"

    @property
    def name(self) -> str:
        """Get a friendly name from the label."""
        # Extract name from last label segment, e.g. user.productivity.myservice -> myservice
        parts = self.label.split('.')
        return parts[-1] if parts else self.label

    @classmethod
    def from_service_id(cls, service_id: str) -> 'LaunchService':
        """Create a LaunchService from a service_id (type:label)."""
        if ':' not in service_id:
            raise ValueError("Invalid service_id format")
        service_type, label = service_id.split(':', 1)
        cls._validate_label(label)
        return cls(label, service_type)

    @classmethod
    def from_file(cls, file_path: Path) -> Optional['LaunchService']:
        """Load a LaunchService from a plist file."""
        try:
            with open(file_path, 'rb') as f:
                data = plistlib.load(f)

            label = data.get('Label', file_path.stem)
            cls._validate_label(label)
            service = cls(label, "agent")
            service.data = data
            return service
        except Exception:
            logger.exception("Error loading %s", file_path)
            return None

    @classmethod
    def list_all(cls) -> List['LaunchService']:
        """List all LaunchAgents."""
        services = []

        # Load LaunchAgents
        if cls.AGENTS_DIR.exists():
            for plist_file in cls.AGENTS_DIR.glob("*.plist"):
                service = cls.from_file(plist_file)
                if service:
                    services.append(service)

        return sorted(services, key=lambda s: s.label)

    DEFAULT_LABEL_PREFIXES = ('user.', 'com.user.')

    @classmethod
    def list_user_services(cls) -> List['LaunchService']:
        """List only user-created services matching known label prefixes.

        Extra prefixes can be added via the MAM_LABEL_PREFIXES env var
        (comma-separated, e.g. "com.myorg.,com.acme.").
        """
        prefixes = list(cls.DEFAULT_LABEL_PREFIXES)
        extra = os.environ.get('MAM_LABEL_PREFIXES', '')
        if extra:
            prefixes.extend(p.strip() for p in extra.split(',') if p.strip())
        all_services = cls.list_all()
        return [s for s in all_services if
                any(s.label.startswith(p) for p in prefixes)]

    @classmethod
    def get_services_tree(cls) -> Dict[str, Any]:
        """
        Get services organized in a tree structure by schedule type and namespace.

        Returns:
            {
                'scheduled': {
                    'automation': [service1, service2],
                    'finance': [service3, service4]
                },
                'keepalive': {
                    'productivity': [service5, service6]
                }
            }
        """
        services = cls.list_user_services()

        tree = {
            'scheduled': {},
            'keepalive': {}
        }

        for service in services:
            # Extract namespace from label
            parts = service.label.split('.')
            if len(parts) >= 2 and parts[0] == 'user':
                # user.productivity.chronometry-menubar -> productivity
                namespace = parts[1]  # e.g., 'productivity', 'finance', 'youtube'
            elif len(parts) >= 3 and parts[0] == 'com':
                # com.chronometry.myapp -> chronometry
                namespace = parts[1]  # e.g., 'chronometry', 'user'
            else:
                namespace = 'other'

            # Determine schedule type
            schedule_type = service.get_schedule_type()
            if schedule_type == 'scheduled':
                if namespace not in tree['scheduled']:
                    tree['scheduled'][namespace] = []
                tree['scheduled'][namespace].append(service)
            else:
                # Default to keepalive for unknown types
                if namespace not in tree['keepalive']:
                    tree['keepalive'][namespace] = []
                tree['keepalive'][namespace].append(service)

        # Sort services within each namespace
        for namespace in tree['scheduled']:
            tree['scheduled'][namespace].sort(key=lambda s: s.name)
        for namespace in tree['keepalive']:
            tree['keepalive'][namespace].sort(key=lambda s: s.name)

        return tree

    @property
    def namespace(self) -> str:
        """Get the namespace from the label."""
        parts = self.label.split('.')
        if len(parts) >= 2 and parts[0] == 'user':
            # user.productivity.service -> productivity
            return parts[1]
        elif len(parts) >= 3 and parts[0] == 'com':
            # com.chronometry.service -> chronometry
            return parts[1]
        return 'other'

    def save(self) -> bool:
        """Save the service to a plist file."""
        try:
            # Ensure directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write plist
            with open(self.file_path, 'wb') as f:
                plistlib.dump(self.data, f, sort_keys=False)
            return True
        except Exception:
            logger.exception("Error saving %s", self.file_path)
            return False

    def delete(self) -> bool:
        """Delete the plist file."""
        try:
            if self.file_path.exists():
                self.file_path.unlink()
            return True
        except Exception:
            logger.exception("Error deleting %s", self.file_path)
            return False

    def get_program(self) -> str:
        """Get the program/script that this service runs."""
        args = self.data.get('ProgramArguments', [])
        if args:
            # Return all arguments joined with space
            return ' '.join(args)
        return self.data.get('Program', '')

    def get_schedule_type(self) -> str:
        """Get the schedule type: 'keepalive' or 'scheduled'."""
        if self.data.get('KeepAlive'):
            return 'keepalive'
        elif self.data.get('StartCalendarInterval'):
            return 'scheduled'
        return 'unknown'

    def get_schedule_times(self) -> List[Dict[str, int]]:
        """Get scheduled times if this is a scheduled service."""
        intervals = self.data.get('StartCalendarInterval', [])
        if isinstance(intervals, dict):
            # Single interval
            return [intervals]
        return intervals

    def get_log_paths(self) -> Dict[str, str]:
        """Get stdout and stderr log paths."""
        return {
            'stdout': self.data.get('StandardOutPath', ''),
            'stderr': self.data.get('StandardErrorPath', '')
        }

    def get_working_directory(self) -> str:
        """Get the working directory."""
        return self.data.get('WorkingDirectory', '')

    def get_environment(self) -> Dict[str, str]:
        """Get environment variables."""
        return self.data.get('EnvironmentVariables', {})

    def to_dict(self) -> Dict[str, Any]:
        """Convert service to dictionary for JSON API."""
        return {
            'service_id': self.service_id,
            'label': self.label,
            'name': self.name,
            'namespace': self.namespace,
            'service_type': self.service_type,
            'program': self.get_program(),
            'schedule_type': self.get_schedule_type(),
            'schedule_times': self.get_schedule_times(),
            'working_directory': self.get_working_directory(),
            'environment': self.get_environment(),
            'log_paths': self.get_log_paths(),
            'plist_xml': self.get_plist_xml(),
            'port': self.get_port()
        }

    def get_port(self) -> Optional[int]:
        """
        Dynamically detect the port this service runs on.
        Uses multiple strategies in order of reliability:
        1. Check running process with lsof
        2. Parse plist Description field
        3. Parse stdout logs for port mentions
        4. Parse environment variables
        5. Parse command arguments
        """
        # Strategy 1: Check if process is running and listening on a port
        port = self._detect_port_from_process()
        if port:
            return port

        # Strategy 2: Parse plist Description field
        port = self._detect_port_from_description()
        if port:
            return port

        # Strategy 3: Parse logs
        port = self._detect_port_from_logs()
        if port:
            return port

        # Strategy 4: Parse environment variables
        port = self._detect_port_from_env()
        if port:
            return port

        # Strategy 5: Parse command arguments
        port = self._detect_port_from_args()
        if port:
            return port

        return None

    def _detect_port_from_process(self) -> Optional[int]:
        """Detect port by checking what the running process is listening on."""
        try:
            # Get PID of the service if it's running
            result = subprocess.run(
                ['launchctl', 'list'],
                capture_output=True,
                text=True,
                timeout=2
            )

            pid = None
            for line in result.stdout.splitlines():
                if self.label in line:
                    parts = line.split()
                    if parts and parts[0].isdigit():
                        pid = parts[0]
                        break

            if not pid or pid == '-':
                return None

            # Use lsof to find listening ports for this PID
            result = subprocess.run(
                ['/usr/sbin/lsof', '-Pan', '-p', pid, '-iTCP', '-sTCP:LISTEN'],
                capture_output=True,
                text=True,
                timeout=2
            )

            # Parse lsof output to extract port
            for line in result.stdout.splitlines():
                if 'LISTEN' in line:
                    # Example: python3 1234 user 5u IPv4 0x123 TCP *:8051 (LISTEN)
                    parts = line.split()
                    for part in parts:
                        if ':' in part and part.split(':')[-1].isdigit():
                            port_str = part.split(':')[-1]
                            return int(port_str)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError):
            pass

        return None

    def _detect_port_from_description(self) -> Optional[int]:
        """Parse port number from plist Description field."""
        description = self.data.get('Description', '')
        if description:
            # Look for patterns like "port 8053", "port:8053", "PORT=8053"
            match = re.search(r'port[:\s=]+(\d+)', description, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _detect_port_from_logs(self) -> Optional[int]:
        """Parse port number from stdout logs."""
        log_paths = self.get_log_paths()
        stdout_path = log_paths.get('stdout', '')

        if not stdout_path:
            return None
        resolved = str(Path(stdout_path).resolve())
        if not any(resolved.startswith(d) for d in ALLOWED_LOG_DIRS):
            return None

        if Path(resolved).exists():
            try:
                with open(resolved, 'r') as f:
                    lines = deque(f, maxlen=50)
                    log_content = ''.join(lines)

                # Look for common patterns in logs
                patterns = [
                    r'listening on port[:\s]+(\d+)',
                    r'started on port[:\s]+(\d+)',
                    r'running on port[:\s]+(\d+)',
                    r'server (?:listening|running) (?:on|at)[:\s]+(?:localhost:)?(\d+)',
                    r'http://[^:]+:(\d+)',
                    r'port[:\s=]+(\d+)',
                ]

                for pattern in patterns:
                    match = re.search(pattern, log_content, re.IGNORECASE)
                    if match:
                        port = int(match.group(1))
                        # Sanity check: port should be in valid range
                        if 1024 <= port <= 65535:
                            return port
            except (IOError, ValueError):
                pass

        return None

    def _detect_port_from_env(self) -> Optional[int]:
        """Parse port from environment variables."""
        env = self.get_environment()

        # Check common port-related environment variable names
        port_keys = ['PORT', 'HTTP_PORT', 'SERVER_PORT', 'APP_PORT', 'WEB_PORT']
        for key in port_keys:
            if key in env:
                try:
                    return int(env[key])
                except ValueError:
                    pass

        return None

    def _detect_port_from_args(self) -> Optional[int]:
        """Parse port from command line arguments."""
        program = self.get_program()

        # Look for common port argument patterns
        patterns = [
            r'--port[=\s]+(\d+)',
            r'-p\s+(\d+)',
            r'--http-port[=\s]+(\d+)',
            r'port=(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, program, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return None

    def get_plist_xml(self) -> str:
        """Get the plist data as XML string."""
        try:
            return plistlib.dumps(self.data, sort_keys=False).decode('utf-8')
        except Exception:
            logger.exception("Error generating plist XML for %s", self.label)
            return "Error generating XML"

    @classmethod
    def create_from_form(cls, form_data: Dict[str, Any]) -> 'LaunchService':
        """Create a new LaunchService from form data."""
        name = form_data.get('name', '').strip()
        category = form_data.get('category', 'other').strip()

        name_re = re.compile(r'^[a-zA-Z0-9_-]+$')
        if not name or not name_re.match(name):
            raise ValueError("Name must contain only alphanumerics, hyphens, or underscores")
        if not category or not name_re.match(category):
            raise ValueError("Category must contain only alphanumerics, hyphens, or underscores")
        if len(name) > 64 or len(category) > 64:
            raise ValueError("Name and category must be 64 characters or fewer")

        label = f"user.{category}.{name}"
        cls._validate_label(label)

        service = cls(label, "agent")

        # Build plist data
        plist_data = {
            'Label': label,
            'ProgramArguments': cls._build_program_arguments(form_data),
            'RunAtLoad': True,
        }

        # Add working directory if provided (don't auto-detect if empty)
        working_dir = form_data.get('working_directory', '').strip()
        if working_dir:
            plist_data['WorkingDirectory'] = working_dir

        # Add environment variables if provided
        env_vars = cls._parse_environment(form_data.get('environment', ''))
        if env_vars:
            plist_data['EnvironmentVariables'] = env_vars

        # Add schedule
        schedule_type = form_data.get('schedule_type', 'keepalive')
        if schedule_type == 'keepalive':
            plist_data['KeepAlive'] = True
        elif schedule_type == 'scheduled':
            intervals = cls._parse_schedule_intervals(form_data)
            if intervals:
                plist_data['StartCalendarInterval'] = intervals

        # Auto-generate log paths using full label for uniqueness
        plist_data['StandardOutPath'] = f"/tmp/{label}.out"
        plist_data['StandardErrorPath'] = f"/tmp/{label}.err"

        service.data = plist_data
        return service

    @staticmethod
    def _build_program_arguments(form_data: Dict[str, Any]) -> List[str]:
        """Build the ProgramArguments array from form data."""
        script_path = form_data.get('script_path', '').strip()

        if not script_path:
            return []

        # Remove any redirection operators (>, 2>&1, etc.) from the script path
        # Split by spaces but be smart about it
        try:
            parts = shlex.split(script_path)
        except ValueError:
            parts = script_path.split()

        # Filter out redirection operators and their targets
        filtered_parts = []
        skip_next = False
        for i, part in enumerate(parts):
            if skip_next:
                skip_next = False
                continue

            # Skip redirection operators
            if part in ['>', '>>', '<', '2>', '&>', '2>&1', '1>&2']:
                skip_next = True  # Skip the next part too (the file)
                continue

            # Skip parts that look like redirections
            if part.startswith('>') or part.startswith('<') or '>' in part:
                continue

            filtered_parts.append(part)

        if not filtered_parts:
            return []

        # First part is the executable/interpreter
        first_part = filtered_parts[0]

        # If it's a .sh file, prepend /bin/bash
        if len(filtered_parts) == 1 and first_part.endswith('.sh'):
            return ['/bin/bash', first_part]

        # If it's a .py file, prepend python3
        if len(filtered_parts) == 1 and first_part.endswith('.py'):
            return ['python3', first_part]

        # Return all filtered parts
        return filtered_parts

    @staticmethod
    def _parse_environment(env_string: str) -> Dict[str, str]:
        """Parse environment variables from text input (KEY=VALUE format)."""
        env_vars = {}
        if not env_string:
            return env_vars

        for line in env_string.strip().split('\n'):
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

        return env_vars

    @staticmethod
    def _parse_schedule_intervals(form_data: Dict[str, Any]) -> List[Dict[str, int]]:
        """Parse schedule intervals from form data."""
        intervals = []

        # Support multiple time slots (schedule_hour_0, schedule_minute_0, etc.)
        i = 0
        while True:
            hour_key = f'schedule_hour_{i}'
            minute_key = f'schedule_minute_{i}'

            if hour_key not in form_data:
                break

            try:
                hour = int(form_data.get(hour_key, 0))
                minute = int(form_data.get(minute_key, 0))
            except (TypeError, ValueError):
                raise ValueError(f"Schedule slot {i}: hour and minute must be integers")
            if not (0 <= hour <= 23):
                raise ValueError(f"Schedule slot {i}: hour must be 0-23, got {hour}")
            if not (0 <= minute <= 59):
                raise ValueError(f"Schedule slot {i}: minute must be 0-59, got {minute}")
            intervals.append({'Hour': hour, 'Minute': minute})

            i += 1

        return intervals

    def update_from_form(self, form_data: Dict[str, Any]) -> None:
        """Update this service from form data."""
        # Update program arguments
        self.data['ProgramArguments'] = self._build_program_arguments(form_data)

        # Update working directory
        working_dir = form_data.get('working_directory', '').strip()
        if working_dir:
            self.data['WorkingDirectory'] = working_dir
        elif 'WorkingDirectory' in self.data:
            del self.data['WorkingDirectory']

        # Update environment variables
        env_vars = self._parse_environment(form_data.get('environment', ''))
        if env_vars:
            self.data['EnvironmentVariables'] = env_vars
        elif 'EnvironmentVariables' in self.data:
            del self.data['EnvironmentVariables']

        # Update schedule
        schedule_type = form_data.get('schedule_type', 'keepalive')

        # Clear old schedule settings
        if 'KeepAlive' in self.data:
            del self.data['KeepAlive']
        if 'StartCalendarInterval' in self.data:
            del self.data['StartCalendarInterval']

        if schedule_type == 'keepalive':
            self.data['KeepAlive'] = True
        elif schedule_type == 'scheduled':
            intervals = self._parse_schedule_intervals(form_data)
            if intervals:
                self.data['StartCalendarInterval'] = intervals


