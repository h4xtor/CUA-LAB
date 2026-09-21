# Windows verification — 2026-09-22

Baseline: local HEAD and freshly fetched `origin/main` both
`c012dcceeaed16c9375d73c3ce1ef5e064a78dac`. Existing untracked `.serena/`
was inspected and preserved. Work runs in the requested HPADMINPC worktree;
Windows reports the hostname `AdminPC`.

## Assessment from current source

The implementation is substantial: Python 3.12 starts a single-instance,
authenticated loopback FastAPI server and a native pywebview/WebView2 window.
The UI starts a bounded runtime task. The driver discovers actual MCP schemas,
captures window UIA and local screenshots, and the OpenRouter provider requests
one structured decision. Pydantic/JSON Schema validation and the safety gate
precede approval, a fresh observation and execution. Separate verification checks
observed evidence before completion. SQLite stores redacted events and sessions;
closed-schema learning records can optionally sync to fixed GitHub paths.

Pause invalidates pending approvals; resume replans; STOP cancels the worker and
closes its owned MCP process. The runtime limits steps, duration, repeated actions,
verification failures and provider retries. Private data and environment secrets
are separate from the installation and are not packaging inputs.

The build blocker was a nonexistent dependency pin. Subsequent real Windows
testing exposed a console-less startup error and background-launch observation
of the wrong window. These are fixed without replacing the architecture.
Danish Calculator button names observed on this machine were added to the
existing narrow safety allowlist. The browser test previously assumed Linux and
checked asynchronous history before loading finished; it now uses an explicit
unavailable-driver fixture and waits for the actual history row.

The provider interface now supports OpenRouter, Ollama and LM Studio; learning
still uses three deterministic detectors. Full model-driven task completion
remains separate from transport, schema and scripted desktop acceptance.
Credential detection is heuristic; native input already delivered cannot be
undone by cancellation. No broader security or production-readiness claim is made.

## Dependency evidence

[pythonnet 3.0.5 metadata](https://pypi.org/pypi/pythonnet/3.0.5/json)
requires `clr_loader>=0.2.7,<0.3.0`. The published
[clr-loader 0.2.7.post0 release](https://pypi.org/project/clr-loader/0.2.7.post0/)
satisfies that range. Pythonnet is retained at 3.0.5. The clean build installs the
complete pinned dependency graph and runs `pip check` before tests.

## Executed locally

- Clean Python 3.12 Windows installation, dependency consistency, unit/integration
  tests, PyInstaller packaging, packaged `--smoke-test`, and ZIP generation PASS.
- Console-less launcher regression, static resource retrieval, authenticated
  status, SQLite initialization and redacted startup failure log PASS.
- Cua Driver 0.28.2 doctor: attached interactive desktop, UI Automation and
  visible-window enumeration PASS.
- Real Calculator: background UIA button actions entered `19 × 23 = 437`.
  The actual display and captured image both show `437`. Runtime Step Mode,
  stale approval rejection, pause/resume, STOP before execution, restart,
  automatic local learning and owned MCP cleanup PASS.
- This desktop test uses a scripted local planner and verifier. It proves the
  runtime/driver path, not model reasoning or OpenRouter inference.
- Packaged EXE: native WebView2 dashboard rendered, connection showed LIVE,
  health reported driver/UIA ready and missing OpenRouter key. Window close
  was verified. The native app used isolated temporary data.

## Reproduce

Close CUA LAB before building (port 8768 must be available), then run `build.ps1`.
It writes `dist/CUA-LAB/CUA-LAB.exe` and `dist/CUA-LAB-windows-x64.zip`.
Keep the entire extracted directory, including `_internal`.

Interactive, opt-in Calculator test (opens Calculator and changes its display):

```powershell
$env:CUA_WINDOWS_TEST='1'
.\.venv-build\Scripts\python.exe -m pytest tests/test_windows_acceptance.py -q -s
Remove-Item Env:CUA_WINDOWS_TEST
```

Optional browser smoke requires Playwright and its Chromium browser, then
`CUA_UI_TEST=1` and `pytest tests/test_ui_smoke.py`. It uses a controlled driver
failure and makes no model requests.

## Remaining acceptance boundary

No `OPENROUTER_API_KEY` was configured in the development process. No paid model
request was made. A user-approved model route is required before testing real
natural-language planning and provider compatibility. STOP during an in-flight
native action, physical mouse/keyboard fallback, other applications, and runtime
GitHub learning publication have not been verified here. Local learning stayed
in temporary test data; no synthetic knowledge was published.

Startup failures now write redacted tracebacks to the private `logs/startup.log`.
Automated smoke failures never open a modal error dialog. Build requires a
machine-readable success report as well as a successful process exit.

## Local models and API settings extension

The user requested both Ollama/LM Studio and GGUF files, plus OpenRouter API
access. A Models tab now discovers, loads and selects installed models, starts
the installed Ollama engine explicitly, imports a chosen GGUF under a new name,
and stores the OpenRouter key using current-user Windows DPAPI. Existing model
server configuration and default models are preserved. No download or paid
request was performed. Local HTTP clients bypass proxies and accept only
loopback addresses. Local models never fall back to a remote provider.

- User-selected `qwen2.5vl:7b`: discovered, loaded, completion/vision capability
  read from Ollama, and actual schema-constrained verification inference PASS.
- GGUF import PASS using a temporary hard link to that chosen model's existing
  GGUF blob. The imported alias advertised completion/vision. Only the temporary
  test alias was removed afterward; the original model and source were retained.
- Native-key encryption round trip, secret-free settings response, model-change
  admission while idle, rejection of nonlocal URLs and cloud models, local
  structured responses, paid-route gate and import collision tests PASS.
- Browser checks include provider switching, model settings persistence and
  history after a controlled driver failure. Browser tests use no real key.
- LM Studio protocol uses controlled transport tests; no LM Studio server is
  installed/running for live acceptance. OpenRouter live inference still awaits
  a key entered by the user. The key should never be pasted into chat.

API references: [Ollama chat](https://docs.ollama.com/api/chat),
[GGUF import](https://docs.ollama.com/import),
[LM Studio loading](https://lmstudio.ai/docs/developer/rest/load).
