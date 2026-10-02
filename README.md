# CUA LAB 0.1.0

A local Windows computer-use workspace: a model of your choice (OpenRouter, any OpenAI-compatible API, or a local GGUF file via llama.cpp) plans actions, Cua Driver executes them, and the app shows observations, approvals and verification. **Development build: interactive Windows acceptance is not yet verified.** See [test report](docs/TEST_REPORT.md).

## Packaged Windows application

Download the `CUA-LAB-windows-x64` artifact from the repository's **Actions → Build Windows CUA LAB** run when its build succeeds. Extract the entire bundle and double-click `CUA-LAB\CUA-LAB.exe`. Keep `_internal` beside the executable. Python is bundled; do not copy only the EXE.

Required externally: Windows 10/11 x64, Microsoft Edge WebView2 Runtime, interactive unlocked desktop, Cua Driver 0.28.2+ and one model backend (see **Model backends** below). The app never bundles or displays your key. No driver installation or elevation is performed silently.

## Model backends

Pick the backend in the **Model** tab. The choice is saved locally and survives restarts. API keys are only read from environment variables; they are never shown, stored or sent to the driver.

| Backend | What you need | Key |
|---|---|---|
| OpenRouter API | Model id, e.g. `qwen/qwen3.7-flash` | `OPENROUTER_API_KEY` |
| OpenAI-compatible API | Base URL + model id. Works with OpenAI, Groq, Mistral, vLLM, and local servers such as Ollama (`http://localhost:11434/v1`) and LM Studio (`http://localhost:1234/v1`) | `CUA_LAB_API_KEY` (or `OPENAI_API_KEY`); not needed for local servers |
| Local GGUF | A `.gguf` model file and llama.cpp's `llama-server` (`winget install llama.cpp`, or set its path). Optional `mmproj` file enables screenshots (vision) | none |

With a local GGUF, CUA LAB starts its own private `llama-server` on a random loopback port with a one-time API key, loads the model at the first task and stops it when the app closes or the backend changes. Nothing leaves the PC; cost shows as $0. Load errors are written to `logs\llama-server.log` in the data folder. Use a model that is good at JSON and tool use (e.g. Qwen2.5/3 Instruct or Qwen2.5-VL with its mmproj for vision); 7B+ is recommended. Lower **GPU layers** to fit your VRAM, 0 means CPU only.

Optional environment defaults (used until you save settings in the app): `CUA_LAB_PROVIDER` (`openrouter`/`openai`/`gguf`), `CUA_LAB_MODEL`, `CUA_LAB_BASE_URL`, `CUA_LAB_GGUF_PATH`, `CUA_LAB_MMPROJ_PATH`, `LLAMA_SERVER_PATH`.

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
- `provider.py`, `settings.py`: pluggable model backends (OpenRouter Responses API, OpenAI-compatible chat completions, local GGUF via a managed llama-server), bounded retries, JSON-schema structured output and reported usage. Missing cost is shown as unknown, never estimated as zero.
- `runtime.py`: single active task, cancellation, pause/step approval epochs, pre-action observation, separate model verification, repetition and failure limits.
- `server.py`, `static/`: loopback REST/WebSocket dashboard, native WebView2 window via pywebview, history and learning panel.
- `store.py`, `learning.py`: SQLite private sessions; closed-vocabulary automatic candidate detection; strictly scoped GitHub contents writes.

## Private data and security

Private data lives in `%LOCALAPPDATA%\CUA-LAB`, independently of the install folder. Upgrading the app does not erase it. For isolated testing, override `CUA_LAB_DATA_DIR`.

UIA observations and task text are sent to the selected model backend (they stay on the PC with a local GGUF or local server). Screenshots stay local unless **Send screenshots to model** is enabled. Password-like UI prevents capture when detected; this heuristic cannot guarantee that a screenshot or arbitrary UI text contains no private data. Use Take control for credentials and keep sensitive applications out of view. Local screenshots and histories are private but not encrypted by this MVP; use appropriate Windows account/disk protection.

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
- Local GGUF does not start: check `logs\llama-server.log`, the file paths, and lower GPU layers or context size if memory runs out. Screenshot mode needs an mmproj file.
- Model replies with invalid JSON: pick a larger/instruct model; tiny models often fail the structured-output contract.
- OpenRouter HTTP 401/402/429: check key, credit or rate limits. HTTP 400 can indicate model/schema incompatibility. Response bodies are not echoed into logs.
- Stale targets: the runtime replans after changed state. Resume always discards cached targets.
- Unknown action effects: approve one action at a time, or use Take control.
- Blank native window: verify Edge WebView2 Runtime. Source developers may use `python main.py --browser` and stop it with Ctrl+C.
- GitHub sync unavailable: candidates remain in SQLite. Add the optional scoped token and retry.

## Known limitations

No claim of a verified Windows Calculator run yet. Driver/version-specific live contracts, OpenRouter model/schema support and packaged WebView2 startup must be validated on KESADMIN. Desktop-global input is limited to the driver's primary display; exact window targets may reside on other monitors. No PyAutoGUI fallback, full replay controls, action editing, automatic application updates or calibrated confidence model. Captures currently favor correctness over minimum latency (multiple window snapshots per step). See development memory and test report before continuing work.
