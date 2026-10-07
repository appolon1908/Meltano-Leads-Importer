from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import canonical_json, now_utc, raw_projection, source_fingerprint
from .store import iter_rows, sha256_file

EXPECTED_SCHEMA = "lead_import_raw"
EXPECTED_BATCH_TABLE = "import_batches"
EXPECTED_RECORD_TABLE = "records"


def _psycopg():
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL support requires the 'postgres' extra: pip install -e .[postgres]"
        ) from exc
    return psycopg


def assert_safe_target(schema: str) -> None:
    if schema != EXPECTED_SCHEMA:
        raise ValueError(
            f"refusing database target {schema!r}; importer may write only to {EXPECTED_SCHEMA!r}"
        )


def verify_contract(dsn: str, schema: str = EXPECTED_SCHEMA) -> dict[str, Any]:
    assert_safe_target(schema)
    psycopg = _psycopg()
    required = {
        EXPECTED_BATCH_TABLE: {
            "import_batch_id", "source_name", "source_path", "source_sha256",
            "source_format", "started_at", "completed_at", "rows_seen",
            "rows_inserted", "rows_skipped", "status", "error",
        },
        EXPECTED_RECORD_TABLE: {
            "raw_id", "import_batch_id", "source_name", "source_path", "source_row",
            "ingested_at", "source_fingerprint", "country_raw",
            "business_category_raw", "payload_json", "promotion_status",
            "promotion_result",
        },
    }
    result = {"schema": schema, "ok": True, "tables": {}}
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for table, columns in required.items():
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema=%s AND table_name=%s
                    """,
                    (schema, table),
                )
                found = {r[0] for r in cur.fetchall()}
                missing = sorted(columns - found)
                result["tables"][table] = {"missing": missing, "found_count": len(found)}
                if missing:
                    result["ok"] = False
    return result


def import_source_postgres(
    dsn: str,
    source_path: str | Path,
    batch_id: str | None = None,
    schema: str = EXPECTED_SCHEMA,
) -> dict[str, Any]:
    assert_safe_target(schema)
    contract = verify_contract(dsn, schema)
    if not contract["ok"]:
        raise RuntimeError("PostgreSQL raw-staging contract is incomplete: " + json.dumps(contract))

    psycopg = _psycopg()
    src = Path(source_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    source_hash = sha256_file(src)
    batch_id = batch_id or f"{src.stem}-{source_hash[:12]}"
    source_format = src.suffix.lower().lstrip(".")
    started = now_utc()

    q_batch = f'"{schema}"."{EXPECTED_BATCH_TABLE}"'
    q_records = f'"{schema}"."{EXPECTED_RECORD_TABLE}"'

    seen = inserted = skipped = 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT status,rows_seen,rows_inserted,rows_skipped FROM {q_batch} WHERE import_batch_id=%s",
                (batch_id,),
            )
            prior = cur.fetchone()
            if prior and prior[0] == "completed":
                return {
                    "import_batch_id": batch_id,
                    "status": prior[0],
                    "rows_seen": prior[1],
                    "rows_inserted": prior[2],
                    "rows_skipped": prior[3],
                    "idempotent_replay": True,
                }

            cur.execute(
                f"""
                INSERT INTO {q_batch}(
                    import_batch_id,source_name,source_path,source_sha256,source_format,
                    started_at,status
                ) VALUES(%s,%s,%s,%s,%s,%s,'running')
                ON CONFLICT(import_batch_id) DO UPDATE SET
                    source_name=EXCLUDED.source_name,
                    source_path=EXCLUDED.source_path,
                    source_sha256=EXCLUDED.source_sha256,
                    source_format=EXCLUDED.source_format,
                    started_at=EXCLUDED.started_at,
                    status='running',
                    error=NULL
                """,
                (batch_id, src.name, str(src), source_hash, source_format, started),
            )

            try:
                for row_no, row in iter_rows(src):
                    seen += 1
                    fp = source_fingerprint(row)
                    country, category = raw_projection(row)
                    cur.execute(
                        f"""
                        INSERT INTO {q_records}(
                            import_batch_id,source_name,source_path,source_row,ingested_at,
                            source_fingerprint,country_raw,business_category_raw,payload_json
                        ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                        ON CONFLICT(import_batch_id,source_fingerprint) DO NOTHING
                        """,
                        (
                            batch_id, src.name, str(src), row_no, now_utc(), fp,
                            country, category, canonical_json(row),
                        ),
                    )
                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        skipped += 1

                cur.execute(
                    f"""
                    UPDATE {q_batch}
                    SET completed_at=%s,rows_seen=%s,rows_inserted=%s,rows_skipped=%s,status='completed'
                    WHERE import_batch_id=%s
                    """,
                    (now_utc(), seen, inserted, skipped, batch_id),
                )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                with conn.cursor() as err_cur:
                    err_cur.execute(
                        f"""
                        UPDATE {q_batch}
                        SET completed_at=%s,rows_seen=%s,rows_inserted=%s,rows_skipped=%s,status='failed',error=%s
                        WHERE import_batch_id=%s
                        """,
                        (now_utc(), seen, inserted, skipped, repr(exc), batch_id),
                    )
                conn.commit()
                raise

    return {
        "import_batch_id": batch_id,
        "source_name": src.name,
        "source_sha256": source_hash,
        "rows_seen": seen,
        "rows_inserted": inserted,
        "rows_skipped": skipped,
        "status": "completed",
        "target": f"{schema}.{EXPECTED_RECORD_TABLE}",
    }
