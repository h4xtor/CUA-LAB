# CUA LAB 0.1.0

A local Windows computer-use workspace: local Ollama/LM Studio models or OpenRouter plan actions, Cua Driver executes them, and the app shows observations, approvals and verification. **Development build: Windows packaging, native startup and scripted Calculator acceptance verified; complete live model-driven acceptance remains pending.** See [Windows verification](docs/WINDOWS_VERIFICATION.md).

## Packaged Windows application

Download the `CUA-LAB-windows-x64` artifact from the repository's **Actions → Build Windows CUA LAB** run when its build succeeds. Extract the entire bundle and double-click `CUA-LAB\CUA-LAB.exe`. Keep `_internal` beside the executable. Python is bundled; do not copy only the EXE.

Required externally: Windows 10/11 x64, Microsoft Edge WebView2 Runtime, an interactive unlocked desktop and Cua Driver 0.28.2+. Choose a local model server or OpenRouter in **Models**. The app never bundles or displays a saved key. No driver installation or elevation is performed silently.

## Choose a model

- **Ollama:** open Models, choose Ollama, click Start Ollama if needed, Refresh models, select an installed model, then Load local model & use. The app does not download models. It stops only a server it started itself, including that server's Windows runner processes.
- **GGUF:** in Models → Ollama → Import a local GGUF file, click Choose file, give it a new `cua-...` name, then Import GGUF. Select the imported model and load it. This uses the installed Ollama engine; Python or a separate terminal is not needed. Existing names are never overwritten and source files are preserved. Only architectures supported by Ollama can be imported; separate vision projector files are not imported by this single-file flow.
- **LM Studio:** enable its local server, choose LM Studio in Models, refresh the list, choose a model, and load/save. The current integration expects a local server without authentication. Loading uses LM Studio's `/api/v1/models/load` endpoint.
- **OpenRouter:** choose OpenRouter, enter your API key in the password field, select a model, and Save connection. Windows DPAPI encrypts the saved key for your Windows account. Leaving the key blank preserves it. `OPENROUTER_API_KEY` remains supported as a fallback. Credit use is off by default: select an explicit `:free` model / `openrouter/free`, or enable credit use yourself.

Configuration is private in `%LOCALAPPDATA%\CUA-LAB\provider.json`; it is excluded from the bundle. Models cannot be switched while a task or another model operation is active. Local providers accept only loopback HTTP addresses, send no OpenRouter credentials, and never fall back to a cloud provider. Ollama cloud models are rejected. Screenshot input requires a vision-capable model; text models can work with UI Automation.

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
- `provider.py`: stateless OpenRouter Responses API and local Ollama / LM Studio structured responses. Missing remote cost is shown as unknown; local API cost is zero.
- `configuration.py`, `model_service.py`, `local_models.py`: Windows-protected API key, idle-only provider changes, installed-model discovery, explicit local loading and GGUF import.
- `runtime.py`: single active task, cancellation, pause/step approval epochs, pre-action observation, separate model verification, repetition and failure limits.
- `server.py`, `static/`: loopback REST/WebSocket dashboard, native WebView2 window via pywebview, history and learning panel.
- `store.py`, `learning.py`: SQLite private sessions; closed-vocabulary automatic candidate detection; strictly scoped GitHub contents writes.

## Private data and security

Private data lives in `%LOCALAPPDATA%\CUA-LAB`, independently of the install folder. Upgrading the app does not erase it. For isolated testing, override `CUA_LAB_DATA_DIR`.

UIA observations and task text go to the selected provider. Ollama and LM Studio use only the configured local server; OpenRouter sends these inputs to its API. Screenshots are included only when **Send screenshots to selected model** is enabled. Password-like UI prevents capture when detected; this heuristic cannot guarantee that a screenshot or arbitrary UI text contains no private data. Use Take control for credentials and keep sensitive applications out of view. Saved API keys are Windows-encrypted; local screenshots and histories are not encrypted by this MVP.

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
