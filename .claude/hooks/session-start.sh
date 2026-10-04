#!/bin/bash
# Cloud sessions only: install test deps, the graphify CLI used by .claude/skills/graphify, and the ponytail plugin.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
python3 -m pip install --quiet --disable-pip-version-check --root-user-action=ignore \
  -r requirements.txt pytest==8.3.5 pytest-asyncio==0.26.0 graphifyy==0.9.74

# Plugins enabled in settings.json aren't fetched in fresh cloud containers; install them.
claude plugin marketplace add DietrichGebert/ponytail >/dev/null 2>&1 || true
claude plugin install ponytail@ponytail --scope user >/dev/null 2>&1 || true
