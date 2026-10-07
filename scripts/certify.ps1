param(
  [string]$Master = "C:\Users\Usuario\03_LEADS_AND_DATA\01_CORE\Master\MASTER_SALES_LEADS_20260921.csv",
  [int]$ExpectedRows = 88379,
  [int]$TestPort = 8766
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Test-Path ".venv\Scripts\python.exe")) { & "$PSScriptRoot\install.ps1" }
$Python = Join-Path $Root ".venv\Scripts\python.exe"

& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "unit tests failed" }
& $Python -m compileall -q src
if ($LASTEXITCODE -ne 0) { throw "compile failed" }

$previewText = & $Python -m meltano_leads_importer preview $Master --sample-limit 0
if ($LASTEXITCODE -ne 0) { throw "master preview failed" }
$preview = $previewText | ConvertFrom-Json
if ($preview.rows_seen -ne $ExpectedRows) {
  throw "preview row count mismatch: expected $ExpectedRows got $($preview.rows_seen)"
}

New-Item -ItemType Directory -Force -Path runtime | Out-Null
$RawDb = Join-Path $Root "runtime\raw-staging.db"
if (Test-Path $RawDb) { Remove-Item $RawDb -Force }
$importText = & $Python -m meltano_leads_importer --db $RawDb import $Master
if ($LASTEXITCODE -ne 0) { throw "master raw import failed" }
$import = $importText | ConvertFrom-Json
if ($import.rows_seen -ne $ExpectedRows -or $import.rows_inserted -ne $ExpectedRows) {
  throw "raw import mismatch"
}

$LeadsRoot = "C:\Users\Usuario\Documents\GitHub\Leads-Workstation"
$LeadsPython = Join-Path $LeadsRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $LeadsPython)) { throw "Leads Workstation runtime not installed" }
$CertLeadsDb = Join-Path $LeadsRoot "runtime\importer-cert-leads.db"
if (Test-Path $CertLeadsDb) { Remove-Item $CertLeadsDb -Force }

$Fixture = Join-Path $Root "runtime\promotion-fixture.csv"
@"
company,full_name,country,lead_category,email_primary,mobile
Importer Alpha,Alpha Contact,Dominican Republic,Importer Test,importer-cert@example.com,8095550101
Importer Beta,Beta Contact,Dominican Republic,Importer Test,importer-cert@example.com,8095550102
"@ | Set-Content -Encoding UTF8 $Fixture

$CertRawDb = Join-Path $Root "runtime\promotion-cert-raw.db"
if (Test-Path $CertRawDb) { Remove-Item $CertRawDb -Force }
& $Python -m meltano_leads_importer --db $CertRawDb import $Fixture --batch-id certification-promotion | Out-Null
if ($LASTEXITCODE -ne 0) { throw "fixture raw import failed" }

$proc = Start-Process -FilePath $LeadsPython -ArgumentList @(
  "-m","leads_workstation","--db",$CertLeadsDb,"serve",
  "--host","127.0.0.1","--port",$TestPort
) -WorkingDirectory $LeadsRoot -PassThru -WindowStyle Hidden

try {
  Start-Sleep -Seconds 2
  $healthText = & $Python -m meltano_leads_importer check-workstation --url "http://127.0.0.1:$TestPort"
  if ($LASTEXITCODE -ne 0) { throw "workstation health integration failed" }
  $health = $healthText | ConvertFrom-Json

  $promotionText = & $Python -m meltano_leads_importer --db $CertRawDb promote-batch certification-promotion --url "http://127.0.0.1:$TestPort"
  if ($LASTEXITCODE -ne 0) { throw "promotion integration failed" }
  $promotion = $promotionText | ConvertFrom-Json
  if ($promotion.attempted -ne 2 -or $promotion.promoted -ne 1 -or $promotion.duplicate -ne 1) {
    throw "unexpected promotion result"
  }
} finally {
  Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}

$meltanoVersion = "not-installed"
if (Test-Path ".venv\Scripts\meltano.exe") {
  $meltanoVersion = (& ".venv\Scripts\meltano.exe" --version 2>&1 | Out-String).Trim()
}

$result = [ordered]@{
  certified_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  master_rows_previewed = $preview.rows_seen
  master_rows_staged = $import.rows_inserted
  master_sha256 = $import.source_sha256
  unit_tests = "passed"
  compile = "passed"
  workstation_health = $health.ok
  fixture_attempted = $promotion.attempted
  fixture_promoted = $promotion.promoted
  fixture_duplicate = $promotion.duplicate
  postgres_schema = "lead_import_raw"
  direct_canonical_write = "forbidden"
  meltano_version = $meltanoVersion
}
$result | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 runtime\certification.json
$result | ConvertTo-Json -Depth 6
