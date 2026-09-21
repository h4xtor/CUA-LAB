# Development lessons

- A cloud Work terminal is not the user's Windows machine. Build portable code here; report interactive acceptance separately.
- Driver docs expose evolving contracts; discover live MCP schemas and restrict them instead of inventing CLI syntax.
- Snapshot IDs are observation identities, not UI changes. Exclude them and opaque tokens from no-change fingerprints, then remap a reviewed element only when semantic identity remains identical.
- STOP is cancellation/admission control, not rollback of native input already delivered.
- Local web applications need origin/host validation and per-launch authentication, including screenshots and WebSockets.
- SQLite is constructed by the launcher and then exclusively used by the backend thread. Explicitly support this handoff; initial tests caught same-thread failures at shutdown.
- SOCKS proxy environments need the optional HTTPX dependency. Include it in locked requirements.
- Closed enums plus computed knowledge paths are a stronger privacy boundary than letting the model generate arbitrary YAML and scanning it afterwards.
- A successful backend smoke test does not prove Windows GUI, WebView2, Cua Driver, or live provider behavior.
