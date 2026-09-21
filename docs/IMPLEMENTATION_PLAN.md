# CUA LAB implementation plan

Goal: a portable local Windows agent with visible, cancellable execution and a strictly isolated learning bank.

The user supplied and approved the product specification and autonomous implementation. Execute inline on main. Existing source at upstream 01add9b is simulated; retain its history, replace the implementation.

1. Implement/test strict tool validation, conservative safety, persistent MCP transport, OpenRouter Responses provider and cancellable runtime.
2. Implement/test SQLite events and template-only automatic learning; GitHub contents sync restricted to generated knowledge JSON paths, never source or scripts.
3. Add loopback-only authenticated FastAPI/WebSocket UI, desktop preview, controls, history and memory panel.
4. Add Windows launcher, single instance, build scripts and Windows CI packaging. Preserve private data outside the repository.
5. Run Linux unit/integration tests, backend/UI smoke tests, inspect diff and publish via GitHub API with original upstream ancestry (direct git network unavailable).
6. Report Windows, live provider, interactive desktop and packaged acceptance tests as NOT RUN until executed on KESADMIN.

Review focus: stale approvals after pause, cancellation during I/O, no-op clicks, malicious model/tool fields, memory path/privacy injection, cross-origin local API access and sync conflicts.
