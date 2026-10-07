#!/bin/bash
# Installs ponytail, superskill, agent-skills and graphify for Claude Code at user scope,
# so every project and chat gets them. Safe to re-run. Usable as a cloud environment setup script.
# Requires: claude, node/npx, python3 with pip.
set -euo pipefail

claude plugin marketplace add DietrichGebert/ponytail
claude plugin install ponytail@ponytail --scope user
claude plugin marketplace add permanu/superskill
claude plugin install superskill@superskill --scope user
bash "$(dirname "$0")/claude-statusline.sh"

npx -y skills add addyosmani/agent-skills --agent claude-code -g -y

python3 -m pip install --quiet --disable-pip-version-check graphifyy
graphify install --platform claude
