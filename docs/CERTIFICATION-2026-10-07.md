# Certification - 2026-10-07

The Meltano Leads Importer is certified on the connected Codestra laptop.

Evidence expected from scripts/certify.ps1:

- full master preview: 88,379 rows
- full raw-staging import: 88,379 rows
- source SHA-256 recorded on the batch
- unit tests pass
- Python compilation passes
- Leads Workstation local health check passes
- end-to-end two-row promotion fixture attempts two rows
- first fixture row is promoted through the Leads Workstation API
- second fixture row is classified duplicate by the Leads Workstation API
- production PostgreSQL writer is restricted to lead_import_raw
- direct canonical database writes are refused
- runtime data is git-ignored

The real master is not re-promoted during certification because it is already present in the canonical Leads Workstation. Full-master certification ends at raw staging; promotion behavior is proven with the isolated fixture.
