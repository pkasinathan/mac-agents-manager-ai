# Mac Agents Manager Release Checklist

Use this checklist before publishing a new release.

## 1) Preflight

- Confirm working tree is clean or intentionally scoped
- Confirm target version in `pyproject.toml`
- Confirm `CHANGELOG.md` includes that version and date

## 2) Documentation pass

- Update user-facing docs:
  - `README.md`
  - `FAQ.md`
  - `TROUBLESHOOTING.md`
- Verify docs match current behavior:
  - Ollama install instructions are present and accurate
  - Default model name matches code (`qwen3.5:4b`)
  - Environment variables table is complete
  - CLI reference matches actual subcommands
  - Commands use `pip3` where appropriate

## 3) Quality gates

Run locally:

```bash
make check
```

This runs lint + tests.

## 4) Build artifacts

```bash
python3 -m pip install --upgrade build twine
python3 -m build
python3 -m twine check dist/*
```

## 5) Final validation smoke

```bash
mam --version
mam list
mam service status
```

Manual UI checks:

- Open `http://localhost:8081`
- IDE tab: browse agents, view details, check logs
- AI Chat tab: verify health indicator, send a test message
- Confirm Apply/Cancel flow works on a mutation

## 6) Publish

- Create release commit
- Tag version (`vX.Y.Z`)
- Push branch and tag
- Publish to PyPI (project workflow/manual process)
- Draft GitHub release notes from `CHANGELOG.md`

## 7) Post-release

- Verify `pip3 install -U mac-agents-manager-ai` pulls the new version
- Verify `mam --version` reports expected version
- Announce release with highlights and migration notes (if any)
