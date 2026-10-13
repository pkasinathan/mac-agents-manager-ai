"""Helpers for parsing `launchctl list` output safely."""


def _parse_launchctl_list_line(line: str) -> tuple[str, str, str] | None:
    """Parse one launchctl list line into (pid, status, label)."""
    tokens = line.strip().split()
    if len(tokens) < 3:
        return None
    if tokens[0] == "PID" and tokens[1] == "Status" and tokens[2] == "Label":
        return None
    return tokens[0], tokens[1], tokens[2]


def launchctl_list_contains_label(output: str, label: str) -> bool:
    """Return True when launchctl list contains an exact label."""
    for line in output.splitlines():
        parsed = _parse_launchctl_list_line(line)
        if not parsed:
            continue
        _pid, _status, parsed_label = parsed
        if parsed_label == label:
            return True
    return False


def launchctl_list_pid_for_label(output: str, label: str) -> str | None:
    """Return PID token for an exact label, or None."""
    for line in output.splitlines():
        parsed = _parse_launchctl_list_line(line)
        if not parsed:
            continue
        pid, _status, parsed_label = parsed
        if parsed_label == label:
            return pid
    return None
