# Test report — 2026-09-21

Latest Windows build and desktop evidence: [2026-09-22 verification](WINDOWS_VERIFICATION.md).
The historical Linux results below are retained separately.

Environment: Linux Work container, Python 3.12. No KESADMIN connection, no Cua Driver executable, no OPENROUTER_API_KEY in this environment. User-reported Windows setup is not independently verified here.

## Executed

- 19 noninteractive tests PASS: strict unknown/extra argument rejection; read-only protection; conservative approval; closed learning schema/path; STOP during blocked model call and subsequent restart; Step Mode exactly one execution; stale approval after pause; local API auth/origin/host; image authorization; Responses API body/usage with HTTP fixture; auth errors exclude response bodies; automatic learning persistence; machine isolation; restricted sync with controlled HTTP transport; conflict retention; persistent MCP JSON-RPC transport with subprocess fixture; token-independent UI fingerprint.
- Backend startup smoke PASS: imports, static resource registration, HTTP health, authenticated status and SQLite startup/shutdown. Initially found and fixed SQLite thread handoff and SOCKS dependency.
- Python compilation PASS.
- Browser/UI smoke and Windows CI results will be appended after execution.

Fixture tests do not constitute real Qwen or Cua Driver acceptance. No fabricated live learning record was pushed.

## Not run / blocked

- Live Qwen3.7 Flash OpenRouter response: key unavailable here.
- Actual Windows desktop read-only, Calculator 19 × 23, Chrome navigation, STOP during native input, native Step Mode: Windows access unavailable.
- Packaged Windows Calculator and WebView2 launch: require interactive Windows even after CI packaging succeeds.
- Real runtime GitHub learning sync: no verified desktop learning and no runtime GitHub token here. Controlled transport tests only.
- UIA/screenshot/Windows action latency: not measurable here. Runtime instrumentation records these when run locally.

## Acceptance on KESADMIN

Start the packaged application. Run Health check, then read-only task; Calculator in Step Mode; Calculator in Autopilot; browser task; STOP during multi-step execution and start a new task. Verify Calculator visibly shows 437, timeline and screenshot updates, per-request usage, SQLite history and an automatically detected learning. Inspect learning before manual sync. Record actual latency and failures here. Never label acceptance PASS from a backend or mocked test.
