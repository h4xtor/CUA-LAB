#!/bin/bash
# Points the user-scope Claude Code statusline at ponytail's mode badge ([PONYTAIL], [PONYTAIL:ULTRA]).
# The command picks the newest installed ponytail version at runtime, so plugin updates don't break it.
# Safe to re-run; leaves the rest of settings.json untouched.
set -euo pipefail

dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
mkdir -p "$dir"
python3 - "$dir/settings.json" <<'PY'
import json, os, sys
path = sys.argv[1]
settings = json.load(open(path, encoding="utf-8-sig")) if os.path.exists(path) else {}
settings["statusLine"] = {
    "type": "command",
    "command": "bash -c 'f=$(ls -d \"${CLAUDE_CONFIG_DIR:-$HOME/.claude}\"/plugins/cache/ponytail/ponytail/*/hooks/ponytail-statusline.sh 2>/dev/null | sort -V | tail -n1); [ -z \"$f\" ] || bash \"$f\"'",
}
json.dump(settings, open(path, "w", encoding="utf-8"), indent=2)
PY
