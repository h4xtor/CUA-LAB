# CUA LAB – notes for Claude

Windows computer-use app (Python 3.12, FastAPI/uvicorn backend, pywebview UI). See README.md for architecture.

- Tests: `python -m pytest -q`. Windows build: `build.ps1` (CI: `.github/workflows/build-windows.yml`).
- Keep changes minimal (ponytail plugin): reuse existing code and the standard library before adding code or dependencies.
- Codebase questions: if `graphify-out/` exists, query it with the graphify skill instead of reading many files. Build it with `/graphify .`.
- Use the agent-skills in `.claude/skills/` (e.g. debugging-and-error-recovery, test-driven-development, security-and-hardening) when the task matches.
- User-scope install for all projects: `scripts/claude-global-setup.sh` (Linux/macOS/cloud) or `scripts/claude-global-setup.ps1` (Windows).
