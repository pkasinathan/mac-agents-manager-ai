# Security Policy

## Security Model

Mac Agents Manager is a **localhost-only** tool designed to run on a single user's machine. It binds exclusively to `127.0.0.1` and is not intended to be exposed to a network.

Key security properties:

- **Localhost binding**: The Flask server listens only on `127.0.0.1`, preventing remote access.
- **CSRF protection**: All state-changing endpoints require a CSRF token passed via the `X-CSRF-Token` header to prevent cross-origin attacks from malicious websites.
- **Path traversal protection**: Service labels are validated against a strict allowlist of characters, and resolved file paths are checked to stay within `~/Library/LaunchAgents/`.
- **Input validation**: Service names and categories are restricted to alphanumeric characters, hyphens, and underscores.
- **Log file access**: Log file reads are restricted to known safe directories (`/tmp/`, `/private/tmp/`, `/var/log/`, `/private/var/log/`, `/var/folders/`, `/private/var/folders/`).
- **Security headers**: Responses include `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and `Content-Security-Policy: frame-ancestors 'none'`.
- **AI Chat execution safety**: Chat mutations require explicit user confirmation. Server-side safeguards prevent accidental re-execution of completed/cancelled actions and ignore assistant "execution claims" that do not include structured action payloads.
- **Ollama boundary**: Browser code talks only to the Flask backend (`connect-src 'self'`). Ollama access is server-side via localhost.

### What this tool does NOT provide

- **Authentication**: There is no login or API key mechanism. Any process on localhost with access to port 8081 can interact with the API (protected by CSRF tokens against browser-based attacks).
- **Encryption**: Traffic is plain HTTP over localhost. Do not expose this tool to a network.
- **Multi-user isolation**: This tool manages the current user's LaunchAgents only.
- **Remote AI sandboxing**: AI chat actions execute local LaunchAgent operations after confirmation; they are not isolated from the current user context.

## Data Egress Notes

- Core Mac Agents Manager operations are local-only and do not call cloud APIs.
- If AI Chat is enabled and the configured Ollama model is missing, Ollama may download that model using the host network.
- Chat/session data is stored locally under `~/.mac_agents_manager/chat/`.

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Use [GitHub's private vulnerability reporting](https://github.com/pkasinathan/mac-agents-manager/security/advisories/new) to submit a description of the vulnerability, steps to reproduce, and any potential impact.
3. Allow reasonable time for a fix before public disclosure.

We appreciate responsible disclosure and will credit reporters in the release notes (unless they prefer to remain anonymous).
