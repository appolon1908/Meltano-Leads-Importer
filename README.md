# Meltano Leads Importer

Codestra ingestion authority for the Ubuntu Leads Workstation.

## Mission

Import lead sources safely into PostgreSQL raw staging with provenance, batch evidence and repeatable state. This repo does **not** own canonical lead business rules.

## Repository workflow

1. **00 Authority & Architecture** — source inventory, connector selection, mapping contract.
2. **10 Build & Test** — Meltano project/plugins, mappings, dry-run fixtures, validation hooks.
3. **20 Integration & Dependencies** — PostgreSQL raw schema, Leads API promotion contract, n8n post-import event handoff.
4. **30 Staging & Release** — repeatable import, idempotency, failure recovery, batch evidence.

## Data path

`source -> Meltano -> PostgreSQL lead_import_raw -> Leads API validation/promotion -> canonical leads`

n8n runs **after** accepted lead events and does not replace Meltano or the Leads API.

## Import guarantees

- source provenance is preserved;
- every run has an import batch ID;
- country and business category remain separate;
- dry-run/preview precedes canonical promotion;
- retries are idempotent;
- exact duplicates can be skipped;
- uncertain duplicates go to review;
- raw imports are never silently deleted.

## Local target

Ubuntu desktop: `desktop-ubuntu-codestra`.
## Governed CSV batch preparation

Before a frozen CSV source is loaded into raw staging, derive an import file with the provenance fields required by `contracts/import-contract.v1.json`:

```bash
python3 scripts/prepare_csv_batch.py \
  --source /path/to/frozen-source.csv \
  --output /path/to/prepared-raw.csv \
  --batch-id <uuid> \
  --source-name <authority-name> \
  --expected-sha256 <frozen-source-sha256>
```

The preparer verifies the frozen source hash, never edits the source, adds `import_batch_id`, `source_name`, `source_row`, `ingested_at`, and `source_fingerprint`, and writes the derived file atomically. The derived file is for `lead_import_raw` only. Canonical promotion remains the responsibility of the Leads Workstation API after validation and review.
