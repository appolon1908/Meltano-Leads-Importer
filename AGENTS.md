# AGENTS.md

## Repository
appolon1908/Meltano-Leads-Importer

## Mission workflow
00 Authority & Architecture -> 10 Build & Test -> 20 Integration & Dependencies -> 30 Staging & Release.

## Rules
- Own extraction, connector state, provenance and raw staging only.
- Production database writes are restricted to the lead_import_raw schema.
- Never write canonical lead tables directly.
- Preserve import_batch_id, source identity, row provenance, source SHA-256 and row fingerprints.
- Dry-run/preview and idempotency are required.
- Country and Business Category remain separate source fields.
- Database-migrations- owns applying PostgreSQL schema/role changes.
- Leads-Workstation owns canonical promotion and canonical lead rules.
- Promotion into canonical leads is allowed only through the Leads Workstation API.
- N8N is downstream and must not directly write canonical lead records.
- Lead/contact payload must never be pushed to a public repository.
- Use one active writer branch/worktree per mission.
- Completion requires implementation, tests, runtime readback and certification evidence.
