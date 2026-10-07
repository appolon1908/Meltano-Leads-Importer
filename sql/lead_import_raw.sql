-- Authority: Database-migrations- owns production application of this schema.
-- Meltano-Leads-Importer consumes it and must not create canonical lead tables.

CREATE SCHEMA IF NOT EXISTS lead_import_raw;

CREATE TABLE IF NOT EXISTS lead_import_raw.import_batches (
    import_batch_id text PRIMARY KEY,
    source_name text NOT NULL,
    source_path text NOT NULL,
    source_sha256 text NOT NULL,
    source_format text NOT NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    rows_seen bigint NOT NULL DEFAULT 0,
    rows_inserted bigint NOT NULL DEFAULT 0,
    rows_skipped bigint NOT NULL DEFAULT 0,
    status text NOT NULL,
    error text
);

CREATE TABLE IF NOT EXISTS lead_import_raw.records (
    raw_id bigserial PRIMARY KEY,
    import_batch_id text NOT NULL REFERENCES lead_import_raw.import_batches(import_batch_id),
    source_name text NOT NULL,
    source_path text NOT NULL,
    source_row bigint NOT NULL,
    ingested_at timestamptz NOT NULL,
    source_fingerprint text NOT NULL,
    country_raw text,
    business_category_raw text,
    payload_json jsonb NOT NULL,
    promotion_status text NOT NULL DEFAULT 'staged',
    promotion_result jsonb,
    UNIQUE(import_batch_id, source_fingerprint)
);

CREATE INDEX IF NOT EXISTS lead_import_raw_records_batch_idx
    ON lead_import_raw.records(import_batch_id);
CREATE INDEX IF NOT EXISTS lead_import_raw_records_status_idx
    ON lead_import_raw.records(promotion_status);
CREATE INDEX IF NOT EXISTS lead_import_raw_records_country_idx
    ON lead_import_raw.records(country_raw);
CREATE INDEX IF NOT EXISTS lead_import_raw_records_category_idx
    ON lead_import_raw.records(business_category_raw);
