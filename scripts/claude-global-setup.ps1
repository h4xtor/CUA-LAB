# Installs ponytail, superskill, agent-skills and graphify for Claude Code at user scope,
# so every project and chat gets them. Safe to re-run.
# Requires: claude, Node.js (npx) and Python with the py launcher.
$ErrorActionPreference = 'Stop'
function Run { & $args[0] $args[1..($args.Count-1)]; if ($LASTEXITCODE -ne 0) { throw "Failed: $args" } }

Run claude plugin marketplace add DietrichGebert/ponytail
Run claude plugin install ponytail@ponytail --scope user
Run claude plugin marketplace add permanu/superskill
Run claude plugin install superskill@superskill --scope user

# Ponytail mode badge in the statusline. Picks the newest installed ponytail version at runtime,
# so plugin updates don't break it. Encoded so no shell can mangle the $ and quotes.
$claudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$badge = @'
$d = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$f = Get-ChildItem (Join-Path $d 'plugins\cache\ponytail\ponytail\*\hooks\ponytail-statusline.ps1') -ErrorAction SilentlyContinue |
  Sort-Object { try { [version]$_.Directory.Parent.Name } catch { [version]'0.0' } } | Select-Object -Last 1
if ($f) { & $f.FullName }
'@
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($badge))
$settingsPath = Join-Path $claudeDir 'settings.json'
New-Item -ItemType Directory -Force $claudeDir | Out-Null
$settings = if (Test-Path $settingsPath) { Get-Content $settingsPath -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
$statusLine = [pscustomobject]@{ type = 'command'; command = "powershell -NoProfile -ExecutionPolicy Bypass -EncodedCommand $encoded" }
$settings | Add-Member -NotePropertyName statusLine -NotePropertyValue $statusLine -Force
# WriteAllText: UTF-8 without BOM (Windows PowerShell's -Encoding utf8 adds one).
[IO.File]::WriteAllText($settingsPath, ($settings | ConvertTo-Json -Depth 32))

Run npx -y skills add addyosmani/agent-skills --agent claude-code -g -y

Run py -m pip install --quiet --disable-pip-version-check graphifyy
Run py -m graphify install --platform claude
Write-Host 'Done. Restart Claude Code to load the plugins and skills.'
