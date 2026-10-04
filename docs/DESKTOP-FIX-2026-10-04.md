# Desktop task handoff

User reproduction: `Vis mig skrivebordet og lav en oprydningsplan` failed in release 0.1.2. The preserved local SQLite event trace showed a model-generated `click` with an exact CUA LAB window target, but no element token or coordinates. Validation admitted it; the native driver returned `tool_invocation_failed`. No cleanup of files was authorized or performed.

Changes for 0.1.3:
- Reject clicks without a current token or both coordinates before native dispatch. Encode this requirement in published tool schemas and give a specific replanning hint.
- Desktop objectives inspect the Windows shell desktop handle via `GetShellWindow`, rather than the foreground CUA LAB window. The app's own process is excluded from desktop window discovery. Generic observations also avoid selecting the app itself.
- Cleanup-plan objectives are read-only; runtime policy is reflected in the UI. The provider is told to inspect through read tools and describe a plan, without clicking or changing files.
- Packaged backend smoke checks use an ephemeral port so validation can run while the user's existing app remains open on 8768. Normal/native startup keeps port 8768.

Evidence: the two regression checks failed before the repair, then passed; targeted driver/boundary/runtime checks passed. The full suite passed **64 tests, 4 skipped** before the final small discovery/UI policy additions. The actual Windows shell target was found and differs from the running app. Clean release build and final CI are pending at this handoff checkpoint. Real shell screenshot/model acceptance has not been rerun; do not infer it from selector/unit evidence.

The user's 0.1.2 app, saved settings, models, SQLite history and existing untracked files remain untouched. Private event diagnostics are not committed. Continue on `codex/windows-build-verification`, PR #1; do not merge or deploy without the user's approval.
