# PostgreSQL raw-staging contract

Production writes are restricted to the lead_import_raw schema:
- import_batches
- records

Meltano-Leads-Importer refuses any other schema target.

Database-migrations- owns applying the DDL in sql/lead_import_raw.sql. The importer verifies required columns and writes raw staging rows only after the schema exists.

Canonical lead tables are outside this repository's authority. Promotion is performed through the Leads Workstation API.
