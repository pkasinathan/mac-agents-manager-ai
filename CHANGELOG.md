# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-03-01

### Added

- Full CLI subcommands mirroring every web UI feature:
  `mam list`, `mam show`, `mam create`, `mam load`, `mam unload`,
  `mam start`, `mam stop`, `mam restart`, `mam delete`, `mam start-all`,
  `mam logs` (with `--follow` and `--stderr`), `mam open`, `mam serve`
- `mam` with no arguments still starts the web server (backward compatible)

## [1.0.1] - 2026-03-01

### Added

- CLI argument parsing: `mam --help`, `mam --port 9090`, `mam --debug`, `mam --version`

## [1.0.0] - 2026-03-01

### Added

- Web-based dashboard for managing macOS LaunchAgents (create, view, edit, delete)
- Service controls: load, unload, start, stop, restart, reload via launchd
- Tree-view sidebar organized by schedule type (Scheduled / KeepAlive) and namespace
- Plist preview, stdout/stderr log viewer in bottom panel
- Auto port detection for KeepAlive agents (via lsof, env vars, log parsing, CLI args)
- "Start All KeepAlive" bulk action
- "Run Once" for scheduled agents
- Self-agent protection (prevents unloading the manager itself)
- Dark/light theme toggle with localStorage persistence
- `install.sh` for one-command setup as a user LaunchAgent
- PyPI package (`mac-agents-manager-ai`) with `mam` CLI entry point

### Security

- CSRF token protection on all state-changing endpoints (constant-time comparison)
- Path traversal protection via label validation and resolved-path checks
- XSS prevention with `escapeHtml()` on all API data interpolated into DOM
- Security headers: X-Frame-Options, CSP, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- Subresource Integrity (SRI) on CDN resources
- Log file reads restricted to `/tmp/`, `/var/log/`, `/var/folders/`
- Error messages sanitized (no internal exception details leaked to clients)
- Input validation on service names, categories, and schedule intervals
- Debug mode off by default (opt-in via `FLASK_DEBUG` env var)
- Localhost-only binding (`127.0.0.1`)
