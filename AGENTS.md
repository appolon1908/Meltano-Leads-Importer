# AGENTS.md

## Repository
ingtrader21-spec/Meltano-Leads-Importer

## Mission workflow
00 Authority & Architecture -> 10 Build & Test -> 20 Integration & Dependencies -> 30 Staging & Release.

## Rules
- Own extraction, connector state, provenance and raw staging only.
- Target PostgreSQL raw staging; never write canonical lead tables directly.
- Preserve import_batch_id, source identity, row provenance and fingerprints.
- Dry-run/preview and idempotency are required.
- Country and Business Category remain separate source fields.
- Database-migrations owns schemas/roles; Leads-Workstation owns canonical promotion; N8N is downstream.
- Use one active writer branch/worktree per mission.
