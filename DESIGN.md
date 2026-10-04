---
name: CUA LAB
description: A quiet desktop workspace with persistent chat controls.
colors:
  page: "#212121"
  panel: "#262626"
  composer: "#343434"
  border: "#414141"
  text: "#f3f3f3"
  secondary: "#b5b5b5"
  connected: "#9bddbb"
  error: "#ffb5b5"
typography:
  body:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  control: "8px"
  panel: "14px"
  composer: "16px"
spacing:
  compact: "8px"
  group: "12px"
  panel: "16px"
---
# CUA LAB workspace

Mode: Operate. The user requested a simple ChatGPT-like interface for the existing Windows desktop app.

The Windows WebView2 UI uses a restrained dark palette: page `#212121`, panel `#262626`, composer `#343434`, border `#414141`, text `#f3f3f3`, secondary text `#b5b5b5`. Green `#9bddbb` indicates connection; red `#ffb5b5` identifies stop, errors and blocked states. Segoe UI/system sans at 14px is the base, with 12px controls and 11px metadata. Panel corners are 14px, composer corners 16px, controls 8px.

Desktop observation stays left, with its complete activity log below. Chat occupies the right column. Model selection is progressive and requires Use selected model. Controls stay at the top; the task composer stays at the bottom. Conversation and activity scroll independently. At widths below 900px, chat comes first, with observation and activity below, within the viewport. Detailed verification is available beside the composer. Escape closes details; Enter sends and Shift+Enter inserts a newline.

Preserve every existing connection, explicit model selection, safety review, task control, history, learning and timeline recovery. Do not turn illustrative browser fixtures into live model proof. Live screenshots remain hidden until actual observation content is available.
