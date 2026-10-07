param([string]$Source = "C:\Users\Usuario\03_LEADS_AND_DATA\01_CORE\Master\MASTER_SALES_LEADS_20260921.csv")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Test-Path ".venv\Scripts\python.exe")) { & "$PSScriptRoot\install.ps1" }
if (-not (Test-Path $Source)) { throw "Lead source not found: $Source" }
& ".venv\Scripts\python.exe" -m meltano_leads_importer --db runtime\raw-staging.db preview $Source --sample-limit 0
if ($LASTEXITCODE -ne 0) { throw "preview failed" }
& ".venv\Scripts\python.exe" -m meltano_leads_importer --db runtime\raw-staging.db import $Source
if ($LASTEXITCODE -ne 0) { throw "import failed" }
& ".venv\Scripts\python.exe" -m meltano_leads_importer --db runtime\raw-staging.db stats
