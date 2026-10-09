# CUA stability, progress and automatic learning — 2026-10-09

Status: implementation checkpoint; autonomous acceptance FAILED. The app is not yet demonstrated reliable for model-driven tasks.

## Changes

- Exact token clicks now supply the inspected native window identity. Fresh token IDs and capture metadata no longer invalidate an unchanged control. Fresh target checks and unique control rebinding remain required.
- Capture combines the screenshot and UIA snapshot after the credential preflight. Admission checks omit capture. Planning reuses verified observations. Local model capabilities are cached per task and duplicate input metadata is removed.
- The UI shows the current phase, step, model and time waiting. Screenshot input follows selected model capabilities and missing UIA coverage; the manual screenshot choice is removed.
- Automatic learning upload defaults to on, persists its setting and runs in the background. New records arriving during uploads remain pending until uploaded. Failures preserve local records for a later task/startup retry.
- Closed learning records retain validated strategy counts and historical window bounds. Current observations govern execution. Screenshots, task text, titles, source code and element tokens are excluded from GitHub records. Existing authenticated GitHub CLI credentials can supply the token without saving it.

## Validation

| Check | Result |
| --- | --- |
| Default pytest suite | PASS — 88 passed, 4 opt-in tests skipped; one dependency deprecation warning |
| Browser UI | PASS — eight viewport sizes, task controls, progress, connection recovery and model selection |
| Actual Windows Calculator with scripted planner | PASS — 437, UIA clicks, capture, pause/resume and STOP; 34.05 seconds |
| Separate Windows executable build | PASS — `dist/progress-build/CUA-LAB/CUA-LAB.exe` |
| Packaged backend and native WebView2 smoke checks | PASS — backend/resources/authentication/SQLite/GGUF grammar and authenticated native idle state |
| Automatic GitHub learning | PASS — background upload followed by exact remote readback; 7 verified Calculator actions, zero failures and historical bounds |

The real GitHub proof is [this machine-specific learning record](https://github.com/h4xtor/CUA-LAB/blob/main/cua_knowledge/machines/09dc5d246c6b3712/fa8442a7983714ef6a6ba423.json). The one-observation window-location candidate remained local because it did not meet the validation threshold. These observations came from actual desktop execution with a scripted planner, not successful autonomous model inference.

## Actual local model tests

All models were installed local routes; no paid route was used. Each autonomous exercise asked the model to calculate 19 × 23 through observed Calculator controls and verify the actual display; the prompt did not supply the final result. STOP was a separate test during a real model request.

| Model | Autonomous exercise | STOP |
| --- | --- | --- |
| qwen3-vl:8b | FAIL — repeated actions without a state change; latest test pair 109.94 seconds | PASS — 0.036 seconds cleanup |
| qwen2.5vl:7b | FAIL — three consecutive unverified actions; test pair 122.35 seconds | PASS — 0.039 seconds cleanup |
| gemma3:4b | FAIL — GPU/model-engine errors; latest retry also failed cleanup and STOP setup | Earlier run PASS — 0.030 seconds; latest retry FAIL |
| hf.co/mradermacher/Holo-3.1-4B-GGUF:Q4_K_M | FAIL — three consecutive unverified actions; latest test pair 68.84 seconds | PASS — 0.028 seconds cleanup |
| qwen3.5:9b | FAIL — insufficient available GPU memory; latest test pair 21.99 seconds | PASS — 0.024 seconds cleanup |

Input compaction reduced observed warm Qwen3-VL planning calls from roughly 7–9 to 4–5 seconds. Different UI states and response lengths make this an indicative observation, not a controlled benchmark or a measured whole-task speedup. No successful autonomous calculation was established.

## Remaining work

Resolve incorrect model plans and local engine failures before claiming stable autonomous CUA. STOP, admission and evidence failures are retained rather than bypassed. Other applications, OpenRouter live inference and arbitrary procedural learning are not acceptance-validated. No replacement of the user's running app, deployment or main code merge was performed.
