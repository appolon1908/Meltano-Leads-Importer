# Meltano Leads Importer

Codestra ingestion authority for the Leads Workstation.

## Implemented runtime

This repository now contains a working importer, not only contracts:

- Meltano project definition with development, testing, staging and production environments
- CSV, JSON and JSONL source preview/import
- local SQLite raw-staging mirror for development/certification
- PostgreSQL raw-staging writer for production
- required batch IDs, source path/name, SHA-256, row number, ingested timestamp and source fingerprint
- idempotent replay protection
- exact raw-row duplicate skipping
- Country and Business Category preserved as separate raw fields
- promotion only through the Leads Workstation API
- canonical database targets explicitly refused
- batch statistics and promotion status tracking
- backup and certification scripts

## Data path

source -> Meltano-Leads-Importer -> lead_import_raw staging -> Leads Workstation API -> canonical leads

n8n runs only after accepted-lead/import-completed events. It does not replace Meltano and must not write canonical lead tables directly.

## Laptop install

PowerShell:

    cd C:\Users\Usuario\Documents\GitHub\Meltano-Leads-Importer
    .\scripts\install.ps1
    .\scripts\import-master.ps1

The full laptop master is read from:

    C:\Users\Usuario\03_LEADS_AND_DATA\01_CORE\Master\MASTER_SALES_LEADS_20260921.csv

Runtime databases are written under runtime/ and are ignored by Git.

## Production PostgreSQL

Database-migrations- owns applying sql/lead_import_raw.sql.

Set LEADS_IMPORT_POSTGRES_DSN, then verify:

    .venv\Scripts\python.exe -m meltano_leads_importer check-postgres

Import:

    .venv\Scripts\python.exe -m meltano_leads_importer import-postgres <source.csv>

The importer refuses any schema except lead_import_raw.

## Promotion

Raw rows are never silently promoted.

To promote a staged batch through the governed Leads Workstation API:

    .venv\Scripts\python.exe -m meltano_leads_importer promote-batch <batch-id> --url http://127.0.0.1:8765

## Repository workflow

00 Authority & Architecture -> 10 Build & Test -> 20 Integration & Dependencies -> 30 Staging & Release.

Promotion order is development -> testing -> staging -> production.

## Privacy

Lead payloads and raw staging databases are local/private runtime data. They must not be committed to a public repository.
