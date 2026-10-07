param([string]$DestinationRoot = "C:\Users\Usuario\Documents\Codestra-Backups\Meltano-Leads-Importer")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$db = Join-Path $Root "runtime\raw-staging.db"
if (-not (Test-Path $db)) { throw "Raw staging database not found." }
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $DestinationRoot $stamp
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item $db (Join-Path $dest "raw-staging.db") -Force
Get-FileHash (Join-Path $dest "raw-staging.db") -Algorithm SHA256 | Format-List
Write-Host "Backup created: $dest"
