# CUA LAB 0.1.0

A local Windows computer-use workspace: Qwen via OpenRouter plans actions, Cua Driver executes them, and the app shows observations, approvals and verification. **Development build: Windows packaging, native startup and scripted Calculator acceptance verified; live model-driven acceptance remains pending.** See [Windows verification](docs/WINDOWS_VERIFICATION.md).

## Packaged Windows application

Download the `CUA-LAB-windows-x64` artifact from the repository's **Actions → Build Windows CUA LAB** run when its build succeeds. Extract the entire bundle and double-click `CUA-LAB\CUA-LAB.exe`. Keep `_internal` beside the executable. Python is bundled; do not copy only the EXE.

Required externally: Windows 10/11 x64, Microsoft Edge WebView2 Runtime, interactive unlocked desktop, Cua Driver 0.28.2+ and a user environment variable `OPENROUTER_API_KEY`. The app never bundles or displays your key. No driver installation or elevation is performed silently.

## Existing source installation

```powershell
.\START-CUA-LAB.ps1
```

## New development machine

```powershell
git clone https://github.com/h4xtor/CUA-LAB.git
cd CUA-LAB
.\INSTALL-CUA-LAB.ps1
.\START-CUA-LAB.ps1
```

Source setup requires Python 3.12 x64 with the `py` launcher. Install the external driver using its official installation instructions: https://cua.ai/docs/how-to-guides/driver/install. Close/reopen the app after adding environment variables. If discovery fails, set `CUA_DRIVER_PATH` to the driver executable. `CUA_LAB_MODEL` defaults to `qwen/qwen3.7-flash`.

## First task

Use **Health check**, select **Step / Learn**, and enter `Open Calculator and calculate 19 × 23. Verify the result from Calculator.` Review each proposed action and choose Execute. The correct result must be observed in Calculator. A computed answer in the model is not proof.

Internal GUI: `http://127.0.0.1:8768`. The launcher supplies a short-lived local authentication token. Opening the bare URL from a separate browser is intentionally not authenticated. Closing the native application closes its backend. A second instance is refused.

## Architecture

- `cua_lab/driver.py`: persistent stdio MCP transport, installed-driver discovery and live schema filtering, exact-window observations, snapshot-bound tokens, process cleanup.
- `protocol.py`, `safety.py`: strict output/action validation, allowlisted tools, read-only enforcement, conservative approvals. Only a small set of recognized Calculator interactions and navigation shortcuts bypass approval.
- `provider.py`: stateless OpenRouter Responses API, bounded retries, structured output and reported usage. Missing cost is shown as unknown, never estimated as zero.
- `runtime.py`: single active task, cancellation, pause/step approval epochs, pre-action observation, separate model verification, repetition and failure limits.
- `server.py`, `static/`: loopback REST/WebSocket dashboard, native WebView2 window via pywebview, history and learning panel.
- `store.py`, `learning.py`: SQLite private sessions; closed-vocabulary automatic candidate detection; strictly scoped GitHub contents writes.

## Private data and security

Private data lives in `%LOCALAPPDATA%\CUA-LAB`, independently of the install folder. Upgrading the app does not erase it. For isolated testing, override `CUA_LAB_DATA_DIR`.

UIA observations and task text are sent to OpenRouter. Screenshots stay local unless **Send screenshots to OpenRouter** is enabled. Password-like UI prevents capture when detected; this heuristic cannot guarantee that a screenshot or arbitrary UI text contains no private data. Use Take control for credentials and keep sensitive applications out of view. Local screenshots and histories are private but not encrypted by this MVP; use appropriate Windows account/disk protection.

The runtime cannot run shell commands or write arbitrary repository paths. Unrecognized mutations need one-shot approval. Desktop content is treated as untrusted model input. Validation does not make semantic GUI safety infallible; inspect approvals. STOP prevents subsequent calls and kills the owned MCP process, but cannot undo input already delivered to Windows.

## Shared learning

Three deterministic detectors currently produce candidates: Calculator UIA actions, Chromium address-bar shortcuts, and visual fallback after a degraded UIA tree. Records use closed enum fields and aggregate counters, not copied conversations. Confidence is a smoothed success ratio, not a calibrated probability.

**Sync to GitHub** uses optional `CUA_LAB_GITHUB_TOKEN` with Contents write permission for this repository. It is separate from OpenRouter and is never sent to Qwen. Application code fixes the repository, branch, schema and generated paths under `cua_knowledge/`; no generic Git/tool path is exposed to the model. A failed or conflicting sync leaves candidates pending.

Detections start machine-specific. Global records can be curated by developers after cross-machine validation. **Get shared knowledge** loads validated repository records into the local cache. Current desktop state always takes priority. Auto sync is off on each application start; enabling it only syncs after a task and requires higher confidence.

## Build

```powershell
.\build.ps1
```

Outputs `dist\CUA-LAB\CUA-LAB.exe` and `dist\CUA-LAB-windows-x64.zip`. Build creates an isolated Python 3.12 environment, installs pinned dependencies, runs noninteractive tests, packages with PyInstaller and starts the packaged backend smoke test. Close running CUA LAB instances before building because the smoke test checks port 8768.

GitHub Actions uses the same script on Windows. CI does **not** perform interactive desktop tests or call OpenRouter.

## Troubleshooting

- Driver unavailable: verify PATH/`CUA_DRIVER_PATH`, run `cua-driver doctor` in your interactive Windows session.
- No windows/UIA: unlock the desktop; Session 0/SSH-only sessions do not provide the required desktop.
- OpenRouter HTTP 401/402/429: check key, credit or rate limits. HTTP 400 can indicate model/schema incompatibility. Response bodies are not echoed into logs.
- Stale targets: the runtime replans after changed state. Resume always discards cached targets.
- Unknown action effects: approve one action at a time, or use Take control.
- Blank native window: verify Edge WebView2 Runtime. Source developers may use `python main.py --browser` and stop it with Ctrl+C.
- GitHub sync unavailable: candidates remain in SQLite. Add the optional scoped token and retry.

## Known limitations

Real Windows Calculator UIA actions produced 437 and packaged WebView2 startup passed on the local Windows machine. That acceptance uses a scripted planner, not live model inference. OpenRouter model/schema support and a fully model-driven run still require an approved configured provider. Desktop-global input is limited to the driver's primary display; exact window targets may reside on other monitors. No PyAutoGUI fallback, full replay controls, action editing, automatic application updates or calibrated confidence model. Captures currently favor correctness over minimum latency (multiple window snapshots per step). See the Windows verification report for tested boundaries.
