# CUA LAB development memory

## Source and execution environment
- Official repository: h4xtor/CUA-LAB, active branch main. User permits replacing prototype and direct main commits.
- Original upstream root 01add9b: simulated agent/provider, label-only PyQt UI, missing QApplication import, raw typed-text logging. Replaced; history retained remotely.
- Development here is Linux, not KESADMIN. No local Windows driver or OpenRouter secret. Never claim desktop acceptance from mocks.
- Direct git transport times out here; files imported via GitHub connector, commits published through Git Data API with original parent. Local inspection snapshot initially has distinct ancestry.

## Architecture and contracts
- Python 3.12 / FastAPI / vanilla JS / WebSocket / SQLite; native pywebview window on Windows; PyInstaller directory bundle.
- Port 8768, loopback only. Launcher-owned random auth token; strict origin/host checks; private image endpoints authenticated. Single instance by exclusive listener bind.
- Model qwen/qwen3.7-flash, OpenRouter /api/v1/responses, store=false; model configurable via CUA_LAB_MODEL. Secrets only environment.
- Driver 0.28.2 official MCP docs inspected. Persistent `cua-driver mcp` legacy initialize 2025-06-18, runtime tools/list validation. Window UIA with opaque snapshot tokens; no arbitrary commands, paths or unregistered tools.
- driver.py owns invocation, cache, images and cleanup. runtime.py owns admission/approval epoch and cancellation. A pause invalidates pending approvals; action before/after snapshots and independent verification; max 40 steps/default, 900-second task deadline.
- STOP cancels task and kills owned MCP process; already delivered input cannot be rolled back. New task waits for cleanup.
- Safety is conservative: unknown mutations require approval. Only narrowly recognized Calculator actions/navigation bypass it. Read-only enforced in execution admission.

## Data and learning
- Private `%LOCALAPPDATA%\CUA-LAB`: database, sessions/images, profile, cache. CUA_LAB_DATA_DIR override for tests. No private data in Git.
- Template-based automatic learning for Calculator UIA, Chromium shortcut, degraded UIA+vision fallback. Fixed enum schema, counters, machine hash. Machine scope default; global manually curated after validation.
- Sync uses separate CUA_LAB_GITHUB_TOKEN; repository and main fixed; only generated cua_knowledge paths, JSON schema-validated contents, optimistic SHA conflict handling. Never source/script/workflow writes.
- No actual learning is seeded as observed. Shared bank starts empty. Auto sync off each startup, thresholds stricter than manual. Refresh is read-only GitHub retrieval into private cache.

## Build / tests / next work
- build.ps1: isolated venv, pinned deps, pytest, PyInstaller, packaged backend smoke, ZIP. GitHub Windows workflow mirrors it.
- Tests distinguish fakes from real interfaces. Read docs/TEST_REPORT.md for latest counts and acceptance status.
- Highest priority: interactive Windows run (driver tool schema, opaque token behavior, Calculator result, stop mid-action, packaged window), then optimize snapshots and expand knowledge detectors.
- No hardcoded username/hostname/PID/resolution. Monitor discovery via Win32; driver desktop mode primary-only, window targeting preferred.
