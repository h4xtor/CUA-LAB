# Installs ponytail, superskill, agent-skills and graphify for Claude Code at user scope,
# so every project and chat gets them. Safe to re-run.
# Requires: claude, Node.js (npx) and Python with the py launcher.
$ErrorActionPreference = 'Stop'
function Run { & $args[0] $args[1..($args.Count-1)]; if ($LASTEXITCODE -ne 0) { throw "Failed: $args" } }

Run claude plugin marketplace add DietrichGebert/ponytail
Run claude plugin install ponytail@ponytail --scope user
Run claude plugin marketplace add permanu/superskill
Run claude plugin install superskill@superskill --scope user

Run npx -y skills add addyosmani/agent-skills --agent claude-code -g -y

Run py -m pip install --quiet --disable-pip-version-check graphifyy
Run py -m graphify install --platform claude
Write-Host 'Done. Restart Claude Code to load the plugins and skills.'
